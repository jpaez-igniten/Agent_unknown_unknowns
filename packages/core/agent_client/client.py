"""
Agent HTTP Client

Llama a http://agent:8000/v1/chat con la hipótesis generada.
Usa httpx (async) con retry y backoff exponencial.

El contenedor 'agent' ya corre en la red igniten_network_global
y retorna el análisis completo en la respuesta.

Payload enviado:
    {
        "user_id": "<AGENT_USER_ID del .env>",
        "message_text": "<hipótesis a analizar>",
        "conversation_id": "uu_{run_id}_{hypothesis_id}",
        "platform": "unknown-unknown"
    }
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from loguru import logger


@dataclass
class AgentResponse:
    """Respuesta parseada del contenedor agent."""
    raw_text: str           # Texto completo del análisis
    conversation_id: str    # Echo del conversation_id enviado
    response_time_ms: int   # Tiempo round-trip en milisegundos
    status_code: int = 200
    error: Optional[str] = None  # Mensaje de error si lo hubo


class AgentClientError(Exception):
    """Raised cuando el agente falla después de todos los reintentos."""
    pass


class AgentClient:
    """
    Cliente HTTP async para el contenedor agent.

    Ejemplo de uso:
        client = AgentClient(
            base_url="http://agent:8000",
            user_id="unknown-unknowns-agent"
        )
        response = await client.chat(
            message_text="Analizar riesgo de clientes...",
            conversation_id="uu_42_pp_0_abc123"
        )
        print(response.raw_text)
        await client.close()
    """

    CHAT_ENDPOINT = "/v1/chat"
    PLATFORM = "unknown-unknown"  # Fijo según requerimiento

    def __init__(
        self,
        base_url: str,
        user_id: str,
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """
        Args:
            base_url: URL base del agente (ej: http://agent:8000)
            user_id: user_id a enviar en cada request
            timeout: Timeout en segundos para la respuesta (el agente puede tardar)
            max_retries: Número de reintentos ante errores retryables
            retry_delay: Segundos base entre reintentos (escala exponencialmente)
        """
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=timeout,
                write=30.0,
                pool=5.0
            ),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )

        logger.info(
            f"AgentClient initialized | URL: {self.base_url} | "
            f"user_id: {self.user_id} | timeout: {timeout}s"
        )

    async def chat(self, message_text: str, conversation_id: str) -> AgentResponse:
        """
        Envía una hipótesis al agente y retorna su análisis.

        Args:
            message_text: La hipótesis/pregunta a enviar
            conversation_id: ID único para esta conversación
                             (formato recomendado: uu_{run_id}_{hyp_id})

        Returns:
            AgentResponse con el análisis del agente

        Raises:
            AgentClientError: Si todos los reintentos fallan
        """
        url = f"{self.base_url}{self.CHAT_ENDPOINT}"

        payload = {
            "user_id": self.user_id,
            "message_text": message_text,
            "conversation_id": conversation_id,
            "platform": self.PLATFORM
        }

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            start_ms = int(time.time() * 1000)
            try:
                logger.debug(
                    f"Agent call attempt {attempt}/{self.max_retries} | "
                    f"conversation_id={conversation_id} | "
                    f"message_len={len(message_text)} chars"
                )

                response = await self._client.post(url, json=payload)
                elapsed_ms = int(time.time() * 1000) - start_ms

                if response.status_code == 200:
                    data = response.json()
                    raw_text = self._extract_text(data)

                    logger.info(
                        f"Agent response OK | conversation_id={conversation_id} | "
                        f"{elapsed_ms}ms | {len(raw_text)} chars"
                    )

                    return AgentResponse(
                        raw_text=raw_text,
                        conversation_id=conversation_id,
                        response_time_ms=elapsed_ms,
                        status_code=response.status_code
                    )

                elif response.status_code in (429, 502, 503):
                    # Errores temporales — reintentar
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        f"Retryable error from agent (attempt {attempt}/{self.max_retries}): "
                        f"{last_error}"
                    )

                elif response.status_code == 404:
                    raise AgentClientError(
                        f"Agent endpoint not found: {url}. "
                        f"Verify AGENT_BASE_URL in .env"
                    )

                else:
                    # Otros errores no retryables (400, 401, 500 real, etc.)
                    raise AgentClientError(
                        f"Agent returned HTTP {response.status_code}: {response.text[:500]}"
                    )

            except httpx.TimeoutException as e:
                elapsed_ms = int(time.time() * 1000) - start_ms
                last_error = f"Timeout after {elapsed_ms}ms (limit: {self.timeout}s)"
                logger.warning(
                    f"Agent timeout (attempt {attempt}/{self.max_retries}): {last_error}"
                )

            except httpx.ConnectError as e:
                last_error = f"Connection failed to {self.base_url}: {e}"
                logger.warning(
                    f"Agent connection error (attempt {attempt}/{self.max_retries}): {last_error}"
                )

            except AgentClientError:
                raise  # Re-raise errores no retryables inmediatamente

            except Exception as e:
                last_error = f"Unexpected error: {type(e).__name__}: {e}"
                logger.error(f"Unexpected error calling agent: {last_error}", exc_info=True)

            # Esperar antes del siguiente intento (backoff exponencial, cap 30s)
            if attempt < self.max_retries:
                delay = min(self.retry_delay * (2 ** (attempt - 1)), 30.0)
                logger.info(f"Waiting {delay:.1f}s before retry {attempt + 1}...")
                await asyncio.sleep(delay)

        raise AgentClientError(
            f"Agent call failed after {self.max_retries} attempts for "
            f"conversation_id={conversation_id}. Last error: {last_error}"
        )

    def _extract_text(self, data: dict) -> str:
        """
        Extrae el texto de la respuesta del agente.

        Soporta múltiples formatos de respuesta que distintos agentes pueden retornar.
        """
        # Formato 1: {"response": "..."}
        if "response" in data and isinstance(data["response"], str):
            return data["response"]

        # Formato 2: {"message": "..."}
        if "message" in data and isinstance(data["message"], str):
            return data["message"]

        # Formato 3: {"text": "..."}
        if "text" in data and isinstance(data["text"], str):
            return data["text"]

        # Formato 4: {"content": "..."}
        if "content" in data and isinstance(data["content"], str):
            return data["content"]

        # Formato 5: OpenAI-style {"choices": [{"message": {"content": "..."}}]}
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if isinstance(choice, dict):
                if "message" in choice and isinstance(choice["message"], dict):
                    if "content" in choice["message"]:
                        return choice["message"]["content"]
                if "text" in choice and isinstance(choice["text"], str):
                    return choice["text"]

        # Formato 6: Anidado {"data": {"response": "..."}}
        if "data" in data and isinstance(data["data"], dict):
            nested = self._extract_text(data["data"])
            if nested:
                return nested

        # Fallback: serializar todo el JSON (loguear advertencia)
        logger.warning(
            f"Unknown agent response format. Keys: {list(data.keys())}. "
            f"Serializing full response."
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    async def health_check(self) -> bool:
        """
        Verifica que el agente esté accesible.
        Útil para diagnóstico en startup.

        Returns:
            True si responde con 200/204, False en caso contrario
        """
        try:
            response = await self._client.get(
                f"{self.base_url}/health",
                timeout=10.0
            )
            healthy = response.status_code in (200, 204)
            if healthy:
                logger.info(f"Agent health check OK: {self.base_url}/health")
            else:
                logger.warning(
                    f"Agent health check returned {response.status_code}: "
                    f"{self.base_url}/health"
                )
            return healthy
        except Exception as e:
            logger.warning(f"Agent health check failed: {self.base_url}/health — {e}")
            return False

    async def close(self):
        """Cierra el cliente HTTP limpiamente."""
        await self._client.aclose()
        logger.debug("AgentClient HTTP client closed")

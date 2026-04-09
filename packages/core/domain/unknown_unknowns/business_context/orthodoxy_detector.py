"""
Orthodoxy Detector

Detecta creencias no cuestionadas (ortodoxos) que limitan el pensamiento estratégico.

CRÍTICO: Esta es NUESTRA responsabilidad, no del cliente.
Los ortodoxos son invisibles para quien está dentro del sistema.

Un ortodoxo es una creencia que:
1. Se toma como verdad absoluta sin cuestionar
2. Limita posibilidades ("no podemos hacer X porque...")
3. Podría ser desafiado con buenos resultados

Métodos de detección:
- Pattern Analysis: Busca "absolutos" en los datos (SIEMPRE, NUNCA, SOLO)
- Conversation Analysis: Detecta frases en conversaciones pasadas
- Industry Comparison: Compara con benchmarks de la industria
"""

import json
import logging
from typing import List, Dict, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class OrthodoxyDetector:
    """
    Detecta creencias no cuestionadas (ortodoxos) analizando:
    1. Patrones en los datos (si SIEMPRE hacen X, eso es un ortodoxo)
    2. Comparación con industry benchmarks
    3. Conversaciones previas del cliente

    IMPORTANTE: Esta es NUESTRA responsabilidad, no del cliente.
    Los ortodoxos son invisibles para quien está dentro del sistema.
    """

    def __init__(self, db_connection, llm):
        """
        Args:
            db_connection: Conexión a Postgres (asyncpg)
            llm: LLM para análisis (ej: ChatGoogleGenerativeAI)
        """
        self.db = db_connection
        self.llm = llm

    async def detect_orthodoxies(self, client_id: str) -> List[Dict[str, Any]]:
        """
        Detecta ortodoxos mediante 3 métodos en paralelo.

        Returns:
            Lista de ortodoxos detectados en formato:
            [
                {
                    "orthodoxy": "Los clientes B2B siempre pagan más que B2C",
                    "discovered_by": "pattern_analysis",
                    "confidence": 0.85,
                    "potential_for_disruption": "high",
                    "evidence": "100% de contratos B2B tienen pricing premium",
                    "detected_at": "2025-01-24T10:30:00"
                }
            ]
        """
        logger.info(f"Detecting orthodoxies for client {client_id}")

        try:
            # Ejecutar los 3 métodos en paralelo
            pattern_based, conversation_based, industry_based = await asyncio.gather(
                self._detect_from_patterns(client_id),
                self._detect_from_conversations(client_id),
                self._detect_from_industry_comparison(client_id),
                return_exceptions=True  # No fallar si uno falla
            )

            # Manejar excepciones
            if isinstance(pattern_based, Exception):
                logger.error(f"Pattern analysis failed: {pattern_based}")
                pattern_based = []
            if isinstance(conversation_based, Exception):
                logger.error(f"Conversation analysis failed: {conversation_based}")
                conversation_based = []
            if isinstance(industry_based, Exception):
                logger.error(f"Industry comparison failed: {industry_based}")
                industry_based = []

            # Combinar y des-duplicar
            all_orthodoxies = pattern_based + conversation_based + industry_based

            if not all_orthodoxies:
                logger.info(f"No orthodoxies detected for client {client_id}")
                return []

            # LLM valida y consolida
            validated = await self._validate_orthodoxies(all_orthodoxies)

            logger.info(f"Detected {len(validated)} validated orthodoxies for client {client_id}")
            return validated

        except Exception as e:
            logger.error(f"Error detecting orthodoxies for {client_id}: {e}")
            return []

    async def _detect_from_patterns(self, client_id: str) -> List[Dict]:
        """
        Detecta ortodoxos analizando patrones en los datos.

        Busca "absolutos" en los datos:
        - Si NUNCA venden producto X en región Y → ortodoxo
        - Si pricing es SIEMPRE cost-plus → ortodoxo
        - Si SOLO contratan de universidades top 10 → ortodoxo

        Returns:
            Lista de ortodoxos detectados desde patrones
        """
        logger.debug(f"Detecting orthodoxies from patterns for client {client_id}")

        orthodoxies = []

        # NOTA: Estos queries son genéricos y asumen nombres de tablas estándar.
        # En producción, deberían adaptarse al schema real del cliente.

        # Query 1: Detectar si SIEMPRE usan el mismo método de pricing
        try:
            query = """
                SELECT
                    COUNT(DISTINCT pricing_method) as unique_methods,
                    MAX(pricing_method) as method,
                    COUNT(*) as total_transactions
                FROM (
                    -- Esto es un placeholder - adaptar al schema real
                    SELECT 'cost_plus' as pricing_method
                    LIMIT 0
                ) pricing_data
            """

            result = await self.db.fetchrow(query)

            if result and result['unique_methods'] == 1 and result['total_transactions'] > 100:
                orthodoxies.append({
                    "orthodoxy": f"Always use {result['method']} pricing method",
                    "discovered_by": "pattern_analysis",
                    "confidence": 0.9,
                    "potential_for_disruption": "high",
                    "evidence": f"{result['total_transactions']} transactions, 100% use {result['method']}",
                    "detected_at": datetime.now().isoformat(),
                    "quote": None
                })

        except Exception as e:
            logger.debug(f"Pricing pattern query failed (expected if table doesn't exist): {e}")

        # Query 2: Detectar restricciones geográficas no cuestionadas
        try:
            query = """
                SELECT
                    product_id,
                    product_name,
                    COUNT(DISTINCT region) as regions_sold,
                    COUNT(DISTINCT region) * 100.0 / (SELECT COUNT(*) FROM regions) as coverage_pct
                FROM (
                    -- Placeholder - adaptar al schema real
                    SELECT 1 as product_id, 'Product A' as product_name, 'North' as region
                    LIMIT 0
                ) product_regions
                GROUP BY product_id, product_name
                HAVING COUNT(DISTINCT region) < 3
            """

            results = await self.db.fetch(query)

            for row in results:
                orthodoxies.append({
                    "orthodoxy": f"Never sell {row['product_name']} outside of {row['regions_sold']} specific regions",
                    "discovered_by": "pattern_analysis",
                    "confidence": 0.75,
                    "potential_for_disruption": "medium",
                    "evidence": f"Product only sold in {row['regions_sold']} regions ({row['coverage_pct']:.1f}% coverage)",
                    "detected_at": datetime.now().isoformat(),
                    "quote": None
                })

        except Exception as e:
            logger.debug(f"Geographic pattern query failed (expected if table doesn't exist): {e}")

        # Query 3: Detectar segmentos de clientes completamente evitados
        try:
            query = """
                SELECT
                    customer_segment,
                    COUNT(*) as count
                FROM (
                    -- Placeholder - adaptar al schema real
                    SELECT 'Enterprise' as customer_segment
                    LIMIT 0
                ) customers
                GROUP BY customer_segment
            """

            results = await self.db.fetch(query)

            # Si hay muy pocos segmentos (< 3), es un ortodoxo
            if len(results) < 3:
                orthodoxies.append({
                    "orthodoxy": f"Only serve {len(results)} customer segment(s)",
                    "discovered_by": "pattern_analysis",
                    "confidence": 0.7,
                    "potential_for_disruption": "high",
                    "evidence": f"All customers fall into only {len(results)} segment(s)",
                    "detected_at": datetime.now().isoformat(),
                    "quote": None
                })

        except Exception as e:
            logger.debug(f"Customer segment query failed (expected if table doesn't exist): {e}")

        logger.debug(f"Found {len(orthodoxies)} orthodoxies from pattern analysis")
        return orthodoxies

    async def _detect_from_conversations(self, client_id: str) -> List[Dict]:
        """
        Analiza conversaciones pasadas buscando frases que revelan ortodoxos.

        Busca frases como:
        - "Siempre hemos hecho X"
        - "Nunca vendemos a Y"
        - "Nuestros clientes no compran Z"
        - "Eso no funciona en nuestra industria"
        - "Así se hacen las cosas aquí"

        Returns:
            Lista de ortodoxos detectados desde conversaciones
        """
        logger.debug(f"Detecting orthodoxies from conversations for client {client_id}")

        try:
            # Obtener conversaciones recientes del cliente
            # NOTA: Esto asume que existe una tabla conversation_history
            # En producción, adaptarse al schema real
            conversations = await self.db.fetch("""
                SELECT content, created_at
                FROM conversation_history
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 100
            """, client_id)

            if not conversations:
                logger.debug(f"No conversations found for client {client_id}")
                return []

            # Concatenar conversaciones
            conversation_text = "\n\n".join([
                f"[{conv['created_at']}]: {conv['content']}"
                for conv in conversations
            ])

            # Prompt al LLM para detectar ortodoxos
            prompt = f"""
Analiza estas conversaciones del cliente y detecta "ortodoxos" (creencias no cuestionadas).

Un ortodoxo es una creencia que:
1. Se toma como verdad absoluta sin cuestionar
2. Limita posibilidades ("no podemos hacer X porque...")
3. Podría ser desafiado con buenos resultados

Busca frases como:
- "Siempre..."
- "Nunca..."
- "Nuestros clientes no..."
- "Eso no funciona en nuestra industria..."
- "Así se hacen las cosas aquí..."
- "No podemos..."
- "Es imposible..."

Conversaciones (últimas 100):
{conversation_text}

---

Retorna JSON con ortodoxos detectados:
[
    {{
        "orthodoxy": "descripción concisa del ortodoxo",
        "quote": "cita textual donde se menciona",
        "confidence": 0.0-1.0,
        "potential_for_disruption": "high" | "medium" | "low",
        "evidence": "contexto adicional"
    }}
]

Si no encuentras ortodoxos claros, retorna lista vacía [].
Retorna SOLO el JSON, sin texto adicional.
"""

            # Invocar LLM
            response = await self.llm.ainvoke(prompt)

            # Parsear respuesta
            try:
                orthodoxies = json.loads(response.content)

                # Agregar metadata
                for orth in orthodoxies:
                    orth["discovered_by"] = "client_mentioned"
                    orth["detected_at"] = datetime.now().isoformat()

                logger.debug(f"Found {len(orthodoxies)} orthodoxies from conversations")
                return orthodoxies

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.debug(f"LLM response was: {response.content}")
                return []

        except Exception as e:
            logger.error(f"Error detecting orthodoxies from conversations: {e}")
            return []

    async def _detect_from_industry_comparison(self, client_id: str) -> List[Dict]:
        """
        Compara prácticas del cliente con industry benchmarks.

        Si todos en la industria hacen X, pero el cliente hace Y,
        entonces Y es un ortodoxo del cliente.

        Returns:
            Lista de ortodoxos detectados desde comparación de industria

        NOTE: En FASE 1, esto retorna lista vacía.
        En FASE 2+, implementar cuando tengamos industry benchmarks.
        """
        logger.debug(f"Industry comparison not implemented yet for client {client_id}")
        # TODO: Implementar cuando tengamos industry benchmarks
        return []

    async def _validate_orthodoxies(self, orthodoxies: List[Dict]) -> List[Dict]:
        """
        LLM valida que los ortodoxos sean realmente creencias no cuestionadas
        y no solo preferencias razonables.

        Args:
            orthodoxies: Lista de posibles ortodoxos

        Returns:
            Lista filtrada de ortodoxos validados
        """
        if not orthodoxies:
            return []

        logger.debug(f"Validating {len(orthodoxies)} potential orthodoxies")

        prompt = f"""
Valida estos posibles "ortodoxos" (creencias no cuestionadas).

Un ortodoxo es una creencia que:
1. Se toma como verdad absoluta sin cuestionar
2. Limita posibilidades ("no podemos hacer X porque...")
3. Podría ser desafiado con buenos resultados

NO es ortodoxo:
- Una preferencia razonable basada en evidencia
- Una restricción regulatoria real (ej: no se puede vender alcohol a menores)
- Una limitación física/técnica real (ej: no se puede enviar a Marte en 1 día)

Posibles ortodoxos:
{json.dumps(orthodoxies, indent=2, default=str)}

---

Para cada uno, determina:
- is_orthodoxy: true/false
- potential_for_disruption: "high" | "medium" | "low" (si is_orthodoxy=true)
- rationale: por qué sí/no es un ortodoxo (1-2 oraciones)

Retorna JSON:
[
    {{
        "orthodoxy": "...",
        "is_orthodoxy": true/false,
        "potential_for_disruption": "high" | "medium" | "low",
        "rationale": "...",
        "confidence": 0.0-1.0,
        "evidence": "...",
        "discovered_by": "...",
        "detected_at": "...",
        "quote": "..." (si aplica)
    }}
]

Retorna SOLO el JSON, sin texto adicional.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            validated = json.loads(response.content)

            # Filtrar solo los que son ortodoxos
            confirmed_orthodoxies = [o for o in validated if o.get("is_orthodoxy", False)]

            logger.info(f"Validated {len(confirmed_orthodoxies)}/{len(orthodoxies)} orthodoxies")
            return confirmed_orthodoxies

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM validation response: {e}")
            logger.debug(f"LLM response was: {response.content}")
            # Si falla la validación, retornar los originales con confianza reducida
            for orth in orthodoxies:
                orth["confidence"] *= 0.5  # Reducir confianza a la mitad
                orth["is_orthodoxy"] = True  # Asumir que sí son ortodoxos
            return orthodoxies
        except Exception as e:
            logger.error(f"Error validating orthodoxies: {e}")
            return []

    async def explain_orthodoxy_impact(self, orthodoxy: Dict[str, Any]) -> str:
        """
        Genera una explicación de por qué este ortodoxo es importante desafiar.

        Args:
            orthodoxy: Dict con información del ortodoxo

        Returns:
            Explicación en texto natural
        """
        prompt = f"""
Explica por qué es importante desafiar este ortodoxo (creencia no cuestionada):

Ortodoxo: {orthodoxy['orthodoxy']}
Evidencia: {orthodoxy.get('evidence', 'N/A')}
Potencial de disrupción: {orthodoxy.get('potential_for_disruption', 'medium')}

Genera una explicación de 2-3 oraciones que:
1. Explique por qué esta creencia podría estar limitando oportunidades
2. Sugiera qué podría ganar el negocio si la desafía
3. Sea específica y accionable, no genérica

Retorna SOLO el texto de la explicación, sin formato.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error explaining orthodoxy impact: {e}")
            return "Could not generate explanation"

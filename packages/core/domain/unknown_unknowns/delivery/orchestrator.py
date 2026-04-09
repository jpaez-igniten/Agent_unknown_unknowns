"""
Insight Delivery Orchestrator - FASE 4

Orquesta la entrega de insights a través de múltiples canales.

Responsabilidades:
1. Seleccionar canal apropiado basado en preferences
2. Formatear insights para cada canal
3. Enviar y registrar deliveries
4. Generar feedback URLs
5. Manejar errores y retries
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..hypothesis.models import Hypothesis
from .channels import ChannelFactory, BaseDeliveryChannel

logger = logging.getLogger(__name__)


class InsightDeliveryOrchestrator:
    """
    Orquesta la entrega de insights a clientes.

    Maneja:
    - Selección de canal (email, Teams, WhatsApp)
    - Formateo de mensajes
    - Envío y tracking
    - Feedback URL generation
    - Retry logic
    """

    def __init__(
        self,
        settings,
        db_connection=None,
        default_channel: str = 'email'
    ):
        """
        Args:
            settings: Settings object con configuración de canales
            db_connection: Conexión asyncpg (opcional, para logging)
            default_channel: Canal por defecto si no se especifica
        """
        self.settings = settings
        self.db = db_connection
        self.default_channel = default_channel

        # Cache de channels
        self._channels_cache = {}

    def _get_channel(self, channel_type: str) -> BaseDeliveryChannel:
        """
        Obtiene canal de delivery (con cache).

        Args:
            channel_type: 'email', 'teams', 'whatsapp'

        Returns:
            BaseDeliveryChannel instance
        """
        if channel_type not in self._channels_cache:
            try:
                self._channels_cache[channel_type] = ChannelFactory.create_from_settings(
                    self.settings,
                    channel_type
                )
                logger.info(f"Created {channel_type} channel")
            except Exception as e:
                logger.error(f"Failed to create {channel_type} channel: {e}")
                # Fallback a email si el canal solicitado falla
                if channel_type != 'email':
                    logger.info(f"Falling back to email channel")
                    return self._get_channel('email')
                raise

        return self._channels_cache[channel_type]

    async def deliver_insights(
        self,
        insights: List[Hypothesis],
        client_id: str,
        client_name: str,
        recipient: str,
        channel_preferences: List[str] = None,
        run_id: str = None,
        generate_feedback_url: bool = True
    ) -> Dict[str, Any]:
        """
        Entrega insights al cliente.

        Args:
            insights: Lista de Hypothesis a entregar
            client_id: ID del cliente
            client_name: Nombre del cliente
            recipient: Email, phone, etc. según canal
            channel_preferences: Lista de canales preferidos (orden de prioridad)
            run_id: ID del run que generó estos insights
            generate_feedback_url: Si generar URL de feedback

        Returns:
            Dict con resultados de delivery:
            {
                "delivery_id": "...",
                "success": True/False,
                "channel_used": "email",
                "insights_delivered": 5,
                "sent_at": "...",
                "feedback_url": "...",
                "error": "..." (si aplica)
            }
        """
        logger.info(
            f"Delivering {len(insights)} insights to {client_id} "
            f"via {channel_preferences or [self.default_channel]}"
        )

        # Generar delivery_id
        delivery_id = f"dlv_{uuid.uuid4().hex[:12]}"

        # Determinar canal a usar
        channel_type = self._select_channel(channel_preferences)

        # Generar feedback URL
        feedback_url = None
        if generate_feedback_url:
            feedback_url = self._generate_feedback_url(
                delivery_id=delivery_id,
                client_id=client_id,
                run_id=run_id
            )

        # Preparar metadata
        metadata = {
            'client_name': client_name,
            'client_id': client_id,
            'run_id': run_id or 'N/A',
            'delivery_id': delivery_id,
            'feedback_url': feedback_url or '#',
            'delivered_at': datetime.now().isoformat()
        }

        # Subject
        subject = f"🔍 {len(insights)} Unknown Unknowns Discovered - {client_name}"

        try:
            # Obtener canal
            channel = self._get_channel(channel_type)

            # Enviar
            result = await channel.send(
                insights=insights,
                recipient=recipient,
                subject=subject,
                metadata=metadata
            )

            # Agregar metadata adicional
            result['delivery_id'] = delivery_id
            result['channel_used'] = channel_type
            result['insights_delivered'] = len(insights)
            result['feedback_url'] = feedback_url
            result['client_id'] = client_id

            # Log delivery en BD (si disponible)
            if self.db and result['success']:
                await self._log_delivery(
                    delivery_id=delivery_id,
                    client_id=client_id,
                    run_id=run_id,
                    channel=channel_type,
                    recipient=recipient,
                    insights_count=len(insights),
                    metadata=metadata
                )

            logger.info(
                f"Delivery {delivery_id} {'successful' if result['success'] else 'failed'} "
                f"via {channel_type}"
            )

            return result

        except Exception as e:
            logger.error(f"Error during delivery {delivery_id}: {e}")

            # Intentar retry con canal fallback
            if channel_preferences and len(channel_preferences) > 1:
                logger.info(f"Retrying with fallback channel")
                return await self.deliver_insights(
                    insights=insights,
                    client_id=client_id,
                    client_name=client_name,
                    recipient=recipient,
                    channel_preferences=channel_preferences[1:],  # Siguiente canal
                    run_id=run_id,
                    generate_feedback_url=False  # Ya generamos URL
                )

            # Si no hay fallback, retornar error
            return {
                "delivery_id": delivery_id,
                "success": False,
                "channel_used": channel_type,
                "insights_delivered": 0,
                "error": str(e),
                "sent_at": datetime.now().isoformat()
            }

    def _select_channel(self, channel_preferences: List[str] = None) -> str:
        """
        Selecciona canal basado en preferencias y disponibilidad.

        Args:
            channel_preferences: Lista ordenada de preferencias

        Returns:
            Nombre del canal a usar
        """
        if not channel_preferences:
            return self.default_channel

        # Verificar disponibilidad de cada canal en orden
        for channel in channel_preferences:
            if self._is_channel_enabled(channel):
                return channel

        # Fallback a default
        logger.warning(
            f"None of the preferred channels available: {channel_preferences}. "
            f"Using default: {self.default_channel}"
        )
        return self.default_channel

    def _is_channel_enabled(self, channel_type: str) -> bool:
        """Verifica si un canal está habilitado en settings."""
        enable_flags = {
            'email': self.settings.enable_email_delivery,
            'teams': self.settings.enable_teams_delivery,
            'whatsapp': self.settings.enable_whatsapp_delivery,
            'slack': self.settings.enable_slack_delivery
        }

        return enable_flags.get(channel_type, False)

    def _generate_feedback_url(
        self,
        delivery_id: str,
        client_id: str,
        run_id: str = None
    ) -> str:
        """
        Genera URL única para feedback.

        En producción, esto apuntaría a un endpoint de API.
        Por ahora, genera URL mock.

        Args:
            delivery_id: ID del delivery
            client_id: ID del cliente
            run_id: ID del run (opcional)

        Returns:
            URL de feedback
        """
        # En producción:
        # base_url = self.settings.api_base_url
        # return f"{base_url}/feedback/{delivery_id}"

        # Mock para FASE 4
        return f"https://feedback.igniten.ai/u/{delivery_id}?client={client_id}&run={run_id or 'NA'}"

    async def _log_delivery(
        self,
        delivery_id: str,
        client_id: str,
        run_id: str,
        channel: str,
        recipient: str,
        insights_count: int,
        metadata: Dict[str, Any]
    ):
        """
        Registra delivery en base de datos.

        NOTA: En FASE 4, esto guardaría en una tabla deliveries.
        Por ahora, solo log.
        """
        logger.info(
            f"Logging delivery {delivery_id}: "
            f"client={client_id}, run={run_id}, channel={channel}, "
            f"recipient={recipient}, count={insights_count}"
        )

        # TODO: INSERT INTO deliveries table cuando exista
        # query = """
        #     INSERT INTO deliveries (
        #         delivery_id, client_id, run_id, channel,
        #         recipient, insights_count, delivered_at, metadata
        #     ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        # """
        # await self.db.execute(
        #     query,
        #     delivery_id, client_id, run_id, channel,
        #     recipient, insights_count, datetime.now(), json.dumps(metadata)
        # )

    async def deliver_to_multiple_recipients(
        self,
        insights: List[Hypothesis],
        client_id: str,
        client_name: str,
        recipients: Dict[str, str],
        channel_preferences: List[str] = None,
        run_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Entrega insights a múltiples destinatarios.

        Args:
            insights: Lista de Hypothesis
            client_id: ID del cliente
            client_name: Nombre del cliente
            recipients: Dict {recipient_email/phone: recipient_name}
            channel_preferences: Canales preferidos
            run_id: ID del run

        Returns:
            Lista de resultados de delivery
        """
        logger.info(f"Delivering to {len(recipients)} recipients")

        results = []

        for recipient, recipient_name in recipients.items():
            try:
                result = await self.deliver_insights(
                    insights=insights,
                    client_id=client_id,
                    client_name=f"{client_name} ({recipient_name})",
                    recipient=recipient,
                    channel_preferences=channel_preferences,
                    run_id=run_id
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Error delivering to {recipient}: {e}")
                results.append({
                    "success": False,
                    "recipient": recipient,
                    "error": str(e)
                })

        successful = sum(1 for r in results if r.get('success'))
        logger.info(f"Delivery complete: {successful}/{len(recipients)} successful")

        return results

    async def schedule_delivery(
        self,
        insights: List[Hypothesis],
        client_id: str,
        client_name: str,
        recipient: str,
        channel_preferences: List[str] = None,
        run_id: str = None,
        schedule_at: datetime = None
    ) -> Dict[str, Any]:
        """
        Programa delivery para después.

        NOTA: En FASE 5, esto usaría un job scheduler (Celery, etc.)
        Por ahora, solo ejecuta inmediatamente.

        Args:
            insights: Insights a entregar
            client_id: ID del cliente
            client_name: Nombre del cliente
            recipient: Destinatario
            channel_preferences: Canales preferidos
            run_id: ID del run
            schedule_at: Datetime para enviar (futuro)

        Returns:
            Dict con resultado
        """
        if schedule_at and schedule_at > datetime.now():
            logger.info(f"Scheduling delivery for {schedule_at}")

            # TODO: Integrar con job scheduler
            # En FASE 5, esto crearía un job:
            # job_id = await self.scheduler.schedule_job(
            #     func=self.deliver_insights,
            #     args=[insights, client_id, ...],
            #     run_at=schedule_at
            # )
            # return {"scheduled": True, "job_id": job_id, "scheduled_at": schedule_at}

            logger.warning("Scheduled delivery not implemented, executing immediately")

        # Por ahora, ejecutar inmediatamente
        return await self.deliver_insights(
            insights=insights,
            client_id=client_id,
            client_name=client_name,
            recipient=recipient,
            channel_preferences=channel_preferences,
            run_id=run_id
        )

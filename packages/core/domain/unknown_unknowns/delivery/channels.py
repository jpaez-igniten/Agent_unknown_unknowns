"""
Delivery Channels - FASE 4

Canales de entrega multi-plataforma para insights.

Soporta:
- Email (SMTP)
- Microsoft Teams (Webhook)
- WhatsApp Business API
- Slack (futuro)
"""

import logging
import smtplib
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from ..hypothesis.models import Hypothesis

logger = logging.getLogger(__name__)


# ============================================================================
# BASE CHANNEL
# ============================================================================

class BaseDeliveryChannel(ABC):
    """
    Base class para canales de delivery.

    Cada canal implementa:
    - format_message(): Formatea insights para el canal específico
    - send(): Envía el mensaje formateado
    - validate_config(): Valida configuración del canal
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Configuración del canal (credentials, endpoints, etc.)
        """
        self.config = config
        self.validate_config()

    @abstractmethod
    def validate_config(self):
        """Valida que la configuración sea válida."""
        pass

    @abstractmethod
    async def send(
        self,
        insights: List[Hypothesis],
        recipient: str,
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Envía insights al destinatario.

        Args:
            insights: Lista de Hypothesis a enviar
            recipient: Email, phone, channel ID, etc.
            subject: Asunto/título del mensaje
            metadata: Metadata adicional (run_id, client_name, etc.)

        Returns:
            Dict con resultado del envío:
            {
                "success": True/False,
                "message_id": "...",
                "sent_at": "...",
                "error": "..." (si aplica)
            }
        """
        pass

    @abstractmethod
    def format_message(
        self,
        insights: List[Hypothesis],
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Formatea insights en el formato apropiado para el canal.

        Args:
            insights: Lista de Hypothesis
            subject: Asunto/título
            metadata: Metadata adicional

        Returns:
            Mensaje formateado (HTML, Markdown, texto plano, etc.)
        """
        pass


# ============================================================================
# EMAIL CHANNEL
# ============================================================================

class EmailChannel(BaseDeliveryChannel):
    """
    Canal de delivery vía Email (SMTP).

    Formatea insights como HTML email profesional.
    """

    def validate_config(self):
        """Valida configuración SMTP."""
        required = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from']
        missing = [k for k in required if k not in self.config]

        if missing:
            raise ValueError(f"Missing required email config: {missing}")

    def format_message(
        self,
        insights: List[Hypothesis],
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Formatea insights como HTML email."""
        metadata = metadata or {}
        client_name = metadata.get('client_name', 'Cliente')
        run_id = metadata.get('run_id', 'N/A')

        # HTML template
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: #2C3E50; color: white; padding: 20px; text-align: center; }}
        .insight {{ background: #f9f9f9; border-left: 4px solid #3498db; margin: 20px 0; padding: 15px; }}
        .insight h3 {{ margin-top: 0; color: #2C3E50; }}
        .metadata {{ color: #7f8c8d; font-size: 0.9em; }}
        .action {{ background: #ecf0f1; padding: 10px; margin: 10px 0; border-radius: 5px; }}
        .footer {{ text-align: center; padding: 20px; color: #7f8c8d; font-size: 0.9em; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; font-weight: bold; }}
        .badge-quick {{ background: #2ecc71; color: white; }}
        .badge-medium {{ background: #f39c12; color: white; }}
        .badge-strategic {{ background: #e74c3c; color: white; }}
        .score {{ color: #2ecc71; font-weight: bold; font-size: 1.2em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Unknown Unknowns Discovery</h1>
        <p>{client_name} | {datetime.now().strftime('%B %d, %Y')}</p>
    </div>

    <div style="padding: 20px; max-width: 800px; margin: 0 auto;">
        <p>Hemos descubierto <strong>{len(insights)}</strong> insights accionables para tu negocio:</p>
"""

        # Agregar cada insight
        for i, insight in enumerate(insights, 1):
            # Badge de portfolio type
            portfolio_class = f"badge-{insight.portfolio_type.value.replace('_', '')}"
            portfolio_label = insight.portfolio_type.value.replace('_', ' ').title()

            html += f"""
        <div class="insight">
            <h3>{i}. {insight.hypothesis_text}</h3>

            <div class="metadata">
                <span class="badge {portfolio_class}">{portfolio_label}</span>
                <span class="score">Score: {insight.delivery_score.delivery_score_total:.0f}/100</span>
                | Categoría: {insight.category}
            </div>

            <div class="action">
                <strong>✅ Si es verdadero:</strong><br>
                {insight.actionability.if_true_then}
            </div>

            <div class="metadata">
                <strong>👤 Decision Owner:</strong> {insight.actionability.decision_owner}<br>
                <strong>💰 Impacto Estimado:</strong> ${insight.actionability.estimated_impact_usd or 0:,.0f} USD<br>
                <strong>📊 Confianza:</strong> {insight.confidence.confidence_total:.0%}
                (Estadística: {insight.confidence.confidence_statistical:.0%},
                Data Quality: {insight.confidence.confidence_data_quality:.0%})
            </div>
"""

            # Evidencia
            if insight.evidence:
                html += f"""
            <div class="metadata">
                <strong>🔬 Evidencia:</strong>
                <ul style="margin: 5px 0; padding-left: 20px;">
"""
                for evidence in insight.evidence[:3]:  # Top 3
                    html += f"                    <li>{evidence}</li>\n"

                html += """
                </ul>
            </div>
"""

            html += "        </div>\n"

        # Footer
        feedback_url = metadata.get('feedback_url', '#')

        html += f"""
        <div class="footer">
            <p>
                <a href="{feedback_url}" style="background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    📝 Dar Feedback
                </a>
            </p>
            <p>Run ID: {run_id}</p>
            <p style="font-size: 0.8em;">
                🤖 Generado automáticamente por Unknown Unknowns Agent<br>
                Powered by Claude Sonnet 4.5
            </p>
        </div>
    </div>
</body>
</html>
"""

        return html

    async def send(
        self,
        insights: List[Hypothesis],
        recipient: str,
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Envía insights vía email."""
        logger.info(f"Sending {len(insights)} insights via email to {recipient}")

        try:
            # Formatear mensaje
            html_body = self.format_message(insights, subject, metadata)

            # Crear mensaje MIME
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject or f"🔍 {len(insights)} Unknown Unknowns Discovered"
            msg['From'] = self.config['smtp_from']
            msg['To'] = recipient
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')

            # Agregar HTML
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)

            # Enviar vía SMTP
            with smtplib.SMTP(self.config['smtp_host'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['smtp_user'], self.config['smtp_password'])
                server.send_message(msg)

            logger.info(f"Email sent successfully to {recipient}")

            return {
                "success": True,
                "message_id": msg['Message-ID'] if 'Message-ID' in msg else None,
                "sent_at": datetime.now().isoformat(),
                "recipient": recipient,
                "insights_count": len(insights)
            }

        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {e}")
            return {
                "success": False,
                "error": str(e),
                "sent_at": datetime.now().isoformat(),
                "recipient": recipient
            }


# ============================================================================
# MICROSOFT TEAMS CHANNEL
# ============================================================================

class TeamsChannel(BaseDeliveryChannel):
    """
    Canal de delivery vía Microsoft Teams (Webhook).

    Formatea insights como Adaptive Card.
    """

    def validate_config(self):
        """Valida webhook URL."""
        if 'webhook_url' not in self.config:
            raise ValueError("Missing required Teams config: webhook_url")

    def format_message(
        self,
        insights: List[Hypothesis],
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Formatea insights como Teams Adaptive Card."""
        metadata = metadata or {}
        client_name = metadata.get('client_name', 'Cliente')

        # Adaptive Card JSON
        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "🔍 Unknown Unknowns Discovery",
                                "weight": "Bolder",
                                "size": "Large",
                                "color": "Accent"
                            },
                            {
                                "type": "TextBlock",
                                "text": f"{client_name} | {datetime.now().strftime('%B %d, %Y')}",
                                "isSubtle": True,
                                "spacing": "None"
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Descubrimos **{len(insights)} insights accionables** para tu negocio:",
                                "wrap": True,
                                "spacing": "Medium"
                            }
                        ]
                    }
                }
            ]
        }

        # Agregar cada insight como columnas
        for i, insight in enumerate(insights[:5], 1):  # Máximo 5 para Teams
            portfolio_emoji = {
                "quick_win": "⚡",
                "medium_term": "📅",
                "strategic_bet": "🎯"
            }.get(insight.portfolio_type.value, "📊")

            card["attachments"][0]["content"]["body"].append({
                "type": "Container",
                "separator": True,
                "spacing": "Medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"{portfolio_emoji} **{i}. {insight.hypothesis_text[:100]}...**",
                        "wrap": True,
                        "weight": "Bolder"
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Score", "value": f"{insight.delivery_score.delivery_score_total:.0f}/100"},
                            {"title": "Owner", "value": insight.actionability.decision_owner},
                            {"title": "Impact", "value": f"${insight.actionability.estimated_impact_usd or 0:,.0f}"}
                        ]
                    },
                    {
                        "type": "TextBlock",
                        "text": f"✅ **Acción:** {insight.actionability.if_true_then[:150]}...",
                        "wrap": True,
                        "isSubtle": True
                    }
                ]
            })

        # Agregar botón de feedback
        feedback_url = metadata.get('feedback_url', '#')
        card["attachments"][0]["content"]["body"].append({
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "📝 Dar Feedback",
                    "url": feedback_url
                }
            ]
        })

        return card

    async def send(
        self,
        insights: List[Hypothesis],
        recipient: str,
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Envía insights vía Teams webhook."""
        logger.info(f"Sending {len(insights)} insights via Teams webhook")

        try:
            # Formatear mensaje
            card = self.format_message(insights, subject, metadata)

            # Enviar POST request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['webhook_url'],
                    json=card,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        logger.info("Teams message sent successfully")
                        return {
                            "success": True,
                            "sent_at": datetime.now().isoformat(),
                            "insights_count": len(insights)
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Teams webhook failed: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}",
                            "sent_at": datetime.now().isoformat()
                        }

        except Exception as e:
            logger.error(f"Error sending Teams message: {e}")
            return {
                "success": False,
                "error": str(e),
                "sent_at": datetime.now().isoformat()
            }


# ============================================================================
# WHATSAPP CHANNEL
# ============================================================================

class WhatsAppChannel(BaseDeliveryChannel):
    """
    Canal de delivery vía WhatsApp Business API.

    Formatea insights como mensajes de texto con formato.
    """

    def validate_config(self):
        """Valida API credentials."""
        required = ['api_token', 'phone_number_id']
        missing = [k for k in required if k not in self.config]

        if missing:
            raise ValueError(f"Missing required WhatsApp config: {missing}")

    def format_message(
        self,
        insights: List[Hypothesis],
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Formatea insights como mensaje de WhatsApp (texto plano con emojis)."""
        metadata = metadata or {}
        client_name = metadata.get('client_name', 'Cliente')

        # Mensaje de texto con formato
        message = f"""🔍 *Unknown Unknowns Discovery*

{client_name} | {datetime.now().strftime('%B %d, %Y')}

Descubrimos *{len(insights)} insights accionables* para tu negocio:

"""

        # Agregar cada insight
        for i, insight in enumerate(insights[:3], 1):  # Máximo 3 para WhatsApp
            portfolio_emoji = {
                "quick_win": "⚡",
                "medium_term": "📅",
                "strategic_bet": "🎯"
            }.get(insight.portfolio_type.value, "📊")

            message += f"""━━━━━━━━━━━━━━━━━━━━
{portfolio_emoji} *{i}. {insight.hypothesis_text[:80]}...*

📊 Score: {insight.delivery_score.delivery_score_total:.0f}/100
👤 Owner: {insight.actionability.decision_owner}
💰 Impact: ${insight.actionability.estimated_impact_usd or 0:,.0f}

✅ Acción:
{insight.actionability.if_true_then[:120]}...

"""

        # Footer
        feedback_url = metadata.get('feedback_url', '#')
        message += f"""━━━━━━━━━━━━━━━━━━━━

📝 Dar feedback: {feedback_url}

🤖 Generado por Unknown Unknowns Agent
"""

        return message

    async def send(
        self,
        insights: List[Hypothesis],
        recipient: str,
        subject: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Envía insights vía WhatsApp Business API."""
        logger.info(f"Sending {len(insights)} insights via WhatsApp to {recipient}")

        try:
            # Formatear mensaje
            message_text = self.format_message(insights, subject, metadata)

            # WhatsApp Business API endpoint
            url = f"https://graph.facebook.com/v18.0/{self.config['phone_number_id']}/messages"

            # Payload
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {
                    "preview_url": True,
                    "body": message_text
                }
            }

            # Headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['api_token']}"
            }

            # Enviar POST request
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"WhatsApp message sent successfully: {result}")
                        return {
                            "success": True,
                            "message_id": result.get('messages', [{}])[0].get('id'),
                            "sent_at": datetime.now().isoformat(),
                            "recipient": recipient,
                            "insights_count": len(insights)
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"WhatsApp API failed: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}",
                            "sent_at": datetime.now().isoformat()
                        }

        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return {
                "success": False,
                "error": str(e),
                "sent_at": datetime.now().isoformat()
            }


# ============================================================================
# CHANNEL FACTORY
# ============================================================================

class ChannelFactory:
    """
    Factory para crear delivery channels basado en configuración.
    """

    @staticmethod
    def create_channel(channel_type: str, config: Dict[str, Any]) -> BaseDeliveryChannel:
        """
        Crea un canal de delivery.

        Args:
            channel_type: 'email', 'teams', 'whatsapp'
            config: Configuración del canal

        Returns:
            Instancia de BaseDeliveryChannel

        Raises:
            ValueError: Si channel_type no es soportado
        """
        channels = {
            'email': EmailChannel,
            'teams': TeamsChannel,
            'whatsapp': WhatsAppChannel
        }

        if channel_type not in channels:
            raise ValueError(
                f"Unsupported channel type: {channel_type}. "
                f"Available: {list(channels.keys())}"
            )

        return channels[channel_type](config)

    @staticmethod
    def create_from_settings(settings, channel_type: str) -> BaseDeliveryChannel:
        """
        Crea canal desde Settings object.

        Args:
            settings: Settings object (de config.settings)
            channel_type: 'email', 'teams', 'whatsapp'

        Returns:
            Instancia de BaseDeliveryChannel configurada
        """
        configs = {
            'email': {
                'smtp_host': settings.smtp_host,
                'smtp_port': settings.smtp_port,
                'smtp_user': settings.smtp_user,
                'smtp_password': settings.smtp_password,
                'smtp_from': settings.smtp_from
            },
            'teams': {
                'webhook_url': settings.teams_webhook_url
            },
            'whatsapp': {
                'api_token': settings.whatsapp_api_token,
                'phone_number_id': settings.whatsapp_phone_number_id
            }
        }

        config = configs.get(channel_type)
        if not config:
            raise ValueError(f"No configuration found for channel: {channel_type}")

        return ChannelFactory.create_channel(channel_type, config)

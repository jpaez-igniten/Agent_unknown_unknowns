"""
Delivery & Feedback Loop - FASE 4

Componentes para entregar insights y capturar feedback.
"""

from .channels import EmailChannel, TeamsChannel, WhatsAppChannel, ChannelFactory
from .orchestrator import InsightDeliveryOrchestrator

__all__ = [
    'EmailChannel',
    'TeamsChannel',
    'WhatsAppChannel',
    'ChannelFactory',
    'InsightDeliveryOrchestrator'
]

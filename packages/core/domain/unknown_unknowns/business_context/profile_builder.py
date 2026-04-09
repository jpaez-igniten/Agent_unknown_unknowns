"""
Business Profile Builder

Construye y enriquece BusinessProfile desde múltiples fuentes:
- FASE 1: Onboarding manual (cuestionario)
- FASE 1: Detección automática de ortodoxos (creencias no cuestionadas)
- FASE 2+: Análisis automático del schema
- FASE 2+: Learning continuo de conversaciones

CRÍTICO: La detección de ortodoxos es NUESTRA responsabilidad, no del cliente.
Los ortodoxos son invisibles para quien está dentro del sistema.

Patrón Builder para construir objetos complejos paso a paso.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from .profile_schema import (
    BusinessProfile,
    BusinessProfileCreate,
    StrategicPriority,
    KPI,
    BusinessProcess,
    Initiative,
    SizeMetrics,
    Orthodoxy
)
from .profile_repository import BusinessProfileRepository
from .orthodoxy_detector import OrthodoxyDetector

logger = logging.getLogger(__name__)


class BusinessProfileBuilder:
    """
    Builder para construir BusinessProfile desde diferentes fuentes.

    En FASE 1, solo implementa build_from_onboarding.
    En fases posteriores, se agregarán:
    - enrich_from_schema_analysis
    - update_from_conversations
    """

    def __init__(
        self,
        repository: BusinessProfileRepository,
        db_connection=None,
        llm=None
    ):
        """
        Args:
            repository: BusinessProfileRepository para persistir perfiles
            db_connection: Conexión asyncpg (opcional, requerido para orthodoxy detection)
            llm: LLM para análisis (opcional, requerido para orthodoxy detection)
        """
        self.repository = repository
        self.db = db_connection
        self.llm = llm

        # Initialize OrthodoxyDetector if dependencies are available
        if db_connection and llm:
            self.orthodoxy_detector = OrthodoxyDetector(db_connection, llm)
            logger.info("OrthodoxyDetector initialized")
        else:
            self.orthodoxy_detector = None
            logger.info("OrthodoxyDetector not initialized (missing db_connection or llm)")

    # ========== FASE 1: ONBOARDING MANUAL ==========

    async def build_from_onboarding(
        self,
        client_id: str,
        answers: Dict[str, Any]
    ) -> BusinessProfile:
        """
        Construye BusinessProfile inicial desde respuestas de onboarding.

        Args:
            client_id: ID único del cliente
            answers: Dict con respuestas del cuestionario de onboarding

        Returns:
            BusinessProfile creado y guardado

        Example answers format:
            {
                "company_name": "Seguros Carga S.A.",
                "industry": "Seguros B2B",
                "industry_sub_segment": "Seguros de carga",
                "business_model": "B2B",
                "revenue_model": "Comisión",
                "size": {
                    "employees": 250,
                    "revenue_range": "$20M-$50M",
                    "locations": 3
                },
                "strategic_priorities": [
                    {
                        "priority": "Reducir costos operativos 15%",
                        "deadline": "Q2 2025",
                        "owner": "COO"
                    }
                ],
                "known_pain_points": [
                    "No sabemos qué clientes son rentables"
                ],
                "north_star_metric": "Margen neto",
                "kpis": [
                    {
                        "name": "Margen bruto",
                        "target": 0.35,
                        "current": 0.28,
                        "unit": "%",
                        "trend": "declining"
                    }
                ],
                "key_departments": ["Ventas", "Operaciones"],
                "erp_system": "SAP ECC",
                "sap_modules": ["FI", "SD"],
                "data_maturity": "medium",
                "historical_data_years": 3
            }
        """
        logger.info(f"Building profile from onboarding for client_id: {client_id}")

        try:
            # Validar datos requeridos
            self._validate_onboarding_data(answers)

            # Parsear StrategicPriority
            strategic_priorities = []
            if 'strategic_priorities' in answers:
                for sp_data in answers['strategic_priorities']:
                    strategic_priorities.append(StrategicPriority(**sp_data))

            # Parsear KPIs
            kpis = []
            if 'kpis' in answers:
                for kpi_data in answers['kpis']:
                    kpis.append(KPI(**kpi_data))

            # Parsear BusinessProcess
            primary_processes = []
            if 'primary_processes' in answers:
                for process_data in answers['primary_processes']:
                    primary_processes.append(BusinessProcess(**process_data))

            # Parsear Initiative
            active_initiatives = []
            if 'active_initiatives' in answers:
                for init_data in answers['active_initiatives']:
                    active_initiatives.append(Initiative(**init_data))

            # Parsear SizeMetrics
            size = SizeMetrics(**(answers.get('size', {})))

            # Construir perfil
            profile = BusinessProfile(
                client_id=client_id,
                company_name=answers['company_name'],
                industry=answers['industry'],
                industry_sub_segment=answers.get('industry_sub_segment'),
                business_model=answers['business_model'],
                revenue_model=answers['revenue_model'],
                size=size,
                key_departments=answers.get('key_departments', []),
                primary_processes=primary_processes,
                erp_system=answers.get('erp_system'),
                sap_modules=answers.get('sap_modules'),
                other_systems=answers.get('other_systems', []),
                data_maturity=answers.get('data_maturity', 'medium'),
                historical_data_years=answers.get('historical_data_years', 2),
                strategic_priorities=strategic_priorities,
                known_pain_points=answers.get('known_pain_points', []),
                active_initiatives=active_initiatives,
                north_star_metric=answers.get('north_star_metric'),
                kpis=kpis,
                industry_benchmarks=answers.get('industry_benchmarks'),
                regulatory_constraints=answers.get('regulatory_constraints', []),
                competitive_context=answers.get('competitive_context'),
                preferences=answers.get('preferences', {}),
                created_at=datetime.now(),
                last_updated=datetime.now()
            )

            # Detect orthodoxies (if detector is available)
            # CRITICAL: This is OUR responsibility, not the client's
            # Orthodoxies are invisible to those inside the system
            if self.orthodoxy_detector:
                try:
                    logger.info(f"Detecting orthodoxies for {client_id}...")
                    detected_orthodoxies = await self.orthodoxy_detector.detect_orthodoxies(client_id)

                    # Convert to Orthodoxy models and add to profile
                    for orth_data in detected_orthodoxies:
                        orthodoxy = Orthodoxy(
                            orthodoxy=orth_data['orthodoxy'],
                            discovered_by=orth_data['discovered_by'],
                            confidence=orth_data['confidence'],
                            potential_for_disruption=orth_data['potential_for_disruption'],
                            evidence=orth_data.get('evidence', ''),
                            detected_at=(
                                datetime.fromisoformat(orth_data['detected_at'])
                                if isinstance(orth_data['detected_at'], str)
                                else orth_data['detected_at']
                            ),
                            quote=orth_data.get('quote')
                        )
                        profile.add_orthodoxy(orthodoxy)

                    logger.info(
                        f"Detected {len(detected_orthodoxies)} orthodoxies for {client_id} "
                        f"({len(profile.get_high_disruption_orthodoxies())} high-disruption)"
                    )

                except Exception as e:
                    logger.warning(f"Could not detect orthodoxies for {client_id}: {e}")
                    # Continue without orthodoxies - not critical to fail the whole profile
            else:
                logger.debug("Orthodoxy detection skipped (detector not initialized)")

            # Calcular completeness (includes orthodoxies now)
            profile.profile_completeness = profile.calculate_completeness()

            # Inferir confidence_score basado en completeness
            # En onboarding manual, asumimos confianza alta
            profile.confidence_score = min(0.7 + (profile.profile_completeness * 0.3), 1.0)

            # Guardar en BD
            created_profile = await self.repository.create_profile(profile)

            logger.info(
                f"Profile created for {client_id}: "
                f"completeness={created_profile.profile_completeness:.2f}, "
                f"confidence={created_profile.confidence_score:.2f}"
            )

            return created_profile

        except Exception as e:
            logger.error(f"Error building profile from onboarding for {client_id}: {e}")
            raise

    def _validate_onboarding_data(self, answers: Dict[str, Any]):
        """
        Valida que los datos de onboarding tengan los campos requeridos.

        Raises:
            ValueError: Si faltan campos requeridos o son inválidos
        """
        required_fields = [
            'company_name',
            'industry',
            'business_model',
            'revenue_model'
        ]

        missing = [field for field in required_fields if field not in answers or not answers[field]]
        if missing:
            raise ValueError(f"Missing required fields in onboarding data: {missing}")

        # Validar data_maturity
        if 'data_maturity' in answers:
            valid_maturity = ['low', 'medium', 'high']
            if answers['data_maturity'] not in valid_maturity:
                raise ValueError(f"data_maturity must be one of: {valid_maturity}")

        # Validar strategic_priorities format
        if 'strategic_priorities' in answers:
            if not isinstance(answers['strategic_priorities'], list):
                raise ValueError("strategic_priorities must be a list")

            for i, sp in enumerate(answers['strategic_priorities']):
                if not isinstance(sp, dict) or 'priority' not in sp:
                    raise ValueError(f"strategic_priorities[{i}] must be a dict with 'priority' field")

        # Validar KPIs format
        if 'kpis' in answers:
            if not isinstance(answers['kpis'], list):
                raise ValueError("kpis must be a list")

            for i, kpi in enumerate(answers['kpis']):
                if not isinstance(kpi, dict) or 'name' not in kpi:
                    raise ValueError(f"kpis[{i}] must be a dict with 'name' field")

        logger.debug(f"Onboarding data validation passed")

    # ========== ENRIQUECIMIENTO ADICIONAL (FASE 1) ==========

    async def enrich_profile_metadata(
        self,
        client_id: str,
        additional_data: Dict[str, Any]
    ) -> Optional[BusinessProfile]:
        """
        Enriquece un perfil existente con metadata adicional.

        Útil para agregar información después del onboarding inicial.

        Args:
            client_id: ID del cliente
            additional_data: Dict con datos adicionales a agregar

        Returns:
            BusinessProfile actualizado o None si no existe
        """
        logger.info(f"Enriching profile metadata for {client_id}")

        try:
            profile = await self.repository.get_profile(client_id)
            if not profile:
                logger.warning(f"Profile {client_id} not found for enrichment")
                return None

            # Agregar datos adicionales a preferences o metadata
            if 'preferences' in additional_data:
                profile.preferences.update(additional_data['preferences'])

            if 'industry_benchmarks' in additional_data:
                profile.industry_benchmarks = additional_data['industry_benchmarks']

            if 'competitive_context' in additional_data:
                profile.competitive_context = additional_data['competitive_context']

            # Actualizar metadata
            profile.last_updated = datetime.now()
            profile.profile_completeness = profile.calculate_completeness()

            # Guardar
            from .profile_schema import BusinessProfileUpdate
            updates = BusinessProfileUpdate(
                preferences=profile.preferences,
                industry_benchmarks=profile.industry_benchmarks,
                competitive_context=profile.competitive_context
            )
            updated = await self.repository.update_profile(client_id, updates)

            logger.info(f"Profile metadata enriched for {client_id}")
            return updated

        except Exception as e:
            logger.error(f"Error enriching profile metadata for {client_id}: {e}")
            raise

    # ========== HELPERS ==========

    def generate_onboarding_template(self) -> Dict[str, Any]:
        """
        Genera un template de ejemplo para el cuestionario de onboarding.

        Returns:
            Dict con estructura de ejemplo para onboarding
        """
        return {
            "company_name": "Ejemplo S.A.",
            "industry": "Retail",  # "Seguros B2B", "Manufactura", etc.
            "industry_sub_segment": "Retail farmacéutico",  # Opcional
            "business_model": "B2B",  # "B2B", "B2C", "B2B2C", "Marketplace"
            "revenue_model": "Transaccional",  # "Transaccional", "Suscripción", "Comisión", "Mixto"

            "size": {
                "employees": 500,
                "revenue_range": "$10M-$50M",  # "$1M-$10M", "$50M-$100M", etc.
                "locations": 5,
                "countries": 2,
                "customers": 1000
            },

            "strategic_priorities": [
                {
                    "priority": "Reducir costos operativos 15%",
                    "deadline": "Q2 2025",
                    "owner": "COO",
                    "target_metric": "Costo operativo / Revenue",
                    "current_status": "planning"
                },
                {
                    "priority": "Aumentar margen neto a 12%",
                    "deadline": "Q4 2025",
                    "owner": "CFO"
                }
            ],

            "known_pain_points": [
                "No sabemos qué clientes son rentables",
                "Descuentos se otorgan sin criterio claro",
                "Inventario muerto representa 20% del total"
            ],

            "north_star_metric": "Margen neto",  # "NPS", "CAC Payback", "Revenue per employee", etc.

            "kpis": [
                {
                    "name": "Margen bruto",
                    "target": 35.0,
                    "current": 28.0,
                    "unit": "%",
                    "trend": "declining",  # "improving", "stable", "declining"
                    "period": "monthly"
                },
                {
                    "name": "Inventory turnover",
                    "target": 8.0,
                    "current": 6.5,
                    "unit": "times/year",
                    "trend": "stable"
                }
            ],

            "key_departments": [
                "Ventas",
                "Operaciones",
                "Finanzas",
                "Supply Chain",
                "IT"
            ],

            "primary_processes": [
                {
                    "name": "Venta a clientes",
                    "department": "Ventas",
                    "steps": [
                        "Prospección",
                        "Cotización",
                        "Negociación",
                        "Cierre",
                        "Entrega"
                    ],
                    "kpis": ["Conversion rate", "Average deal size"],
                    "pain_points": ["Descuentos sin control"]
                }
            ],

            "active_initiatives": [
                {
                    "name": "Implementar pricing dinámico",
                    "status": "planning",  # "in_progress", "on_hold", "completed"
                    "start_date": "2025-02-01",
                    "expected_completion": "2025-06-30",
                    "owner": "VP Sales",
                    "budget": 150000
                }
            ],

            "erp_system": "SAP ECC",  # "SAP S/4HANA", "Oracle", "Dynamics", "Custom", None
            "sap_modules": ["FI", "CO", "MM", "SD"],  # Si aplica
            "other_systems": [
                "Salesforce",
                "Shopify",
                "Tableau"
            ],

            "data_maturity": "medium",  # "low", "medium", "high"
            "historical_data_years": 3,

            "industry_benchmarks": {
                "avg_gross_margin": 0.32,
                "avg_inventory_turnover": 7.5,
                "avg_revenue_per_employee": 250000
            },

            "regulatory_constraints": [
                "GDPR",
                "SOX"
            ],

            "competitive_context": "Mercado fragmentado con 3 grandes competidores y muchos pequeños",

            "preferences": {
                "insight_frequency": "weekly",  # "daily", "weekly", "monthly"
                "focus_areas": ["financial", "operational"],
                "delivery_channels": ["email", "teams"]
            }
        }

    async def validate_profile_quality(self, client_id: str) -> Dict[str, Any]:
        """
        Valida la calidad de un perfil y sugiere mejoras.

        Args:
            client_id: ID del cliente

        Returns:
            Dict con score de calidad y sugerencias de mejora
        """
        profile = await self.repository.get_profile(client_id)
        if not profile:
            return {"error": "Profile not found"}

        suggestions = []

        # Verificar strategic_priorities
        if not profile.strategic_priorities:
            suggestions.append({
                "field": "strategic_priorities",
                "severity": "high",
                "message": "No strategic priorities defined. This is critical for generating relevant hypotheses."
            })
        elif len(profile.strategic_priorities) < 2:
            suggestions.append({
                "field": "strategic_priorities",
                "severity": "medium",
                "message": "Only 1 strategic priority defined. Consider adding 2-3 priorities for better context."
            })

        # Verificar pain_points
        if not profile.known_pain_points:
            suggestions.append({
                "field": "known_pain_points",
                "severity": "high",
                "message": "No known pain points. These help generate targeted hypotheses."
            })

        # Verificar KPIs
        if not profile.kpis:
            suggestions.append({
                "field": "kpis",
                "severity": "medium",
                "message": "No KPIs defined. KPIs help prioritize and quantify insights."
            })
        else:
            kpis_with_targets = [kpi for kpi in profile.kpis if kpi.target is not None]
            if len(kpis_with_targets) == 0:
                suggestions.append({
                    "field": "kpis",
                    "severity": "medium",
                    "message": "KPIs defined but no targets set. Targets help measure impact."
                })

        # Verificar north_star_metric
        if not profile.north_star_metric:
            suggestions.append({
                "field": "north_star_metric",
                "severity": "low",
                "message": "No North Star Metric defined. This helps align all insights to top priority."
            })

        # Verificar data context
        if not profile.erp_system and not profile.other_systems:
            suggestions.append({
                "field": "systems",
                "severity": "medium",
                "message": "No systems information. Understanding data sources improves hypothesis relevance."
            })

        # Calcular quality score
        quality_score = profile.profile_completeness

        # Penalizar si faltan campos críticos
        critical_missing = [s for s in suggestions if s['severity'] == 'high']
        quality_score -= len(critical_missing) * 0.15

        quality_score = max(0.0, min(1.0, quality_score))

        return {
            "client_id": client_id,
            "quality_score": round(quality_score, 2),
            "completeness": profile.profile_completeness,
            "confidence": profile.confidence_score,
            "suggestions": suggestions,
            "critical_issues": len(critical_missing),
            "total_suggestions": len(suggestions),
            "ready_for_hypothesis_generation": quality_score >= 0.5 and len(critical_missing) == 0
        }

    # ========== FASE 2+: SCHEMA ANALYSIS (STUB) ==========

    async def enrich_from_schema_analysis(self, client_id: str) -> Optional[BusinessProfile]:
        """
        [FASE 2+] Analiza el schema del cliente para inferir información.

        En FASE 1, esto es un stub que retorna el perfil sin cambios.

        TODO en FASE 2:
        - Detectar módulos SAP activos desde nombres de tablas
        - Inferir áreas de negocio con más datos
        - Calcular quality score de datos por tabla
        - Identificar relaciones clave usando Neo4j

        Args:
            client_id: ID del cliente

        Returns:
            BusinessProfile enriquecido
        """
        logger.info(f"[STUB] Schema analysis not implemented in PHASE 1 for {client_id}")
        return await self.repository.get_profile(client_id)

    # ========== FASE 2+: CONVERSATION LEARNING (STUB) ==========

    async def update_from_conversations(
        self,
        client_id: str,
        recent_days: int = 30
    ) -> Optional[BusinessProfile]:
        """
        [FASE 2+] Analiza conversaciones recientes para actualizar el perfil.

        En FASE 1, esto es un stub que retorna el perfil sin cambios.

        TODO en FASE 2:
        - Analizar conversation_history table
        - Detectar nuevas prioridades mencionadas
        - Identificar pain points emergentes
        - Actualizar KPIs de interés

        Args:
            client_id: ID del cliente
            recent_days: Ventana de días a analizar

        Returns:
            BusinessProfile actualizado
        """
        logger.info(f"[STUB] Conversation learning not implemented in PHASE 1 for {client_id}")
        return await self.repository.get_profile(client_id)

"""
Business Profile Schema

Modelos Pydantic para representar el perfil completo de un negocio cliente.
Este perfil se usa para generar hipótesis contextualizadas.

Ventana de Johari aplicada a datos empresariales:
- Arena Abierta: Lo que el cliente sabe y mide
- Punto Ciego: Lo que sus datos revelan pero no ha visto
- Fachada: Lo que oculta o no comparte
- Unknown Unknowns: Lo que este agente busca iluminar
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator, root_validator


class StrategicPriority(BaseModel):
    """Prioridad estratégica del negocio"""
    priority: str = Field(..., description="Descripción de la prioridad estratégica")
    deadline: Optional[str] = Field(None, description="Fecha límite (ej: 'Q2 2025')")
    owner: Optional[str] = Field(None, description="Responsable (rol/nombre)")
    target_metric: Optional[str] = Field(None, description="Métrica objetivo asociada")
    current_status: Optional[str] = Field("planning", description="Estado actual")


class KPI(BaseModel):
    """Indicador clave de desempeño"""
    name: str = Field(..., description="Nombre del KPI")
    target: Optional[float] = Field(None, description="Valor objetivo")
    current: Optional[float] = Field(None, description="Valor actual")
    unit: Optional[str] = Field(None, description="Unidad de medida (%, USD, etc.)")
    trend: Optional[str] = Field(None, description="Tendencia: 'improving', 'stable', 'declining'")
    period: Optional[str] = Field("monthly", description="Período de medición")


class BusinessProcess(BaseModel):
    """Proceso de negocio clave"""
    name: str = Field(..., description="Nombre del proceso")
    department: Optional[str] = Field(None, description="Departamento responsable")
    steps: List[str] = Field(default_factory=list, description="Pasos principales")
    kpis: List[str] = Field(default_factory=list, description="KPIs asociados")
    pain_points: List[str] = Field(default_factory=list, description="Problemas conocidos")


class Initiative(BaseModel):
    """Iniciativa o proyecto activo"""
    name: str = Field(..., description="Nombre de la iniciativa")
    status: str = Field(..., description="Estado: 'planning', 'in_progress', 'on_hold', 'completed'")
    start_date: Optional[str] = Field(None, description="Fecha de inicio")
    expected_completion: Optional[str] = Field(None, description="Fecha esperada de finalización")
    owner: Optional[str] = Field(None, description="Responsable")
    budget: Optional[float] = Field(None, description="Presupuesto asignado (USD)")


class SizeMetrics(BaseModel):
    """Métricas de tamaño de la empresa"""
    employees: Optional[int] = Field(None, description="Número de empleados")
    revenue_range: Optional[str] = Field(None, description="Rango de ingresos (ej: '$10M-$50M')")
    locations: Optional[int] = Field(None, description="Número de ubicaciones/plantas")
    countries: Optional[int] = Field(None, description="Países donde opera")
    customers: Optional[int] = Field(None, description="Número de clientes activos")


class ValidatedInsight(BaseModel):
    """Insight previamente validado"""
    insight_id: int = Field(..., description="ID del insight")
    hypothesis_text: str = Field(..., description="Hipótesis original")
    validation_date: datetime = Field(..., description="Fecha de validación")
    impact_usd: Optional[float] = Field(None, description="Impacto realizado en USD")
    action_taken: Optional[str] = Field(None, description="Acción tomada")
    category: str = Field(..., description="Categoría del insight")


class RejectedInsight(BaseModel):
    """Insight rechazado o marcado como no útil"""
    insight_id: int = Field(..., description="ID del insight")
    hypothesis_text: str = Field(..., description="Hipótesis original")
    rejection_date: datetime = Field(..., description="Fecha de rechazo")
    reason: str = Field(..., description="Razón del rechazo")


class BusinessProfile(BaseModel):
    """
    Perfil completo del negocio del cliente.

    Se construye mediante:
    1. Onboarding inicial (cuestionario)
    2. Análisis automático del schema (FASE 2+)
    3. Learning continuo de conversaciones (FASE 2+)
    4. Input manual del equipo Igniten
    """

    # ========== IDENTIDAD ==========
    client_id: str = Field(..., description="ID único del cliente")
    company_name: str = Field(..., description="Nombre de la empresa")
    industry: str = Field(..., description="Industria principal (ej: 'Seguros B2B', 'Retail', 'Manufactura')")
    industry_sub_segment: Optional[str] = Field(
        None,
        description="Sub-segmento específico (ej: 'Seguros de carga', 'Retail farmacéutico')"
    )

    # ========== CONTEXTO DE NEGOCIO ==========
    business_model: str = Field(..., description="Modelo de negocio: 'B2B', 'B2C', 'B2B2C', 'Marketplace', etc.")
    revenue_model: str = Field(
        ...,
        description="Modelo de ingresos: 'Transaccional', 'Suscripción', 'Comisión', 'Mixto', etc."
    )
    size: SizeMetrics = Field(default_factory=SizeMetrics, description="Métricas de tamaño de la empresa")

    # ========== ESTRUCTURA OPERATIVA ==========
    key_departments: List[str] = Field(
        default_factory=list,
        description="Departamentos clave (ej: ['Ventas', 'Operaciones', 'Finanzas', 'Supply Chain'])"
    )
    primary_processes: List[BusinessProcess] = Field(
        default_factory=list,
        description="Procesos de negocio principales"
    )

    # ========== SISTEMA DE INFORMACIÓN ==========
    erp_system: Optional[str] = Field(
        None,
        description="Sistema ERP principal (ej: 'SAP ECC', 'SAP S/4HANA', 'Oracle', 'Dynamics', 'Custom')"
    )
    sap_modules: Optional[List[str]] = Field(
        None,
        description="Módulos SAP activos (ej: ['FI', 'CO', 'MM', 'SD', 'PP'])"
    )
    other_systems: List[str] = Field(
        default_factory=list,
        description="Otros sistemas integrados (ej: ['Salesforce', 'Shopify', 'WMS'])"
    )
    data_maturity: str = Field(
        default="medium",
        description="Madurez de datos: 'low', 'medium', 'high'"
    )
    historical_data_years: int = Field(
        default=2,
        description="Años de datos históricos disponibles"
    )

    # ========== CONTEXTO ESTRATÉGICO (CRÍTICO para priorización) ==========
    strategic_priorities: List[StrategicPriority] = Field(
        default_factory=list,
        description="Prioridades estratégicas ordenadas por importancia"
    )
    known_pain_points: List[str] = Field(
        default_factory=list,
        description="Problemas de negocio conocidos (ej: 'No sabemos qué clientes son rentables')"
    )
    active_initiatives: List[Initiative] = Field(
        default_factory=list,
        description="Iniciativas o proyectos activos"
    )

    # ========== MÉTRICAS CLAVE ==========
    north_star_metric: Optional[str] = Field(
        None,
        description="Métrica norte (la más importante) (ej: 'Margen neto', 'NPS', 'CAC Payback')"
    )
    kpis: List[KPI] = Field(
        default_factory=list,
        description="KPIs clave que el cliente monitorea"
    )

    # ========== CONOCIMIENTO INDUSTRIA ==========
    industry_benchmarks: Optional[Dict[str, Any]] = Field(
        None,
        description="Benchmarks de la industria para comparación"
    )
    regulatory_constraints: List[str] = Field(
        default_factory=list,
        description="Restricciones regulatorias relevantes (ej: ['GDPR', 'SOX', 'HIPAA'])"
    )
    competitive_context: Optional[str] = Field(
        None,
        description="Contexto competitivo del mercado"
    )

    # ========== METADATA ==========
    profile_completeness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score de completitud del perfil (0.0 - 1.0)"
    )
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Score de confianza en la precisión del perfil (0.0 - 1.0)"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Fecha de creación")
    last_updated: datetime = Field(default_factory=datetime.now, description="Última actualización")
    last_enrichment: Optional[datetime] = Field(
        None,
        description="Última vez que se enriqueció automáticamente"
    )

    # ========== HIPÓTESIS HISTÓRICAS ==========
    explored_hypotheses: List[str] = Field(
        default_factory=list,
        description="IDs de hipótesis ya exploradas (para evitar repetición)"
    )
    validated_insights: List[ValidatedInsight] = Field(
        default_factory=list,
        description="Insights que fueron validados y útiles"
    )
    rejected_insights: List[RejectedInsight] = Field(
        default_factory=list,
        description="Insights rechazados o marcados como no útiles"
    )

    # ========== CONFIGURACIÓN ==========
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preferencias del cliente (ej: frecuencia de insights, áreas de enfoque)"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('data_maturity')
    def validate_data_maturity(cls, v):
        """Valida que data_maturity sea un valor permitido"""
        allowed = ['low', 'medium', 'high']
        if v not in allowed:
            raise ValueError(f"data_maturity debe ser uno de: {allowed}")
        return v

    @validator('profile_completeness', 'confidence_score')
    def validate_scores(cls, v):
        """Valida que los scores estén entre 0 y 1"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("El score debe estar entre 0.0 y 1.0")
        return v

    @root_validator(skip_on_failure=True)
    def update_last_updated(cls, values):
        """Actualiza last_updated al modificar el perfil"""
        if 'last_updated' not in values or values.get('last_updated') is None:
            values['last_updated'] = datetime.now()
        return values

    def calculate_completeness(self) -> float:
        """
        Calcula el score de completitud del perfil basado en campos poblados.

        Pesos:
        - Identidad y contexto básico: 20%
        - Contexto estratégico (prioridades, pain points): 40%
        - Métricas y KPIs: 25%
        - Sistemas y datos: 15%
        """
        score = 0.0

        # Identidad y contexto básico (20%)
        basic_fields = [
            self.company_name,
            self.industry,
            self.business_model,
            self.revenue_model
        ]
        score += 0.20 * (sum(1 for f in basic_fields if f) / len(basic_fields))

        # Contexto estratégico (40%)
        strategic_score = 0.0
        if self.strategic_priorities:
            strategic_score += 0.15
        if self.known_pain_points:
            strategic_score += 0.15
        if self.north_star_metric:
            strategic_score += 0.10
        score += min(strategic_score, 0.40)

        # Métricas y KPIs (25%)
        if self.kpis:
            score += 0.15
        if self.primary_processes:
            score += 0.10

        # Sistemas y datos (15%)
        if self.erp_system or self.other_systems:
            score += 0.10
        if self.historical_data_years > 0:
            score += 0.05

        return min(round(score, 2), 1.0)

    def add_explored_hypothesis(self, hypothesis_id: str):
        """Agrega un ID de hipótesis a la lista de exploradas"""
        if hypothesis_id not in self.explored_hypotheses:
            self.explored_hypotheses.append(hypothesis_id)
            self.last_updated = datetime.now()

    def add_validated_insight(self, insight: ValidatedInsight):
        """Agrega un insight validado"""
        self.validated_insights.append(insight)
        self.last_updated = datetime.now()

    def add_rejected_insight(self, insight: RejectedInsight):
        """Agrega un insight rechazado"""
        self.rejected_insights.append(insight)
        self.last_updated = datetime.now()

    def get_top_priorities(self, limit: int = 3) -> List[StrategicPriority]:
        """Retorna las top N prioridades estratégicas"""
        return self.strategic_priorities[:limit]

    def get_active_kpis(self) -> List[KPI]:
        """Retorna KPIs que tienen target definido"""
        return [kpi for kpi in self.kpis if kpi.target is not None]

    def to_context_string(self) -> str:
        """
        Genera un string de contexto para usar en prompts del LLM.
        Resume la información más relevante del perfil.
        """
        context_parts = [
            f"Cliente: {self.company_name}",
            f"Industria: {self.industry}" + (f" - {self.industry_sub_segment}" if self.industry_sub_segment else ""),
            f"Modelo: {self.business_model} ({self.revenue_model})",
            ""
        ]

        if self.strategic_priorities:
            context_parts.append("Prioridades estratégicas:")
            for i, priority in enumerate(self.strategic_priorities[:3], 1):
                context_parts.append(f"  {i}. {priority.priority}" + (f" ({priority.deadline})" if priority.deadline else ""))
            context_parts.append("")

        if self.known_pain_points:
            context_parts.append("Pain points conocidos:")
            for pain_point in self.known_pain_points[:5]:
                context_parts.append(f"  - {pain_point}")
            context_parts.append("")

        if self.north_star_metric:
            context_parts.append(f"North Star Metric: {self.north_star_metric}")

        if self.kpis:
            context_parts.append("KPIs clave:")
            for kpi in self.kpis[:5]:
                kpi_str = f"  - {kpi.name}"
                if kpi.current is not None and kpi.target is not None:
                    kpi_str += f": {kpi.current} → {kpi.target}"
                    if kpi.unit:
                        kpi_str += f" {kpi.unit}"
                context_parts.append(kpi_str)

        return "\n".join(context_parts)


class BusinessProfileCreate(BaseModel):
    """Schema para crear un nuevo perfil desde onboarding"""
    client_id: str
    company_name: str
    industry: str
    industry_sub_segment: Optional[str] = None
    business_model: str
    revenue_model: str
    size: Optional[SizeMetrics] = None
    key_departments: List[str] = []
    erp_system: Optional[str] = None
    sap_modules: Optional[List[str]] = None
    other_systems: List[str] = []
    data_maturity: str = "medium"
    historical_data_years: int = 2
    strategic_priorities: List[StrategicPriority] = []
    known_pain_points: List[str] = []
    active_initiatives: List[Initiative] = []
    north_star_metric: Optional[str] = None
    kpis: List[KPI] = []
    regulatory_constraints: List[str] = []
    preferences: Dict[str, Any] = {}


class BusinessProfileUpdate(BaseModel):
    """Schema para actualizar un perfil existente"""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    industry_sub_segment: Optional[str] = None
    business_model: Optional[str] = None
    revenue_model: Optional[str] = None
    size: Optional[SizeMetrics] = None
    key_departments: Optional[List[str]] = None
    primary_processes: Optional[List[BusinessProcess]] = None
    erp_system: Optional[str] = None
    sap_modules: Optional[List[str]] = None
    other_systems: Optional[List[str]] = None
    data_maturity: Optional[str] = None
    historical_data_years: Optional[int] = None
    strategic_priorities: Optional[List[StrategicPriority]] = None
    known_pain_points: Optional[List[str]] = None
    active_initiatives: Optional[List[Initiative]] = None
    north_star_metric: Optional[str] = None
    kpis: Optional[List[KPI]] = None
    industry_benchmarks: Optional[Dict[str, Any]] = None
    regulatory_constraints: Optional[List[str]] = None
    competitive_context: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

    class Config:
        # Permitir actualización parcial
        extra = 'forbid'

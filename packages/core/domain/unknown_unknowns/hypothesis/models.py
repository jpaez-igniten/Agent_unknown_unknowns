"""
Hypothesis Models - FASE 2

Modelos Pydantic para hipótesis con ACTIONABILITY built-in.

CRÍTICO: Cada hipótesis DEBE incluir:
1. ACTIONABILITY: if_true_then, if_false_then, decision_owner, action_threshold
2. MULTI-DIMENSIONAL CONFIDENCE: statistical, data_quality, model, caveats
3. COUNTERFACTUALS: past-present-future comparisons
4. DELIVERY SCORE: 0-100 con breakdown detallado
5. PORTFOLIO TYPE: quick_win, medium_term, strategic_bet

Filosofía: Una hipótesis sin acción clara es solo ruido.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


# ========== ENUMS ==========

class PortfolioType(str, Enum):
    """
    Tipo de hipótesis en el portfolio mix.

    TARGET MIX:
    - 40% quick_win: <3 meses, bajo costo, alto impacto visible
    - 40% medium_term: 3-12 meses, inversión moderada
    - 20% strategic_bet: >12 meses, alto riesgo, potencial transformador
    """
    QUICK_WIN = "quick_win"          # <3 meses
    MEDIUM_TERM = "medium_term"       # 3-12 meses
    STRATEGIC_BET = "strategic_bet"   # >12 meses


class HypothesisStatus(str, Enum):
    """Estado del ciclo de vida de una hipótesis."""
    PENDING_VALIDATION = "pending_validation"  # Generada, esperando validación técnica
    VALIDATED = "validated"                     # Validada, esperando análisis
    ANALYZED = "analyzed"                       # Analizada, esperando delivery decision
    PENDING_DELIVERY = "pending_delivery"       # Aprobada, esperando entrega
    DELIVERED = "delivered"                     # Entregada al cliente
    PENDING_FEEDBACK = "pending_feedback"       # Esperando respuesta del cliente
    IN_GRAVEYARD = "in_graveyard"              # Movida al graveyard (con categoría)


class GraveyardCategory(str, Enum):
    """
    Categorías del Hypothesis Graveyard.

    Cada hipótesis rechazada va a una de estas categorías para aprendizaje.
    """
    USEFUL = "useful"                             # Cliente la usó y generó valor
    REJECTED = "rejected"                         # Cliente dijo "no, no sirve"
    ALREADY_TRIED = "already_tried"               # Cliente ya lo intentó antes
    POLITICALLY_IMPOSSIBLE = "politically_impossible"  # Bloqueado por política/cultura


class ReviewDecision(str, Enum):
    """Decisión humana en la review queue."""
    APPROVE = "approve"              # Aprobar para entrega
    REJECT = "reject"                # Rechazar (no enviar)
    NEEDS_REFINEMENT = "needs_refinement"  # Requiere más trabajo
    ESCALATE = "escalate"            # Escalar a senior analyst


# ========== ACTIONABILITY MODELS ==========

class ActionThreshold(BaseModel):
    """
    Umbrales para tomar acción basada en el resultado de validar la hipótesis.

    Example:
        Si confidence > 0.7 → implementar
        Si impact > $100K → prioridad alta
        Si ROI > 3x → fast-track
    """
    min_confidence: Optional[float] = Field(
        None,
        description="Confianza mínima requerida para actuar (0-1)"
    )
    min_impact_usd: Optional[float] = Field(
        None,
        description="Impacto mínimo en USD para justificar acción"
    )
    min_roi: Optional[float] = Field(
        None,
        description="ROI mínimo esperado (ej: 3.0 = 3x retorno)"
    )
    max_cost_usd: Optional[float] = Field(
        None,
        description="Costo máximo aceptable para implementar"
    )
    max_time_months: Optional[int] = Field(
        None,
        description="Tiempo máximo aceptable para ver resultados"
    )
    other_conditions: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Otras condiciones personalizadas"
    )


class Actionability(BaseModel):
    """
    Información de ACTIONABILITY para cada hipótesis.

    CRÍTICO: Sin esto, la hipótesis es solo ruido.
    """
    if_true_then: str = Field(
        ...,
        description="Acción específica si la hipótesis es verdadera. DEBE ser clara y accionable."
    )
    if_false_then: Optional[str] = Field(
        None,
        description="Acción si la hipótesis es falsa. Útil para hipótesis exploratorias."
    )
    decision_owner: str = Field(
        ...,
        description="Rol/persona que debe tomar la decisión (ej: 'CFO', 'VP Sales', 'CEO')"
    )
    action_threshold: ActionThreshold = Field(
        default_factory=ActionThreshold,
        description="Umbrales para decidir si actuar"
    )
    estimated_effort_hours: Optional[int] = Field(
        None,
        description="Esfuerzo estimado para implementar la acción (en horas)"
    )
    estimated_cost_usd: Optional[float] = Field(
        None,
        description="Costo estimado de implementación (en USD)"
    )
    estimated_impact_usd: Optional[float] = Field(
        None,
        description="Impacto estimado si se implementa (en USD)"
    )
    time_to_impact_months: Optional[int] = Field(
        None,
        description="Meses estimados para ver impacto"
    )


# ========== CONFIDENCE MODELS ==========

class ConfidenceBreakdown(BaseModel):
    """
    Breakdown multi-dimensional del confidence score.

    Transparency > single number.
    """
    confidence_total: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confianza total (0-1). Calculada como promedio ponderado."
    )
    confidence_statistical: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confianza estadística (p-value, effect size, etc.)"
    )
    confidence_data_quality: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calidad de datos usados (completeness, freshness, accuracy)"
    )
    confidence_model: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confianza del modelo LLM/ML usado"
    )
    confidence_caveats: List[str] = Field(
        default_factory=list,
        description="Advertencias específicas sobre limitaciones de la confianza"
    )

    @validator('confidence_total', always=True)
    def validate_total_confidence(cls, v, values):
        """Valida que confidence_total esté en rango razonable."""
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence_total must be between 0.0 and 1.0")
        return v


# ========== COUNTERFACTUAL MODELS ==========

class Counterfactual(BaseModel):
    """
    Comparación contrafactual para dar contexto a la hipótesis.

    Formato: "Si hubiéramos hecho X en el pasado, Y habría sido el resultado"
    """
    scenario: str = Field(
        ...,
        description="Descripción del escenario contrafactual"
    )
    metric: str = Field(
        ...,
        description="Métrica a comparar (ej: 'revenue', 'churn_rate')"
    )
    actual_value: Optional[float] = Field(
        None,
        description="Valor real observado"
    )
    counterfactual_value: Optional[float] = Field(
        None,
        description="Valor estimado en el escenario contrafactual"
    )
    difference_pct: Optional[float] = Field(
        None,
        description="Diferencia porcentual entre actual y contrafactual"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confianza en esta estimación contrafactual"
    )


class CounterfactualAnalysis(BaseModel):
    """
    Análisis contrafactual completo: pasado-presente-futuro.

    Ayuda al cliente a entender el contexto temporal de la hipótesis.
    """
    past: Optional[Counterfactual] = Field(
        None,
        description="Contrafactual del pasado: 'Si hubiéramos hecho X hace 12 meses...'"
    )
    present: Optional[Counterfactual] = Field(
        None,
        description="Contrafactual del presente: 'Si hacemos X ahora...'"
    )
    future: Optional[Counterfactual] = Field(
        None,
        description="Contrafactual del futuro: 'Si NO hacemos X en los próximos 6 meses...'"
    )


# ========== DELIVERY SCORE MODELS ==========

class DeliveryScoreBreakdown(BaseModel):
    """
    Breakdown del delivery score (0-100).

    WEIGHTS:
    - statistical_confidence: 25%
    - business_impact: 30%
    - actionability: 25%
    - strategic_alignment: 20%

    THRESHOLD: >= 70 → deliver, < 70 → refinement queue
    """
    statistical_confidence_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Score de confianza estadística (0-100). Weight: 25%"
    )
    business_impact_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Score de impacto de negocio (0-100). Weight: 30%"
    )
    actionability_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Score de actionability (0-100). Weight: 25%"
    )
    strategic_alignment_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Score de alineación estratégica (0-100). Weight: 20%"
    )
    delivery_score_total: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Score total ponderado (0-100)"
    )
    should_deliver: bool = Field(
        ...,
        description="True if delivery_score_total >= 70"
    )

    @validator('delivery_score_total', always=True)
    def calculate_total_score(cls, v, values):
        """Calcula el score total como promedio ponderado."""
        weights = {
            'statistical_confidence_score': 0.25,
            'business_impact_score': 0.30,
            'actionability_score': 0.25,
            'strategic_alignment_score': 0.20
        }

        total = sum(
            values.get(key, 0) * weight
            for key, weight in weights.items()
        )

        return round(total, 2)

    @validator('should_deliver', always=True)
    def determine_should_deliver(cls, v, values):
        """Determina si se debe entregar basado en el score total."""
        return values.get('delivery_score_total', 0) >= 70.0


# ========== MAIN HYPOTHESIS MODEL ==========

class Hypothesis(BaseModel):
    """
    Modelo principal de Hipótesis con ACTIONABILITY built-in.

    Cada hipótesis debe poder responder:
    1. ¿Qué creemos? (hypothesis_text)
    2. ¿Por qué lo creemos? (evidence, confidence)
    3. ¿Qué hacemos si es verdad? (if_true_then)
    4. ¿Quién decide? (decision_owner)
    5. ¿Cuándo actuamos? (action_threshold)
    6. ¿Cuál es el contexto? (counterfactuals)
    """

    # ===== IDENTIFICATION =====
    hypothesis_id: str = Field(
        ...,
        description="ID único de la hipótesis (generado)"
    )
    client_id: str = Field(
        ...,
        description="ID del cliente para quien se generó"
    )
    run_id: str = Field(
        ...,
        description="ID del run que generó esta hipótesis"
    )

    # ===== CORE HYPOTHESIS =====
    hypothesis_text: str = Field(
        ...,
        min_length=10,
        description="Texto de la hipótesis. Debe ser clara, específica y testeable."
    )
    hypothesis_type: str = Field(
        ...,
        description="Tipo de hipótesis: 'knowledge_driven', 'anomaly_driven', 'orthodoxy_challenge'"
    )
    category: str = Field(
        ...,
        description="Categoría de negocio: 'pricing', 'churn', 'profitability', 'operations', etc."
    )

    # ===== GENERATION CONTEXT =====
    generated_from: str = Field(
        ...,
        description="Fuente: 'strategic_priority', 'pain_point', 'anomaly_detection', 'orthodoxy'"
    )
    source_orthodoxy_id: Optional[str] = Field(
        None,
        description="ID del ortodoxo que provocó esta hipótesis (si aplica)"
    )
    source_anomaly_id: Optional[str] = Field(
        None,
        description="ID de la anomalía que provocó esta hipótesis (si aplica)"
    )

    # ===== ACTIONABILITY (REQUIRED) =====
    actionability: Actionability = Field(
        ...,
        description="Información de actionability. REQUERIDO."
    )

    # ===== CONFIDENCE (MULTI-DIMENSIONAL) =====
    confidence: ConfidenceBreakdown = Field(
        ...,
        description="Breakdown multi-dimensional de confianza"
    )

    # ===== COUNTERFACTUALS =====
    counterfactuals: Optional[CounterfactualAnalysis] = Field(
        None,
        description="Análisis contrafactual pasado-presente-futuro"
    )

    # ===== EVIDENCE =====
    evidence: List[str] = Field(
        default_factory=list,
        description="Lista de evidencias que soportan la hipótesis"
    )
    data_sources_used: List[str] = Field(
        default_factory=list,
        description="Fuentes de datos usadas (tablas, vistas, etc.)"
    )

    # ===== DELIVERY SCORE =====
    delivery_score: DeliveryScoreBreakdown = Field(
        ...,
        description="Breakdown del delivery score"
    )

    # ===== PORTFOLIO CLASSIFICATION =====
    portfolio_type: PortfolioType = Field(
        ...,
        description="Clasificación en portfolio: quick_win, medium_term, strategic_bet"
    )

    # ===== STATUS & LIFECYCLE =====
    status: HypothesisStatus = Field(
        default=HypothesisStatus.PENDING_VALIDATION,
        description="Estado en el ciclo de vida"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp de creación"
    )
    validated_at: Optional[datetime] = Field(
        None,
        description="Timestamp de validación técnica"
    )
    analyzed_at: Optional[datetime] = Field(
        None,
        description="Timestamp de análisis"
    )
    delivered_at: Optional[datetime] = Field(
        None,
        description="Timestamp de entrega al cliente"
    )

    # ===== HUMAN REVIEW =====
    needs_human_review: bool = Field(
        default=True,
        description="Si requiere review humana. TRUE en primeros 6 meses."
    )
    reviewed_by: Optional[str] = Field(
        None,
        description="Quién hizo la review (analyst name/ID)"
    )
    review_decision: Optional[ReviewDecision] = Field(
        None,
        description="Decisión de la review humana"
    )
    review_notes: Optional[str] = Field(
        None,
        description="Notas de la review"
    )
    reviewed_at: Optional[datetime] = Field(
        None,
        description="Timestamp de review"
    )

    # ===== GRAVEYARD (if rejected) =====
    graveyard_category: Optional[GraveyardCategory] = Field(
        None,
        description="Categoría en el graveyard (si fue rechazada)"
    )
    graveyard_reason: Optional[str] = Field(
        None,
        description="Razón de rechazo (si aplica)"
    )
    moved_to_graveyard_at: Optional[datetime] = Field(
        None,
        description="Timestamp de movimiento al graveyard"
    )

    # ===== METADATA =====
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata adicional flexible"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "hypothesis_id": "hyp_abc123",
                "client_id": "seguros_001",
                "run_id": "run_2025_01_24_001",
                "hypothesis_text": "Los clientes con más de 3 reclamos rechazados tienen 5x más probabilidad de churn",
                "hypothesis_type": "knowledge_driven",
                "category": "churn",
                "generated_from": "pain_point",
                "actionability": {
                    "if_true_then": "Crear programa de retención para clientes con 2+ reclamos rechazados",
                    "if_false_then": "Investigar otros factores de churn",
                    "decision_owner": "Chief Customer Officer",
                    "action_threshold": {
                        "min_confidence": 0.7,
                        "min_impact_usd": 50000,
                        "max_time_months": 6
                    }
                },
                "confidence": {
                    "confidence_total": 0.82,
                    "confidence_statistical": 0.9,
                    "confidence_data_quality": 0.85,
                    "confidence_model": 0.75,
                    "confidence_caveats": ["Sample size < 1000", "Data only from last 12 months"]
                },
                "delivery_score": {
                    "statistical_confidence_score": 82,
                    "business_impact_score": 85,
                    "actionability_score": 90,
                    "strategic_alignment_score": 80,
                    "delivery_score_total": 84.5,
                    "should_deliver": True
                },
                "portfolio_type": "medium_term"
            }
        }


# ========== VALIDATION RESULT MODEL ==========

class ValidationResult(BaseModel):
    """
    Resultado de validar la viabilidad técnica de una hipótesis.

    Valida:
    1. ¿Tenemos los datos necesarios?
    2. ¿Es técnicamente factible validarla con SQL?
    3. ¿Qué queries necesitamos?
    """
    hypothesis_id: str = Field(
        ...,
        description="ID de la hipótesis validada"
    )
    is_feasible: bool = Field(
        ...,
        description="True si es técnicamente factible validar la hipótesis"
    )
    feasibility_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de viabilidad (0-1)"
    )
    required_tables: List[str] = Field(
        default_factory=list,
        description="Tablas requeridas para validar"
    )
    available_tables: List[str] = Field(
        default_factory=list,
        description="Tablas disponibles"
    )
    missing_tables: List[str] = Field(
        default_factory=list,
        description="Tablas faltantes (blockers)"
    )
    suggested_queries: List[str] = Field(
        default_factory=list,
        description="Queries SQL sugeridos para validar"
    )
    estimated_complexity: str = Field(
        ...,
        description="Complejidad estimada: 'low', 'medium', 'high'"
    )
    blockers: List[str] = Field(
        default_factory=list,
        description="Bloqueadores técnicos encontrados"
    )
    validated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp de validación"
    )
    validator_notes: Optional[str] = Field(
        None,
        description="Notas del validador"
    )


# ========== ANALYSIS RESULT MODEL ==========

class AnalysisResult(BaseModel):
    """
    Resultado de analizar una hipótesis contra los datos reales.

    Incluye:
    1. Query ejecutado
    2. Resultado (confirmada/rechazada)
    3. Evidencia cuantitativa
    4. Impacto estimado
    """
    hypothesis_id: str = Field(
        ...,
        description="ID de la hipótesis analizada"
    )
    is_confirmed: bool = Field(
        ...,
        description="True si la hipótesis fue confirmada por los datos"
    )
    confidence_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza en el resultado (0-1)"
    )
    query_executed: str = Field(
        ...,
        description="Query SQL ejecutado"
    )
    query_result_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resumen del resultado del query"
    )
    quantitative_evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Evidencia cuantitativa (métricas, correlaciones, etc.)"
    )
    estimated_business_impact_usd: Optional[float] = Field(
        None,
        description="Impacto de negocio estimado en USD"
    )
    impact_calculation_method: Optional[str] = Field(
        None,
        description="Método usado para calcular el impacto"
    )
    statistical_tests: Optional[Dict[str, Any]] = Field(
        None,
        description="Tests estadísticos realizados (p-value, effect size, etc.)"
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp de análisis"
    )
    analyst_notes: Optional[str] = Field(
        None,
        description="Notas del analyst"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "hypothesis_id": "hyp_abc123",
                "is_confirmed": True,
                "confidence_level": 0.85,
                "query_executed": "SELECT ... FROM claims WHERE ...",
                "query_result_summary": {
                    "total_customers": 1500,
                    "customers_with_3plus_rejections": 120,
                    "churn_rate_normal": 0.08,
                    "churn_rate_3plus_rejections": 0.42,
                    "lift": 5.25
                },
                "quantitative_evidence": {
                    "chi_square_p_value": 0.001,
                    "effect_size": "large",
                    "correlation": 0.72
                },
                "estimated_business_impact_usd": 250000,
                "impact_calculation_method": "120 customers * $2,083 avg CLV * 0.34 prevented churn"
            }
        }

"""
LLM Prompt Templates - FASE 2

Prompts para generación de hipótesis con actionability built-in.

CRÍTICO: Todos los prompts deben instruir al LLM a:
1. Incluir actionability clara (if_true_then, if_false_then, decision_owner)
2. Calcular multi-dimensional confidence
3. Sugerir counterfactuals cuando sea posible
4. Ser específicos y testeables
"""

from typing import Dict, Any


# ============================================================================
# KNOWLEDGE-DRIVEN HYPOTHESIS GENERATION
# ============================================================================

KNOWLEDGE_DRIVEN_PROMPT = """
Eres un estratega de negocio experto analizando datos para descubrir insights accionables.

Tu tarea es generar HIPÓTESIS KNOWLEDGE-DRIVEN basadas en las prioridades estratégicas del cliente.

## CONTEXTO DEL CLIENTE

{business_context}

## ORTODOXOS DETECTADOS

Los siguientes ortodoxos (creencias no cuestionadas) han sido detectados:
{orthodoxies_context}

## INSTRUCCIONES

Genera {max_hypotheses} hipótesis **accionables** que:

1. ESTÉN DIRECTAMENTE RELACIONADAS con las prioridades estratégicas del cliente
2. DESAFÍEN LOS ORTODOXOS detectados (cuando sea apropiado)
3. SEAN TESTEABLES con los datos disponibles
4. INCLUYAN ACTIONABILITY CLARA:
   - if_true_then: Qué acción específica tomar si la hipótesis es verdadera
   - if_false_then: Qué acción tomar si es falsa (opcional pero recomendado)
   - decision_owner: Quién debe tomar la decisión (rol específico: CFO, CEO, VP Sales, etc.)
   - action_threshold: Umbrales para actuar (min_confidence, min_impact_usd, etc.)

5. INCLUYAN CONFIDENCE BREAKDOWN:
   - confidence_statistical: Basado en métodos estadísticos que usarías (0-1)
   - confidence_data_quality: Basado en la calidad de datos disponibles (0-1)
   - confidence_model: Tu confianza en el análisis (0-1)
   - confidence_caveats: Lista de advertencias específicas

6. SEAN ESPECÍFICAS Y CUANTIFICABLES:
   - Evita hipótesis vagas como "mejorar ventas"
   - Usa métricas concretas: "clientes con >3 reclamos tienen 5x más churn"

7. INCLUYAN PORTFOLIO CLASSIFICATION:
   - quick_win: <3 meses, bajo costo, alto impacto visible
   - medium_term: 3-12 meses, inversión moderada
   - strategic_bet: >12 meses, alto riesgo, potencial transformador

## EJEMPLOS DE HIPÓTESIS BIEN FORMULADAS

### Ejemplo 1: Churn prediction
```json
{{
  "hypothesis_text": "Clientes B2B con más de 3 reclamos rechazados en los últimos 6 meses tienen 5x más probabilidad de churn que el promedio",
  "hypothesis_type": "knowledge_driven",
  "category": "churn",
  "generated_from": "strategic_priority",
  "source_orthodoxy_id": "orth_001",
  "actionability": {{
    "if_true_then": "Crear programa de retención proactiva para clientes con 2+ reclamos rechazados: (1) Llamada personal del account manager, (2) Revisión de pricing, (3) Training sobre proceso de reclamos",
    "if_false_then": "Investigar otros predictores de churn: NPS score, payment delays, usage patterns",
    "decision_owner": "Chief Customer Officer",
    "action_threshold": {{
      "min_confidence": 0.7,
      "min_impact_usd": 50000,
      "max_time_months": 3
    }},
    "estimated_effort_hours": 120,
    "estimated_cost_usd": 25000,
    "estimated_impact_usd": 200000,
    "time_to_impact_months": 2
  }},
  "confidence": {{
    "confidence_total": 0.78,
    "confidence_statistical": 0.85,
    "confidence_data_quality": 0.75,
    "confidence_model": 0.75,
    "confidence_caveats": [
      "Requiere validar con al menos 12 meses de datos históricos",
      "Sample size debe ser >100 clientes para significancia estadística",
      "Factores externos (economía, competencia) no considerados"
    ]
  }},
  "evidence": [
    "Pain point del cliente: 'No sabemos por qué los clientes cancelan'",
    "Prioridad estratégica: Mejorar retention de clientes top a 95%",
    "Industria típicamente tiene correlation entre claims experience y churn"
  ],
  "data_sources_used": ["claims_table", "customer_churn_table", "customer_profiles"],
  "portfolio_type": "medium_term"
}}
```

### Ejemplo 2: Pricing optimization
```json
{{
  "hypothesis_text": "Clientes del sector 'Retail' con volumen >$100K/año tienen elasticidad de precio -0.3, permitiendo aumentos de hasta 15% sin pérdida de volumen",
  "hypothesis_type": "knowledge_driven",
  "category": "pricing",
  "generated_from": "pain_point",
  "actionability": {{
    "if_true_then": "Implementar pricing premium para Retail customers con volumen >$100K: +10% en renovaciones, +15% en nuevos contratos. Piloto con 20 clientes durante Q2.",
    "if_false_then": "Analizar elasticidad por sub-segmento. Considerar value-based pricing en lugar de volume-based.",
    "decision_owner": "CFO",
    "action_threshold": {{
      "min_confidence": 0.75,
      "min_impact_usd": 100000,
      "max_cost_usd": 50000
    }},
    "estimated_impact_usd": 450000
  }},
  "confidence": {{
    "confidence_total": 0.72,
    "confidence_statistical": 0.80,
    "confidence_data_quality": 0.70,
    "confidence_model": 0.65,
    "confidence_caveats": [
      "Elasticidad puede variar por sub-segmento dentro de Retail",
      "Contexto competitivo actual debe verificarse",
      "Requiere análisis de sensibilidad con diferentes thresholds de volumen"
    ]
  }},
  "evidence": [
    "Pain point: 'El pricing es estático y no refleja el riesgo real de cada cliente'",
    "Ortodoxo desafiado: 'Siempre usamos cost-plus pricing'",
    "KPI actual: Margen bruto 28% vs target 35%"
  ],
  "data_sources_used": ["pricing_history", "customer_transactions", "revenue_data"],
  "portfolio_type": "quick_win"
}}
```

## OUTPUT FORMAT

Retorna un JSON array con las hipótesis generadas. Estructura:

```json
[
  {{
    "hypothesis_text": "...",
    "hypothesis_type": "knowledge_driven",
    "category": "pricing" | "churn" | "profitability" | "operations" | "product" | "sales",
    "generated_from": "strategic_priority" | "pain_point" | "kpi_gap" | "orthodoxy",
    "source_orthodoxy_id": "..." (si aplica),
    "actionability": {{ ... }},
    "confidence": {{ ... }},
    "evidence": [...],
    "data_sources_used": [...],
    "portfolio_type": "quick_win" | "medium_term" | "strategic_bet"
  }}
]
```

IMPORTANTE:
- Genera hipótesis DIVERSAS (no todas de la misma categoría)
- Prioriza hipótesis de ALTO IMPACTO relacionadas con prioridades top
- Asegúrate que TODAS incluyan actionability completa
- Sé ESPECÍFICO con números, timeframes, y acciones

Retorna SOLO el JSON, sin texto adicional.
"""


# ============================================================================
# ANOMALY-DRIVEN HYPOTHESIS GENERATION
# ============================================================================

ANOMALY_DRIVEN_PROMPT = """
Eres un analista de datos experto detectando anomalías y patrones ocultos.

Tu tarea es generar HIPÓTESIS ANOMALY-DRIVEN basadas en anomalías detectadas en los datos.

## CONTEXTO DEL CLIENTE

{business_context}

## ANOMALÍAS DETECTADAS

Las siguientes anomalías estadísticas han sido detectadas en los datos:
{anomalies_context}

## INSTRUCCIONES

Genera {max_hypotheses} hipótesis que expliquen o aprovechen las anomalías detectadas.

Cada hipótesis DEBE:

1. EXPLICAR LA ANOMALÍA o sugerir cómo aprovecharla
2. SER TESTEABLE con queries SQL
3. INCLUIR ACTIONABILITY COMPLETA (if_true_then, decision_owner, etc.)
4. INCLUIR CONFIDENCE BREAKDOWN multi-dimensional
5. CUANTIFICAR EL IMPACTO potencial

## TIPOS DE ANOMALÍAS A CONSIDERAR

1. **Outliers**: Valores que se desvían >3 std dev de la media
2. **Sudden changes**: Cambios >30% period-over-period
3. **Unexpected correlations**: Correlaciones >0.7 entre variables no relacionadas
4. **Segmentation anomalies**: Un segmento se comporta muy diferente
5. **Temporal patterns**: Estacionalidad o tendencias inesperadas

## EJEMPLO

```json
{{
  "hypothesis_text": "El segmento 'Manufactura' tiene claim ratio de 85% vs 45% promedio, pero genera 40% de revenue total - están subsidiando otros segmentos",
  "hypothesis_type": "anomaly_driven",
  "category": "profitability",
  "generated_from": "anomaly_detection",
  "source_anomaly_id": "anom_001",
  "actionability": {{
    "if_true_then": "Opción 1: Aumentar pricing para Manufactura +25% gradualmente. Opción 2: Mejorar underwriting process para reducir claim ratio. Opción 3: Renegociar términos con clientes Manufactura top 10.",
    "if_false_then": "Verificar si hay errores en categorización de claims o revenue attribution",
    "decision_owner": "CFO + Chief Underwriting Officer",
    "action_threshold": {{
      "min_confidence": 0.8,
      "min_impact_usd": 200000
    }},
    "estimated_impact_usd": 800000
  }},
  "confidence": {{
    "confidence_total": 0.85,
    "confidence_statistical": 0.92,
    "confidence_data_quality": 0.85,
    "confidence_model": 0.78,
    "confidence_caveats": [
      "Verificar que claim categorization sea consistente",
      "Analizar si hay temporal patterns (ej: Q4 siempre es peor)"
    ]
  }},
  "evidence": [
    "Anomalía: Claim ratio manufactura 85% vs 45% promedio (90% outlier)",
    "Manufactura = 40% revenue pero 65% de claims costs",
    "Pricing no ha sido ajustado en 3 años para este segmento"
  ],
  "data_sources_used": ["claims_summary", "revenue_by_segment", "pricing_history"],
  "portfolio_type": "medium_term",
  "counterfactuals": {{
    "past": {{
      "scenario": "Si hubiéramos ajustado pricing de Manufactura hace 12 meses",
      "metric": "net_margin",
      "actual_value": 8.0,
      "counterfactual_value": 10.5,
      "difference_pct": 31.25,
      "confidence": 0.75
    }},
    "future": {{
      "scenario": "Si NO ajustamos pricing en próximos 6 meses",
      "metric": "net_margin",
      "actual_value": 8.0,
      "counterfactual_value": 6.5,
      "difference_pct": -18.75,
      "confidence": 0.70
    }}
  }}
}}
```

## OUTPUT FORMAT

Retorna JSON array con las hipótesis. SOLO JSON, sin texto adicional.
"""


# ============================================================================
# ORTHODOXY-CHALLENGE HYPOTHESIS GENERATION
# ============================================================================

ORTHODOXY_CHALLENGE_PROMPT = """
Eres un estratega disruptivo que desafía creencias establecidas.

Tu tarea es generar hipótesis que DESAFÍEN los ortodoxos (creencias no cuestionadas) del cliente.

## CONTEXTO DEL CLIENTE

{business_context}

## ORTODOXO A DESAFIAR

{orthodoxy}

**Discovered by**: {discovered_by}
**Confidence**: {confidence}
**Potential for disruption**: {potential_for_disruption}
**Evidence**: {evidence}

## INSTRUCCIONES

Genera {max_hypotheses} hipótesis que desafíen este ortodoxo de formas diferentes.

Cada hipótesis debe:

1. CUESTIONAR DIRECTAMENTE el ortodoxo
2. PROPONER UNA ALTERNATIVA ESPECÍFICA
3. SER TESTEABLE con datos
4. INCLUIR ACTIONABILITY (qué hacer si el ortodoxo es falso)
5. INCLUIR análisis de RIESGO vs REWARD

## FRAMEWORK

Para cada hipótesis, considera:

1. **¿Qué pasaría si el ortodoxo es FALSO?**
   - ¿Qué oportunidades se abren?
   - ¿Qué costos evitamos?

2. **¿Cómo lo probamos con bajo riesgo?**
   - Piloto pequeño
   - A/B test
   - Análisis retrospectivo

3. **¿Quién se beneficia si desafiamos esto?**
   - Cliente final
   - Empresa (revenue, margin, efficiency)
   - Empleados (mejor proceso)

## EJEMPLO

Ortodoxo: "Los clientes B2B siempre pagan más que B2C"

```json
[
  {{
    "hypothesis_text": "Clientes B2C con ticket >$50K tienen mejor payment behavior (98% on-time) y menor cost-to-serve que B2B promedio (92% on-time), sugiriendo que deberíamos priorizar B2C high-value sobre B2B low-value",
    "hypothesis_type": "orthodoxy_challenge",
    "category": "commercial",
    "generated_from": "orthodoxy",
    "source_orthodoxy_id": "orth_b2b_premium",
    "actionability": {{
      "if_true_then": "Lanzar programa piloto de 3 meses targeting B2C customers con potencial >$50K: (1) Crear ofertas premium para B2C, (2) Re-asignar 2 sales reps de B2B low-value a B2C high-value, (3) Medir CAC, LTV, payment behavior",
      "if_false_then": "Confirmar que diferenciación B2B vs B2C es correcta, pero analizar sub-segmentos dentro de cada uno",
      "decision_owner": "VP Sales + CFO",
      "action_threshold": {{
        "min_confidence": 0.65,
        "min_impact_usd": 75000,
        "max_cost_usd": 30000,
        "max_time_months": 3
      }},
      "estimated_impact_usd": 300000
    }},
    "confidence": {{
      "confidence_total": 0.68,
      "confidence_statistical": 0.75,
      "confidence_data_quality": 0.70,
      "confidence_model": 0.60,
      "confidence_caveats": [
        "B2C high-value es un segmento pequeño (5% de base)",
        "Payment behavior puede estar influenciado por payment methods, no tipo de cliente",
        "Piloto pequeño necesario antes de cambio estratégico"
      ]
    }},
    "evidence": [
      "Ortodoxo asume B2B>B2C sin analizar sub-segmentos",
      "Data histórica muestra variation dentro de B2B y B2C",
      "Cost-to-serve B2C es 40% menor (self-service)"
    ],
    "data_sources_used": ["payment_history", "customer_segments", "cost_to_serve"],
    "portfolio_type": "quick_win"
  }},
  {{
    "hypothesis_text": "El ortodoxo 'B2B paga más' ignora customer acquisition cost: CAC de B2B es 3x vs B2C, haciendo que B2C high-volume sea más rentable a 24 meses",
    "hypothesis_type": "orthodoxy_challenge",
    "category": "profitability",
    "generated_from": "orthodoxy",
    "source_orthodoxy_id": "orth_b2b_premium",
    "actionability": {{
      "if_true_then": "Rebalancear marketing budget: reducir B2B acquisition spend -30%, incrementar B2C digital marketing +50%. Medir LTV/CAC ratio por segmento mensualmente.",
      "if_false_then": "Analizar otros factores de rentabilidad: retention rate, upsell potential, referral rate",
      "decision_owner": "CMO + CFO",
      "action_threshold": {{
        "min_confidence": 0.70,
        "min_impact_usd": 100000
      }},
      "estimated_impact_usd": 400000
    }},
    "confidence": {{
      "confidence_total": 0.72,
      "confidence_statistical": 0.80,
      "confidence_data_quality": 0.75,
      "confidence_model": 0.60,
      "confidence_caveats": [
        "CAC calculation debe incluir todos los costos (sales, marketing, onboarding)",
        "Timeframe de 24 meses es assumption, podría variar",
        "Referral rates y upsell potential no están considerados"
      ]
    }},
    "evidence": [
      "B2B CAC promedio: $1,200 vs B2C CAC: $400",
      "B2B deal cycle: 6 meses vs B2C: 2 semanas",
      "B2C retention a 24m: 75% vs B2B: 80% (similar)"
    ],
    "data_sources_used": ["cac_by_segment", "sales_cycle_data", "retention_cohorts"],
    "portfolio_type": "medium_term"
  }}
]
```

## OUTPUT FORMAT

Retorna JSON array con hipótesis. SOLO JSON, sin texto adicional.
"""


# ============================================================================
# DELIVERY SCORE CALCULATION
# ============================================================================

DELIVERY_SCORE_PROMPT = """
Calcula el delivery score para esta hipótesis.

## HIPÓTESIS

{hypothesis_json}

## INSTRUCCIONES

Calcula un delivery score de 0-100 con el siguiente breakdown:

**WEIGHTS**:
- statistical_confidence_score: 25%
- business_impact_score: 30%
- actionability_score: 25%
- strategic_alignment_score: 20%

**CRITERIOS**:

1. **Statistical Confidence Score (0-100)**:
   - confidence_total >= 0.8: 90-100
   - confidence_total >= 0.7: 75-89
   - confidence_total >= 0.6: 60-74
   - confidence_total < 0.6: 0-59

2. **Business Impact Score (0-100)**:
   - estimated_impact_usd >= $500K: 90-100
   - estimated_impact_usd >= $200K: 75-89
   - estimated_impact_usd >= $50K: 60-74
   - estimated_impact_usd < $50K: 0-59

3. **Actionability Score (0-100)**:
   - if_true_then específico y detallado: +50
   - decision_owner claro: +20
   - action_threshold definido: +15
   - estimated_effort y cost presentes: +15

4. **Strategic Alignment Score (0-100)**:
   - Alineado con prioridad top: 90-100
   - Alineado con KPI principal: 75-89
   - Alineado con pain point: 60-74
   - No claramente alineado: 0-59

**THRESHOLD**: delivery_score_total >= 70 → should_deliver = true

## OUTPUT FORMAT

```json
{{
  "delivery_score_breakdown": {{
    "statistical_confidence_score": 85,
    "business_impact_score": 80,
    "actionability_score": 90,
    "strategic_alignment_score": 85,
    "delivery_score_total": 84.5,
    "should_deliver": true
  }},
  "rationale": "Explicación breve de por qué el score es alto/bajo"
}}
```

Retorna SOLO el JSON.
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_knowledge_driven_prompt(
    business_context: str,
    orthodoxies_context: str,
    max_hypotheses: int = 10
) -> str:
    """Construye prompt para knowledge-driven hypothesis generation."""
    return KNOWLEDGE_DRIVEN_PROMPT.format(
        business_context=business_context,
        orthodoxies_context=orthodoxies_context,
        max_hypotheses=max_hypotheses
    )


def build_anomaly_driven_prompt(
    business_context: str,
    anomalies_context: str,
    max_hypotheses: int = 10
) -> str:
    """Construye prompt para anomaly-driven hypothesis generation."""
    return ANOMALY_DRIVEN_PROMPT.format(
        business_context=business_context,
        anomalies_context=anomalies_context,
        max_hypotheses=max_hypotheses
    )


def build_orthodoxy_challenge_prompt(
    business_context: str,
    orthodoxy_dict: Dict[str, Any],
    max_hypotheses: int = 3
) -> str:
    """Construye prompt para orthodoxy-challenge hypothesis generation."""
    return ORTHODOXY_CHALLENGE_PROMPT.format(
        business_context=business_context,
        orthodoxy=orthodoxy_dict.get('orthodoxy', ''),
        discovered_by=orthodoxy_dict.get('discovered_by', ''),
        confidence=orthodoxy_dict.get('confidence', 0.0),
        potential_for_disruption=orthodoxy_dict.get('potential_for_disruption', 'medium'),
        evidence=orthodoxy_dict.get('evidence', ''),
        max_hypotheses=max_hypotheses
    )


def build_delivery_score_prompt(hypothesis_json: str) -> str:
    """Construye prompt para calcular delivery score."""
    return DELIVERY_SCORE_PROMPT.format(
        hypothesis_json=hypothesis_json
    )


def format_orthodoxies_context(orthodoxies: list) -> str:
    """Formatea lista de ortodoxos para contexto del prompt."""
    if not orthodoxies:
        return "No se han detectado ortodoxos aún."

    lines = []
    for i, orth in enumerate(orthodoxies, 1):
        lines.append(f"{i}. **{orth.orthodoxy}**")
        lines.append(f"   - Discovered by: {orth.discovered_by}")
        lines.append(f"   - Confidence: {orth.confidence:.2f}")
        lines.append(f"   - Disruption potential: {orth.potential_for_disruption}")
        lines.append(f"   - Evidence: {orth.evidence}")
        if orth.quote:
            lines.append(f"   - Quote: \"{orth.quote}\"")
        lines.append("")

    return "\n".join(lines)


def format_anomalies_context(anomalies: list) -> str:
    """Formatea lista de anomalías para contexto del prompt."""
    if not anomalies:
        return "No se han detectado anomalías aún. Genera hipótesis basadas en prioridades estratégicas."

    lines = []
    for i, anom in enumerate(anomalies, 1):
        lines.append(f"{i}. **{anom.get('description', 'Anomalía detectada')}**")
        lines.append(f"   - Type: {anom.get('type', 'unknown')}")
        lines.append(f"   - Severity: {anom.get('severity', 'medium')}")
        lines.append(f"   - Metric: {anom.get('metric', 'N/A')}")
        lines.append(f"   - Expected: {anom.get('expected_value', 'N/A')}")
        lines.append(f"   - Actual: {anom.get('actual_value', 'N/A')}")
        lines.append(f"   - Deviation: {anom.get('deviation_pct', 'N/A')}%")
        lines.append("")

    return "\n".join(lines)

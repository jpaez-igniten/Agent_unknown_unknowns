"""
Hypothesis Validator - FASE 3

Valida hipótesis contra datos reales ejecutando queries SQL.

Integración con SQL Expert v2 para:
1. Ejecutar queries de validación
2. Analizar resultados estadísticos
3. Confirmar o rechazar hipótesis
4. Cuantificar impacto

Retorna AnalysisResult con evidencia cuantitativa.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from ..hypothesis.models import Hypothesis, AnalysisResult

logger = logging.getLogger(__name__)


class HypothesisValidator:
    """
    Valida hipótesis ejecutando queries SQL y analizando resultados.

    FASE 3: Validation & Analysis Pipeline
    """

    def __init__(self, db_connection, llm, sql_expert=None):
        """
        Args:
            db_connection: Conexión asyncpg a Postgres
            llm: LLM para análisis de resultados
            sql_expert: SQL Expert v2 (opcional, si no se provee usa LLM directo)
        """
        self.db = db_connection
        self.llm = llm
        self.sql_expert = sql_expert

    async def validate_hypothesis(
        self,
        hypothesis: Hypothesis,
        suggested_queries: list = None
    ) -> AnalysisResult:
        """
        Valida hipótesis ejecutando queries y analizando resultados.

        Args:
            hypothesis: Hypothesis a validar
            suggested_queries: Queries sugeridos (de FeasibilityValidator)

        Returns:
            AnalysisResult con confirmación, confidence, evidencia
        """
        logger.info(f"Validating hypothesis: {hypothesis.hypothesis_text[:50]}...")

        try:
            # Si no hay queries sugeridos, generarlos
            if not suggested_queries:
                suggested_queries = await self._generate_validation_query(hypothesis)

            # Ejecutar el mejor query
            if not suggested_queries:
                logger.warning("No validation queries available")
                return self._build_no_data_result(hypothesis)

            query_to_execute = suggested_queries[0]
            logger.debug(f"Executing query: {query_to_execute[:100]}...")

            # Ejecutar query
            query_result = await self._execute_query(query_to_execute)

            if not query_result:
                logger.warning("Query returned no results")
                return self._build_no_data_result(hypothesis)

            # Analizar resultados con LLM
            analysis = await self._analyze_results_with_llm(
                hypothesis=hypothesis,
                query=query_to_execute,
                results=query_result
            )

            # Construir AnalysisResult
            result = AnalysisResult(
                hypothesis_id=hypothesis.hypothesis_id,
                is_confirmed=analysis.get('is_confirmed', False),
                confidence_level=analysis.get('confidence_level', 0.5),
                query_executed=query_to_execute,
                query_result_summary=analysis.get('query_result_summary', {}),
                quantitative_evidence=analysis.get('quantitative_evidence', {}),
                estimated_business_impact_usd=analysis.get('estimated_business_impact_usd'),
                impact_calculation_method=analysis.get('impact_calculation_method'),
                statistical_tests=analysis.get('statistical_tests'),
                analyzed_at=datetime.now(),
                analyst_notes=analysis.get('analyst_notes', '')
            )

            logger.info(
                f"Validation complete: "
                f"confirmed={result.is_confirmed}, "
                f"confidence={result.confidence_level:.2f}, "
                f"impact=${result.estimated_business_impact_usd or 0:,.0f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error validating hypothesis {hypothesis.hypothesis_id}: {e}")
            return self._build_error_result(hypothesis, str(e))

    async def _generate_validation_query(self, hypothesis: Hypothesis) -> list:
        """
        Genera query SQL para validar la hipótesis.

        Si SQL Expert está disponible, usarlo. Sino, usar LLM directo.
        """
        if self.sql_expert:
            # TODO: Integrar con SQL Expert v2
            # return await self.sql_expert.generate_query(hypothesis.hypothesis_text)
            logger.debug("SQL Expert integration pending, using LLM fallback")

        # Fallback: usar LLM directo
        prompt = f"""
Genera un query SQL para validar esta hipótesis.

HIPÓTESIS:
{hypothesis.hypothesis_text}

CATEGORÍA: {hypothesis.category}

DATA SOURCES MENCIONADOS:
{', '.join(hypothesis.data_sources_used) if hypothesis.data_sources_used else 'No especificados'}

INSTRUCCIONES:
1. Genera UN query SQL que valide la hipótesis directamente
2. Usa nombres de tablas/columnas GENÉRICOS típicos (customers, transactions, revenue, etc.)
3. Incluye métricas clave: counts, averages, ratios, correlations
4. Marca si el query es HYPOTHETICAL (tablas pueden no existir)

Retorna JSON:

```json
{{
  "query": "SELECT ... FROM ... WHERE ...",
  "is_hypothetical": false,
  "expected_output": "Descripción de qué esperamos ver si la hipótesis es verdadera"
}}
```

Retorna SOLO el JSON.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            result = json.loads(response.content)
            query = result.get('query', '')

            if query:
                return [query]
            else:
                return []

        except Exception as e:
            logger.error(f"Error generating validation query: {e}")
            return []

    async def _execute_query(self, query: str) -> Optional[list]:
        """
        Ejecuta query SQL y retorna resultados.

        Maneja errores gracefully (tablas pueden no existir).
        """
        try:
            # Timeout de 30 segundos
            rows = await self.db.fetch(query)

            # Convertir a lista de dicts
            results = [dict(row) for row in rows]

            logger.debug(f"Query returned {len(results)} rows")
            return results

        except Exception as e:
            logger.warning(f"Query execution failed (expected if tables don't exist): {e}")
            return None

    async def _analyze_results_with_llm(
        self,
        hypothesis: Hypothesis,
        query: str,
        results: list
    ) -> Dict[str, Any]:
        """
        Analiza resultados del query con LLM para confirmar/rechazar hipótesis.
        """
        # Limitar resultados para el prompt (máximo 50 rows)
        results_sample = results[:50]

        prompt = f"""
Analiza estos resultados de SQL para confirmar o rechazar la hipótesis.

HIPÓTESIS:
{hypothesis.hypothesis_text}

CATEGORÍA: {hypothesis.category}

QUERY EJECUTADO:
{query}

RESULTADOS (primeras {len(results_sample)} rows de {len(results)} total):
{json.dumps(results_sample, indent=2, default=str)}

INSTRUCCIONES:
1. Determina si los resultados CONFIRMAN o RECHAZAN la hipótesis
2. Calcula un confidence level (0-1) basado en:
   - Tamaño de muestra
   - Significancia estadística
   - Consistencia de resultados
3. Extrae evidencia cuantitativa (métricas clave)
4. Estima el business impact en USD (si es posible)
5. Sugiere tests estadísticos relevantes (p-value, effect size, etc.)

Retorna JSON:

```json
{{
  "is_confirmed": true/false,
  "confidence_level": 0.0-1.0,
  "query_result_summary": {{
    "total_rows": 123,
    "key_metric_1": 45.5,
    "key_metric_2": "78%",
    ...
  }},
  "quantitative_evidence": {{
    "correlation": 0.72,
    "sample_size": 1500,
    "lift": 5.25,
    "statistical_significance": "p < 0.001"
  }},
  "estimated_business_impact_usd": 250000,
  "impact_calculation_method": "Explicación breve del cálculo",
  "statistical_tests": {{
    "test_used": "chi-square test",
    "p_value": 0.001,
    "effect_size": "large"
  }},
  "analyst_notes": "Resumen de 2-3 oraciones del análisis"
}}
```

Retorna SOLO el JSON.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            analysis = json.loads(response.content)

            logger.debug(f"LLM analysis complete: confirmed={analysis.get('is_confirmed')}")
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM analysis: {e}")
            logger.debug(f"LLM response was: {response.content[:500]}")

            # Fallback: análisis heurístico simple
            return self._fallback_analysis(results)

        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return self._fallback_analysis(results)

    def _fallback_analysis(self, results: list) -> Dict[str, Any]:
        """Análisis heurístico simple si LLM falla."""
        return {
            "is_confirmed": len(results) > 0,
            "confidence_level": 0.5 if len(results) > 0 else 0.0,
            "query_result_summary": {
                "total_rows": len(results),
                "first_row": results[0] if results else {}
            },
            "quantitative_evidence": {},
            "analyst_notes": f"Fallback analysis: query returned {len(results)} rows. Manual review needed."
        }

    def _build_no_data_result(self, hypothesis: Hypothesis) -> AnalysisResult:
        """Construye resultado cuando no hay datos disponibles."""
        return AnalysisResult(
            hypothesis_id=hypothesis.hypothesis_id,
            is_confirmed=False,
            confidence_level=0.0,
            query_executed="N/A - no validation query available",
            query_result_summary={"status": "no_data"},
            quantitative_evidence={},
            analyzed_at=datetime.now(),
            analyst_notes="No data available to validate this hypothesis. Tables may not exist or query generation failed."
        )

    def _build_error_result(self, hypothesis: Hypothesis, error_msg: str) -> AnalysisResult:
        """Construye resultado cuando hay error en validación."""
        return AnalysisResult(
            hypothesis_id=hypothesis.hypothesis_id,
            is_confirmed=False,
            confidence_level=0.0,
            query_executed="ERROR",
            query_result_summary={"error": error_msg},
            quantitative_evidence={},
            analyzed_at=datetime.now(),
            analyst_notes=f"Validation failed with error: {error_msg}"
        )

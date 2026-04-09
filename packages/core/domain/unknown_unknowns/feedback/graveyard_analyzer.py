"""
Graveyard Analyzer - FASE 4

Analiza patrones en hypothesis_graveyard para learning loop.

Funciones:
1. Identificar qué tipo de hipótesis son rechazadas frecuentemente
2. Detectar reasons comunes de rechazo
3. Identificar ortodoxos que NO deberían desafiarse
4. Generar recomendaciones para ajustar prompts
5. Evitar regenerar hipótesis similares
6. Calcular success rates por categoría/tipo

LEARNING LOOP: Los insights del graveyard se usan para:
- Ajustar prompts LLM
- Filtrar hipótesis antes de entregarlas
- Mejorar delivery scores
- Personalizar por cliente
"""

import logging
import json
from typing import Dict, Any, List, Optional
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class GraveyardAnalyzer:
    """
    Analiza el hypothesis graveyard para aprendizaje continuo.

    Genera insights sobre:
    - Qué funciona (useful insights)
    - Qué no funciona (rejected insights)
    - Qué evitar (already_tried, politically_impossible)
    - Cómo mejorar (prompt recommendations)
    """

    def __init__(self, db_connection, llm=None):
        """
        Args:
            db_connection: Conexión asyncpg a Postgres
            llm: LLM para análisis semántico (opcional)
        """
        self.db = db_connection
        self.llm = llm

    async def analyze_rejection_patterns(
        self,
        client_id: Optional[str] = None,
        min_samples: int = 5
    ) -> Dict[str, Any]:
        """
        Analiza patrones en hipótesis rechazadas.

        Args:
            client_id: Filtrar por cliente específico (None = todos)
            min_samples: Mínimo de muestras para detectar patrón

        Returns:
            Dict con patrones detectados:
            {
                "total_rejected": 25,
                "rejection_rate": 0.35,
                "common_categories": {...},
                "common_reasons": [...],
                "orthodoxies_to_avoid": [...],
                "recommendations": [...]
            }
        """
        logger.info(f"Analyzing rejection patterns for client {client_id or 'all'}")

        try:
            # Query base
            where_clause = "category IN ('rejected', 'politically_impossible')"
            params = []

            if client_id:
                where_clause += " AND client_id = $1"
                params.append(client_id)

            # Obtener insights rechazados
            query = f"""
                SELECT
                    hypothesis_id,
                    client_id,
                    hypothesis_text,
                    category,
                    rejection_reason,
                    why_impossible,
                    comment,
                    rating,
                    metadata
                FROM hypothesis_graveyard
                WHERE {where_clause}
                ORDER BY feedback_received_at DESC
            """

            results = await self.db.fetch(query, *params)

            if len(results) < min_samples:
                logger.warning(
                    f"Not enough samples for pattern detection: "
                    f"{len(results)} < {min_samples}"
                )
                return {
                    "total_rejected": len(results),
                    "rejection_rate": 0,
                    "message": "Not enough samples for pattern detection"
                }

            # Analizar patrones
            total_rejected = len(results)
            total_insights = await self._get_total_insights_count(client_id)
            rejection_rate = total_rejected / total_insights if total_insights > 0 else 0

            # Agrupar por categoría
            by_category = Counter(r['category'] for r in results)

            # Extraer reasons
            reasons = []
            for row in results:
                reason = (
                    row['rejection_reason'] or
                    row['why_impossible'] or
                    row['comment']
                )
                if reason:
                    reasons.append(reason)

            # Detectar ortodoxos que NO deberían desafiarse
            orthodoxies_to_avoid = await self._detect_untouchable_orthodoxies(results)

            # Generar recomendaciones
            recommendations = await self._generate_recommendations(
                results=results,
                reasons=reasons,
                rejection_rate=rejection_rate
            )

            analysis = {
                "total_rejected": total_rejected,
                "total_insights": total_insights,
                "rejection_rate": round(rejection_rate, 3),
                "by_category": dict(by_category),
                "common_reasons": self._extract_common_reasons(reasons),
                "orthodoxies_to_avoid": orthodoxies_to_avoid,
                "recommendations": recommendations
            }

            logger.info(
                f"Rejection analysis complete: "
                f"{total_rejected} rejected ({rejection_rate:.1%})"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing rejection patterns: {e}")
            return {"error": str(e)}

    async def get_successful_hypothesis_patterns(
        self,
        client_id: Optional[str] = None,
        min_impact_usd: float = 10000
    ) -> Dict[str, Any]:
        """
        Analiza patrones en hipótesis exitosas (useful).

        Args:
            client_id: Filtrar por cliente
            min_impact_usd: Impacto mínimo para considerar

        Returns:
            Dict con patrones de éxito:
            {
                "total_useful": 12,
                "success_rate": 0.45,
                "total_business_impact_usd": 750000,
                "avg_impact_usd": 62500,
                "common_categories": {...},
                "common_characteristics": [...]
            }
        """
        logger.info(f"Analyzing successful patterns for client {client_id or 'all'}")

        try:
            where_clause = "category = 'useful'"
            params = []
            param_idx = 1

            if client_id:
                where_clause += f" AND client_id = ${param_idx}"
                params.append(client_id)
                param_idx += 1

            where_clause += f" AND business_impact_realized_usd >= ${param_idx}"
            params.append(min_impact_usd)

            # Query insights útiles
            query = f"""
                SELECT
                    hypothesis_id,
                    client_id,
                    hypothesis_text,
                    business_impact_realized_usd,
                    rating,
                    comment,
                    metadata
                FROM hypothesis_graveyard
                WHERE {where_clause}
                ORDER BY business_impact_realized_usd DESC
            """

            results = await self.db.fetch(query, *params)

            if not results:
                return {
                    "total_useful": 0,
                    "success_rate": 0,
                    "message": "No successful hypotheses found"
                }

            # Calcular métricas
            total_useful = len(results)
            total_insights = await self._get_total_insights_count(client_id)
            success_rate = total_useful / total_insights if total_insights > 0 else 0

            total_impact = sum(r['business_impact_realized_usd'] for r in results)
            avg_impact = total_impact / total_useful if total_useful > 0 else 0

            # Analizar características comunes
            common_characteristics = await self._extract_common_characteristics(results)

            analysis = {
                "total_useful": total_useful,
                "total_insights": total_insights,
                "success_rate": round(success_rate, 3),
                "total_business_impact_usd": float(total_impact),
                "avg_impact_usd": float(avg_impact),
                "common_characteristics": common_characteristics,
                "top_performers": [
                    {
                        "hypothesis_text": r['hypothesis_text'],
                        "impact_usd": float(r['business_impact_realized_usd']),
                        "rating": r['rating']
                    }
                    for r in results[:5]  # Top 5
                ]
            }

            logger.info(
                f"Success analysis complete: "
                f"{total_useful} useful ({success_rate:.1%}), "
                f"${total_impact:,.0f} total impact"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing successful patterns: {e}")
            return {"error": str(e)}

    async def should_avoid_hypothesis(
        self,
        hypothesis_text: str,
        client_id: str,
        similarity_threshold: float = 0.7
    ) -> Dict[str, bool]:
        """
        Determina si una hipótesis debería evitarse basado en graveyard.

        Args:
            hypothesis_text: Texto de la hipótesis a evaluar
            client_id: ID del cliente
            similarity_threshold: Umbral de similitud (0-1)

        Returns:
            Dict con decisión:
            {
                "should_avoid": True/False,
                "reason": "...",
                "similar_to": "..." (si aplica)
            }
        """
        logger.debug(f"Checking if should avoid hypothesis: {hypothesis_text[:50]}...")

        try:
            # Buscar hipótesis similares en graveyard
            # NOTA: En producción, esto usaría embeddings + vector search
            # Por ahora, búsqueda simple por keywords

            query = """
                SELECT
                    hypothesis_id,
                    hypothesis_text,
                    category,
                    rejection_reason,
                    why_impossible
                FROM hypothesis_graveyard
                WHERE client_id = $1
                  AND category IN ('rejected', 'already_tried', 'politically_impossible')
                ORDER BY feedback_received_at DESC
                LIMIT 50
            """

            results = await self.db.fetch(query, client_id)

            # Buscar similitud simple (keywords)
            hypothesis_keywords = set(hypothesis_text.lower().split())

            for row in results:
                graveyard_keywords = set(row['hypothesis_text'].lower().split())
                overlap = len(hypothesis_keywords & graveyard_keywords)
                total = len(hypothesis_keywords | graveyard_keywords)
                similarity = overlap / total if total > 0 else 0

                if similarity >= similarity_threshold:
                    reason = (
                        row['rejection_reason'] or
                        row['why_impossible'] or
                        f"Similar to previously {row['category']} hypothesis"
                    )

                    logger.debug(
                        f"Found similar hypothesis (similarity={similarity:.2f}): "
                        f"should avoid"
                    )

                    return {
                        "should_avoid": True,
                        "reason": reason,
                        "similar_to": row['hypothesis_text'],
                        "similarity": similarity,
                        "graveyard_category": row['category']
                    }

            logger.debug("No similar hypothesis in graveyard, OK to proceed")

            return {
                "should_avoid": False,
                "reason": "No similar hypothesis found in graveyard"
            }

        except Exception as e:
            logger.error(f"Error checking hypothesis: {e}")
            # En caso de error, no bloquear
            return {
                "should_avoid": False,
                "reason": f"Error checking: {str(e)}"
            }

    async def get_prompt_improvement_suggestions(
        self,
        client_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Genera sugerencias para mejorar prompts LLM basado en graveyard analysis.

        Args:
            client_id: Filtrar por cliente

        Returns:
            Lista de sugerencias:
            [
                {
                    "prompt_section": "knowledge_driven",
                    "suggestion": "Avoid hypotheses about X",
                    "reason": "High rejection rate (75%) for this topic",
                    "priority": "high"
                }
            ]
        """
        logger.info(f"Generating prompt improvement suggestions for client {client_id}")

        suggestions = []

        try:
            # Analizar rechazos
            rejection_analysis = await self.analyze_rejection_patterns(client_id)

            if rejection_analysis.get('rejection_rate', 0) > 0.3:
                suggestions.append({
                    "prompt_section": "general",
                    "suggestion": "Increase specificity and actionability requirements",
                    "reason": f"High rejection rate: {rejection_analysis['rejection_rate']:.1%}",
                    "priority": "high"
                })

            # Analizar éxitos
            success_analysis = await self.get_successful_hypothesis_patterns(client_id)

            if success_analysis.get('success_rate', 0) < 0.2:
                suggestions.append({
                    "prompt_section": "general",
                    "suggestion": "Focus more on quick wins and measurable outcomes",
                    "reason": f"Low success rate: {success_analysis['success_rate']:.1%}",
                    "priority": "high"
                })

            # Ortodoxos intocables
            orthodoxies_to_avoid = rejection_analysis.get('orthodoxies_to_avoid', [])
            if orthodoxies_to_avoid:
                suggestions.append({
                    "prompt_section": "orthodoxy_challenge",
                    "suggestion": f"Avoid challenging these orthodoxies: {', '.join(orthodoxies_to_avoid[:3])}",
                    "reason": "These orthodoxies consistently get rejected or marked as politically impossible",
                    "priority": "medium"
                })

            logger.info(f"Generated {len(suggestions)} prompt improvement suggestions")

            return suggestions

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return []

    # ========== HELPER METHODS ==========

    async def _get_total_insights_count(self, client_id: Optional[str]) -> int:
        """Obtiene total de insights entregados."""
        try:
            where_clause = "TRUE"
            params = []

            if client_id:
                where_clause = "client_id = $1"
                params.append(client_id)

            query = f"""
                SELECT COUNT(*) as total
                FROM hypothesis_graveyard
                WHERE {where_clause}
            """

            result = await self.db.fetchrow(query, *params)
            return result['total']

        except Exception as e:
            logger.error(f"Error getting total count: {e}")
            return 0

    async def _detect_untouchable_orthodoxies(self, rejected_results: list) -> List[str]:
        """
        Detecta ortodoxos que NO deberían desafiarse.

        Identifica ortodoxos que:
        - Siempre son rechazados
        - Marcados como politically_impossible
        - Bajo rating consistente
        """
        untouchable = []

        # Buscar hipótesis ortodoxas rechazadas
        for row in rejected_results:
            if row['category'] == 'politically_impossible':
                # Extraer ortodoxo del hypothesis_text
                # En producción, esto vendría del source_orthodoxy_id
                hypothesis = row['hypothesis_text']
                if "ortodoxo" in hypothesis.lower() or "creencia" in hypothesis.lower():
                    untouchable.append(hypothesis[:100])

        # Deduplicar
        return list(set(untouchable))[:5]  # Top 5

    async def _generate_recommendations(
        self,
        results: list,
        reasons: List[str],
        rejection_rate: float
    ) -> List[str]:
        """Genera recomendaciones basadas en análisis."""
        recommendations = []

        # Alta tasa de rechazo
        if rejection_rate > 0.4:
            recommendations.append(
                "⚠️ High rejection rate detected. Consider increasing feasibility validation threshold."
            )

        # Reasons comunes
        if reasons:
            # Análisis simple de keywords en reasons
            all_reasons_text = " ".join(reasons).lower()

            if "data" in all_reasons_text and "no" in all_reasons_text:
                recommendations.append(
                    "📊 Many rejections mention lack of data. Improve feasibility validation."
                )

            if "cost" in all_reasons_text or "caro" in all_reasons_text:
                recommendations.append(
                    "💰 Cost concerns detected. Focus more on ROI and quick wins."
                )

            if "time" in all_reasons_text or "tiempo" in all_reasons_text:
                recommendations.append(
                    "⏰ Time concerns detected. Prioritize hypotheses with shorter time-to-impact."
                )

        # Bajo número de muestras
        if len(results) < 10:
            recommendations.append(
                "📈 Limited feedback data. Continue collecting more samples for better insights."
            )

        return recommendations

    def _extract_common_reasons(self, reasons: List[str]) -> List[str]:
        """Extrae reasons más comunes."""
        # Contar reasons similares
        reason_counts = Counter(reasons)

        # Top 5
        common = [reason for reason, count in reason_counts.most_common(5)]

        return common

    async def _extract_common_characteristics(self, results: list) -> List[str]:
        """Extrae características comunes de hipótesis exitosas."""
        characteristics = []

        # Análisis simple
        avg_rating = sum(r['rating'] for r in results) / len(results) if results else 0

        if avg_rating >= 4.0:
            characteristics.append("High customer satisfaction (avg rating ≥4.0)")

        # Análisis de hypothesis_text (keywords comunes)
        all_text = " ".join(r['hypothesis_text'].lower() for r in results)

        if "client" in all_text or "customer" in all_text:
            characteristics.append("Customer-centric focus")

        if "revenue" in all_text or "cost" in all_text or "margin" in all_text:
            characteristics.append("Financial impact emphasis")

        if "quick" in all_text or "rápid" in all_text:
            characteristics.append("Quick wins approach")

        return characteristics

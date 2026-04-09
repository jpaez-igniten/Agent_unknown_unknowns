"""
Feedback Collector - FASE 4

Captura y procesa feedback de clientes sobre insights entregados.

Categoriza en Hypothesis Graveyard:
- useful: Cliente lo usó y generó valor
- rejected: Cliente dijo "no sirve"
- already_tried: Cliente ya lo intentó antes
- politically_impossible: Bloqueado por política/cultura

Learning loop para mejorar future runs.
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from ..hypothesis.models import GraveyardCategory

logger = logging.getLogger(__name__)


class FeedbackCollector:
    """
    Recolecta y procesa feedback de clientes sobre insights.

    Responsabilidades:
    1. Capturar feedback (rating, comments, categoría)
    2. Mover insights a hypothesis_graveyard
    3. Registrar business_impact_realized
    4. Generar analytics sobre feedback
    """

    def __init__(self, db_connection):
        """
        Args:
            db_connection: Conexión asyncpg a Postgres
        """
        self.db = db_connection

    async def collect_feedback(
        self,
        insight_id: str,
        client_id: str,
        rating: int,
        category: str,
        comment: Optional[str] = None,
        business_impact_realized_usd: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Captura feedback de un cliente sobre un insight.

        Args:
            insight_id: ID del insight (hypothesis_id)
            client_id: ID del cliente
            rating: Rating 1-5 stars
            category: Categoría del graveyard (useful, rejected, already_tried, politically_impossible)
            comment: Comentario del cliente (opcional)
            business_impact_realized_usd: Impacto en USD si fue útil
            metadata: Metadata adicional

        Returns:
            Dict con resultado:
            {
                "feedback_id": "...",
                "insight_id": "...",
                "graveyard_entry_created": True/False,
                "created_at": "..."
            }
        """
        logger.info(
            f"Collecting feedback for insight {insight_id}: "
            f"rating={rating}, category={category}"
        )

        # Validar rating
        if not 1 <= rating <= 5:
            raise ValueError(f"Rating must be 1-5, got: {rating}")

        # Validar categoría
        try:
            graveyard_category = GraveyardCategory(category)
        except ValueError:
            valid_categories = [c.value for c in GraveyardCategory]
            raise ValueError(
                f"Invalid category: {category}. "
                f"Valid categories: {valid_categories}"
            )

        # Generar feedback_id
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"

        try:
            # Mover a hypothesis_graveyard
            await self._move_to_graveyard(
                hypothesis_id=insight_id,
                client_id=client_id,
                category=graveyard_category,
                rating=rating,
                comment=comment,
                business_impact_realized_usd=business_impact_realized_usd,
                metadata=metadata or {}
            )

            logger.info(
                f"Feedback {feedback_id} collected and moved to graveyard: "
                f"category={category}"
            )

            return {
                "feedback_id": feedback_id,
                "insight_id": insight_id,
                "graveyard_entry_created": True,
                "category": category,
                "rating": rating,
                "created_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error collecting feedback for {insight_id}: {e}")
            raise

    async def _move_to_graveyard(
        self,
        hypothesis_id: str,
        client_id: str,
        category: GraveyardCategory,
        rating: int,
        comment: Optional[str],
        business_impact_realized_usd: Optional[float],
        metadata: Dict[str, Any]
    ):
        """
        Mueve hipótesis al graveyard con categorización.

        Inserta en hypothesis_graveyard table.
        """
        logger.debug(f"Moving {hypothesis_id} to graveyard: category={category.value}")

        # Preparar campos según categoría
        rejection_reason = None
        when_tried = None
        why_failed = None
        context_then_vs_now = None
        why_impossible = None

        if category == GraveyardCategory.REJECTED:
            rejection_reason = comment or "Cliente rechazó sin comentario"

        elif category == GraveyardCategory.ALREADY_TRIED:
            # Parsear del comment si está disponible
            # En producción, estos serían campos separados en el form
            when_tried = metadata.get('when_tried')
            why_failed = metadata.get('why_failed') or comment
            context_then_vs_now = metadata.get('context_then_vs_now')

        elif category == GraveyardCategory.POLITICALLY_IMPOSSIBLE:
            why_impossible = comment or "Bloqueado por razones políticas/culturales"

        # Query para insertar en graveyard
        query = """
            INSERT INTO hypothesis_graveyard (
                hypothesis_id,
                client_id,
                hypothesis_text,
                category,
                rating,
                comment,
                business_impact_realized_usd,
                rejection_reason,
                when_tried,
                why_failed,
                context_then_vs_now,
                why_impossible,
                feedback_received_at,
                metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (hypothesis_id)
            DO UPDATE SET
                category = EXCLUDED.category,
                rating = EXCLUDED.rating,
                comment = EXCLUDED.comment,
                business_impact_realized_usd = EXCLUDED.business_impact_realized_usd,
                rejection_reason = EXCLUDED.rejection_reason,
                when_tried = EXCLUDED.when_tried,
                why_failed = EXCLUDED.why_failed,
                context_then_vs_now = EXCLUDED.context_then_vs_now,
                why_impossible = EXCLUDED.why_impossible,
                feedback_received_at = EXCLUDED.feedback_received_at,
                metadata = EXCLUDED.metadata
        """

        # NOTA: hypothesis_text vendría del insight original
        # Por ahora, usar placeholder
        hypothesis_text = metadata.get('hypothesis_text', 'N/A')

        try:
            await self.db.execute(
                query,
                hypothesis_id,
                client_id,
                hypothesis_text,
                category.value,
                rating,
                comment,
                business_impact_realized_usd,
                rejection_reason,
                when_tried,
                why_failed,
                context_then_vs_now,
                why_impossible,
                datetime.now(),
                None  # metadata JSONB (opcional)
            )

            logger.debug(f"Graveyard entry created for {hypothesis_id}")

        except Exception as e:
            logger.error(f"Error inserting into graveyard: {e}")
            raise

    async def get_feedback_stats(
        self,
        client_id: Optional[str] = None,
        category: Optional[str] = None,
        min_rating: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtiene estadísticas de feedback.

        Args:
            client_id: Filtrar por cliente (opcional)
            category: Filtrar por categoría (opcional)
            min_rating: Rating mínimo (opcional)

        Returns:
            Dict con estadísticas:
            {
                "total_feedback": 100,
                "by_category": {...},
                "avg_rating": 3.8,
                "total_business_impact_usd": 500000,
                "by_client": {...}
            }
        """
        logger.info(f"Getting feedback stats: client={client_id}, category={category}")

        try:
            # Query base
            where_clauses = []
            params = []
            param_idx = 1

            if client_id:
                where_clauses.append(f"client_id = ${param_idx}")
                params.append(client_id)
                param_idx += 1

            if category:
                where_clauses.append(f"category = ${param_idx}")
                params.append(category)
                param_idx += 1

            if min_rating:
                where_clauses.append(f"rating >= ${param_idx}")
                params.append(min_rating)
                param_idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

            # Stats query
            query = f"""
                SELECT
                    COUNT(*) as total_feedback,
                    AVG(rating) as avg_rating,
                    SUM(COALESCE(business_impact_realized_usd, 0)) as total_impact_usd
                FROM hypothesis_graveyard
                WHERE {where_sql}
            """

            result = await self.db.fetchrow(query, *params)

            # By category
            category_query = f"""
                SELECT
                    category,
                    COUNT(*) as count,
                    AVG(rating) as avg_rating
                FROM hypothesis_graveyard
                WHERE {where_sql}
                GROUP BY category
                ORDER BY count DESC
            """

            categories = await self.db.fetch(category_query, *params)
            by_category = {
                row['category']: {
                    'count': row['count'],
                    'avg_rating': float(row['avg_rating']) if row['avg_rating'] else 0
                }
                for row in categories
            }

            stats = {
                "total_feedback": result['total_feedback'],
                "avg_rating": float(result['avg_rating']) if result['avg_rating'] else 0,
                "total_business_impact_usd": float(result['total_impact_usd'] or 0),
                "by_category": by_category
            }

            logger.info(f"Feedback stats: {stats['total_feedback']} total")
            return stats

        except Exception as e:
            logger.error(f"Error getting feedback stats: {e}")
            return {
                "total_feedback": 0,
                "avg_rating": 0,
                "total_business_impact_usd": 0,
                "by_category": {},
                "error": str(e)
            }

    async def get_useful_insights(
        self,
        client_id: Optional[str] = None,
        min_impact_usd: float = 0,
        limit: int = 10
    ) -> list:
        """
        Obtiene insights que fueron útiles (category=useful).

        Args:
            client_id: Filtrar por cliente
            min_impact_usd: Impacto mínimo en USD
            limit: Máximo de resultados

        Returns:
            Lista de insights útiles ordenados por impacto
        """
        logger.info(f"Getting useful insights: client={client_id}, min_impact={min_impact_usd}")

        try:
            where_clauses = ["category = 'useful'"]
            params = []
            param_idx = 1

            if client_id:
                where_clauses.append(f"client_id = ${param_idx}")
                params.append(client_id)
                param_idx += 1

            where_clauses.append(f"business_impact_realized_usd >= ${param_idx}")
            params.append(min_impact_usd)
            param_idx += 1

            where_sql = " AND ".join(where_clauses)

            query = f"""
                SELECT
                    hypothesis_id,
                    client_id,
                    hypothesis_text,
                    business_impact_realized_usd,
                    rating,
                    comment,
                    feedback_received_at
                FROM hypothesis_graveyard
                WHERE {where_sql}
                ORDER BY business_impact_realized_usd DESC
                LIMIT ${param_idx}
            """

            params.append(limit)

            results = await self.db.fetch(query, *params)

            insights = [dict(row) for row in results]

            logger.info(f"Found {len(insights)} useful insights")
            return insights

        except Exception as e:
            logger.error(f"Error getting useful insights: {e}")
            return []

    async def get_rejected_patterns(
        self,
        client_id: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Analiza patrones en insights rechazados.

        Args:
            client_id: Filtrar por cliente
            limit: Máximo de resultados

        Returns:
            Dict con patrones comunes:
            {
                "total_rejected": 15,
                "common_reasons": [...],
                "common_categories": [...],
                "avg_rating": 1.2
            }
        """
        logger.info(f"Analyzing rejected patterns for client {client_id}")

        try:
            where_clause = "category = 'rejected'"
            params = []

            if client_id:
                where_clause += " AND client_id = $1"
                params.append(client_id)

            # Query rechazados
            query = f"""
                SELECT
                    hypothesis_id,
                    hypothesis_text,
                    rejection_reason,
                    comment,
                    rating
                FROM hypothesis_graveyard
                WHERE {where_clause}
                ORDER BY feedback_received_at DESC
                LIMIT {limit}
            """

            results = await self.db.fetch(query, *params)

            # Analizar reasons
            reasons = []
            for row in results:
                reason = row['rejection_reason'] or row['comment']
                if reason:
                    reasons.append(reason)

            patterns = {
                "total_rejected": len(results),
                "common_reasons": reasons[:10],  # Top 10
                "avg_rating": sum(r['rating'] for r in results) / len(results) if results else 0,
                "sample_hypotheses": [
                    {
                        "hypothesis_id": r['hypothesis_id'],
                        "hypothesis_text": r['hypothesis_text'],
                        "reason": r['rejection_reason'] or r['comment']
                    }
                    for r in results[:5]  # Top 5
                ]
            }

            logger.info(f"Found {patterns['total_rejected']} rejected insights")
            return patterns

        except Exception as e:
            logger.error(f"Error analyzing rejected patterns: {e}")
            return {
                "total_rejected": 0,
                "common_reasons": [],
                "avg_rating": 0,
                "error": str(e)
            }

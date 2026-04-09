"""
Unknown Unknowns Orchestrator - FASE 2 + FASE 3

Pipeline completo end-to-end:
1. Carga BusinessProfile
2. Genera hipótesis (FASE 2)
3. Valida viabilidad técnica (FASE 2)
4. Valida contra datos (FASE 3)
5. Calcula delivery scores finales
6. Envía a human review queue
7. Guarda resultados en BD

Este es el componente principal que se expone vía API.
"""

import logging
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from .business_context.profile_repository import BusinessProfileRepository
from .business_context.profile_schema import BusinessProfile
from .hypothesis.generator import HypothesisGenerator
from .hypothesis.feasibility_validator import FeasibilityValidator
from .hypothesis.models import Hypothesis, ValidationResult, AnalysisResult
from .validation.hypothesis_validator import HypothesisValidator

logger = logging.getLogger(__name__)


class UnknownUnknownsOrchestrator:
    """
    Orquesta el pipeline completo de Unknown Unknowns.

    Coordina:
    - ProfileRepository: Carga perfil del cliente
    - HypothesisGenerator: Genera hipótesis con dual approach
    - FeasibilityValidator: Valida viabilidad técnica
    - HypothesisValidator: Valida contra datos
    - Human Review Queue: Primeros 6 meses
    - Database persistence: Guarda runs e insights
    """

    def __init__(
        self,
        profile_repository: BusinessProfileRepository,
        hypothesis_generator: HypothesisGenerator,
        feasibility_validator: FeasibilityValidator,
        hypothesis_validator: HypothesisValidator,
        db_connection
    ):
        """
        Args:
            profile_repository: Repository para cargar perfiles
            hypothesis_generator: Generador de hipótesis
            feasibility_validator: Validador de viabilidad técnica
            hypothesis_validator: Validador contra datos
            db_connection: Conexión asyncpg para persistencia
        """
        self.profile_repo = profile_repository
        self.hypothesis_gen = hypothesis_generator
        self.feasibility_val = feasibility_validator
        self.hypothesis_val = hypothesis_validator
        self.db = db_connection

    async def run_discovery_pipeline(
        self,
        client_id: str,
        max_hypotheses: int = 20,
        min_feasibility_score: float = 0.5,
        enable_human_review: bool = True,
        validate_with_data: bool = True
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de discovery para un cliente.

        Args:
            client_id: ID del cliente
            max_hypotheses: Máximo de hipótesis a generar
            min_feasibility_score: Threshold de feasibility (0-1)
            enable_human_review: Si enviar a human review queue
            validate_with_data: Si validar hipótesis contra datos reales

        Returns:
            Dict con resultados del run:
            {
                "run_id": "...",
                "client_id": "...",
                "total_hypotheses_generated": 20,
                "feasible_hypotheses": 15,
                "validated_hypotheses": 12,
                "deliverable_insights": 8,
                "insights": [...],
                "run_metadata": {...}
            }
        """
        logger.info(f"Starting discovery pipeline for client {client_id}")

        # Generar run_id
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        start_time = datetime.now()

        try:
            # ===== PASO 1: Cargar BusinessProfile =====
            logger.info(f"[{run_id}] STEP 1: Loading BusinessProfile")
            profile = await self.profile_repo.get_profile(client_id)

            if not profile:
                logger.error(f"Profile not found for client {client_id}")
                return self._build_error_result(run_id, client_id, "Profile not found")

            logger.info(
                f"[{run_id}] Profile loaded: {profile.company_name}, "
                f"completeness={profile.profile_completeness:.2%}"
            )

            # ===== PASO 2: Generar Hipótesis =====
            logger.info(f"[{run_id}] STEP 2: Generating hypotheses (max: {max_hypotheses})")
            hypotheses = await self.hypothesis_gen.generate_hypotheses(
                profile=profile,
                run_id=run_id,
                max_hypotheses=max_hypotheses
            )

            logger.info(f"[{run_id}] Generated {len(hypotheses)} hypotheses")

            if not hypotheses:
                logger.warning(f"No hypotheses generated for {client_id}")
                return self._build_empty_result(run_id, client_id, "No hypotheses generated")

            # ===== PASO 3: Validar Viabilidad Técnica =====
            logger.info(f"[{run_id}] STEP 3: Validating technical feasibility")
            feasible_hypotheses = []
            not_feasible_hypotheses = []
            validation_results = {}

            for hypothesis in hypotheses:
                # Convertir a dict para FeasibilityValidator
                hyp_dict = hypothesis.model_dump()

                # Validar feasibility
                validation_result = await self.feasibility_val.validate_hypothesis_feasibility(
                    hypothesis=hyp_dict,
                    client_id=client_id
                )

                validation_results[hypothesis.hypothesis_id] = validation_result

                # Filtrar por feasibility score
                if validation_result.is_feasible and validation_result.feasibility_score >= min_feasibility_score:
                    feasible_hypotheses.append(hypothesis)
                    logger.debug(
                        f"Hypothesis {hypothesis.hypothesis_id} is feasible "
                        f"(score: {validation_result.feasibility_score:.2f})"
                    )
                else:
                    not_feasible_hypotheses.append((hypothesis, validation_result))
                    logger.debug(
                        f"Hypothesis {hypothesis.hypothesis_id} filtered out "
                        f"(feasible: {validation_result.is_feasible}, "
                        f"score: {validation_result.feasibility_score:.2f})"
                    )

            # Guardar hipótesis no factibles en el graveyard para learning loop
            if not_feasible_hypotheses:
                logger.info(f"[{run_id}] Saving {len(not_feasible_hypotheses)} non-feasible hypotheses to graveyard")
                await self._save_not_feasible_to_graveyard(
                    not_feasible_hypotheses=not_feasible_hypotheses,
                    client_id=client_id
                )

            logger.info(
                f"[{run_id}] Feasibility validation complete: "
                f"{len(feasible_hypotheses)}/{len(hypotheses)} feasible"
            )

            if not feasible_hypotheses:
                logger.warning("No feasible hypotheses after validation")
                return await self._save_run_results(
                    run_id=run_id,
                    client_id=client_id,
                    profile=profile,
                    hypotheses=hypotheses,
                    feasible_hypotheses=[],
                    validated_hypotheses=[],
                    deliverable_insights=[],
                    start_time=start_time
                )

            # ===== PASO 4: Validar contra Datos =====
            validated_hypotheses = []
            analysis_results = {}

            if validate_with_data:
                logger.info(f"[{run_id}] STEP 4: Validating against data")

                for hypothesis in feasible_hypotheses:
                    try:
                        # Obtener suggested queries de FeasibilityValidator
                        validation_result = validation_results.get(hypothesis.hypothesis_id)
                        suggested_queries = validation_result.suggested_queries if validation_result else []

                        # Validar contra datos
                        analysis_result = await self.hypothesis_val.validate_hypothesis(
                            hypothesis=hypothesis,
                            suggested_queries=suggested_queries
                        )

                        analysis_results[hypothesis.hypothesis_id] = analysis_result

                        # Agregar a validated si tiene resultados
                        if analysis_result.is_confirmed or analysis_result.confidence_level > 0:
                            validated_hypotheses.append(hypothesis)

                    except Exception as e:
                        logger.error(f"Error validating hypothesis {hypothesis.hypothesis_id}: {e}")
                        continue

                logger.info(
                    f"[{run_id}] Data validation complete: "
                    f"{len(validated_hypotheses)}/{len(feasible_hypotheses)} validated"
                )
            else:
                # Skip data validation
                logger.info(f"[{run_id}] STEP 4: Skipping data validation (disabled)")
                validated_hypotheses = feasible_hypotheses

            # ===== PASO 5: Filtrar por Delivery Score =====
            logger.info(f"[{run_id}] STEP 5: Filtering by delivery score")
            deliverable_insights = [
                h for h in validated_hypotheses
                if h.delivery_score.should_deliver
            ]

            logger.info(
                f"[{run_id}] Delivery score filtering: "
                f"{len(deliverable_insights)}/{len(validated_hypotheses)} deliverable"
            )

            # ===== PASO 6: Human Review Queue =====
            if enable_human_review and deliverable_insights:
                logger.info(f"[{run_id}] STEP 6: Sending to human review queue")
                await self._send_to_human_review_queue(
                    insights=deliverable_insights,
                    run_id=run_id,
                    client_id=client_id
                )
            else:
                logger.info(f"[{run_id}] STEP 6: Skipping human review (disabled or no insights)")

            # ===== PASO 7: Guardar Resultados =====
            logger.info(f"[{run_id}] STEP 7: Saving results to database")
            results = await self._save_run_results(
                run_id=run_id,
                client_id=client_id,
                profile=profile,
                hypotheses=hypotheses,
                feasible_hypotheses=feasible_hypotheses,
                validated_hypotheses=validated_hypotheses,
                deliverable_insights=deliverable_insights,
                validation_results=validation_results,
                analysis_results=analysis_results,
                start_time=start_time
            )

            logger.info(
                f"[{run_id}] Pipeline complete! "
                f"Generated: {len(hypotheses)}, "
                f"Feasible: {len(feasible_hypotheses)}, "
                f"Validated: {len(validated_hypotheses)}, "
                f"Deliverable: {len(deliverable_insights)}"
            )

            return results

        except Exception as e:
            logger.error(f"Error in discovery pipeline for {client_id}: {e}")
            import traceback
            traceback.print_exc()
            return self._build_error_result(run_id, client_id, str(e))

    async def _send_to_human_review_queue(
        self,
        insights: List[Hypothesis],
        run_id: str,
        client_id: str
    ):
        """
        Envía insights a human review queue.

        NOTA: En FASE 4, esto se integraría con sistema de review.
        Por ahora, solo guardamos en la tabla human_review_queue.
        """
        logger.info(f"Sending {len(insights)} insights to human review queue")

        try:
            for insight in insights:
                # Insertar en human_review_queue
                # NOTA: Esto asume que la tabla existe (de migration v2)
                query = """
                    INSERT INTO human_review_queue (
                        insight_id,
                        client_id,
                        queued_at,
                        status
                    ) VALUES ($1, $2, $3, $4)
                """

                # Por ahora usar hypothesis_id como insight_id
                # En producción, esto se mapearía a un insight_id real
                await self.db.execute(
                    query,
                    insight.hypothesis_id,
                    client_id,
                    datetime.now(),
                    'pending'
                )

            logger.info(f"Successfully queued {len(insights)} insights for human review")

        except Exception as e:
            logger.error(f"Error sending to human review queue: {e}")
            # No fallar el pipeline si esto falla
            pass

    async def _save_run_results(
        self,
        run_id: str,
        client_id: str,
        profile: BusinessProfile,
        hypotheses: List[Hypothesis],
        feasible_hypotheses: List[Hypothesis],
        validated_hypotheses: List[Hypothesis],
        deliverable_insights: List[Hypothesis],
        validation_results: Dict[str, ValidationResult] = None,
        analysis_results: Dict[str, AnalysisResult] = None,
        start_time: datetime = None
    ) -> Dict[str, Any]:
        """
        Guarda resultados del run en la base de datos.

        NOTA: En FASE 4, esto guardaría en unknown_unknowns_runs e insights.
        Por ahora, retornar dict con resultados.
        """
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds() if start_time else 0

        logger.info(f"Saving run results for {run_id}")

        # TODO: Guardar en unknown_unknowns_runs table
        # TODO: Guardar cada insight en unknown_unknowns_insights table

        # Por ahora, retornar resultados en memoria
        results = {
            "run_id": run_id,
            "client_id": client_id,
            "company_name": profile.company_name,
            "total_hypotheses_generated": len(hypotheses),
            "feasible_hypotheses": len(feasible_hypotheses),
            "validated_hypotheses": len(validated_hypotheses),
            "deliverable_insights": len(deliverable_insights),
            "duration_seconds": duration_seconds,
            "started_at": start_time.isoformat() if start_time else None,
            "completed_at": end_time.isoformat(),
            "insights": [
                {
                    "hypothesis_id": h.hypothesis_id,
                    "hypothesis_text": h.hypothesis_text,
                    "category": h.category,
                    "portfolio_type": h.portfolio_type.value,
                    "delivery_score": h.delivery_score.delivery_score_total,
                    "should_deliver": h.delivery_score.should_deliver,
                    "actionability": {
                        "if_true_then": h.actionability.if_true_then,
                        "decision_owner": h.actionability.decision_owner,
                        "estimated_impact_usd": h.actionability.estimated_impact_usd
                    },
                    "confidence": {
                        "total": h.confidence.confidence_total,
                        "statistical": h.confidence.confidence_statistical,
                        "data_quality": h.confidence.confidence_data_quality
                    }
                }
                for h in deliverable_insights
            ],
            "run_metadata": {
                "profile_completeness": profile.profile_completeness,
                "strategic_priorities_count": len(profile.strategic_priorities),
                "orthodoxies_detected": len(profile.industry_orthodoxies),
                "kpis_count": len(profile.kpis)
            }
        }

        logger.info(f"Run results prepared for {run_id}")
        return results

    def _build_error_result(
        self,
        run_id: str,
        client_id: str,
        error_msg: str
    ) -> Dict[str, Any]:
        """Construye resultado cuando hay error."""
        return {
            "run_id": run_id,
            "client_id": client_id,
            "status": "error",
            "error": error_msg,
            "total_hypotheses_generated": 0,
            "feasible_hypotheses": 0,
            "validated_hypotheses": 0,
            "deliverable_insights": 0,
            "insights": []
        }

    def _build_empty_result(
        self,
        run_id: str,
        client_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Construye resultado cuando no hay insights."""
        return {
            "run_id": run_id,
            "client_id": client_id,
            "status": "completed",
            "reason": reason,
            "total_hypotheses_generated": 0,
            "feasible_hypotheses": 0,
            "validated_hypotheses": 0,
            "deliverable_insights": 0,
            "insights": []
        }

    async def _save_not_feasible_to_graveyard(
        self,
        not_feasible_hypotheses: list,
        client_id: str
    ):
        """
        Guarda hipótesis no factibles en el graveyard para learning loop.

        Esto permite que el sistema aprenda qué tipo de hipótesis no funcionan
        para este cliente específico (por falta de datos, tablas, etc.)
        """
        logger.info(f"Saving {len(not_feasible_hypotheses)} non-feasible hypotheses to graveyard")

        for hypothesis, validation_result in not_feasible_hypotheses:
            try:
                # Construir rejection reason desde los blockers
                rejection_reason = f"Not feasible (score: {validation_result.feasibility_score:.2f}). "

                if validation_result.blockers:
                    rejection_reason += f"Blockers: {'; '.join(validation_result.blockers[:3])}"

                if validation_result.missing_tables:
                    rejection_reason += f" Missing tables: {', '.join(validation_result.missing_tables[:5])}"

                # Query para insertar en graveyard
                query = """
                    INSERT INTO hypothesis_graveyard (
                        hypothesis_id,
                        client_id,
                        hypothesis_text,
                        category,
                        rejection_reason,
                        rejected_by,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (hypothesis_id) DO UPDATE SET
                        rejection_reason = EXCLUDED.rejection_reason,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                """

                metadata = {
                    "hypothesis_type": hypothesis.hypothesis_type,
                    "portfolio_type": hypothesis.portfolio_type.value,
                    "delivery_score": hypothesis.delivery_score.delivery_score_total,
                    "feasibility_score": validation_result.feasibility_score,
                    "missing_tables": validation_result.missing_tables,
                    "required_tables": validation_result.required_tables,
                    "blockers": validation_result.blockers,
                    "generated_from": hypothesis.generated_from,
                    "category": hypothesis.category
                }

                await self.db.execute(
                    query,
                    hypothesis.hypothesis_id,
                    client_id,
                    hypothesis.hypothesis_text,
                    "rejected",  # Categoría del graveyard
                    rejection_reason,
                    "system_feasibility_validator",  # Rechazado por el sistema
                    json.dumps(metadata)
                )

                logger.debug(f"Saved {hypothesis.hypothesis_id} to graveyard: {rejection_reason[:100]}")

            except Exception as e:
                logger.error(f"Error saving hypothesis {hypothesis.hypothesis_id} to graveyard: {e}")
                # No fallar el pipeline si esto falla
                continue

        logger.info(f"Successfully saved {len(not_feasible_hypotheses)} hypotheses to graveyard for learning loop")

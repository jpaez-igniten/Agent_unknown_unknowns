"""
Pipeline Runner

Orquesta el pipeline completo para todos los clientes activos.
Es invocado por APScheduler cada jueves 11am Colombia.

Flujo por cliente:
    1. Cargar BusinessProfile desde Postgres
    2. Generar hipótesis por plantilla (sin LLM en FASE 1.5)
    3. Crear registro de run en unknown_unknowns_runs
    4. Para cada hipótesis: llamar agent → guardar insight
    5. Finalizar run con métricas

FASE 2: HypothesisTemplate será reemplazado por HypothesisGenerator (Gemini).
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg
from loguru import logger

from config.settings import Settings
from packages.core.domain.unknown_unknowns.business_context.profile_repository import (
    BusinessProfileRepository
)
from packages.core.domain.unknown_unknowns.business_context.profile_schema import (
    BusinessProfile
)
from packages.core.agent_client.client import AgentClient, AgentResponse, AgentClientError


# ============================================================================
# HYPOTHESIS TEMPLATE (FASE 1.5 — Sin LLM)
# ============================================================================

class HypothesisTemplate:
    """
    Generador de hipótesis basado en plantillas de texto.

    FASE 1.5: Sin LLM. Usa pain_points y strategic_priorities del perfil
    directamente para formular preguntas de investigación hacia el agente.

    FASE 2: Será reemplazado por HypothesisGenerator con Gemini Flash.
    """

    # Plantillas para pain points — rotan para dar variedad
    PAIN_POINT_TEMPLATES = [
        (
            "Company context: {context}. "
            "Deep dive investigation on a known pain point: '{pain_point}'. "
            "Find patterns, anomalies, correlations, or root causes in the data "
            "that the client may not be aware of. Quantify the financial impact if possible."
        ),
        (
            "Company context: {context}. "
            "For the pain point '{pain_point}': identify which specific segments, "
            "products, clients, or processes are most affected. What hidden data "
            "correlations exist that could explain or solve this problem?"
        ),
        (
            "Company context: {context}. "
            "The client struggles with: '{pain_point}'. "
            "What unknown patterns in the data could reveal the true root cause? "
            "Look for trends, outliers, or cross-segment correlations they haven't explored."
        ),
    ]

    # Plantillas para prioridades estratégicas
    PRIORITY_TEMPLATES = [
        (
            "Company context: {context}. "
            "Strategic priority: '{priority}'{deadline_str}. "
            "What unknown risks, dependencies, or untapped opportunities in the data "
            "could impact achieving this goal? Find insights the client hasn't considered."
        ),
        (
            "Company context: {context}. "
            "The company wants to: '{priority}'. "
            "Identify the top data-driven actions they should take that they haven't "
            "explored yet. Focus on what's hiding in the data that directly affects "
            "this strategic objective."
        ),
    ]

    @staticmethod
    def generate(
        profile: BusinessProfile,
        max_pain_point: int = 5,
        max_priority: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Genera hipótesis desde el perfil de negocio.

        Args:
            profile: BusinessProfile con pain_points y strategic_priorities
            max_pain_point: Máximo de hipótesis desde pain_points
            max_priority: Máximo de hipótesis desde strategic_priorities

        Returns:
            Lista de dicts con estructura:
                hypothesis_id: str
                hypothesis_text: str (mensaje a enviar al agente)
                business_rationale: str
                pain_point_addressed: str | None
                strategic_priority: str | None
                source: 'pain_point' | 'strategic_priority'
        """
        hypotheses = []

        # Contexto base incluido en todas las hipótesis
        context = (
            f"Company: {profile.company_name} | "
            f"Industry: {profile.industry}"
            + (f" / {profile.industry_sub_segment}" if profile.industry_sub_segment else "")
            + f" | Business model: {profile.business_model}"
            + f" | Revenue model: {profile.revenue_model}"
            + (f" | North star metric: {profile.north_star_metric}" if profile.north_star_metric else "")
        )

        # --- Hipótesis desde pain points ---
        pain_points = profile.known_pain_points[:max_pain_point]
        templates = HypothesisTemplate.PAIN_POINT_TEMPLATES

        for i, pain_point in enumerate(pain_points):
            template = templates[i % len(templates)]
            text = template.format(
                context=context,
                pain_point=pain_point
            )

            hypotheses.append({
                "hypothesis_id": f"pp_{i}_{uuid.uuid4().hex[:8]}",
                "hypothesis_text": text,
                "business_rationale": f"Investigación directa del pain point: '{pain_point}'",
                "pain_point_addressed": pain_point,
                "strategic_priority": None,
                "source": "pain_point"
            })

        # --- Hipótesis desde prioridades estratégicas ---
        priorities = profile.strategic_priorities[:max_priority]
        templates = HypothesisTemplate.PRIORITY_TEMPLATES

        for i, sp in enumerate(priorities):
            template = templates[i % len(templates)]
            deadline_str = f" (deadline: {sp.deadline})" if sp.deadline else ""
            text = template.format(
                context=context,
                priority=sp.priority,
                deadline_str=deadline_str
            )

            hypotheses.append({
                "hypothesis_id": f"prio_{i}_{uuid.uuid4().hex[:8]}",
                "hypothesis_text": text,
                "business_rationale": (
                    f"Alineado con prioridad estratégica: '{sp.priority}'"
                    + (f" — deadline: {sp.deadline}" if sp.deadline else "")
                    + (f" — owner: {sp.owner}" if sp.owner else "")
                ),
                "pain_point_addressed": None,
                "strategic_priority": sp.priority,
                "source": "strategic_priority"
            })

        logger.info(
            f"Generated {len(hypotheses)} hypotheses for {profile.client_id} "
            f"({len(pain_points)} pain_point + {len(priorities)} strategic_priority)"
        )

        return hypotheses


# ============================================================================
# RUN REPOSITORY
# ============================================================================

class RunRepository:
    """
    Maneja la persistencia de runs e insights en Postgres.

    Usa el mismo patrón asyncpg de BusinessProfileRepository:
    async with pool.acquire() as conn: ...
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_active_clients(self) -> List[str]:
        """
        Retorna client_ids activos, ordenados por último run ASC
        (primero los que llevan más tiempo sin analizar).
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT client_id
                FROM business_profiles
                WHERE is_active = TRUE
                  AND insights_enabled = TRUE
                ORDER BY last_hypothesis_run ASC NULLS FIRST
                """
            )
        client_ids = [row["client_id"] for row in rows]
        logger.info(f"Active clients found: {len(client_ids)} → {client_ids}")
        return client_ids

    async def create_run(
        self,
        client_id: str,
        run_type: str,
        max_hypotheses: int
    ) -> int:
        """
        Crea un registro de run y retorna el run_id.

        Args:
            client_id: ID del cliente
            run_type: 'weekly', 'daily', 'monthly', 'ad_hoc'
            max_hypotheses: Número de hipótesis que se van a procesar

        Returns:
            run_id (int)
        """
        async with self.pool.acquire() as conn:
            run_id = await conn.fetchval(
                """
                INSERT INTO unknown_unknowns_runs (
                    client_id,
                    run_type,
                    max_hypotheses,
                    max_insights_to_deliver,
                    started_at,
                    status
                ) VALUES ($1, $2, $3, $4, NOW(), 'running')
                RETURNING run_id
                """,
                client_id,
                run_type,
                max_hypotheses,
                10  # default max insights a entregar
            )

        logger.info(f"Created run {run_id} for client {client_id} (type={run_type})")
        return run_id

    async def save_insight(
        self,
        run_id: int,
        client_id: str,
        hypothesis: Dict[str, Any],
        agent_response: AgentResponse
    ) -> int:
        """
        Guarda un insight en unknown_unknowns_insights.

        Valores hardcodeados para FASE 1.5 (se clasificarán con LLM en FASE 2):
        - insight_type: 'opportunity' (valor válido del CHECK constraint)
        - category: 'other' (valor válido del CHECK constraint)
        - priority: 3 (rango válido: 1-5)

        Returns:
            insight_id (int)
        """
        sql_results = json.dumps({
            "raw_response": agent_response.raw_text,
            "response_time_ms": agent_response.response_time_ms
        })

        metadata = json.dumps({
            "hypothesis_source": hypothesis["source"],
            "pain_point_addressed": hypothesis.get("pain_point_addressed"),
            "strategic_priority": hypothesis.get("strategic_priority"),
            "agent_conversation_id": agent_response.conversation_id,
            "agent_response_time_ms": agent_response.response_time_ms,
            "agent_status_code": agent_response.status_code,
            "generated_at": datetime.now().isoformat()
        })

        async with self.pool.acquire() as conn:
            insight_id = await conn.fetchval(
                """
                INSERT INTO unknown_unknowns_insights (
                    run_id,
                    client_id,
                    hypothesis_id,
                    hypothesis_text,
                    business_rationale,
                    pain_point_addressed,
                    insight_type,
                    category,
                    sql_query,
                    sql_results,
                    analysis,
                    priority,
                    created_at,
                    metadata
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6,
                    'opportunity',
                    'other',
                    'N/A - agent-based analysis',
                    $7::jsonb,
                    $8,
                    3,
                    NOW(),
                    $9::jsonb
                )
                RETURNING insight_id
                """,
                run_id,
                client_id,
                hypothesis["hypothesis_id"],
                hypothesis["hypothesis_text"],
                hypothesis["business_rationale"],
                hypothesis.get("pain_point_addressed"),
                sql_results,
                agent_response.raw_text,   # analysis = respuesta completa del agente
                metadata
            )

        logger.debug(
            f"Saved insight {insight_id} | run={run_id} | client={client_id} | "
            f"hyp={hypothesis['hypothesis_id']} | source={hypothesis['source']}"
        )
        return insight_id

    async def finalize_run(
        self,
        run_id: int,
        hypotheses_generated: int,
        insights_found: int,
        status: str = "completed",
        error_message: Optional[str] = None
    ):
        """
        Actualiza el run con métricas finales.

        Args:
            status: 'completed', 'failed', 'cancelled'
            error_message: Mensaje de error si lo hubo (truncado a 500 chars)
        """
        # Truncar mensaje de error para no romper el límite de la columna
        if error_message and len(error_message) > 500:
            error_message = error_message[:497] + "..."

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE unknown_unknowns_runs
                SET
                    completed_at = NOW(),
                    status = $2,
                    hypotheses_generated = $3,
                    hypotheses_validated = $4,
                    insights_found = $4,
                    insights_delivered = 0,
                    execution_time_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INT,
                    error_message = $5
                WHERE run_id = $1
                """,
                run_id,
                status,
                hypotheses_generated,
                insights_found,
                error_message
            )

        logger.info(
            f"Finalized run {run_id}: status={status} | "
            f"hypotheses={hypotheses_generated} | insights={insights_found}"
        )

    async def update_last_hypothesis_run(self, client_id: str):
        """Actualiza business_profiles.last_hypothesis_run al momento actual."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE business_profiles
                SET last_hypothesis_run = NOW()
                WHERE client_id = $1
                """,
                client_id
            )


# ============================================================================
# PIPELINE RUNNER
# ============================================================================

class PipelineRunner:
    """
    Orquestador principal del pipeline.

    Se inicializa una vez al arrancar el contenedor.
    run_all_clients() es llamado por APScheduler en cada trigger.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: Optional[asyncpg.Pool] = None
        self.profile_repo: Optional[BusinessProfileRepository] = None
        self.run_repo: Optional[RunRepository] = None
        self.agent_client: Optional[AgentClient] = None

    async def initialize(self):
        """
        Crea el pool de Postgres y los clientes.
        Llamado UNA VEZ en el startup de main.py.

        Raises:
            Exception: Si no puede conectar a Postgres
        """
        logger.info("Initializing PipelineRunner...")

        self.pool = await asyncpg.create_pool(
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            database=self.settings.postgres_db,
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
            min_size=self.settings.postgres_pool_min_size,
            max_size=self.settings.postgres_pool_max_size
        )

        logger.info(
            f"Postgres pool created: {self.settings.postgres_host}:"
            f"{self.settings.postgres_port}/{self.settings.postgres_db}"
        )

        # Repository pattern — igual que en FASE 1
        self.profile_repo = BusinessProfileRepository(
            db_pool=self.pool,
            chroma_client=None,      # ChromaDB no necesario para el scheduler
            embedding_function=None
        )

        self.run_repo = RunRepository(self.pool)

        self.agent_client = AgentClient(
            base_url=self.settings.agent_base_url,
            user_id=self.settings.agent_user_id,
            api_key=self.settings.agent_api_key,
            timeout=float(self.settings.agent_timeout_seconds),
            max_retries=self.settings.agent_max_retries,
            retry_delay=self.settings.agent_retry_delay_seconds
        )

        logger.info("PipelineRunner initialized successfully")

    async def shutdown(self):
        """Cierra conexiones limpiamente al parar el contenedor."""
        if self.agent_client:
            await self.agent_client.close()
        if self.pool:
            await self.pool.close()
        logger.info("PipelineRunner shut down cleanly")

    # -------------------------------------------------------------------------
    # ENTRY POINT — llamado por APScheduler
    # -------------------------------------------------------------------------

    async def run_all_clients(self):
        """
        Entry point del cron job.
        Obtiene todos los clientes activos y ejecuta el pipeline para cada uno.
        """
        run_start = datetime.now()
        logger.info("=" * 60)
        logger.info(f"Pipeline run started at {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Obtener clientes activos
        try:
            client_ids = await self.run_repo.get_active_clients()
        except Exception as e:
            logger.error(f"Failed to get active clients: {e}", exc_info=True)
            return

        if not client_ids:
            logger.warning("No active clients found (is_active=TRUE AND insights_enabled=TRUE). Skipping.")
            return

        logger.info(f"Processing {len(client_ids)} client(s)...")

        results = {"success": 0, "failed": 0}

        for client_id in client_ids:
            logger.info(f"▶ Starting pipeline for client: {client_id}")
            try:
                await self.run_client_pipeline(client_id)
                results["success"] += 1
                logger.info(f"✓ Pipeline completed for client: {client_id}")
            except Exception as e:
                results["failed"] += 1
                logger.error(
                    f"✗ Pipeline failed for client {client_id}: {e}",
                    exc_info=True
                )

            # Pequeña pausa entre clientes para no saturar el agente
            if client_id != client_ids[-1]:
                await asyncio.sleep(2)

        elapsed = (datetime.now() - run_start).total_seconds()
        logger.info("=" * 60)
        logger.info(
            f"Pipeline run complete in {elapsed:.1f}s | "
            f"Success: {results['success']} | Failed: {results['failed']}"
        )
        logger.info("=" * 60)

    # -------------------------------------------------------------------------
    # PIPELINE POR CLIENTE
    # -------------------------------------------------------------------------

    async def run_client_pipeline(self, client_id: str):
        """
        Pipeline completo para un cliente individual.

        Pasos:
            1. Cargar BusinessProfile
            2. Generar hipótesis por plantilla
            3. Crear run record
            4. Procesar cada hipótesis: call agent → save insight
            5. Finalizar run
        """
        # 1. Cargar perfil
        profile = await self.profile_repo.get_profile(client_id)
        if not profile:
            logger.error(f"Profile not found for client: {client_id}")
            return

        logger.info(
            f"Loaded profile: {profile.company_name} | "
            f"Industry: {profile.industry} | "
            f"Completeness: {profile.profile_completeness:.0%} | "
            f"Pain points: {len(profile.known_pain_points)} | "
            f"Priorities: {len(profile.strategic_priorities)}"
        )

        # 2. Generar hipótesis
        hypotheses = HypothesisTemplate.generate(
            profile=profile,
            max_pain_point=self.settings.max_pain_point_hypotheses,
            max_priority=self.settings.max_priority_hypotheses
        )

        if not hypotheses:
            logger.warning(
                f"No hypotheses generated for {client_id}. "
                f"Profile needs pain_points or strategic_priorities."
            )
            return

        # 3. Crear run record en Postgres
        run_id = await self.run_repo.create_run(
            client_id=client_id,
            run_type=self.settings.pipeline_run_type,
            max_hypotheses=len(hypotheses)
        )

        # 4. Procesar cada hipótesis
        insights_saved = 0
        errors = []

        for i, hyp in enumerate(hypotheses, 1):
            logger.info(
                f"  [{i}/{len(hypotheses)}] Processing hypothesis {hyp['hypothesis_id']} "
                f"(source: {hyp['source']})"
            )

            try:
                # conversation_id único para que el agente no mezcle contextos
                conversation_id = f"uu_{run_id}_{hyp['hypothesis_id']}"

                # Llamar al agente
                response = await self.agent_client.chat(
                    message_text=hyp["hypothesis_text"],
                    conversation_id=conversation_id
                )

                # Guardar insight en Postgres
                insight_id = await self.run_repo.save_insight(
                    run_id=run_id,
                    client_id=client_id,
                    hypothesis=hyp,
                    agent_response=response
                )

                insights_saved += 1
                logger.info(
                    f"  ✓ Insight {insight_id} saved | "
                    f"{response.response_time_ms}ms | "
                    f"{len(response.raw_text)} chars"
                )

            except AgentClientError as e:
                error_msg = f"Agent error for {hyp['hypothesis_id']}: {e}"
                logger.error(f"  ✗ {error_msg}")
                errors.append(error_msg)
                # Continúa con la siguiente hipótesis
                await asyncio.sleep(1)

            except Exception as e:
                error_msg = f"Unexpected error for {hyp['hypothesis_id']}: {type(e).__name__}: {e}"
                logger.error(f"  ✗ {error_msg}", exc_info=True)
                errors.append(error_msg)
                await asyncio.sleep(1)

        # 5. Finalizar run
        if errors and insights_saved == 0:
            final_status = "failed"
        else:
            final_status = "completed"

        # Limitar mensaje de error para no superar límite de columna
        error_summary = "; ".join(errors[:3]) if errors else None

        await self.run_repo.finalize_run(
            run_id=run_id,
            hypotheses_generated=len(hypotheses),
            insights_found=insights_saved,
            status=final_status,
            error_message=error_summary
        )

        # Actualizar timestamp en business_profiles
        await self.run_repo.update_last_hypothesis_run(client_id)

        logger.info(
            f"Pipeline for {client_id} → "
            f"{insights_saved}/{len(hypotheses)} insights saved | "
            f"run_id={run_id} | status={final_status}"
        )

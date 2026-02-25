"""
Pipeline Routes

Endpoints para trigger manual del pipeline.
Retornan 202 Accepted inmediatamente; el pipeline corre en background.

Endpoints:
    GET  /api/v1/health              → Healthcheck
    POST /api/v1/run/all             → Trigger para todos los clientes activos
    POST /api/v1/run/{client_id}     → Trigger para un cliente específico
"""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from packages.core.scheduler.runner import PipelineRunner

router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class HealthResponse(BaseModel):
    status: str
    mode: str
    postgres: str
    agent_url: str


class RunAllResponse(BaseModel):
    status: str
    message: str
    run_started_at: str
    note: str


class RunClientResponse(BaseModel):
    status: str
    client_id: str
    run_started_at: str
    note: str


class ErrorResponse(BaseModel):
    detail: str


# ============================================================================
# DEPENDENCY
# ============================================================================

def get_runner(request: Request) -> PipelineRunner:
    """Obtiene el PipelineRunner desde el estado de la app (inicializado en lifespan)."""
    runner = getattr(request.app.state, "runner", None)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PipelineRunner no inicializado. Revisar logs de startup."
        )
    return runner


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Healthcheck",
    description="Verifica que la API esté levantada y el PipelineRunner inicializado."
)
async def health(request: Request):
    runner = get_runner(request)
    settings = runner.settings

    return HealthResponse(
        status="ok",
        mode="api",
        postgres=f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
        agent_url=settings.agent_base_url
    )


@router.post(
    "/run/all",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunAllResponse,
    summary="Trigger pipeline para todos los clientes activos",
    description=(
        "Dispara el pipeline de Unknown Unknowns para **todos** los clientes con "
        "`is_active=TRUE` e `insights_enabled=TRUE` en la tabla `business_profiles`.\n\n"
        "La respuesta es inmediata (202 Accepted). El pipeline corre en background. "
        "Seguí los logs con `docker compose logs -f` para ver el progreso.\n\n"
        "Los resultados se guardan en:\n"
        "- `unknown_unknowns_runs` — registro de la ejecución\n"
        "- `unknown_unknowns_insights` — insights generados por el agente"
    )
)
async def run_all(request: Request):
    runner = get_runner(request)
    started_at = datetime.now().isoformat()

    # Lanzar en background — no bloqueamos la respuesta HTTP
    asyncio.create_task(
        _run_all_safe(runner),
        name=f"pipeline_all_{started_at}"
    )

    return RunAllResponse(
        status="started",
        message="Pipeline iniciado para todos los clientes activos",
        run_started_at=started_at,
        note="El pipeline corre en background. Seguí el progreso en los logs del contenedor."
    )


@router.post(
    "/run/{client_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunClientResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Cliente no encontrado"},
        503: {"model": ErrorResponse, "description": "PipelineRunner no disponible"}
    },
    summary="Trigger pipeline para un cliente específico",
    description=(
        "Dispara el pipeline de Unknown Unknowns para **un cliente específico**.\n\n"
        "Primero verifica que el `client_id` exista en `business_profiles`. "
        "Si no existe, retorna 404.\n\n"
        "La respuesta es inmediata (202 Accepted). El pipeline corre en background."
    )
)
async def run_client(client_id: str, request: Request):
    runner = get_runner(request)

    # Verificar que el cliente existe antes de lanzar el background task
    try:
        profile = await runner.profile_repo.get_profile(client_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error consultando Postgres: {e}"
        )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Cliente '{client_id}' no encontrado en business_profiles. "
                f"Tip: Creá el perfil primero con el script de onboarding."
            )
        )

    started_at = datetime.now().isoformat()

    # Lanzar en background
    asyncio.create_task(
        _run_client_safe(runner, client_id),
        name=f"pipeline_{client_id}_{started_at}"
    )

    return RunClientResponse(
        status="started",
        client_id=client_id,
        run_started_at=started_at,
        note=f"Pipeline iniciado para '{profile.company_name}'. Seguí el progreso en los logs."
    )


# ============================================================================
# HELPERS — wrappers con manejo de errores para los background tasks
# ============================================================================

async def _run_all_safe(runner: PipelineRunner):
    """Wrapper con manejo de excepciones para run_all en background."""
    try:
        await runner.run_all_clients()
    except Exception as e:
        # El error no puede propagarse al cliente (ya respondimos 202)
        # Queda logueado para inspección
        from loguru import logger
        logger.error(f"Background task run_all failed: {e}", exc_info=True)


async def _run_client_safe(runner: PipelineRunner, client_id: str):
    """Wrapper con manejo de excepciones para run_client en background."""
    try:
        await runner.run_client_pipeline(client_id)
    except Exception as e:
        from loguru import logger
        logger.error(f"Background task run_client({client_id}) failed: {e}", exc_info=True)

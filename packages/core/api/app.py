"""
FastAPI Application — Unknown Unknowns Agent

Solo activa cuando RUN_MODE=api en el .env.

Modo scheduler (default): APScheduler corre el pipeline cada jueves.
Modo api:                  FastAPI expone endpoints para trigger manual.

Docs interactivas: http://localhost:8080/docs
"""

import sys
import os
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from fastapi import FastAPI
from loguru import logger

from config.settings import get_settings
from packages.core.scheduler.runner import PipelineRunner


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la app.
    Inicializa el PipelineRunner (pool Postgres + AgentClient) al arrancar
    y lo cierra limpiamente al apagar.
    """
    settings = get_settings()
    logger.info("FastAPI starting up — initializing PipelineRunner...")

    runner = PipelineRunner(settings)
    try:
        await runner.initialize()
        app.state.runner = runner
        logger.info(
            f"PipelineRunner ready | "
            f"Postgres: {settings.postgres_host}/{settings.postgres_db} | "
            f"Agent: {settings.agent_base_url}"
        )
    except Exception as e:
        logger.critical(f"Failed to initialize PipelineRunner: {e}")
        logger.critical("Check POSTGRES_* and AGENT_BASE_URL in .env")
        raise

    yield  # La app está corriendo aquí

    logger.info("FastAPI shutting down — closing PipelineRunner...")
    await runner.shutdown()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Unknown Unknowns Agent",
    description=(
        "Trigger manual del pipeline de análisis de Unknown Unknowns.\n\n"
        "**Modo de uso:**\n"
        "- `POST /api/v1/run/all` — Dispara el pipeline para todos los clientes activos\n"
        "- `POST /api/v1/run/{client_id}` — Dispara el pipeline para un cliente específico\n"
        "- `GET /api/v1/health` — Healthcheck\n\n"
        "El pipeline corre en background. Los resultados se guardan en Postgres "
        "(tablas `unknown_unknowns_runs` e `unknown_unknowns_insights`)."
    ),
    version="1.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Registrar routers
from packages.core.api.routes.pipeline import router as pipeline_router
app.include_router(pipeline_router, prefix="/api/v1", tags=["Pipeline"])


@app.get("/", include_in_schema=False)
async def root():
    """Redirect info para la raíz."""
    return {
        "service": "Unknown Unknowns Agent",
        "mode": "api",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

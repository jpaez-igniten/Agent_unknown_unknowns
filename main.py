"""
Unknown Unknowns Agent - Entry Point

Soporta dos modos de ejecución según la variable de entorno RUN_MODE:

  RUN_MODE=scheduler (default)
      APScheduler corre el pipeline cada jueves 11am hora Colombia.
      Sin puertos expuestos. Modo producción.

  RUN_MODE=api
      FastAPI + uvicorn expuesto en API_PORT (default 8080).
      Endpoints para trigger manual del pipeline. Modo testing/desarrollo.

Docker CMD: python main.py
"""

import asyncio
import os
import sys

# Asegurar que el root esté en el path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RUN_MODE = os.getenv("RUN_MODE", "scheduler").lower().strip()


# ============================================================================
# MODO SCHEDULER
# ============================================================================

async def run_scheduler():
    """Inicia el APScheduler con el pipeline semanal."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from loguru import logger

    from config.settings import get_settings
    from packages.core.scheduler.runner import PipelineRunner

    settings = get_settings()
    _setup_logging(settings)

    logger.info("=" * 60)
    logger.info("  Unknown Unknowns Agent")
    logger.info(f"  Mode: SCHEDULER")
    logger.info("=" * 60)
    logger.info(f"Environment  : {settings.environment}")
    logger.info(f"Postgres     : {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"Agent URL    : {settings.agent_base_url}")
    logger.info(f"Agent user   : {settings.agent_user_id}")
    logger.info(
        f"Cron         : every {settings.cron_day_of_week} at "
        f"{settings.cron_hour}:{settings.cron_minute:02d} {settings.cron_timezone}"
    )

    runner = PipelineRunner(settings)
    try:
        await runner.initialize()
    except Exception as e:
        logger.critical(f"Failed to initialize PipelineRunner: {e}")
        logger.critical("Check POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD in .env")
        sys.exit(1)

    scheduler = AsyncIOScheduler(timezone=settings.cron_timezone)

    scheduler.add_job(
        runner.run_all_clients,
        trigger=CronTrigger(
            day_of_week=settings.cron_day_of_week,
            hour=settings.cron_hour,
            minute=settings.cron_minute,
            timezone=settings.cron_timezone
        ),
        id="weekly_pipeline",
        name="Unknown Unknowns Weekly Pipeline",
        misfire_grace_time=3600,  # Tolerar hasta 1h de retraso
        coalesce=True             # Si hubo múltiples runs perdidos, ejecutar solo una vez
    )

    scheduler.start()

    job = scheduler.get_job("weekly_pipeline")
    if job and job.next_run_time:
        logger.info(f"Scheduler started. Next run: {job.next_run_time}")
    else:
        logger.info("Scheduler started.")

    logger.info("=" * 60)

    try:
        heartbeat_count = 0
        while True:
            await asyncio.sleep(3600)
            heartbeat_count += 1
            job = scheduler.get_job("weekly_pipeline")
            next_run = job.next_run_time if job else "unknown"
            logger.info(f"[Heartbeat #{heartbeat_count}] Scheduler running. Next job: {next_run}")

    except (KeyboardInterrupt, SystemExit):
        pass

    finally:
        from loguru import logger as log
        log.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        await runner.shutdown()
        log.info("Unknown Unknowns Agent (scheduler) stopped.")


# ============================================================================
# MODO API
# ============================================================================

def run_api():
    """Inicia FastAPI con uvicorn."""
    import uvicorn
    from loguru import logger
    from config.settings import get_settings

    settings = get_settings()
    _setup_logging(settings)

    logger.info("=" * 60)
    logger.info("  Unknown Unknowns Agent")
    logger.info(f"  Mode: API")
    logger.info("=" * 60)
    logger.info(f"Environment  : {settings.environment}")
    logger.info(f"Postgres     : {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"Agent URL    : {settings.agent_base_url}")
    logger.info(f"Listening on : {settings.api_host}:{settings.api_port}")
    logger.info(f"Docs         : http://localhost:{settings.api_port}/docs")
    logger.info("=" * 60)

    uvicorn.run(
        "packages.core.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
        access_log=True
    )


# ============================================================================
# LOGGING SETUP (compartido entre modos)
# ============================================================================

def _setup_logging(settings):
    """Configura loguru."""
    from loguru import logger

    logger.remove()

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
        colorize=False
    )

    try:
        os.makedirs(os.path.dirname(settings.log_file_path), exist_ok=True)
        logger.add(
            settings.log_file_path,
            level="INFO",
            rotation="100 MB",
            retention="10 days",
            compression="gz",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}"
        )
    except Exception as e:
        logger.warning(f"Could not enable file logging at {settings.log_file_path}: {e}")


# ============================================================================
# ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    if RUN_MODE == "api":
        run_api()
    elif RUN_MODE == "scheduler":
        asyncio.run(run_scheduler())
    else:
        print(f"ERROR: RUN_MODE='{RUN_MODE}' no es válido. Usar 'scheduler' o 'api'.")
        sys.exit(1)

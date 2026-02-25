"""
Unknown Unknowns Agent - Entry Point

Inicia el scheduler APScheduler que ejecuta el pipeline cada jueves
a las 11am hora Colombia (America/Bogota, UTC-5).

NO es un web server. Es un proceso largo que duerme entre ejecuciones.

Docker CMD: python main.py
"""

import asyncio
import sys
import os

# Asegurar que el root esté en el path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config.settings import get_settings
from packages.core.scheduler.runner import PipelineRunner


def setup_logging(settings):
    """Configura loguru para producción."""
    logger.remove()  # Eliminar handler default

    # stdout siempre
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
        colorize=False
    )

    # Archivo (si el directorio es accesible)
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
        logger.info(f"File logging enabled: {settings.log_file_path}")
    except Exception as e:
        logger.warning(f"Could not enable file logging at {settings.log_file_path}: {e}")


async def main():
    settings = get_settings()
    setup_logging(settings)

    logger.info("=" * 60)
    logger.info("  Unknown Unknowns Agent - Starting")
    logger.info("=" * 60)
    logger.info(f"Environment  : {settings.environment}")
    logger.info(f"Postgres     : {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"Agent URL    : {settings.agent_base_url}")
    logger.info(f"Agent user   : {settings.agent_user_id}")
    logger.info(
        f"Cron schedule: every {settings.cron_day_of_week} at "
        f"{settings.cron_hour}:{settings.cron_minute:02d} {settings.cron_timezone}"
    )

    # Inicializar pipeline runner (crea pool de Postgres y cliente HTTP)
    runner = PipelineRunner(settings)
    try:
        await runner.initialize()
    except Exception as e:
        logger.critical(f"Failed to initialize PipelineRunner: {e}")
        logger.critical("Check POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD in .env")
        sys.exit(1)

    # Crear scheduler con asyncio (compatible con await en los jobs)
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
        misfire_grace_time=3600,  # Tolerar hasta 1h de retraso si el contenedor estuvo caído
        coalesce=True             # Si se perdieron N runs, ejecutar solo una vez al volver
    )

    scheduler.start()

    job = scheduler.get_job("weekly_pipeline")
    if job and job.next_run_time:
        logger.info(f"Scheduler started. Next run: {job.next_run_time}")
    else:
        logger.info("Scheduler started.")

    logger.info("=" * 60)

    # Mantener el event loop vivo indefinidamente
    try:
        heartbeat_count = 0
        while True:
            await asyncio.sleep(3600)  # Dormir 1 hora
            heartbeat_count += 1
            job = scheduler.get_job("weekly_pipeline")
            next_run = job.next_run_time if job else "unknown"
            logger.info(f"[Heartbeat #{heartbeat_count}] Scheduler running. Next job: {next_run}")

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received")

    finally:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        await runner.shutdown()
        logger.info("Unknown Unknowns Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())

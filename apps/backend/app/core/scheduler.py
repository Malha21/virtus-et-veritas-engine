import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.services.market_insight_service import fetch_and_store_bestsellers

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def run_market_insight_fetch() -> None:
    with SessionLocal() as db:
        fetch_and_store_bestsellers(db)


def start_scheduler() -> None:
    scheduler.add_job(
        run_market_insight_fetch,
        trigger="interval",
        hours=24,
        id="market_insight_fetch",
        next_run_time=datetime.now(UTC),  # roda uma vez logo na subida, depois a cada 24h
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Agendador iniciado: insights de mercado atualizam a cada 24h.")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)

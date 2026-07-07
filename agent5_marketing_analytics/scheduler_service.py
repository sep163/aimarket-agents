"""Long-running scheduler process for Agent 5: daily ad-metrics sync at 06:00,
weekly report Sundays at 09:00. One systemd service instead of separate cron entries.

Run directly for local testing:
    python -m agent5_marketing_analytics.scheduler_service
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from common.logging_setup import configure_logging

from .sync import run_all as run_daily_sync
from .weekly_report import send_weekly_report

logger = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(run_daily_sync, CronTrigger(hour=6, minute=0), id="daily_sync", misfire_grace_time=3600)
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="sun", hour=9, minute=0),
        id="weekly_report",
        misfire_grace_time=3600,
    )
    return scheduler


async def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started: daily sync at 06:00, weekly report Sundays at 09:00")
    await asyncio.Event().wait()  # keep the process alive


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())

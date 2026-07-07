"""Daily ad-metrics sync for Agent 5: pull yesterday's stats from every
connector and upsert them into ad_metrics_daily.

Run directly for local testing:
    python -m agent5_marketing_analytics.sync

In production this runs inside scheduler_service.py at 06:00 daily.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from common.config import settings
from common.logging_setup import configure_logging

from .connectors import vk_ads, yandex_direct
from .db import apply_schema, get_pool
from .models import AdMetricRow

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO ad_metrics_daily
    (channel, campaign_id, campaign_name, metric_date, spend, clicks, impressions, conversions, cpl, ctr, raw_payload)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (channel, campaign_id, metric_date)
DO UPDATE SET
    campaign_name = EXCLUDED.campaign_name,
    spend = EXCLUDED.spend,
    clicks = EXCLUDED.clicks,
    impressions = EXCLUDED.impressions,
    conversions = EXCLUDED.conversions,
    cpl = EXCLUDED.cpl,
    ctr = EXCLUDED.ctr,
    raw_payload = EXCLUDED.raw_payload,
    synced_at = now();
"""


async def upsert_rows(database_url: str, rows: list[AdMetricRow]) -> None:
    if not rows:
        logger.info("No rows to upsert")
        return
    pool = await get_pool(database_url)
    async with pool.acquire() as conn:
        await conn.executemany(
            UPSERT_SQL,
            [
                (
                    row.channel,
                    row.campaign_id,
                    row.campaign_name,
                    row.metric_date,
                    row.spend,
                    row.clicks,
                    row.impressions,
                    row.conversions,
                    row.cpl,
                    row.ctr,
                    None,  # raw_payload: not populated in this MVP, column reserved for future audit use
                )
                for row in rows
            ],
        )
    logger.info("Upserted %d rows", len(rows))


async def sync_yandex_direct(yesterday: dt.date) -> None:
    rows = await yandex_direct.fetch_daily_stats(settings.yandex_direct_token, yesterday, yesterday)
    await upsert_rows(settings.database_url, rows)


async def sync_vk_ads(yesterday: dt.date) -> None:
    rows = await vk_ads.fetch_daily_stats(settings.vk_ads_token, yesterday, yesterday)
    await upsert_rows(settings.database_url, rows)


async def run_all() -> None:
    await apply_schema(settings.database_url)
    yesterday = dt.date.today() - dt.timedelta(days=1)

    for name, coro in (
        ("yandex_direct", sync_yandex_direct(yesterday)),
        ("vk_ads", sync_vk_ads(yesterday)),
    ):
        try:
            await coro
        except Exception:
            logger.exception("Sync failed for %s", name)


if __name__ == "__main__":
    configure_logging()
    asyncio.run(run_all())

"""VK Ads (ads.vk.com) statistics connector.

Docs: https://ads.vk.com/api/docs
Auth: OAuth2 Bearer token in the Authorization header.
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx

from ..models import AdMetricRow

logger = logging.getLogger(__name__)

STATS_URL = "https://ads.vk.com/api/v2/statistics/ad_plans/day.json"


async def fetch_daily_stats(token: str, date_from: dt.date, date_to: dt.date) -> list[AdMetricRow]:
    """Fetch and normalize ad plan stats for the given date range."""
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "metrics": "all",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(STATS_URL, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
    return normalize(payload)


def normalize(payload: dict) -> list[AdMetricRow]:
    rows: list[AdMetricRow] = []
    for plan in payload.get("items", []):
        plan_id = str(plan.get("id", ""))
        plan_name = plan.get("name", "")
        for row in plan.get("rows", []):
            base = row.get("base", row)
            rows.append(
                AdMetricRow(
                    channel="vk_ads",
                    campaign_id=plan_id,
                    campaign_name=plan_name,
                    metric_date=dt.date.fromisoformat(row["date"]),
                    spend=float(base.get("spent", base.get("spend", 0)) or 0),
                    clicks=int(base.get("clicks", 0) or 0),
                    impressions=int(base.get("shows", base.get("impressions", 0)) or 0),
                    conversions=int(base.get("goals", base.get("conversions", 0)) or 0),
                )
            )
    return rows

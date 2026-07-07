"""Yandex Direct Reports API connector.

Docs: https://yandex.ru/dev/direct/doc/reports/reports.html
The Reports API is asynchronous: it can answer 201/202 while the report is
being built server-side, with a `retryIn` header telling us how long to wait
before asking again.
"""

from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import logging

import httpx

from ..models import AdMetricRow

logger = logging.getLogger(__name__)

REPORTS_URL = "https://api.direct.yandex.com/json/v5/reports"
FIELD_NAMES = ["CampaignId", "CampaignName", "Date", "Impressions", "Clicks", "Cost", "Conversions"]


def _build_report_body(date_from: dt.date, date_to: dt.date) -> dict:
    return {
        "params": {
            "SelectionCriteria": {
                "DateFrom": date_from.isoformat(),
                "DateTo": date_to.isoformat(),
            },
            "FieldNames": FIELD_NAMES,
            "ReportName": f"Agent5DailyReport-{date_from.isoformat()}-{date_to.isoformat()}",
            "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV",
            "IncludeVAT": "YES",
        }
    }


async def fetch_daily_stats(
    token: str,
    date_from: dt.date,
    date_to: dt.date,
    *,
    max_wait_seconds: int = 120,
) -> list[AdMetricRow]:
    """Fetch and normalize campaign stats for the given date range."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
        "processingMode": "auto",
        "returnMoneyInMicros": "false",
        "skipReportHeader": "true",
        "skipReportSummary": "true",
    }
    body = _build_report_body(date_from, date_to)

    waited = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            response = await client.post(REPORTS_URL, json=body, headers=headers)
            if response.status_code == 200:
                return _parse_tsv(response.text)
            if response.status_code in (201, 202):
                retry_after = int(response.headers.get("retryIn", response.headers.get("Retry-After", "5")))
                if waited >= max_wait_seconds:
                    raise TimeoutError("Yandex Direct report was not ready within the time budget")
                logger.info("Report not ready yet, retrying in %ss", retry_after)
                await asyncio.sleep(retry_after)
                waited += retry_after
                continue
            response.raise_for_status()


def _parse_tsv(text: str) -> list[AdMetricRow]:
    """Parse a TSV report body (header row + data rows) into AdMetricRow list.

    skipReportHeader/skipReportSummary=true means the response has no title or
    footer lines, just the tab-separated header followed by data rows.
    """
    reader = csv.DictReader(io.StringIO(text.strip()), delimiter="\t")
    rows: list[AdMetricRow] = []
    for record in reader:
        rows.append(
            AdMetricRow(
                channel="yandex_direct",
                campaign_id=str(record.get("CampaignId", "")),
                campaign_name=record.get("CampaignName", ""),
                metric_date=dt.date.fromisoformat(record["Date"]),
                spend=float(record.get("Cost") or 0),
                clicks=int(record.get("Clicks") or 0),
                impressions=int(record.get("Impressions") or 0),
                conversions=int(record.get("Conversions") or 0),
            )
        )
    return rows

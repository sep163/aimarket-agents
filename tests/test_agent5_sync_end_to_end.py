"""Runs the full daily sync flow (fetch from both connectors -> upsert into
Postgres) with fake connectors and a fake DB - no real DATABASE_URL, no real
Yandex Direct / VK Ads tokens.
"""

import datetime as dt

import pytest

from agent5_marketing_analytics import sync
from agent5_marketing_analytics.models import AdMetricRow
from tests.fakes import FakeConnection, FakePool


@pytest.mark.asyncio
async def test_run_all_without_real_postgres_or_ad_platform_tokens(monkeypatch):
    yesterday = dt.date.today() - dt.timedelta(days=1)
    yandex_rows = [
        AdMetricRow(
            channel="yandex_direct", campaign_id="1", campaign_name="Тест ЯД",
            metric_date=yesterday, spend=1500.5, clicks=50, impressions=1000, conversions=5,
        )
    ]
    vk_rows = [
        AdMetricRow(
            channel="vk_ads", campaign_id="2", campaign_name="Тест VK",
            metric_date=yesterday, spend=800.25, clicks=30, impressions=4000, conversions=3,
        )
    ]

    fake_connection = FakeConnection()
    fake_pool = FakePool(fake_connection)

    async def fake_apply_schema(_database_url):
        return None

    async def fake_get_pool(_database_url):
        return fake_pool

    async def fake_yandex_fetch(*_args, **_kwargs):
        return yandex_rows

    async def fake_vk_fetch(*_args, **_kwargs):
        return vk_rows

    monkeypatch.setattr(sync, "apply_schema", fake_apply_schema)
    monkeypatch.setattr(sync, "get_pool", fake_get_pool)
    monkeypatch.setattr(sync.yandex_direct, "fetch_daily_stats", fake_yandex_fetch)
    monkeypatch.setattr(sync.vk_ads, "fetch_daily_stats", fake_vk_fetch)

    await sync.run_all()

    assert len(fake_connection.executed_many) == 2, "one upsert batch per connector"
    channels_upserted = {row[0] for _query, rows in fake_connection.executed_many for row in rows}
    assert channels_upserted == {"yandex_direct", "vk_ads"}

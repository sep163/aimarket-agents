"""Runs the full weekly report flow (Postgres query -> prompt -> LLM ->
report_log insert) with a fake DB connection and a fake LLM - no real
DATABASE_URL, no real LLM_API_KEY.
"""

import pytest

from agent5_marketing_analytics import weekly_report
from tests.fakes import FakeConnection, FakeLLMClient, FakePool

CHANNEL_ROWS = [
    {
        "channel": "yandex_direct",
        "spend": 12000,
        "prev_spend": 9000,
        "clicks": 400,
        "prev_clicks": 380,
        "conversions": 20,
        "prev_conversions": 30,
        "cpl": 600,
        "prev_cpl": 300,
    }
]
PROBLEM_ROWS = [{"problem_tag": "низкая конверсия рекламы", "cnt": 5}]


@pytest.mark.asyncio
async def test_generate_weekly_summary_without_real_db_or_llm(monkeypatch):
    fake_connection = FakeConnection(fetch_results=[CHANNEL_ROWS, PROBLEM_ROWS])
    fake_pool = FakePool(fake_connection)
    fake_llm = FakeLLMClient(["Сводка: у Яндекс.Директ аномальный рост CPL, стоит проверить кампанию."])

    async def fake_get_pool(_database_url):
        return fake_pool

    monkeypatch.setattr(weekly_report, "get_pool", fake_get_pool)
    monkeypatch.setattr(weekly_report, "build_llm_client", lambda _settings: fake_llm)

    summary = await weekly_report.generate_weekly_summary()

    assert "Сводка" in summary
    assert fake_llm.received_messages, "LLM was actually called with a prompt"
    assert len(fake_connection.executed) == 1, "report_log insert happened exactly once"

    # Sanity check: the prompt actually contains the anomaly-flagged channel data.
    prompt_sent = fake_llm.received_messages[0][-1].content
    assert "yandex_direct" in prompt_sent
    assert "АНОМАЛИЯ" in prompt_sent

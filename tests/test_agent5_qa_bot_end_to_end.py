"""Runs the full Q&A flow (Postgres context -> prompt -> LLM) with a fake DB
connection and a fake LLM - no real DATABASE_URL, no real LLM_API_KEY.
"""

import json

import pytest

from agent5_marketing_analytics import qa_bot
from tests.fakes import FakeConnection, FakeLLMClient, FakePool

CONTEXT_ROW = {
    # ensure_ascii=False mirrors what Postgres actually returns for json_agg:
    # real UTF-8 text, not \uXXXX-escaped.
    "weekly_metrics": json.dumps(
        [{"channel": "yandex_direct", "week_start": "2026-06-29", "spend": 12000, "clicks": 400, "conversions": 20}],
        ensure_ascii=False,
    ),
    "top_problems": json.dumps([{"problem_tag": "низкая конверсия рекламы", "cnt": 5}], ensure_ascii=False),
    "funnel_summary": "[]",
}


@pytest.mark.asyncio
async def test_answer_question_without_real_db_or_llm(monkeypatch):
    fake_connection = FakeConnection(fetchrow_result=CONTEXT_ROW)
    fake_pool = FakePool(fake_connection)
    fake_llm = FakeLLMClient(["Больше всего лидов на этой неделе принёс Яндекс.Директ - 20 конверсий."])

    async def fake_get_pool(_database_url):
        return fake_pool

    monkeypatch.setattr(qa_bot, "get_pool", fake_get_pool)
    monkeypatch.setattr(qa_bot, "build_llm_client", lambda _settings: fake_llm)

    answer = await qa_bot.answer_question("Какой канал привёл больше лидов на этой неделе?")

    assert "Яндекс.Директ" in answer
    assert fake_llm.received_messages, "LLM was actually called with a prompt"

    prompt_sent = fake_llm.received_messages[0][-1].content
    assert "yandex_direct" in prompt_sent
    assert "низкая конверсия рекламы" in prompt_sent

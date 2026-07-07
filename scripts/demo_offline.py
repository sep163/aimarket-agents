"""Run every agent end-to-end with a fake LLM, fake Postgres and a fake
Google Sheet - no Telegram token, no LLM API key, no DATABASE_URL, no ad
platform tokens, no Google credentials.

This is meant to prove the actual business logic works (conversation flow,
lead capture, sync + upsert, anomaly detection, prompt building) before you
plug in any real credentials.

Usage:
    python scripts/demo_offline.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent4_lead_qualifier.conversation import ConversationSession, run_turn
from agent5_marketing_analytics import qa_bot, sync, weekly_report
from agent5_marketing_analytics.models import AdMetricRow
from tests.fakes import FakeConnection, FakeLeadsSheet, FakeLLMClient, FakePool


async def demo_agent4() -> None:
    print("\n=== Агент 4: разговорная квалификация лидов (офлайн) ===")
    scripted_replies = [
        json.dumps(
            {"reply": "Вы сами продаёте или ведёте кабинеты клиентов?", "qualification_complete": False, "lead": {}},
            ensure_ascii=False,
        ),
        json.dumps(
            {"reply": "Какими маркетплейсами пользуетесь?", "qualification_complete": False, "lead": {"role": "селлер"}},
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "reply": "Спасибо, всё записал!",
                "qualification_complete": True,
                "lead": {
                    "role": "селлер",
                    "marketplaces": "Wildberries",
                    "category": "одежда",
                    "experience": "2 года",
                    "turnover": "500000",
                    "team_size": "1",
                    "pain_points": "не хватает денег на продвижение",
                    "contact": "@ivan",
                },
            },
            ensure_ascii=False,
        ),
    ]
    user_messages = [
        "Привет, хочу узнать про рекламу",
        "Я сам продаю",
        "Wildberries, одежда, 2 года, оборот 500000, я один, не хватает денег на продвижение, контакт @ivan",
    ]

    llm = FakeLLMClient(scripted_replies)
    sheets = FakeLeadsSheet()
    session = ConversationSession()

    result = None
    for user_text in user_messages:
        result = await run_turn(llm, session, user_text)
        print(f"  Пользователь: {user_text}")
        print(f"  Бот: {result.reply}")

    if result and result.qualification_complete:
        link = sheets.get_referral_link("telegram")
        sheets.append_lead(channel="telegram", chat_id=1, username="demo_user", lead=result.lead, referral_link=link)
        print(f"  -> Лид записан в таблицу: {sheets.appended_rows[-1]}")


async def demo_agent5_sync() -> None:
    print("\n=== Агент 5: синк Яндекс.Директ + VK Ads (офлайн) ===")
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

    connection = FakeConnection()
    pool = FakePool(connection)

    async def fake_apply_schema(_url):
        return None

    async def fake_get_pool(_url):
        return pool

    async def fake_yandex_fetch(*_args, **_kwargs):
        return yandex_rows

    async def fake_vk_fetch(*_args, **_kwargs):
        return vk_rows

    sync.apply_schema = fake_apply_schema  # type: ignore[assignment]
    sync.get_pool = fake_get_pool  # type: ignore[assignment]
    sync.yandex_direct.fetch_daily_stats = fake_yandex_fetch  # type: ignore[assignment]
    sync.vk_ads.fetch_daily_stats = fake_vk_fetch  # type: ignore[assignment]

    await sync.run_all()
    for _query, rows in connection.executed_many:
        channels = sorted({row[0] for row in rows})
        print(f"  Upsert {len(rows)} строк(и) в ad_metrics_daily, канал(ы): {channels}")


async def demo_agent5_weekly_report() -> None:
    print("\n=== Агент 5: еженедельный отчёт (офлайн) ===")
    channel_rows = [
        {
            "channel": "yandex_direct", "spend": 12000, "prev_spend": 9000,
            "clicks": 400, "prev_clicks": 380,
            "conversions": 20, "prev_conversions": 30,
            "cpl": 600, "prev_cpl": 300,
        }
    ]
    problem_rows = [{"problem_tag": "низкая конверсия рекламы", "cnt": 5}]
    connection = FakeConnection(fetch_results=[channel_rows, problem_rows])
    pool = FakePool(connection)

    async def fake_get_pool(_url):
        return pool

    fake_llm = FakeLLMClient(
        ["На этой неделе Яндекс.Директ показал аномальный рост CPL (+100%) при падении конверсий - стоит проверить настройки кампании."]
    )

    weekly_report.get_pool = fake_get_pool  # type: ignore[assignment]
    weekly_report.build_llm_client = lambda _settings: fake_llm  # type: ignore[assignment]

    summary = await weekly_report.generate_weekly_summary()
    print(f"  {summary}")


async def demo_agent5_qa() -> None:
    print("\n=== Агент 5: Q&A по метрикам в Telegram (офлайн) ===")
    row = {
        "weekly_metrics": json.dumps(
            [{"channel": "yandex_direct", "week_start": "2026-06-29", "spend": 12000, "clicks": 400, "conversions": 20}],
            ensure_ascii=False,
        ),
        "top_problems": json.dumps([{"problem_tag": "низкая конверсия рекламы", "cnt": 5}], ensure_ascii=False),
        "funnel_summary": "[]",
    }
    connection = FakeConnection(fetchrow_result=row)
    pool = FakePool(connection)

    async def fake_get_pool(_url):
        return pool

    fake_llm = FakeLLMClient(["Больше всего лидов на этой неделе принёс Яндекс.Директ - 20 конверсий."])

    qa_bot.get_pool = fake_get_pool  # type: ignore[assignment]
    qa_bot.build_llm_client = lambda _settings: fake_llm  # type: ignore[assignment]

    question = "Какой канал привёл больше лидов на этой неделе?"
    answer = await qa_bot.answer_question(question)
    print(f"  Вопрос: {question}")
    print(f"  Ответ: {answer}")


async def main() -> None:
    await demo_agent4()
    await demo_agent5_sync()
    await demo_agent5_weekly_report()
    await demo_agent5_qa()
    print("\nВсё выполнено без единого реального ключа (Telegram / LLM / Postgres / Google / Яндекс.Директ / VK Ads).")
    print("Когда будете готовы - вставьте реальные ключи в .env и запускайте те же модули как обычно (см. README).")


if __name__ == "__main__":
    asyncio.run(main())

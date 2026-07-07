"""Telegram Q&A bot for Agent 5: the manager asks a question, the bot pulls an
aggregated 8-week metrics context from Postgres and asks the LLM to answer
grounded in that data.

Run directly for local testing:
    python -m agent5_marketing_analytics.qa_bot

MVP simplification: this does not generate SQL on the fly for each question -
it always fetches the same aggregated context (8 weeks of metrics, top 5
feedback problems, 30-day funnel) and asks the LLM to answer from it. For more
flexible ad-hoc queries later, replace this with an agent that has Postgres as
a tool (text-to-SQL).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

from common.config import settings
from common.llm import ChatMessage, build_llm_client
from common.logging_setup import configure_logging

from .db import get_pool

logger = logging.getLogger(__name__)

CONTEXT_SQL = """
WITH weekly AS (
    SELECT channel, date_trunc('week', metric_date)::date AS week_start,
           SUM(spend) AS spend, SUM(clicks) AS clicks, SUM(conversions) AS conversions
    FROM ad_metrics_daily
    WHERE metric_date >= CURRENT_DATE - INTERVAL '56 days'
    GROUP BY channel, week_start
    ORDER BY week_start DESC
),
problems AS (
    SELECT problem_tag, COUNT(*) AS cnt
    FROM client_feedback
    WHERE call_date >= CURRENT_DATE - INTERVAL '60 days'
    GROUP BY problem_tag
    ORDER BY cnt DESC
    LIMIT 5
),
funnel AS (
    SELECT channel, stage, COUNT(*) AS cnt
    FROM crm_funnel
    WHERE stage_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY channel, stage
)
SELECT
    (SELECT json_agg(weekly) FROM weekly) AS weekly_metrics,
    (SELECT json_agg(problems) FROM problems) AS top_problems,
    (SELECT json_agg(funnel) FROM funnel) AS funnel_summary;
"""


def build_prompt(question: str, weekly_metrics: str | None, top_problems: str | None, funnel_summary: str | None) -> str:
    return (
        "Ты аналитик маркетинга. Ответь на вопрос руководителя кратко и по-русски, "
        "опираясь только на данные ниже. Если данных не хватает, так и скажи.\n\n"
        f"Вопрос: {question}\n\n"
        f"Метрики по каналам за 8 недель:\n{weekly_metrics or '[]'}\n\n"
        f"Топ проблем клиентов (60 дней):\n{top_problems or '[]'}\n\n"
        f"Воронка CRM (30 дней):\n{funnel_summary or '[]'}"
    )


async def answer_question(question: str) -> str:
    pool = await get_pool(settings.database_url)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(CONTEXT_SQL)

    prompt = build_prompt(question, row["weekly_metrics"], row["top_problems"], row["funnel_summary"])
    llm = build_llm_client(settings)
    return await llm.chat(
        [
            ChatMessage(
                role="system",
                content="Ты аналитик маркетинга, отвечаешь кратко и по-русски, только на основе предоставленных данных.",
            ),
            ChatMessage(role="user", content=prompt),
        ]
    )


async def main() -> None:
    # Retry loop instead of letting the process crash-exit on a bad/placeholder
    # AGENT5_BOT_TOKEN - see agent4_lead_qualifier.bot.main() for the same pattern.
    while True:
        bot = Bot(token=settings.agent5_bot_token)
        dispatcher = Dispatcher()

        @dispatcher.message(F.text)
        async def on_question(message: Message) -> None:
            try:
                answer = await answer_question(message.text or "")
            except Exception:
                logger.exception("Failed to answer question")
                await message.answer("Не получилось получить ответ, попробуйте ещё раз чуть позже.")
                return
            await message.answer(answer)

        logger.info("Agent 5 Q&A bot starting...")
        try:
            await dispatcher.start_polling(bot)
        except Exception:
            logger.exception(
                "Bot polling stopped (often an invalid or placeholder AGENT5_BOT_TOKEN). Retrying in 30s..."
            )
            await bot.session.close()
            await asyncio.sleep(30)
            continue
        break


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())

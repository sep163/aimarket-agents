"""Weekly marketing summary for Agent 5: metrics vs previous week, anomaly
flags, top client-feedback problems, LLM writeup, sent to the manager on Telegram.

Run directly for local testing:
    python -m agent5_marketing_analytics.weekly_report

In production this runs inside scheduler_service.py, Sundays at 09:00.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from aiogram import Bot

from common.config import settings
from common.llm import ChatMessage, build_llm_client
from common.logging_setup import configure_logging

from .db import get_pool

logger = logging.getLogger(__name__)

ANOMALY_THRESHOLD_PCT = 20.0

METRICS_SQL = """
WITH cur AS (
    SELECT channel, SUM(spend) AS spend, SUM(clicks) AS clicks, SUM(conversions) AS conversions,
           CASE WHEN SUM(conversions) > 0 THEN ROUND(SUM(spend) / SUM(conversions), 2) ELSE NULL END AS cpl
    FROM ad_metrics_daily
    WHERE metric_date BETWEEN CURRENT_DATE - 7 AND CURRENT_DATE - 1
    GROUP BY channel
),
prev AS (
    SELECT channel, SUM(spend) AS spend, SUM(clicks) AS clicks, SUM(conversions) AS conversions,
           CASE WHEN SUM(conversions) > 0 THEN ROUND(SUM(spend) / SUM(conversions), 2) ELSE NULL END AS cpl
    FROM ad_metrics_daily
    WHERE metric_date BETWEEN CURRENT_DATE - 14 AND CURRENT_DATE - 8
    GROUP BY channel
)
SELECT
    COALESCE(cur.channel, prev.channel) AS channel,
    COALESCE(cur.spend, 0) AS spend, COALESCE(prev.spend, 0) AS prev_spend,
    COALESCE(cur.clicks, 0) AS clicks, COALESCE(prev.clicks, 0) AS prev_clicks,
    COALESCE(cur.conversions, 0) AS conversions, COALESCE(prev.conversions, 0) AS prev_conversions,
    cur.cpl AS cpl, prev.cpl AS prev_cpl
FROM cur FULL OUTER JOIN prev ON cur.channel = prev.channel;
"""

FEEDBACK_SQL = """
SELECT problem_tag, COUNT(*) AS cnt
FROM client_feedback
WHERE call_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY problem_tag
ORDER BY cnt DESC
LIMIT 3;
"""


def pct_change(current: float, previous: float) -> float | None:
    """Percent change from `previous` to `current`, or None if there's no baseline."""
    if not previous:
        return None
    return round(((current - previous) / previous) * 100, 1)


def is_anomaly(pct: float | None, *, direction: str = "both") -> bool:
    if pct is None:
        return False
    if direction == "up":
        return pct > ANOMALY_THRESHOLD_PCT
    if direction == "down":
        return pct < -ANOMALY_THRESHOLD_PCT
    return abs(pct) > ANOMALY_THRESHOLD_PCT


def format_channel_line(row: dict) -> str:
    spend_pct = pct_change(row["spend"], row["prev_spend"])
    conversions_pct = pct_change(row["conversions"], row["prev_conversions"])
    cpl_pct = pct_change(row["cpl"], row["prev_cpl"]) if row["cpl"] is not None else None

    anomaly = (
        is_anomaly(spend_pct)
        or is_anomaly(cpl_pct, direction="up")
        or is_anomaly(conversions_pct, direction="down")
    )
    flag = " - АНОМАЛИЯ (больше 20% отклонение)" if anomaly else ""

    return (
        f"{row['channel']}: расход {row['spend']} (было {row['prev_spend']}, {spend_pct}%), "
        f"клики {row['clicks']} (было {row['prev_clicks']}), "
        f"конверсии {row['conversions']} (было {row['prev_conversions']}, {conversions_pct}%), "
        f"CPL {row['cpl']} (было {row['prev_cpl']}, {cpl_pct}%){flag}"
    )


def build_prompt(channel_rows: list[dict], problem_rows: list[dict]) -> str:
    channels_text = (
        "\n".join(format_channel_line(row) for row in channel_rows)
        if channel_rows
        else "Данных по каналам за неделю нет."
    )
    problems_text = (
        "\n".join(f"{i + 1}. {row['problem_tag']} ({row['cnt']} упоминаний)" for i, row in enumerate(problem_rows))
        if problem_rows
        else "Проблем клиентов за последние 30 дней не зафиксировано."
    )

    return (
        "Ты аналитик маркетинга. На основе данных ниже напиши краткую еженедельную сводку "
        "на русском для руководителя: общая динамика по каждому каналу, явные аномалии "
        "(больше 20% отклонение), топ 3 повторяющиеся проблемы клиентов и один два практических вывода. "
        "Пиши компактно, простым текстом с эмодзи для Telegram.\n\n"
        f"Метрики по каналам (эта неделя против прошлой):\n{channels_text}\n\n"
        f"Топ проблемы клиентов (30 дней):\n{problems_text}"
    )


async def generate_weekly_summary() -> str:
    pool = await get_pool(settings.database_url)
    async with pool.acquire() as conn:
        channel_rows = [dict(record) for record in await conn.fetch(METRICS_SQL)]
        problem_rows = [dict(record) for record in await conn.fetch(FEEDBACK_SQL)]

    prompt = build_prompt(channel_rows, problem_rows)
    llm = build_llm_client(settings)
    summary = await llm.chat(
        [
            ChatMessage(role="system", content="Ты аналитик маркетинга, пишешь кратко и по-русски."),
            ChatMessage(role="user", content=prompt),
        ]
    )

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO report_log (report_type, period_start, period_end, telegram_chat_id, content)
               VALUES ($1, $2, $3, $4, $5)""",
            "weekly_summary",
            dt.date.today() - dt.timedelta(days=7),
            dt.date.today() - dt.timedelta(days=1),
            settings.report_chat_id,
            summary,
        )

    return summary


async def send_weekly_report() -> None:
    summary = await generate_weekly_summary()
    bot = Bot(token=settings.agent5_bot_token)
    try:
        await bot.send_message(chat_id=settings.report_chat_id, text=summary)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(send_weekly_report())

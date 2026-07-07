"""Runs a full 6-question qualification conversation through the real
conversation/session logic, with a fake LLM and a fake Google Sheet - no
Telegram token, no LLM API key, no Google credentials needed.
"""

import json

import pytest

from agent4_lead_qualifier.conversation import ConversationSession, run_turn
from tests.fakes import FakeLeadsSheet, FakeLLMClient

SCRIPTED_REPLIES = [
    json.dumps({"reply": "Вы сами продаёте или ведёте кабинеты клиентов?", "qualification_complete": False, "lead": {}}),
    json.dumps({"reply": "Какими маркетплейсами пользуетесь?", "qualification_complete": False, "lead": {"role": "селлер"}}),
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
        }
    ),
]

USER_MESSAGES = [
    "Привет, хочу узнать про рекламу",
    "Я сам продаю",
    "Wildberries, одежда, 2 года, оборот 500000, я один, не хватает денег на продвижение, контакт @ivan",
]


@pytest.mark.asyncio
async def test_full_qualification_conversation_without_any_real_keys():
    llm = FakeLLMClient(SCRIPTED_REPLIES)
    sheets = FakeLeadsSheet()
    session = ConversationSession()

    result = None
    for user_text in USER_MESSAGES:
        result = await run_turn(llm, session, user_text)

    assert result.qualification_complete is True
    assert result.lead.contact == "@ivan"
    assert llm.received_messages, "LLM was actually called"

    # This is exactly what agent4_lead_qualifier.bot.handle_turn does once
    # qualification_complete flips to True.
    referral_link = sheets.get_referral_link("telegram")
    sheets.append_lead(channel="telegram", chat_id=1, username="ivan_seller", lead=result.lead, referral_link=referral_link)

    assert len(sheets.appended_rows) == 1
    row = sheets.appended_rows[0]
    assert row["lead"].marketplaces == "Wildberries"
    assert row["referral_link"] == "https://example.com/ref/test"

"""End-to-end test for the userbot entrypoint (agent4_lead_qualifier/userbot.py)
using a fake Telethon-like event, so the qualification flow can be verified
with zero real Telegram/LLM/Sheets credentials.
"""

from __future__ import annotations

import json

import pytest

from agent4_lead_qualifier import userbot
from tests.fakes import FakeLeadsSheet, FakeLLMClient


class FakeSender:
    def __init__(self, username: str | None) -> None:
        self.username = username


class FakeEvent:
    """Minimal stand-in for a Telethon NewMessage event."""

    def __init__(self, *, sender_id: int, text: str, username: str | None = "seller_ivan") -> None:
        self.sender_id = sender_id
        self.raw_text = text
        self.responses: list[str] = []
        self._username = username

    async def respond(self, text: str) -> None:
        self.responses.append(text)

    async def get_sender(self) -> FakeSender:
        return FakeSender(self._username)


@pytest.mark.asyncio
async def test_userbot_never_sends_first_and_replies_only_on_incoming() -> None:
    """The userbot module has no code path that initiates a conversation -
    handle_incoming only ever runs in reaction to an incoming event, and only
    ever calls event.respond(), never some other "send new message" API."""
    llm = FakeLLMClient(
        [
            json.dumps(
                {
                    "reply": "Вы сами продавец, наёмный менеджер, или оказываете услуги селлерам?",
                    "qualification_complete": False,
                    "lead": {},
                }
            )
        ]
    )
    sheets = FakeLeadsSheet()
    event = FakeEvent(sender_id=555, text="Здравствуйте, увидел ваше сообщение")

    await userbot.handle_incoming(event, llm, sheets)

    assert event.responses == ["Вы сами продавец, наёмный менеджер, или оказываете услуги селлерам?"]
    assert sheets.appended_rows == []


@pytest.mark.asyncio
async def test_userbot_completes_qualification_and_autofills_contact() -> None:
    llm = FakeLLMClient(
        [
            json.dumps(
                {
                    "reply": "Спасибо, все данные собрали.",
                    "qualification_complete": True,
                    "lead": {
                        "role": "селлер",
                        "marketplaces": "Wildberries",
                        "category": "одежда, 2 года",
                        "turnover": "500к/мес",
                        "team_size": "1",
                        "pain_points": "не хватает денег на продвижение",
                        "contact": "",
                    },
                }
            )
        ]
    )
    sheets = FakeLeadsSheet()
    event = FakeEvent(sender_id=777, text="да все ок, все рассказал", username="ivan_seller")

    await userbot.handle_incoming(event, llm, sheets)

    assert len(sheets.appended_rows) == 1
    row = sheets.appended_rows[0]
    assert row["channel"] == "telegram_userbot"
    assert row["chat_id"] == 777
    assert row["lead"].contact == "@ivan_seller"
    assert any("ссылка для регистрации" in text for text in event.responses)

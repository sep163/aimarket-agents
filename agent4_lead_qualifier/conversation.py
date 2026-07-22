"""Conversational lead-qualification logic for Agent 4.

The bot leads the seller through a fixed 6-point script (not free-form small
talk), one question per turn, in short direct messages. The lead arrives here
after replying to an outbound cold message, so the bot never introduces
itself or explains why it's asking, it goes straight into the script. The
model always replies with a strict JSON envelope that this module parses:

    {"reply": "...", "qualification_complete": false, "lead": {...}}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, fields

from common.llm import ChatMessage, LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты ведёшь квалификацию продавца на маркетплейсах строго по скрипту, по одному пункту за раз:
1. Роль: сам селлер, наёмный менеджер, или агентство/специалист, оказывающий услуги селлерам.
2. Какие маркетплейсы использует (Wildberries, Ozon, Яндекс Маркет и т.д.).
3. Чем торгует (одежда или другая товарка) и как давно в этом бизнесе.
4. Примерный оборот.
5. Сколько человек в компании занимается или управляет рекламным кабинетом.
6. Какие сейчас боли: не хватает денег на продвижение, хочет лучше понимать, как работает реклама, или есть проблемы в организации работы команды.

Правила стиля, обязательно соблюдай:
- Никаких вводных фраз и представлений себя или агентства. Собеседник уже ответил на сообщение из рассылки, ты не начинаешь знакомство, а сразу продолжаешь по скрипту.
- Никакой AI-типичной риторики: без "Отлично!", "Конечно!", "Буду рад помочь", восклицательных всплесков и объяснений зачем нужен вопрос.
- Первое сообщение до 20 слов. Каждое следующее сообщение тоже короткое, один вопрос без комментариев.
- Строго по порядку пунктов 1-6, без отклонений и лишних уточнений сверх скрипта. Если пользователь уже ответил на несколько пунктов в одном сообщении, не переспрашивай то, что уже узнал, и переходи к следующему недостающему пункту.

В конце обязательно попроси номер телефона или ник в Telegram для связи (если не даст, можно использовать его текущий Telegram аккаунт).

Как только собраны ВСЕ 6 пунктов и контакт, коротко поблагодари, скажи, что дальше пришлёшь ссылку на регистрацию, и заверши анкету.

Отвечай строго в виде JSON, без markdown-разметки и без текста вне JSON, по схеме:
{"reply": "текст для пользователя в Telegram", "qualification_complete": true или false (true только когда собраны все 6 пунктов и контакт), "lead": {"role": "", "marketplaces": "", "category": "", "experience": "", "turnover": "", "team_size": "", "pain_points": "", "contact": ""}}
Заполняй поля lead по мере получения информации, оставляй пустую строку, если поле ещё неизвестно.
"""


@dataclass
class LeadData:
    role: str = ""
    marketplaces: str = ""
    category: str = ""
    experience: str = ""
    turnover: str = ""
    team_size: str = ""
    pain_points: str = ""
    contact: str = ""


@dataclass
class AgentReply:
    reply: str
    qualification_complete: bool
    lead: LeadData


class ConversationSession:
    """Running chat history for a single Telegram chat.

    This is an in-memory, per-process store - simplest thing that works for a
    single bot instance. If you need the qualification flow to survive a
    restart or scale to multiple processes, swap this for a small SQLite/Redis
    table keyed by chat_id (see README "Upgrade paths").
    """

    def __init__(self) -> None:
        self.history: list[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

    def add_user_message(self, text: str) -> None:
        self.history.append(ChatMessage(role="user", content=text))

    def add_assistant_message(self, raw_json: str) -> None:
        self.history.append(ChatMessage(role="assistant", content=raw_json))


async def run_turn(llm: LLMClient, session: ConversationSession, user_text: str) -> AgentReply:
    """Advance the conversation by one turn: send history + new message to the
    LLM, parse its JSON reply, and record it back into the session history."""
    session.add_user_message(user_text)
    raw = await llm.chat(session.history, temperature=0.4)
    session.add_assistant_message(raw)
    return parse_agent_json(raw)


def parse_agent_json(raw: str) -> AgentReply:
    """Parse the model's JSON reply, tolerating stray markdown code fences.

    Falls back to treating the raw text as a plain reply (qualification not
    complete) if the model didn't return valid JSON, so a single malformed
    turn never crashes the conversation.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON reply, using it as plain text: %r", raw)
        return AgentReply(reply=raw.strip(), qualification_complete=False, lead=LeadData())

    lead_dict = data.get("lead") or {}
    known_fields = {f.name for f in fields(LeadData)}
    lead = LeadData(**{key: str(lead_dict.get(key, "") or "") for key in known_fields})

    return AgentReply(
        reply=str(data.get("reply", "")),
        qualification_complete=bool(data.get("qualification_complete", False)),
        lead=lead,
    )

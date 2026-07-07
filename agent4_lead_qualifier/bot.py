"""Entrypoint for Agent 4: Telegram lead-qualification bot.

Run directly for local testing:
    python -m agent4_lead_qualifier.bot

In production this is what the aimarket-agent4-bot systemd unit runs.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from common.config import settings
from common.llm import LLMClient, build_llm_client
from common.logging_setup import configure_logging

from .conversation import ConversationSession, run_turn
from .sheets import LeadsSheet

logger = logging.getLogger(__name__)

CHANNEL = "telegram"

# In-memory session store keyed by chat_id - see ConversationSession docstring
# for the tradeoff and the upgrade path to persistent storage.
_sessions: dict[int, ConversationSession] = {}


async def handle_turn(message: Message, llm: LLMClient, sheets: LeadsSheet) -> None:
    chat_id = message.chat.id
    session = _sessions.setdefault(chat_id, ConversationSession())
    user_text = message.text or ""

    try:
        result = await run_turn(llm, session, user_text)
    except Exception:
        logger.exception("LLM turn failed for chat_id=%s", chat_id)
        await message.answer("Извините, что-то пошло не так. Попробуйте написать ещё раз чуть позже.")
        return

    if result.reply:
        await message.answer(result.reply)

    if result.qualification_complete:
        username = message.from_user.username if message.from_user else ""
        # Auto-fill contact from the Telegram handle if the model forgot to
        # collect one - the system prompt asks it to do this, but we don't
        # want a blank "contact" cell in Sheets to depend solely on the LLM
        # following instructions.
        lead = result.lead
        if not lead.contact:
            lead.contact = f"@{username}" if username else f"tg_id:{chat_id}"

        try:
            referral_link = await asyncio.to_thread(sheets.get_referral_link, CHANNEL)
            await asyncio.to_thread(
                sheets.append_lead,
                channel=CHANNEL,
                chat_id=chat_id,
                username=username or "",
                lead=lead,
                referral_link=referral_link,
            )
        except Exception:
            # A Sheets API blip must not strand the user mid-conversation:
            # keep the session alive (don't pop it) so the next message
            # retries this same qualification-complete branch instead of
            # silently losing the lead.
            logger.exception("Failed to record lead to Google Sheets for chat_id=%s", chat_id)
            await message.answer(
                "Спасибо! Почти всё готово, но не получилось сохранить данные - "
                "попробуйте, пожалуйста, написать что-нибудь ещё раз через минуту."
            )
            return

        await message.answer(f"Спасибо! Все данные записали.\nВот ссылка для регистрации: {referral_link}")
        _sessions.pop(chat_id, None)


async def main() -> None:
    configure_logging()
    llm = build_llm_client(settings)
    sheets = LeadsSheet(settings.google_service_account_file, settings.google_sheet_id)

    # Retry loop instead of letting the process crash-exit on a bad/placeholder
    # AGENT4_BOT_TOKEN. This matters right after a fresh deploy with stub
    # secrets: the systemd unit stays up and simply waits, logging one clear
    # line every 30s, instead of crash-looping and spamming journalctl.
    while True:
        bot = Bot(token=settings.agent4_bot_token)
        dispatcher = Dispatcher()

        @dispatcher.message(CommandStart())
        async def on_start(message: Message) -> None:
            _sessions.pop(message.chat.id, None)
            await handle_turn(message, llm, sheets)

        @dispatcher.message(F.text)
        async def on_text(message: Message) -> None:
            await handle_turn(message, llm, sheets)

        logger.info("Agent 4 (lead qualifier) bot starting...")
        try:
            await dispatcher.start_polling(bot)
        except Exception:
            logger.exception(
                "Bot polling stopped (often an invalid or placeholder AGENT4_BOT_TOKEN). Retrying in 30s..."
            )
            await bot.session.close()
            await asyncio.sleep(30)
            continue
        break


if __name__ == "__main__":
    asyncio.run(main())

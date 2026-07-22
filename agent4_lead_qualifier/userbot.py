"""Userbot entrypoint for Agent 4: runs the qualification script inside a
personal Telegram account's own DMs, instead of a separate official bot.

This is for the scenario where a real person manually sends the first cold
message from their own account (a normal, reasonable volume - not a mass
automated mailing), and once the seller replies, this process takes over the
conversation with the same qualification logic as agent4_lead_qualifier/bot.py.

Hard rule: this client NEVER sends the first message in a chat. It only
reacts to incoming private messages. If you want it to also handle group
chats or send unsolicited first messages, that's a different (and much
riskier) use case that this module deliberately does not support.

First-time setup (must be run once, interactively, from a real terminal):
    1. Get api_id / api_hash for your own account at https://my.telegram.org
       (Api development tools - create an app, any name is fine).
    2. Put them in .env as TELEGRAM_API_ID / TELEGRAM_API_HASH.
    3. Run:  python -m agent4_lead_qualifier.userbot
       Telethon will ask for your phone number, then the login code Telegram
       sends you, then (if enabled) your 2FA password. This creates a local
       session file (TELEGRAM_SESSION_NAME + ".session") next to the project.
    4. After that first interactive login, the session file is reused and
       the same command can run unattended under systemd
       (see systemd/aimarket-agent4-userbot.service).

The session file is your logged-in account - treat it like a password.
It's git-ignored (see .gitignore: *.session) and must never be committed or
shared.
"""

from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, events

from common.config import settings
from common.llm import LLMClient, build_llm_client
from common.logging_setup import configure_logging

from .conversation import ConversationSession, run_turn
from .sheets import LeadsSheet

logger = logging.getLogger(__name__)

CHANNEL = "telegram_userbot"

# In-memory session store keyed by the other user's Telegram id - same
# tradeoff as agent4_lead_qualifier/bot.py (see ConversationSession docstring).
_sessions: dict[int, ConversationSession] = {}


async def handle_incoming(event, llm: LLMClient, sheets: LeadsSheet) -> None:
    peer_id = event.sender_id
    user_text = event.raw_text or ""

    session = _sessions.setdefault(peer_id, ConversationSession())

    try:
        result = await run_turn(llm, session, user_text)
    except Exception:
        logger.exception("LLM turn failed for peer_id=%s", peer_id)
        await event.respond("Извините, что-то пошло не так. Попробуйте написать ещё раз чуть позже.")
        return

    if result.reply:
        await event.respond(result.reply)

    if result.qualification_complete:
        sender = await event.get_sender()
        username = getattr(sender, "username", None) or ""

        lead = result.lead
        if not lead.contact:
            lead.contact = f"@{username}" if username else f"tg_id:{peer_id}"

        try:
            referral_link = await asyncio.to_thread(sheets.get_referral_link, CHANNEL)
            await asyncio.to_thread(
                sheets.append_lead,
                channel=CHANNEL,
                chat_id=peer_id,
                username=username,
                lead=lead,
                referral_link=referral_link,
            )
        except Exception:
            logger.exception("Failed to record lead to Google Sheets for peer_id=%s", peer_id)
            await event.respond(
                "Спасибо! Почти всё готово, но не получилось сохранить данные - "
                "попробуйте, пожалуйста, написать что-нибудь ещё раз через минуту."
            )
            return

        await event.respond(f"Спасибо! Все данные записали.\nВот ссылка для регистрации: {referral_link}")
        _sessions.pop(peer_id, None)


async def main() -> None:
    configure_logging()

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise SystemExit(
            "TELEGRAM_API_ID / TELEGRAM_API_HASH не заданы. Получите их на https://my.telegram.org "
            "и добавьте в .env перед первым запуском."
        )

    llm = build_llm_client(settings)
    sheets = LeadsSheet(settings.google_service_account_file, settings.google_sheet_id)

    client = TelegramClient(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def _on_message(event):
        await handle_incoming(event, llm, sheets)

    logger.info("Agent 4 userbot starting (private-message replies only, never sends first)...")
    await client.start()  # interactive on first run only; reuses the session file afterwards
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

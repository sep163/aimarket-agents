"""Central configuration for all aimarket agents, loaded from environment variables / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    # Telegram (official Bot API - used by agent4_lead_qualifier/bot.py and Agent 5)
    agent4_bot_token: str = ""
    agent5_bot_token: str = ""

    # Telegram userbot mode for Agent 4 (agent4_lead_qualifier/userbot.py):
    # runs the same qualification logic inside a personal Telegram account's
    # own DMs instead of a separate official bot. Get api_id/api_hash once
    # from https://my.telegram.org (your own account, your own phone number).
    # The userbot never sends the first message - it only reacts to incoming
    # private replies, see userbot.py docstring.
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session_name: str = "agent4_userbot"

    # LLM (provider-agnostic, see common.llm)
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Google Sheets (Agent 4)
    google_service_account_file: str = "service_account.json"
    google_sheet_id: str = ""

    # Postgres (Agent 5)
    database_url: str = "postgresql://user:pass@localhost:5432/aimarket"

    # Ad platform credentials (Agent 5)
    yandex_direct_token: str = ""
    vk_ads_token: str = ""

    # Recipient for weekly report / who the Q&A bot treats as the manager
    report_chat_id: str = ""


settings = Settings()

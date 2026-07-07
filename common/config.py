"""Central configuration for all aimarket agents, loaded from environment variables / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    # Telegram
    agent4_bot_token: str = ""
    agent5_bot_token: str = ""

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

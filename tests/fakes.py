"""Test doubles for exercising every agent end-to-end without any real
external credentials: no Telegram token, no LLM API key, no Postgres, no
Google service account.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from common.llm import ChatMessage, LLMClient


class FakeLLMClient(LLMClient):
    """Returns pre-scripted replies in order, one per call to `.chat()`.
    Once the script runs out, keeps repeating the last reply."""

    def __init__(self, scripted_replies: list[str]) -> None:
        self._replies = scripted_replies
        self._call_count = 0
        self.received_messages: list[list[ChatMessage]] = []

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        self.received_messages.append(messages)
        index = min(self._call_count, len(self._replies) - 1)
        self._call_count += 1
        return self._replies[index]


@dataclass
class FakeLeadsSheet:
    """In-memory stand-in for agent4_lead_qualifier.sheets.LeadsSheet."""

    links: dict = field(default_factory=lambda: {"telegram": "https://example.com/ref/test"})
    appended_rows: list = field(default_factory=list)

    def get_referral_link(self, channel: str) -> str:
        return self.links.get(channel.lower(), "[ссылка]")

    def append_lead(self, *, channel, chat_id, username, lead, referral_link) -> None:
        self.appended_rows.append(
            {
                "channel": channel,
                "chat_id": chat_id,
                "username": username,
                "lead": lead,
                "referral_link": referral_link,
            }
        )


class _AcquireCtx:
    """Fakes asyncpg's `async with pool.acquire() as conn:` context manager."""

    def __init__(self, connection) -> None:
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, *exc_info) -> bool:
        return False


class FakeConnection:
    """Fakes an asyncpg connection.

    `fetch_results` is a queue: each call to `.fetch()` pops the next list off
    the front, so a function that runs two different queries in sequence
    (e.g. weekly_report's metrics query then its feedback query) gets the
    right canned rows for each call, in order.
    """

    def __init__(self, *, fetch_results: list | None = None, fetchrow_result: dict | None = None) -> None:
        self._fetch_results = list(fetch_results or [])
        self._fetchrow_result = fetchrow_result or {}
        self.executed: list[tuple] = []
        self.executed_many: list[tuple] = []

    async def fetch(self, query, *args):
        if not self._fetch_results:
            return []
        return self._fetch_results.pop(0)

    async def fetchrow(self, query, *args):
        return self._fetchrow_result

    async def execute(self, query, *args) -> None:
        self.executed.append((query, args))

    async def executemany(self, query, rows) -> None:
        self.executed_many.append((query, list(rows)))


class FakePool:
    """Fakes an asyncpg.Pool - just enough for `pool.acquire()` to work."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> _AcquireCtx:
        return _AcquireCtx(self.connection)

"""Provider-agnostic LLM chat client.

Every agent talks to `LLMClient.chat()` only. Swapping providers means changing
`LLM_PROVIDER` in .env (and, if needed, `LLM_BASE_URL` / `LLM_MODEL`) - no code
changes in the agents themselves.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

import httpx


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient(abc.ABC):
    """Abstract chat completion interface implemented by each concrete provider."""

    @abc.abstractmethod
    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        """Send a chat completion request and return the assistant's reply text."""


class OpenAICompatibleClient(LLMClient):
    """Works with OpenAI and any OpenAI-compatible /chat/completions endpoint
    (DeepSeek, OpenRouter, Groq, a local vLLM server, etc)."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        payload = {
            "model": self._model,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]


class AnthropicClient(LLMClient):
    """Native Anthropic Messages API (api.anthropic.com)."""

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str, model: str, timeout: float = 60.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        system_text = "\n".join(m.content for m in messages if m.role == "system") or None
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        payload: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "temperature": temperature,
            "messages": turns,
        }
        if system_text:
            payload["system"] = system_text
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self.API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return "".join(block["text"] for block in data["content"] if block.get("type") == "text")


def build_llm_client(settings) -> LLMClient:
    """Factory: picks the concrete client based on settings.llm_provider."""
    if settings.llm_provider.lower() == "anthropic":
        return AnthropicClient(api_key=settings.llm_api_key, model=settings.llm_model)
    return OpenAICompatibleClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model)

"""Pluggable LLM clients. The rest of the system only sees `LLMClient.complete`."""

from __future__ import annotations

import os
from typing import Any, Protocol

from copilot.config import LLMConfig


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> Any:
    import httpx

    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request to {url} failed: {exc}") from exc
    return r.json()


class OllamaClient:
    """Local models via Ollama (https://ollama.com). Free, private, runs on Apple Silicon."""

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.name = f"ollama:{cfg.model}"

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            f"{self.cfg.base_url.rstrip('/')}/api/chat",
            {
                "model": self.cfg.model,
                "stream": False,
                "options": {"temperature": self.cfg.temperature},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            headers={},
            timeout=self.cfg.timeout_seconds,
        )
        try:
            return str(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise LLMError(f"unexpected Ollama response: {data!r}") from exc


class OpenAICompatibleClient:
    """Any server that speaks the OpenAI chat-completions API (OpenAI, vLLM, LM Studio, ...)."""

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.name = f"openai:{cfg.model}"
        self.api_key = os.environ.get(cfg.api_key_env, "")

    def complete(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = _post_json(
            f"{self.cfg.base_url.rstrip('/')}/chat/completions",
            {
                "model": self.cfg.model,
                "temperature": self.cfg.temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            headers=headers,
            timeout=self.cfg.timeout_seconds,
        )
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected OpenAI-compatible response: {data!r}") from exc


def make_llm(cfg: LLMConfig) -> LLMClient | None:
    """Returns None for provider 'none', which means extractive answers with no LLM."""
    if cfg.provider == "ollama":
        return OllamaClient(cfg)
    if cfg.provider == "openai":
        return OpenAICompatibleClient(cfg)
    return None

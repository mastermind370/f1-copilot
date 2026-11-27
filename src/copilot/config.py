"""Typed configuration loaded from config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    seeds: list[str]
    allowed_prefixes: list[str]


@dataclass(frozen=True)
class CrawlConfig:
    user_agent: str = "F1-Copilot/0.1 (student research project; respects robots.txt)"
    delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    max_pages_per_source: int = 25
    max_depth: int = 1


@dataclass(frozen=True)
class ChunkConfig:
    max_words: int = 220
    overlap_words: int = 40
    min_words: int = 5

    def __post_init__(self) -> None:
        if not 0 <= self.overlap_words < self.max_words:
            raise ConfigError("chunking.overlap_words must be >= 0 and < max_words")


@dataclass(frozen=True)
class RetrievalConfig:
    embedding_model: str = "intfloat/multilingual-e5-small"
    top_k: int = 5
    candidate_k: int = 30
    rrf_k: int = 60
    min_confidence: float = 0.80


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "ollama"  # ollama | openai | none
    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.0
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.provider not in {"ollama", "openai", "none"}:
            raise ConfigError(f"llm.provider must be ollama|openai|none, got {self.provider!r}")


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    sources: list[Source]
    dso_message: str
    crawl: CrawlConfig = field(default_factory=CrawlConfig)
    chunking: ChunkConfig = field(default_factory=ChunkConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    def source(self, name: str) -> Source:
        for s in self.sources:
            if s.name == name:
                return s
        raise ConfigError(f"unknown source {name!r}")


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}

    sources = [Source(**s) for s in raw.get("sources", [])]
    if not sources:
        raise ConfigError("config must define at least one source")
    for s in sources:
        if not s.allowed_prefixes:
            raise ConfigError(f"source {s.name!r} has no allowed_prefixes")

    data_dir = Path(raw.get("data_dir", "data"))
    if not data_dir.is_absolute():
        data_dir = path.parent / data_dir

    return AppConfig(
        data_dir=data_dir,
        sources=sources,
        dso_message=str(raw.get("dso_message", "Please contact your school's DSO.")).strip(),
        crawl=CrawlConfig(**raw.get("crawl", {})),
        chunking=ChunkConfig(**raw.get("chunking", {})),
        retrieval=RetrievalConfig(**raw.get("retrieval", {})),
        llm=LLMConfig(**raw.get("llm", {})),
    )

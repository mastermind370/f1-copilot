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
    school: str | None = None  # set for one university's own pages; None = applies to everyone


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
class RulesConfig:
    dir: Path = Path("rules")
    max_age_days: int = 180  # rules verified longer ago than this are flagged as stale


@dataclass(frozen=True)
class EvalConfig:
    dataset_glob: str = "eval/dataset/*.jsonl"
    thresholds: Path = Path("eval/thresholds.yaml")
    results_dir: Path = Path("eval/results")
    snapshot: Path = Path("eval/snapshot/chunks.jsonl")
    # Only public-domain US government text goes in the committed snapshot.
    snapshot_exclude_sources: tuple[str, ...] = ("rutgers_global",)
    faithfulness_model: str = "cross-encoder/nli-deberta-v3-xsmall"
    base_dir: Path = Path(".")


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    sources: list[Source]
    dso_message: str
    crawl: CrawlConfig = field(default_factory=CrawlConfig)
    chunking: ChunkConfig = field(default_factory=ChunkConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)
    evaluation: EvalConfig = field(default_factory=EvalConfig)

    def source(self, name: str) -> Source:
        for s in self.sources:
            if s.name == name:
                return s
        raise ConfigError(f"unknown source {name!r}")


def _resolve(base: Path, p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else base / p


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

    rules_raw = dict(raw.get("rules", {}))
    rules = RulesConfig(
        dir=_resolve(path.parent, rules_raw.get("dir", "rules")),
        max_age_days=int(rules_raw.get("max_age_days", 180)),
    )

    ev = dict(raw.get("evaluation", {}))
    evaluation = EvalConfig(
        dataset_glob=str(ev.get("dataset_glob", EvalConfig.dataset_glob)),
        thresholds=_resolve(path.parent, ev.get("thresholds", EvalConfig.thresholds)),
        results_dir=_resolve(path.parent, ev.get("results_dir", EvalConfig.results_dir)),
        snapshot=_resolve(path.parent, ev.get("snapshot", EvalConfig.snapshot)),
        snapshot_exclude_sources=tuple(ev.get("snapshot_exclude_sources",
                                              EvalConfig.snapshot_exclude_sources)),
        faithfulness_model=str(ev.get("faithfulness_model", EvalConfig.faithfulness_model)),
        base_dir=path.parent.resolve(),
    )

    return AppConfig(
        data_dir=_resolve(path.parent, raw.get("data_dir", "data")),
        sources=sources,
        dso_message=str(raw.get("dso_message", "Please contact your school's DSO.")).strip(),
        crawl=CrawlConfig(**raw.get("crawl", {})),
        chunking=ChunkConfig(**raw.get("chunking", {})),
        retrieval=RetrievalConfig(**raw.get("retrieval", {})),
        llm=LLMConfig(**raw.get("llm", {})),
        rules=rules,
        evaluation=evaluation,
    )

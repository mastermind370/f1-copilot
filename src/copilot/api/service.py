"""Framework-free service layer behind the HTTP API.

Keeping this free of FastAPI means every behavior (caching, stale answers, timeline
validation, privacy) is tested with plain function calls, and the web framework stays
a thin, replaceable shell.

Privacy contract for the timeline:
  - Facts arrive in the request body, are used to compute the timeline, and are discarded.
  - They are never written to disk, cached, or logged. The service has no code path that
    persists them, and a test asserts the data directory is unchanged after a timeline call.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from typing import Any

from copilot import DISCLAIMER
from copilot.answer import QAPipeline
from copilot.changes import load_latest_report
from copilot.config import AppConfig
from copilot.crawler import now_utc
from copilot.embeddings import Embedder
from copilot.llm import LLMClient, make_llm
from copilot.retrieval import HybridRetriever
from copilot.store import Store
from copilot.timeline import evaluate, load_rules, parse_facts
from copilot.timeline.facts import facts_schema

MAX_QUESTION_CHARS = 1000


class BadRequest(ValueError):
    """Client error, mapped to HTTP 422 by the API layer."""


class NotReady(RuntimeError):
    """The index hasn't been built yet. Mapped to HTTP 503."""


def question_key(q: str) -> str:
    return " ".join(q.lower().split())


class CopilotService:
    def __init__(
        self,
        cfg: AppConfig,
        embedder_factory: Callable[[], Embedder] | None = None,
        llm: LLMClient | None | str = "from-config",
    ) -> None:
        self.cfg = cfg
        self._embedder_factory = embedder_factory
        self._llm = make_llm(cfg.llm) if llm == "from-config" else llm
        self._lock = threading.Lock()
        self._pipeline: QAPipeline | None = None
        self._index_mtime: float | None = None
        self._embedder: Embedder | None = None
        r = cfg.retrieval
        llm_name = getattr(self._llm, "name", "none")
        self.config_key = hashlib.sha256(
            f"{r.embedding_model}|{r.min_confidence}|{r.top_k}|{llm_name}".encode()
        ).hexdigest()[:16]

    # --- Q&A ---------------------------------------------------------------------------
    def _get_pipeline(self, store: Store) -> QAPipeline:
        mtime = store.emb_path.stat().st_mtime if store.emb_path.exists() else None
        if mtime is None:
            raise NotReady("index not built yet; run `copilot ingest`")
        if self._pipeline is None or mtime != self._index_mtime:  # reload after a recheck
            if self._embedder is None:
                if self._embedder_factory is None:
                    from copilot.embeddings import SentenceTransformerEmbedder

                    self._embedder = SentenceTransformerEmbedder(self.cfg.retrieval.embedding_model)
                else:
                    self._embedder = self._embedder_factory()
            retriever = HybridRetriever.from_store(store, self._embedder, self.cfg.retrieval)
            self._pipeline = QAPipeline(retriever, self._llm, self.cfg.retrieval, self.cfg.dso_message)
            self._index_mtime = mtime
        return self._pipeline

    def school_exclusions(self, school: str | None) -> set[str]:
        """Pages that belong to a different school than the student's are never cited."""
        return {s.name for s in self.cfg.sources if s.school and s.school != school}

    def ask(self, question: str, school: str | None = None) -> dict[str, Any]:
        q = (question or "").strip()
        if not q:
            raise BadRequest("question is empty")
        if len(q) > MAX_QUESTION_CHARS:
            raise BadRequest(f"question is longer than {MAX_QUESTION_CHARS} characters")
        if school is not None and (len(school) > 40 or not school.replace("-", "").isalnum()):
            raise BadRequest("invalid school id")
        key = f"{question_key(q)}|{school or ''}"
        exclude = self.school_exclusions(school)
        with self._lock, Store(self.cfg.data_dir) as store:
            cached = store.get_cached_answer(key, self.config_key)
            if cached is not None:
                return {**cached, "cached": True}
            answer = self._get_pipeline(store).ask(q, exclude)
            payload: dict[str, Any] = {
                "question": answer.question,
                "text": answer.text,
                "refused": answer.refused,
                "reason": answer.reason,
                "confidence": round(answer.confidence, 4),
                "citations": [
                    {"chunk_id": c.chunk_id, "url": c.url, "heading": c.heading,
                     "text": c.text, "retrieved_at": c.retrieved_at, "source": c.source}
                    for c in answer.citations
                ],
                "disclaimer": DISCLAIMER,
            }
            if not answer.refused:  # refusals are cheap and depend on nothing; don't cache them
                store.put_cached_answer(key, self.config_key, payload,
                                        [c.url for c in answer.citations], now_utc())
        return {**payload, "cached": False}

    # --- timeline ----------------------------------------------------------------------
    def timeline(self, facts: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
        from copilot.timeline.facts import FactError

        try:
            parsed = parse_facts({k: v for k, v in facts.items() if v not in ("", None)})
            when = date.fromisoformat(as_of) if as_of else date.today()
        except (FactError, ValueError) as exc:
            raise BadRequest(str(exc)) from exc
        tl = evaluate(load_rules(self.cfg.rules.dir), parsed, when, self.cfg.rules.max_age_days)
        out = asdict(tl)
        out["disclaimer"] = "Dates are computed by fixed rules, not AI. " + DISCLAIMER
        return out

    @staticmethod
    def facts_schema() -> list[dict[str, object]]:
        return facts_schema()

    def rules(self) -> list[dict[str, Any]]:
        today = date.today()
        out = []
        for r in load_rules(self.cfg.rules.dir):
            out.append({
                "id": r.id, "version": r.version, "title": r.title, "category": r.category,
                "summary": r.summary, "source_url": r.source.url, "citation": r.source.citation,
                "verification": r.source.verification,
                "last_verified": r.source.last_verified.isoformat(),
                "stale": (today - r.source.last_verified).days > self.cfg.rules.max_age_days,
                "notes": r.notes,
            })
        return out

    # --- change detection ----------------------------------------------------------------
    def changes(self) -> dict[str, Any]:
        report = load_latest_report(self.cfg.data_dir / "changes")
        return {"report": report}

    def health(self) -> dict[str, Any]:
        with Store(self.cfg.data_dir) as store:
            stats = {**store.stats(), **store.cache_stats()}
        return {"ok": True, "index": stats, "llm": getattr(self._llm, "name", "none (extractive)"),
                "embedding_model": self.cfg.retrieval.embedding_model}

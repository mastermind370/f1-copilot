"""Hybrid retrieval: BM25 + dense embeddings, combined with Reciprocal Rank Fusion.

Why RRF? BM25 scores are unbounded and cosine scores sit in [-1, 1], so adding them
directly takes per-query normalization hacks. RRF only uses *ranks*:
    score(d) = sum over lists of 1 / (k + rank(d))
It needs no tuning, holds up well in practice, and is easy to explain.

Confidence (for refusals) uses the top *dense* cosine score, because it is bounded and
comparable across queries. RRF scores are not. The threshold is calibrated in Stage 3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from copilot.bm25 import BM25, tokenize
from copilot.config import RetrievalConfig
from copilot.embeddings import Embedder
from copilot.models import Chunk, ScoredChunk
from copilot.store import Store


class IndexNotReadyError(RuntimeError):
    """Raised when the on-disk index is missing or inconsistent."""


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + rank)
    return fused


@dataclass
class RetrievalResult:
    hits: list[ScoredChunk]
    confidence: float


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        embedder: Embedder,
        cfg: RetrievalConfig,
    ) -> None:
        if embeddings.shape[0] != len(chunks):
            raise IndexNotReadyError("embeddings and chunks are misaligned; run `copilot reindex`")
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        self.embedder = embedder
        self.cfg = cfg
        self.bm25 = BM25([tokenize(c.index_text) for c in chunks])

    @classmethod
    def from_store(cls, store: Store, embedder: Embedder, cfg: RetrievalConfig) -> HybridRetriever:
        loaded = store.load_embeddings()
        if loaded is None:
            raise IndexNotReadyError("no index found; run `copilot ingest` first")
        ids, matrix, model_name = loaded
        if model_name != embedder.name:
            raise IndexNotReadyError(
                f"index built with {model_name!r} but config uses {embedder.name!r}; "
                "run `copilot reindex`"
            )
        by_id = {c.chunk_id: c for c in store.all_chunks()}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise IndexNotReadyError(f"{len(missing)} embedded chunks missing from DB; run `copilot reindex`")
        return cls([by_id[i] for i in ids], matrix, embedder, cfg)

    def search(
        self, query: str, top_k: int | None = None, exclude_sources: set[str] | None = None
    ) -> RetrievalResult:
        """exclude_sources: source names to leave out, e.g. other schools' international
        office pages, so a student never gets another university's internal rules cited."""
        top_k = top_k or self.cfg.top_k
        if not self.chunks:
            return RetrievalResult(hits=[], confidence=0.0)
        allowed = np.ones(len(self.chunks), dtype=bool)
        if exclude_sources:
            allowed = np.array([c.source not in exclude_sources for c in self.chunks])
        if not allowed.any():
            return RetrievalResult(hits=[], confidence=0.0)
        cand = min(self.cfg.candidate_k, int(allowed.sum()))

        bm25_scores = np.where(allowed, self.bm25.scores(tokenize(query)), 0.0)
        bm25_order = [int(i) for i in np.argsort(-bm25_scores, kind="stable")[:cand]
                      if bm25_scores[i] > 0]

        q = self.embedder.embed_query(query).astype(np.float32)
        dense_scores = np.where(allowed, self.embeddings @ q, -np.inf)
        dense_order = [int(i) for i in np.argsort(-dense_scores, kind="stable")[:cand]]

        fused = reciprocal_rank_fusion([bm25_order, dense_order], k=self.cfg.rrf_k)
        ranked = sorted(fused, key=lambda i: (-fused[i], i))[:top_k]

        bm25_rank = {doc: r for r, doc in enumerate(bm25_order, start=1)}
        dense_rank = {doc: r for r, doc in enumerate(dense_order, start=1)}
        hits = [
            ScoredChunk(
                chunk=self.chunks[i],
                fused_score=fused[i],
                dense_score=float(dense_scores[i]),
                bm25_rank=bm25_rank.get(i),
                dense_rank=dense_rank.get(i),
            )
            for i in ranked
        ]
        return RetrievalResult(hits=hits, confidence=float(dense_scores.max()))

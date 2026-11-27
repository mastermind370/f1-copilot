"""Plain data types shared across the pipeline.

These are frozen dataclasses so they are hashable, immutable, and trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FetchedPage:
    url: str
    source: str
    fetched_at: str  # ISO 8601, UTC
    status_code: int
    content_hash: str  # hash of the *visible text*, not raw HTML (see crawler.py)
    html: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # content-addressed: changes iff url/heading/text changes
    url: str
    source: str
    heading: str  # "Page title > Section > Subsection"
    text: str
    retrieved_at: str
    doc_hash: str  # content_hash of the page this chunk came from
    position: int  # order within the page

    @property
    def index_text(self) -> str:
        """Text used for BM25 and embeddings. The heading adds context to short chunks."""
        return f"{self.heading}\n{self.text}" if self.heading else self.text


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    fused_score: float
    dense_score: float
    bm25_rank: int | None  # 1-based rank in the BM25 list, None if absent
    dense_rank: int | None  # 1-based rank in the dense list, None if absent


@dataclass
class Answer:
    question: str
    text: str
    refused: bool
    confidence: float
    citations: list[Chunk] = field(default_factory=list)
    reason: str | None = None  # why we refused, or None
    dropped_sentences: list[str] = field(default_factory=list)  # uncited LLM output we removed

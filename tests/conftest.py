"""Shared test helpers. No test touches the network or downloads a model."""

from __future__ import annotations

import zlib
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from copilot.bm25 import tokenize
from copilot.models import Chunk

FIXTURES = Path(__file__).parent / "fixtures"


class FakeEmbedder:
    """Deterministic hashed bag-of-words embedder.

    Close enough to a real embedder for tests: texts sharing words get high cosine
    similarity, and unrelated texts get ~0. Uses crc32 because Python's hash() is
    randomized per process.
    """

    name = "fake-hash-embedder"

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in tokenize(text):
            v[zlib.crc32(tok.encode()) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim))

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


def make_chunk(chunk_id: str, text: str, heading: str = "Test page") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        url=f"https://example.gov/{chunk_id}",
        source="test",
        heading=heading,
        text=text,
        retrieved_at="2026-11-26T00:00:00+00:00",
        doc_hash="deadbeef",
        position=0,
    )


@pytest.fixture
def sample_html() -> str:
    return (FIXTURES / "sample_opt.html").read_text()


@pytest.fixture
def corpus() -> list[Chunk]:
    return [
        make_chunk("aaaaaaaaaaa1", "Students file Form I-765 to request OPT employment authorization."),
        make_chunk("aaaaaaaaaaa2", "Curricular Practical Training (CPT) is authorized by the school."),
        make_chunk("aaaaaaaaaaa3", "Carry a Form I-20 with a recent travel signature when traveling abroad."),
        make_chunk("aaaaaaaaaaa4", "Report a change of address to your DSO within the required time."),
        make_chunk("aaaaaaaaaaa5", "A Social Security number is needed for paid employment and taxes."),
    ]

from __future__ import annotations

import numpy as np
import pytest

from copilot.bm25 import BM25, tokenize
from copilot.config import RetrievalConfig
from copilot.models import Chunk
from copilot.retrieval import HybridRetriever, IndexNotReadyError, reciprocal_rank_fusion

from .conftest import FakeEmbedder


def _retriever(corpus: list[Chunk], **cfg: object) -> HybridRetriever:
    emb = FakeEmbedder()
    matrix = emb.embed_passages([c.index_text for c in corpus])
    return HybridRetriever(corpus, matrix, emb, RetrievalConfig(**cfg))  # type: ignore[arg-type]


class TestTokenizer:
    def test_keeps_form_identifiers(self) -> None:
        assert "i-20" in tokenize("Bring your I-20 to the DSO")
        assert "f-1" in tokenize("F-1 students")
        assert "i-765" in tokenize("Form I-765")

    def test_removes_stopwords(self) -> None:
        assert tokenize("What is the OPT") == ["opt"]


class TestBM25:
    def test_relevant_doc_ranks_first(self) -> None:
        docs = [tokenize(t) for t in ["opt application form", "cpt school authorization", "travel signature i-20"]]
        scores = BM25(docs).scores(tokenize("cpt authorization"))
        assert int(np.argmax(scores)) == 1

    def test_unknown_term_scores_zero(self) -> None:
        scores = BM25([["opt"], ["cpt"]]).scores(["zebra"])
        assert scores.tolist() == [0.0, 0.0]

    def test_rare_terms_weigh_more(self) -> None:
        bm = BM25([["opt", "rare"], ["opt"], ["opt"]])
        assert bm.idf["rare"] > bm.idf["opt"] > 0

    def test_empty_corpus(self) -> None:
        assert BM25([]).scores(["opt"]).shape == (0,)


class TestRRF:
    def test_math(self) -> None:
        fused = reciprocal_rank_fusion([[1, 2], [2, 3]], k=60)
        assert fused[2] == pytest.approx(1 / 62 + 1 / 61)
        assert fused[1] == pytest.approx(1 / 61)
        assert fused[3] == pytest.approx(1 / 62)

    def test_agreement_beats_single_list(self) -> None:
        fused = reciprocal_rank_fusion([[1, 2], [2, 1], [2]], k=60)
        assert max(fused, key=fused.__getitem__) == 2


class TestHybrid:
    def test_finds_lexical_identifier(self, corpus: list[Chunk]) -> None:
        res = _retriever(corpus).search("where do I get an I-20 travel signature", top_k=3)
        assert res.hits[0].chunk.chunk_id == "aaaaaaaaaaa3"
        assert res.hits[0].bm25_rank == 1

    def test_respects_top_k(self, corpus: list[Chunk]) -> None:
        assert len(_retriever(corpus).search("employment", top_k=2).hits) == 2

    def test_confidence_low_for_unrelated_query(self, corpus: list[Chunk]) -> None:
        r = _retriever(corpus)
        related = r.search("CPT authorized by the school").confidence
        unrelated = r.search("chocolate cake recipe").confidence
        assert related > 0.5 > unrelated

    def test_misaligned_index_rejected(self, corpus: list[Chunk]) -> None:
        with pytest.raises(IndexNotReadyError):
            HybridRetriever(corpus, np.zeros((1, 8), dtype=np.float32), FakeEmbedder(), RetrievalConfig())

    def test_empty_corpus(self) -> None:
        r = HybridRetriever([], np.zeros((0, 256), dtype=np.float32), FakeEmbedder(), RetrievalConfig())
        res = r.search("opt")
        assert res.hits == [] and res.confidence == 0.0


class TestSourceExclusion:
    def test_excluded_sources_never_returned(self, corpus: list[Chunk]) -> None:
        from dataclasses import replace

        tagged = [replace(c, source="rutgers_global") if c.chunk_id == "aaaaaaaaaaa3" else c for c in corpus]
        r = _retriever(tagged)
        assert r.search("I-20 travel signature", top_k=3).hits[0].chunk.chunk_id == "aaaaaaaaaaa3"
        res = r.search("I-20 travel signature", top_k=5, exclude_sources={"rutgers_global"})
        assert all(h.chunk.source != "rutgers_global" for h in res.hits)
        assert res.confidence < r.search("I-20 travel signature").confidence

    def test_everything_excluded(self, corpus: list[Chunk]) -> None:
        res = _retriever(corpus).search("opt", exclude_sources={"test"})
        assert res.hits == [] and res.confidence == 0.0

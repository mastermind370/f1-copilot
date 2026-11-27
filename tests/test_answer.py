from __future__ import annotations

from copilot.answer import INSUFFICIENT, QAPipeline, validate_citations
from copilot.config import RetrievalConfig
from copilot.models import Chunk
from copilot.retrieval import HybridRetriever

from .conftest import FakeEmbedder

ID1, ID2, FAKE = "aaaaaaaaaaa1", "aaaaaaaaaaa2", "ffffffffffff"


class FakeLLM:
    name = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


def _pipeline(corpus: list[Chunk], llm: FakeLLM | None, min_conf: float = 0.3) -> QAPipeline:
    emb = FakeEmbedder()
    matrix = emb.embed_passages([c.index_text for c in corpus])
    cfg = RetrievalConfig(min_confidence=min_conf, top_k=3)
    return QAPipeline(HybridRetriever(corpus, matrix, emb, cfg), llm, cfg, "Contact your DSO.")


class TestValidateCitations:
    def test_keeps_cited_sentences(self) -> None:
        out = validate_citations(f"OPT needs Form I-765 [{ID1}]. CPT is school-authorized [{ID2}].", {ID1, ID2})
        assert out.cited_ids == [ID1, ID2]
        assert out.dropped == []

    def test_drops_uncited_sentence(self) -> None:
        out = validate_citations(f"OPT needs Form I-765 [{ID1}]. You will definitely be approved.", {ID1})
        assert "definitely" not in out.text
        assert out.dropped == ["You will definitely be approved."]

    def test_removes_hallucinated_ids(self) -> None:
        out = validate_citations(f"OPT needs Form I-765 [{ID1}, {FAKE}].", {ID1})
        assert FAKE not in out.text
        assert f"[{ID1}]" in out.text

    def test_sentence_citing_only_fake_id_is_dropped(self) -> None:
        out = validate_citations(f"Made-up fact [{FAKE}].", {ID1})
        assert out.cited_ids == [] and out.text == ""

    def test_citation_after_period(self) -> None:
        out = validate_citations(f"OPT needs Form I-765. [{ID1}] CPT is different. [{ID2}]", {ID1, ID2})
        assert out.cited_ids == [ID1, ID2] and out.dropped == []

    def test_bullet_lines(self) -> None:
        out = validate_citations(f"- File Form I-765 [{ID1}]\n- Get a DSO recommendation [{ID2}]", {ID1, ID2})
        assert out.text.count("\n") == 1


class TestPipeline:
    def test_low_confidence_refuses_without_calling_llm(self, corpus: list[Chunk]) -> None:
        llm = FakeLLM("should not be called")
        ans = _pipeline(corpus, llm).ask("best chocolate cake recipe")
        assert ans.refused and ans.reason == "low_retrieval_confidence"
        assert "DSO" in ans.text
        assert llm.calls == []

    def test_grounded_answer(self, corpus: list[Chunk]) -> None:
        llm = FakeLLM(f"Students file Form I-765 to request OPT [{ID1}].")
        ans = _pipeline(corpus, llm).ask("how do I request OPT employment authorization")
        assert not ans.refused
        assert [c.chunk_id for c in ans.citations] == [ID1]
        system, user = llm.calls[0]
        assert ID1 in user and "Question:" in user
        assert INSUFFICIENT in system

    def test_llm_insufficient_context_refuses(self, corpus: list[Chunk]) -> None:
        ans = _pipeline(corpus, FakeLLM(INSUFFICIENT)).ask("OPT employment authorization form")
        assert ans.refused and ans.reason == "llm_insufficient_context"

    def test_uncited_llm_output_refuses(self, corpus: list[Chunk]) -> None:
        ans = _pipeline(corpus, FakeLLM("OPT is great and you qualify.")).ask("OPT employment authorization")
        assert ans.refused and ans.reason == "no_supported_claims"
        assert ans.dropped_sentences

    def test_extractive_mode_cites_passages(self, corpus: list[Chunk]) -> None:
        ans = _pipeline(corpus, None).ask("OPT employment authorization Form I-765")
        assert not ans.refused
        assert ans.citations and all(f"[{c.chunk_id}]" in ans.text for c in ans.citations)

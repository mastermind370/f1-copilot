"""Tests for the eval harness. Metrics are checked against hand-computed values."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from copilot.answer import QAPipeline
from copilot.config import RetrievalConfig
from copilot.evaluation.dataset import (
    DatasetError,
    GoldMatcher,
    load_dataset,
    load_snapshot,
    resolve_gold,
    write_snapshot,
)
from copilot.evaluation.faithfulness import cited_sentences, faithfulness
from copilot.evaluation.metrics import (
    calibrate,
    check_thresholds,
    hit_at_k,
    ratchet_thresholds,
    reciprocal_rank,
    refusal_stats,
    retrieval_metrics,
)
from copilot.evaluation.report import to_markdown
from copilot.evaluation.runner import run_items, summarize
from copilot.models import Chunk
from copilot.retrieval import HybridRetriever

from .conftest import FakeEmbedder, make_chunk

REPO = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return path


def _item(id: str, q: str = "q", **kw: object) -> dict[str, object]:
    base: dict[str, object] = {"id": id, "language": "en", "question": q, "should_refuse": False,
                               "gold": [{"phrases": ["opt"]}]}
    base.update(kw)
    return base


# --- metrics ---------------------------------------------------------------------------

class TestMetrics:
    def test_hit_and_rr(self) -> None:
        ranked = ["a", "b", "c", "d"]
        assert hit_at_k(ranked, {"c"}, 2) == 0.0
        assert hit_at_k(ranked, {"c"}, 3) == 1.0
        assert reciprocal_rank(ranked, {"c", "d"}) == pytest.approx(1 / 3)
        assert reciprocal_rank(ranked, {"z"}) == 0.0

    def test_retrieval_metrics(self) -> None:
        rows = [(["a", "b"], {"a"}), (["a", "b"], {"b"}), (["a", "b"], {"z"})]
        m = retrieval_metrics(rows)
        assert m["n"] == 3
        assert m["recall@1"] == pytest.approx(1 / 3)
        assert m["recall@3"] == pytest.approx(2 / 3)
        assert m["mrr@10"] == pytest.approx((1 + 0.5 + 0) / 3)

    def test_empty_slice_is_none(self) -> None:
        assert retrieval_metrics([])["recall@5"] is None

    def test_refusal_stats(self) -> None:
        rows = [(0.9, False), (0.7, False), (0.6, True), (0.85, True)]
        s = refusal_stats(rows, 0.8)
        assert (s.true_refusals, s.missed_refusals, s.false_refusals, s.correct_answers) == (1, 1, 1, 1)
        assert s.refusal_recall == 0.5 and s.false_refusal_rate == 0.5
        assert s.balanced_accuracy == 0.5

    def test_calibration_finds_separating_threshold(self) -> None:
        rows = [(0.90, False), (0.88, False), (0.86, False), (0.78, True), (0.75, True)]
        best, table = calibrate(rows)
        assert best is not None and best.balanced_accuracy == 1.0
        assert 0.78 < best.threshold <= 0.86
        assert best.threshold == pytest.approx(0.79)  # lowest perfect threshold wins ties
        assert len(table) > 10

    def test_calibration_without_refuse_items(self) -> None:
        best, _ = calibrate([(0.9, False)])
        assert best is None

    def test_check_and_ratchet(self) -> None:
        summary = {"a": {"x": 0.72}, "b": 0.10}
        gates = {"min": {"a.x": 0.80}, "max": {"b": 0.05}}
        failures = check_thresholds(summary, gates)
        assert len(failures) == 2
        new = ratchet_thresholds(summary, gates)
        assert new == {"min": {"a.x": 0.67}, "max": {"b": 0.15}}
        assert check_thresholds(summary, new) == []

    def test_missing_metric_fails(self) -> None:
        assert check_thresholds({}, {"min": {"nope.x": 0.5}}) == ["nope.x: metric not found"]
        assert "no value" in check_thresholds({"x": None}, {"min": {"x": 0.5}})[0]


# --- dataset ---------------------------------------------------------------------------

class TestDataset:
    def test_matcher(self) -> None:
        c = make_chunk("aaaaaaaaaaa1", "File Form   I-765 within 90 days.", heading="OPT")
        assert GoldMatcher(("form i-765", "90 DAYS")).matches(c)
        assert GoldMatcher(("opt",), url_contains="example.gov").matches(c)  # heading counts
        assert not GoldMatcher(("i-765",), url_contains="uscis").matches(c)
        assert not GoldMatcher(("i-765", "60 days")).matches(c)

    def test_seed_dataset_is_valid(self) -> None:
        items = load_dataset((REPO / "eval" / "dataset").glob("*.jsonl"))
        assert len(items) >= 50
        langs = {i.language for i in items}
        assert langs == {"en", "zh", "hi", "ko", "es"}
        assert sum(i.should_refuse for i in items) >= 8
        for lang in langs - {"en"}:
            assert any(i.translation_of and i.language == lang for i in items)

    @pytest.mark.parametrize(
        ("rows", "message"),
        [
            ([_item("a", language="fr")], "language"),
            ([_item("a", q="")], "question is required"),
            ([_item("a", gold=[])], "at least one gold"),
            ([_item("a", should_refuse=True)], "must not have gold"),
            ([_item("a", gold=[{"phrases": []}])], "needs phrases"),
            ([_item("a"), _item("a")], "duplicate"),
            ([_item("a", language="zh", translation_of="missing")], "does not exist"),
            ([_item("a", surprise=1)], "unknown keys"),
        ],
    )
    def test_rejects_invalid(self, tmp_path: Path, rows: list[dict[str, object]], message: str) -> None:
        with pytest.raises(DatasetError, match=message):
            load_dataset([_write_jsonl(tmp_path / "d.jsonl", rows)])

    def test_errors_on_line_10_do_not_drop_line_1(self, tmp_path: Path) -> None:
        rows = [_item(f"i{n}") for n in range(9)] + [_item("bad", language="xx")]
        with pytest.raises(DatasetError) as exc:
            load_dataset([_write_jsonl(tmp_path / "d.jsonl", rows)])
        assert len(exc.value.errors) == 1 and exc.value.errors[0].startswith("d.jsonl:10")

    def test_underscore_keys_allowed(self, tmp_path: Path) -> None:
        [item] = load_dataset([_write_jsonl(tmp_path / "d.jsonl", [_item("a", _chunk_text="x")])])
        assert item.id == "a"

    def test_resolution(self, corpus: list[Chunk], tmp_path: Path) -> None:
        items = load_dataset([_write_jsonl(tmp_path / "d.jsonl", [
            _item("hit", gold=[{"phrases": ["I-765"]}]),
            _item("miss", gold=[{"phrases": ["nonexistent phrase"]}]),
            _item("ref", should_refuse=True, gold=[]),
        ])])
        res = resolve_gold(items, corpus)
        assert res.gold_ids["hit"] == {"aaaaaaaaaaa1"}
        assert res.unresolved == ["miss"]

    def test_snapshot_roundtrip(self, corpus: list[Chunk], tmp_path: Path) -> None:
        p = tmp_path / "snap" / "chunks.jsonl"
        assert write_snapshot(corpus, p) == len(corpus)
        assert load_snapshot(p) == corpus


# --- faithfulness ----------------------------------------------------------------------

class KeywordJudge:
    """Entails iff every word of the claim appears in the premise."""

    def entailment(self, premise: str, hypothesis: str) -> float:
        words = [w.strip(".,").lower() for w in hypothesis.split()]
        return 1.0 if all(w in premise.lower() for w in words) else 0.0


class TestFaithfulness:
    ID1, ID2 = "aaaaaaaaaaa1", "aaaaaaaaaaa2"

    def test_cited_sentences(self) -> None:
        out = cited_sentences(f"File Form I-765 [{self.ID1}]. CPT is school-authorized [{self.ID1}, {self.ID2}].")
        assert out == [("File Form I-765 .", [self.ID1]), ("CPT is school-authorized .", [self.ID1, self.ID2])]

    def test_scores(self) -> None:
        texts = {self.ID1: "students file form i-765", self.ID2: "cpt is school-authorized"}
        ans = f"Students file Form I-765 [{self.ID1}]. CPT is school-authorized [{self.ID1}]. CPT is school-authorized [{self.ID2}]."
        assert faithfulness(ans, texts, KeywordJudge()) == pytest.approx(2 / 3)

    def test_no_cited_sentences(self) -> None:
        assert faithfulness("no citations here", {}, KeywordJudge()) is None


# --- runner end to end -----------------------------------------------------------------

class TestRunner:
    def _setup(self, corpus: list[Chunk], tmp_path: Path):  # type: ignore[no-untyped-def]
        items = load_dataset([_write_jsonl(tmp_path / "d.jsonl", [
            _item("en-1", "How do I request OPT employment authorization with Form I-765?",
                  gold=[{"phrases": ["I-765"]}]),
            _item("en-2", "What is CPT and who authorizes it?", gold=[{"phrases": ["CPT"]}]),
            _item("zh-1", "Form I-765 OPT 申请", language="zh", translation_of="en-1",
                  gold=[{"phrases": ["I-765"]}]),
            _item("en-r", "chocolate cake recipe with frosting", should_refuse=True, gold=[]),
            _item("en-u", "unresolvable", gold=[{"phrases": ["nothing matches this"]}]),
        ])])
        emb = FakeEmbedder()
        cfg = RetrievalConfig(min_confidence=0.3, top_k=3)
        retriever = HybridRetriever(corpus, emb.embed_passages([c.index_text for c in corpus]), emb, cfg)
        return items, retriever, cfg

    def test_summary(self, corpus: list[Chunk], tmp_path: Path) -> None:
        items, retriever, cfg = self._setup(corpus, tmp_path)
        results = run_items(items, resolve_gold(items, corpus), retriever)
        s = summarize(results, threshold=0.3)
        assert s["unresolved"] == ["en-u"]
        assert s["retrieval"]["overall"]["n"] == 3  # unresolved excluded
        assert s["retrieval"]["overall"]["recall@1"] == 1.0
        assert s["retrieval"]["by_language"]["zh"]["recall@5"] == 1.0
        assert s["cross_lingual"]["zh"]["gap"] == 0.0
        assert s["refusal"]["configured"]["refusal_recall"] == 1.0
        assert "answers" not in s
        md = to_markdown(s, {"corpus": "test", "n_chunks": 5})
        assert "| overall | 3 |" in md and "Cross-lingual" in md

    def test_with_answers(self, corpus: list[Chunk], tmp_path: Path) -> None:
        items, retriever, cfg = self._setup(corpus, tmp_path)
        pipeline = QAPipeline(retriever, None, cfg, "Contact your DSO.")
        results = run_items(items, resolve_gold(items, corpus), retriever, pipeline, KeywordJudge())
        s = summarize(results, threshold=0.3)
        a = s["answers"]
        assert a["refusal_recall"] == 1.0
        assert a["citation_gold_hit_rate"] == 1.0
        assert a["faithfulness_en"] is not None  # extractive answers quote their sources
        zh = next(r for r in results if r.id == "zh-1")
        assert zh.faithfulness is None  # English-only judge


def test_thresholds_file_matches_summary_keys(corpus: list[Chunk], tmp_path: Path) -> None:
    """Every gate in eval/thresholds.yaml must name a metric the runner actually produces."""
    rows = [_item(f"{lang}-1", "Form I-765 OPT", language=lang, gold=[{"phrases": ["I-765"]}])
            for lang in ("en", "zh", "hi", "ko", "es")]
    rows.append(_item("r", "cake", should_refuse=True, gold=[]))
    items = load_dataset([_write_jsonl(tmp_path / "d.jsonl", rows)])
    emb = FakeEmbedder()
    cfg = RetrievalConfig()
    retriever = HybridRetriever(corpus, emb.embed_passages([c.index_text for c in corpus]), emb, cfg)
    s = summarize(run_items(items, resolve_gold(items, corpus), retriever), 0.8)
    gates = yaml.safe_load((REPO / "eval" / "thresholds.yaml").read_text())
    assert not [f for f in check_thresholds(s, gates) if "not found" in f]

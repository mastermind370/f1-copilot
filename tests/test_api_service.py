from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from copilot.api.service import BadRequest, CopilotService, NotReady, question_key
from copilot.changes import compare, write_report
from copilot.config import AppConfig, RetrievalConfig, RulesConfig
from copilot.crawler import Crawler
from copilot.indexing import build_embeddings, crawl_sources
from copilot.store import Store

from .conftest import FakeEmbedder
from .test_crawler_store import BASE, SOURCE, FakeFetcher, _cfg, _web

REPO = Path(__file__).resolve().parents[1]
Q = "Do I need an I-20 travel signature from the DSO?"


@pytest.fixture
def cfg(sample_html: str, tmp_path: Path) -> AppConfig:
    base = _cfg(tmp_path)
    cfg = replace(base, retrieval=RetrievalConfig(min_confidence=0.3, top_k=3),
                  rules=RulesConfig(dir=REPO / "rules"))
    with Store(tmp_path) as store:
        crawl_sources([SOURCE], Crawler(cfg.crawl, FakeFetcher(_web(sample_html))), store, cfg)
        build_embeddings(store, FakeEmbedder())
    return cfg


@pytest.fixture
def svc(cfg: AppConfig) -> CopilotService:
    return CopilotService(cfg, embedder_factory=FakeEmbedder, llm=None)


def _snapshot_dir(d: Path) -> dict[str, tuple[int, float]]:
    return {str(p): (p.stat().st_size, p.stat().st_mtime) for p in d.rglob("*") if p.is_file()}


class TestAsk:
    def test_answer_then_cache(self, svc: CopilotService) -> None:
        first = svc.ask(Q)
        assert not first["refused"] and first["citations"] and first["cached"] is False
        assert all(c["url"].startswith(BASE) for c in first["citations"])
        second = svc.ask("  do i need an i-20 TRAVEL signature from the dso? ")
        assert second["cached"] is True and second["text"] == first["text"]

    def test_refusals_not_cached(self, svc: CopilotService) -> None:
        assert svc.ask("chocolate cake recipe")["refused"]
        assert svc.ask("chocolate cake recipe")["cached"] is False

    def test_stale_answer_is_regenerated(self, svc: CopilotService, cfg: AppConfig) -> None:
        first = svc.ask(Q)
        with Store(cfg.data_dir) as store:
            assert store.mark_answers_stale({first["citations"][0]["url"]}) == 1
        assert svc.ask(Q)["cached"] is False

    def test_config_change_invalidates_cache(self, cfg: AppConfig) -> None:
        a = CopilotService(cfg, embedder_factory=FakeEmbedder, llm=None)
        a.ask(Q)
        b = CopilotService(replace(cfg, retrieval=RetrievalConfig(min_confidence=0.31, top_k=3)),
                           embedder_factory=FakeEmbedder, llm=None)
        assert a.config_key != b.config_key and b.ask(Q)["cached"] is False

    def test_reloads_after_index_rebuild(self, svc: CopilotService, cfg: AppConfig) -> None:
        svc.ask(Q)
        p1 = svc._pipeline
        with Store(cfg.data_dir) as store:
            st = store.emb_path.stat()
            os.utime(store.emb_path, (st.st_atime, st.st_mtime + 10))
        svc.ask("what is CPT")
        assert svc._pipeline is not p1

    @pytest.mark.parametrize("q", ["", "   ", "x" * 1001])
    def test_bad_questions(self, svc: CopilotService, q: str) -> None:
        with pytest.raises(BadRequest):
            svc.ask(q)

    def test_not_ready_without_index(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path / "empty")
        with pytest.raises(NotReady):
            CopilotService(cfg, embedder_factory=FakeEmbedder, llm=None).ask("hi")

    def test_question_key(self) -> None:
        assert question_key("  What IS   OPT? ") == "what is opt?"


class TestTimeline:
    def test_computes(self, svc: CopilotService) -> None:
        out = svc.timeline({"program_end_date": "2027-05-15", "on_opt": "no"}, "2026-11-27")
        ids = {i["rule_id"] for i in out["items"]}
        assert {"opt-post-completion-filing-window", "grace-period-after-completion"} <= ids
        assert "not AI" in out["disclaimer"]

    def test_empty_strings_are_unknown(self, svc: CopilotService) -> None:
        out = svc.timeline({"program_end_date": "2027-05-15", "on_opt": ""}, "2026-11-27")
        assert any(n["rule_id"] == "grace-period-after-completion" for n in out["needs_info"])

    @pytest.mark.parametrize(("facts", "as_of"), [({"nope": 1}, None), ({"on_opt": "maybe"}, None),
                                                  ({}, "not-a-date")])
    def test_bad_input(self, svc: CopilotService, facts: dict[str, object], as_of: str | None) -> None:
        with pytest.raises(BadRequest):
            svc.timeline(facts, as_of)

    def test_personal_facts_are_never_persisted(self, svc: CopilotService, cfg: AppConfig) -> None:
        before = _snapshot_dir(cfg.data_dir)
        svc.timeline({"program_end_date": "2027-05-15", "address_change_date": "2026-11-20",
                      "on_opt": True}, "2026-11-27")
        assert _snapshot_dir(cfg.data_dir) == before


class TestMetadata:
    def test_rules_and_schema(self, svc: CopilotService) -> None:
        rules = svc.rules()
        assert len(rules) >= 10 and all(r["source_url"].startswith("https://") for r in rules)
        schema = svc.facts_schema()
        assert {f["name"] for f in schema} >= {"program_end_date", "on_opt"}
        assert next(f for f in schema if f["name"] == "degree_level")["options"]

    def test_changes(self, svc: CopilotService, cfg: AppConfig) -> None:
        assert svc.changes() == {"report": None}
        r = compare({"https://a/1": "h"}, [], {"test"}, {"https://a/1": "test"})
        write_report(r, cfg.data_dir / "changes")
        assert svc.changes()["report"]["unreachable"] == ["https://a/1"]

    def test_health(self, svc: CopilotService) -> None:
        h = svc.health()
        assert h["ok"] and h["index"]["chunks"] > 0 and "cached_answers" in h["index"]


class TestSchools:
    @pytest.fixture
    def school_cfg(self, cfg: AppConfig) -> AppConfig:
        return replace(cfg, sources=[replace(SOURCE, school="rutgers")])

    def test_school_specific_pages_only_for_that_school(self, school_cfg: AppConfig) -> None:
        svc = CopilotService(school_cfg, embedder_factory=FakeEmbedder, llm=None)
        assert svc.school_exclusions("rutgers") == set()
        assert svc.school_exclusions("ohio-state") == {"test"}
        assert svc.school_exclusions(None) == {"test"}
        assert not svc.ask(Q, school="rutgers")["refused"]
        other = svc.ask(Q, school="ohio-state")
        assert other["refused"] and other["citations"] == []  # only source belongs to Rutgers

    def test_cache_is_per_school(self, school_cfg: AppConfig) -> None:
        svc = CopilotService(school_cfg, embedder_factory=FakeEmbedder, llm=None)
        svc.ask(Q, school="rutgers")
        assert svc.ask(Q, school="rutgers")["cached"] is True
        assert svc.ask(Q, school="ohio-state")["cached"] is False

    @pytest.mark.parametrize("school", ["../etc", "x" * 41, "a b"])
    def test_invalid_school(self, svc: CopilotService, school: str) -> None:
        with pytest.raises(BadRequest):
            svc.ask(Q, school=school)

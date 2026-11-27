from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from copilot.changes import (
    compare,
    load_latest_report,
    recheck_index,
    recheck_snapshot,
    render,
    rule_flags,
    write_report,
)
from copilot.crawler import Crawler
from copilot.evaluation.dataset import load_snapshot, write_snapshot
from copilot.indexing import build_embeddings, crawl_sources
from copilot.models import FetchedPage
from copilot.store import Store
from copilot.timeline import Rule, load_rules

from .conftest import FakeEmbedder
from .test_crawler_store import BASE, SOURCE, FakeFetcher, _cfg, _page, _web


def _rules(tmp_path: Path, urls: list[str]) -> list[Rule]:
    d = tmp_path / "rules"
    d.mkdir(exist_ok=True)
    for i, url in enumerate(urls):
        (d / f"r{i}.yaml").write_text(yaml.safe_dump({
            "id": f"r{i}", "version": 1, "title": "t", "category": "c", "summary": "s",
            "source": {"url": url, "verification": "primary", "last_verified": "2026-11-27"},
            "outputs": [{"kind": "notice", "label": "l", "message": "m"}],
        }))
    return load_rules(d)


def _page_obj(url: str, h: str) -> FetchedPage:
    return FetchedPage(url=url, source="test", fetched_at="t", status_code=200, content_hash=h, html="")


class TestCompare:
    def test_classifies_pages(self) -> None:
        baseline = {"https://a/1": "h1", "https://a/2": "h2", "https://a/3": "h3"}
        pages = [_page_obj("https://a/1", "h1"), _page_obj("https://a/2", "CHANGED"),
                 _page_obj("https://a/4", "h4")]
        r = compare(baseline, pages, {"test"}, {u: "test" for u in baseline})
        assert r.unchanged == 1 and r.pages_checked == 3
        assert [c.url for c in r.changed] == ["https://a/2"]
        assert [c.url for c in r.new] == ["https://a/4"]
        assert r.unreachable == ["https://a/3"]
        assert r.has_content_changes

    def test_unreachable_only_for_checked_sources(self) -> None:
        r = compare({"https://a/1": "h"}, [], {"other"}, {"https://a/1": "test"})
        assert r.unreachable == []

    def test_rule_flags(self, tmp_path: Path) -> None:
        rules = _rules(tmp_path, ["https://a.gov/changed/", "https://a.gov/gone", "https://a.gov/fine",
                                  "https://irs.gov/elsewhere"])
        reverify, unmonitored = rule_flags(
            rules, changed={"https://A.gov/changed"}, unreachable={"https://a.gov/gone"},
            corpus_urls={"https://a.gov/changed", "https://a.gov/gone", "https://a.gov/fine"})
        assert {(f.rule_id, f.reason.split()[2]) for f in reverify} == {("r0", "content"), ("r1", "could")}
        assert [f.rule_id for f in unmonitored] == ["r3"]  # URL normalization: trailing slash, case


class TestRecheckIndex:
    def test_end_to_end(self, sample_html: str, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        emb = FakeEmbedder()
        web = _web(sample_html)
        with Store(tmp_path) as store:
            crawl_sources([SOURCE], Crawler(cfg.crawl, FakeFetcher(web)), store, cfg)
            build_embeddings(store, emb)
            store.put_cached_answer("q-travel", "cfg", {"text": "x"}, [f"{BASE}/travel"], "t")
            store.put_cached_answer("q-other", "cfg", {"text": "y"}, [BASE], "t")
            old_ids = store.chunk_ids_for_url(f"{BASE}/travel")

        # The travel page changes; everything else stays the same.
        web2 = dict(web)
        web2[f"{BASE}/travel"] = (200, _page("Travel", "The travel signature rules changed for OPT students in 2027."))
        rules = _rules(tmp_path, [f"{BASE}/travel", BASE, "https://www.irs.gov/x"])
        report = recheck_index(cfg, [SOURCE], Crawler(cfg.crawl, FakeFetcher(web2)), rules, emb)

        assert [c.url for c in report.changed] == [f"{BASE}/travel"]
        assert report.changed[0].chunks_added == 1 and report.changed[0].chunks_removed == 1
        assert report.unchanged == 1 and report.new == [] and report.unreachable == []
        assert report.stale_answers == 1
        assert [f.rule_id for f in report.rules_to_reverify] == ["r0"]
        assert [f.rule_id for f in report.unmonitored_rules] == ["r2"]

        with Store(tmp_path) as store:
            assert store.get_cached_answer("q-travel", "cfg") is None  # stale -> regenerated
            assert store.get_cached_answer("q-other", "cfg") == {"text": "y"}
            assert store.chunk_ids_for_url(f"{BASE}/travel") != old_ids
            loaded = store.load_embeddings()
            assert loaded is not None and set(loaded[0]) == {c.chunk_id for c in store.all_chunks()}

    def test_no_changes(self, sample_html: str, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        web = _web(sample_html)
        with Store(tmp_path) as store:
            crawl_sources([SOURCE], Crawler(cfg.crawl, FakeFetcher(web)), store, cfg)
        report = recheck_index(cfg, [SOURCE], Crawler(cfg.crawl, FakeFetcher(web)), [], None)
        assert not report.has_content_changes and report.unchanged == 2


class TestRecheckSnapshot:
    def test_read_only_diff(self, sample_html: str, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        web = _web(sample_html)
        with Store(tmp_path / "idx") as store:
            crawl_sources([SOURCE], Crawler(cfg.crawl, FakeFetcher(web)), store, cfg)
            write_snapshot(store.all_chunks(), tmp_path / "snap.jsonl")
        snap = load_snapshot(tmp_path / "snap.jsonl")
        web2 = dict(web)
        web2[BASE] = (200, sample_html.replace("temporary employment", "temporary paid employment"))
        other = replace(SOURCE, name="not-in-snapshot")
        report = recheck_snapshot(snap, [SOURCE, other], Crawler(cfg.crawl, FakeFetcher(web2)), [])
        assert [c.url for c in report.changed] == [BASE]
        assert report.baseline == "snapshot"


def test_report_roundtrip_and_render(tmp_path: Path) -> None:
    r = compare({"https://a/1": "h"}, [_page_obj("https://a/1", "x")], {"test"}, {"https://a/1": "test"})
    r.baseline = "index"
    write_report(r, tmp_path)
    loaded = load_latest_report(tmp_path)
    assert loaded is not None and loaded["has_content_changes"] is True
    assert len(list(tmp_path.glob("recheck-*.json"))) == 1
    assert "CHANGED  https://a/1" in render(r)
    assert load_latest_report(tmp_path / "missing") is None

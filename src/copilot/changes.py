"""Source change detection: re-crawl, diff, and flag everything that depends on a changed page.

The 2026 grace-period episode is the motivating case. A DHS rule changed the 60-day period
to 30 days, and a court later vacated it. Official pages update quietly when that
happens. This module re-crawls the allowlisted sources, compares each page's visible-text
hash with the baseline, and then reports:
  - which pages changed, appeared, or became unreachable;
  - which chunks were added or removed (a set diff, possible because chunk IDs are
    content-addressed);
  - which RULES cite a changed page and need re-verification by a human;
  - which rules cite pages we don't crawl at all, so changes there can't be detected;
  - how many cached Q&A answers cited a changed page (they are marked stale and
    regenerated on the next request).

There are two baselines:
  index:    the live local index. Pages are re-stored, re-chunked and re-embedded.
  snapshot: the committed eval snapshot. Read-only. Used by the scheduled CI job.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from copilot.config import AppConfig, Source
from copilot.crawler import Crawler, normalize_url, now_utc
from copilot.models import Chunk, FetchedPage
from copilot.timeline.schema import Rule

log = logging.getLogger(__name__)


@dataclass
class DocChange:
    url: str
    source: str
    status: str  # changed | new
    old_hash: str | None
    new_hash: str
    chunks_added: int = 0
    chunks_removed: int = 0


@dataclass
class RuleFlag:
    rule_id: str
    source_url: str
    reason: str


@dataclass
class ChangeReport:
    checked_at: str
    baseline: str
    pages_checked: int = 0
    unchanged: int = 0
    changed: list[DocChange] = field(default_factory=list)
    new: list[DocChange] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    rules_to_reverify: list[RuleFlag] = field(default_factory=list)
    unmonitored_rules: list[RuleFlag] = field(default_factory=list)
    stale_answers: int = 0

    @property
    def has_content_changes(self) -> bool:
        return bool(self.changed or self.new)

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["has_content_changes"] = self.has_content_changes
        return d


# --- pure helpers (unit-tested) ------------------------------------------------------

def rule_flags(
    rules: Iterable[Rule], changed: set[str], unreachable: set[str], corpus_urls: set[str]
) -> tuple[list[RuleFlag], list[RuleFlag]]:
    """Return (rules whose source changed or vanished, rules whose source we don't monitor)."""
    changed_n = {normalize_url(u) for u in changed}
    gone_n = {normalize_url(u) for u in unreachable}
    corpus_n = {normalize_url(u) for u in corpus_urls}
    reverify: list[RuleFlag] = []
    unmonitored: list[RuleFlag] = []
    for r in rules:
        u = normalize_url(r.source.url)
        if u in changed_n:
            reverify.append(RuleFlag(r.id, r.source.url, "source page content changed"))
        elif u in gone_n:
            reverify.append(RuleFlag(r.id, r.source.url, "source page could not be fetched"))
        elif u not in corpus_n:
            unmonitored.append(RuleFlag(r.id, r.source.url, "source page is not in the crawled corpus"))
    return reverify, unmonitored


def compare(
    baseline: dict[str, str],
    pages: Iterable[FetchedPage],
    sources_checked: set[str],
    baseline_sources: dict[str, str],
    on_page: Callable[[FetchedPage, str], tuple[int, int]] | None = None,
) -> ChangeReport:
    """Diff fetched pages against a {url: hash} baseline.

    on_page(page, status) is called for every fetched page and may persist it. It returns
    (chunks_added, chunks_removed) for changed or new pages.
    """
    report = ChangeReport(checked_at=now_utc(), baseline="")
    seen: set[str] = set()
    for page in pages:
        seen.add(page.url)
        report.pages_checked += 1
        old = baseline.get(page.url)
        status = "new" if old is None else ("unchanged" if old == page.content_hash else "changed")
        added, removed = on_page(page, status) if on_page else (0, 0)
        if status == "unchanged":
            report.unchanged += 1
            continue
        change = DocChange(page.url, page.source, status, old, page.content_hash, added, removed)
        (report.changed if status == "changed" else report.new).append(change)
    report.unreachable = sorted(
        u for u in baseline if u not in seen and baseline_sources.get(u) in sources_checked
    )
    return report


# --- recheck against the live index ----------------------------------------------------

def recheck_index(cfg: AppConfig, sources: list[Source], crawler: Crawler,
                  rules: list[Rule], embedder: object | None) -> ChangeReport:
    from copilot.indexing import build_embeddings, store_and_chunk
    from copilot.store import Store

    with Store(cfg.data_dir) as store:
        docs = store.documents()
        baseline = {d["url"]: d["content_hash"] for d in docs}
        baseline_sources = {d["url"]: d["source"] for d in docs}

        def persist(page: FetchedPage, status: str) -> tuple[int, int]:
            before = store.chunk_ids_for_url(page.url)
            store_and_chunk(page, store, cfg)
            if status == "unchanged":
                return 0, 0
            after = store.chunk_ids_for_url(page.url)
            return len(after - before), len(before - after)

        pages = (p for s in sources for p in crawler.crawl(s))
        report = compare(baseline, pages, {s.name for s in sources}, baseline_sources, persist)
        report.baseline = "index"

        changed_urls = {c.url for c in report.changed}
        if report.has_content_changes and embedder is not None:
            build_embeddings(store, embedder)  # type: ignore[arg-type]
        report.stale_answers = store.mark_answers_stale(changed_urls)
        corpus = {d["url"] for d in store.documents()}

    report.rules_to_reverify, report.unmonitored_rules = rule_flags(
        rules, changed_urls, set(report.unreachable), corpus)
    return report


# --- recheck against the committed snapshot (read-only, for CI) ------------------------

def recheck_snapshot(snapshot: list[Chunk], sources: list[Source], crawler: Crawler,
                     rules: list[Rule]) -> ChangeReport:
    baseline = {c.url: c.doc_hash for c in snapshot}
    baseline_sources = {c.url: c.source for c in snapshot}
    in_snapshot = set(baseline_sources.values())
    checked = [s for s in sources if s.name in in_snapshot]
    pages = (p for s in checked for p in crawler.crawl(s))
    report = compare(baseline, pages, {s.name for s in checked}, baseline_sources)
    report.baseline = "snapshot"
    report.rules_to_reverify, report.unmonitored_rules = rule_flags(
        rules, {c.url for c in report.changed}, set(report.unreachable), set(baseline))
    return report


# --- persistence -----------------------------------------------------------------------

def write_report(report: ChangeReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.to_dict(), indent=2)
    stamp = report.checked_at.replace(":", "").replace("-", "").split("+")[0]
    (out_dir / f"recheck-{stamp}.json").write_text(payload)
    latest = out_dir / "latest.json"
    latest.write_text(payload)
    return latest


def load_latest_report(out_dir: Path) -> dict[str, object] | None:
    p = out_dir / "latest.json"
    return json.loads(p.read_text()) if p.exists() else None


def render(report: ChangeReport) -> str:
    lines = [f"Recheck against {report.baseline} at {report.checked_at}",
             f"  pages checked: {report.pages_checked}, unchanged: {report.unchanged}, "
             f"changed: {len(report.changed)}, new: {len(report.new)}, "
             f"unreachable: {len(report.unreachable)}"]
    for c in report.changed:
        lines.append(f"  CHANGED  {c.url}  (+{c.chunks_added}/-{c.chunks_removed} chunks)")
    for c in report.new:
        lines.append(f"  NEW      {c.url}")
    for u in report.unreachable:
        lines.append(f"  UNREACHABLE {u}")
    if report.rules_to_reverify:
        lines.append("\nRules that need re-verification:")
        lines += [f"  - {f.rule_id}: {f.reason} ({f.source_url})" for f in report.rules_to_reverify]
    if report.unmonitored_rules:
        lines.append("\nRules whose source isn't crawled (changes can't be detected automatically):")
        lines += [f"  - {f.rule_id}: {f.source_url}" for f in report.unmonitored_rules]
    if report.baseline == "index":
        lines.append(f"\nCached answers marked stale: {report.stale_answers}")
    return "\n".join(lines)

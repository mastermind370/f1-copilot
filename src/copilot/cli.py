"""Command-line interface.

    copilot ingest [--source NAME]       crawl allowlisted sources, chunk, embed
    copilot import-html FILE --url URL --source NAME
    copilot reindex [--force]            re-chunk stored HTML and refresh embeddings (offline)
    copilot ask "question" [--json] [--debug]
    copilot timeline --facts FILE [--set k=v] [--as-of DATE] [--json]
    copilot rules check [--strict]
    copilot eval run|resolve|snapshot|sample
    copilot recheck [--baseline index|snapshot]   detect source changes
    copilot serve [--port 8000]          local HTTP API for the web UI
    copilot stats
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import textwrap
from dataclasses import asdict
from pathlib import Path

from copilot import DISCLAIMER
from copilot.config import AppConfig, ConfigError, load_config
from copilot.store import Store


def _embedder(cfg: AppConfig):  # type: ignore[no-untyped-def]
    from copilot.embeddings import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(cfg.retrieval.embedding_model)


def cmd_ingest(cfg: AppConfig, args: argparse.Namespace) -> int:
    from copilot.crawler import Crawler, HttpxFetcher
    from copilot.indexing import build_embeddings, crawl_sources

    sources = [cfg.source(args.source)] if args.source else cfg.sources
    fetcher = HttpxFetcher(cfg.crawl)
    try:
        with Store(cfg.data_dir) as store:
            report = crawl_sources(sources, Crawler(cfg.crawl, fetcher), store, cfg)
            print(f"Fetched {report.pages} pages ({report.changed_pages} new/changed), "
                  f"{report.chunks} chunks.")
            for name, n in report.per_source.items():
                flag = "  <- 0 pages: check logs for 403/robots/404" if n == 0 else ""
                print(f"  {name:<22} {n:>3} pages{flag}")
            print("Embedding chunks (first run downloads the model)...")
            new = build_embeddings(store, _embedder(cfg))
            print(f"Embedded {new} new chunks. Index: {store.stats()}")
    finally:
        fetcher.close()
    return 0


def cmd_import_html(cfg: AppConfig, args: argparse.Namespace) -> int:
    from copilot.crawler import is_allowed
    from copilot.indexing import build_embeddings, import_html_file

    source = cfg.source(args.source)
    if not is_allowed(args.url, source.allowed_prefixes):
        print(f"error: {args.url} is not within the allowlist for source {source.name!r}",
              file=sys.stderr)
        return 2
    with Store(cfg.data_dir) as store:
        n = import_html_file(Path(args.file), args.url, source.name, store, cfg)
        new = build_embeddings(store, _embedder(cfg))
        print(f"Imported {args.url}: {n} chunks, {new} newly embedded.")
    return 0


def cmd_reindex(cfg: AppConfig, args: argparse.Namespace) -> int:
    from copilot.indexing import build_embeddings, rechunk_from_raw

    with Store(cfg.data_dir) as store:
        n = rechunk_from_raw(store, cfg)
        new = build_embeddings(store, _embedder(cfg), force=args.force)
        print(f"Re-chunked into {n} chunks; embedded {new}. Index: {store.stats()}")
    return 0


def cmd_ask(cfg: AppConfig, args: argparse.Namespace) -> int:
    from copilot.answer import QAPipeline
    from copilot.llm import LLMError, make_llm
    from copilot.retrieval import HybridRetriever, IndexNotReadyError

    with Store(cfg.data_dir) as store:
        try:
            retriever = HybridRetriever.from_store(store, _embedder(cfg), cfg.retrieval)
        except IndexNotReadyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    pipeline = QAPipeline(retriever, make_llm(cfg.llm), cfg.retrieval, cfg.dso_message)
    try:
        answer = pipeline.ask(args.question)
    except LLMError as exc:
        print(f"error: {exc}\nTip: start Ollama (`ollama serve`) or set llm.provider: none",
              file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(asdict(answer), indent=2, ensure_ascii=False))
        return 0

    print()
    print(textwrap.indent(answer.text, "  "))
    print()
    if answer.citations:
        print("Sources:")
        for c in answer.citations:
            print(f"  [{c.chunk_id}] {c.heading}\n      {c.url}  (retrieved {c.retrieved_at[:10]})")
    print(f"\nconfidence={answer.confidence:.3f}"
          + (f"  refused ({answer.reason})" if answer.refused else ""))
    if args.debug and answer.dropped_sentences:
        print("\nDropped (uncited) sentences:")
        for s in answer.dropped_sentences:
            print(f"  - {s}")
    print(f"\n{DISCLAIMER}")
    return 0


def _load_facts(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    import yaml

    from copilot.timeline.facts import parse_facts

    raw: dict[str, object] = {}
    if args.facts:
        loaded = yaml.safe_load(Path(args.facts).read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{args.facts} must contain key: value pairs")
        raw.update(loaded)
    for item in args.set or []:
        if "=" not in item:
            raise ValueError(f"--set expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        raw[key.strip()] = value.strip()
    return parse_facts(raw)


def _fmt_item(item) -> list[str]:  # type: ignore[no-untyped-def]
    if item.kind == "window":
        when = f"{item.start} -> {item.end}"
    elif item.kind in {"deadline", "earliest"}:
        when = str(item.date)
    elif item.kind == "limit":
        when = f"{item.value} {item.unit}"
    else:
        when = ""
    rel = ""
    if item.days_until is not None and item.status == "upcoming":
        rel = f"  (in {item.days_until} days)"
    elif item.status == "active":
        rel = "  (OPEN NOW)" if item.kind == "window" else ""
    lines = [f"  [{item.status.upper():<8}] {item.label}: {when}{rel}"]
    if item.message:
        lines.append(textwrap.fill(item.message, 88, initial_indent="      ",
                                   subsequent_indent="      "))
    lines += [f"      how: {step}" for step in item.explanation]
    cite = f" ({item.citation})" if item.citation else ""
    lines.append(f"      rule: {item.rule_id} v{item.rule_version} | source{cite}: {item.source_url}")
    flag = "" if item.verification == "primary" else "  <- verified via secondary sources"
    lines.append(f"      last verified: {item.last_verified}{flag}")
    for note in item.notes:
        lines.append(textwrap.fill(f"note: {note}", 88, initial_indent="      ",
                                   subsequent_indent="        "))
    return lines


def cmd_timeline(cfg: AppConfig, args: argparse.Namespace) -> int:
    from datetime import date

    from copilot.timeline import RuleValidationError, evaluate, load_rules
    from copilot.timeline.facts import FactError

    try:
        rules = load_rules(cfg.rules.dir)
        facts = _load_facts(args)
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    except (RuleValidationError, FactError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tl = evaluate(rules, facts, as_of, cfg.rules.max_age_days)

    if args.json:
        print(json.dumps(asdict(tl), indent=2, default=str))
        return 0

    print(f"\nYour F-1 timeline as of {as_of}\n")
    groups = [("Open now and upcoming", ("active", "upcoming")), ("Limits and notices", ("info",)),
              ("Already passed", ("past",))]
    for title, statuses in groups:
        items = [i for i in tl.items if i.status in statuses]
        if items:
            print(title)
            for item in items:
                print("\n".join(_fmt_item(item)))
                print()
    if tl.needs_info:
        print("Add these facts to compute more of your timeline:")
        for n in tl.needs_info:
            print(f"  - {n.title}: needs {', '.join(n.missing)}")
        print()
    if tl.stale_rules:
        print(f"WARNING: rules not re-verified in {cfg.rules.max_age_days} days: "
              f"{', '.join(tl.stale_rules)}\n")
    print("Dates are computed by fixed rules, not AI. " + DISCLAIMER)
    return 0


def cmd_rules_check(cfg: AppConfig, args: argparse.Namespace) -> int:
    from datetime import date

    from copilot.timeline import RuleValidationError, load_rules

    try:
        rules = load_rules(cfg.rules.dir)
    except RuleValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    today = date.today()
    stale = 0
    print(f"{len(rules)} rules valid in {cfg.rules.dir}\n")
    for r in rules:
        age = (today - r.source.last_verified).days
        flags = []
        if age > cfg.rules.max_age_days:
            flags.append("STALE")
            stale += 1
        if r.source.verification != "primary":
            flags.append("secondary-verified")
        print(f"  {r.id:<36} v{r.version}  verified {r.source.last_verified} ({age}d ago)"
              + (f"  [{', '.join(flags)}]" if flags else ""))
    return 1 if (stale and args.strict) else 0


def _eval_items(cfg: AppConfig, args: argparse.Namespace):  # type: ignore[no-untyped-def]
    from copilot.evaluation.dataset import load_dataset

    if args.dataset:
        paths = [Path(args.dataset)] if Path(args.dataset).is_file() else sorted(Path().glob(args.dataset))
    else:
        paths = sorted(cfg.evaluation.base_dir.glob(cfg.evaluation.dataset_glob))
    if not paths:
        raise FileNotFoundError(f"no dataset files found for {args.dataset or cfg.evaluation.dataset_glob}")
    return load_dataset(paths)


def _eval_corpus(cfg: AppConfig, corpus: str | None):  # type: ignore[no-untyped-def]
    from copilot.evaluation.dataset import load_snapshot

    if corpus:
        return load_snapshot(Path(corpus)), corpus
    with Store(cfg.data_dir) as store:
        return store.all_chunks(), "live index"


def cmd_eval_run(cfg: AppConfig, args: argparse.Namespace) -> int:
    from datetime import UTC, datetime

    import yaml

    from copilot.answer import QAPipeline
    from copilot.evaluation.dataset import DatasetError, resolve_gold
    from copilot.evaluation.metrics import check_thresholds, ratchet_thresholds
    from copilot.evaluation.report import to_markdown
    from copilot.evaluation.runner import results_as_dicts, run_items, summarize
    from copilot.llm import make_llm
    from copilot.retrieval import HybridRetriever, IndexNotReadyError

    try:
        items = _eval_items(cfg, args)
        chunks, corpus_name = _eval_corpus(cfg, args.corpus)
    except (DatasetError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not chunks:
        print("error: corpus is empty; run `copilot ingest` or pass --corpus", file=sys.stderr)
        return 2

    embedder = _embedder(cfg)
    if args.corpus:
        print(f"Embedding {len(chunks)} snapshot chunks...")
        matrix = embedder.embed_passages([c.index_text for c in chunks])
        retriever = HybridRetriever(chunks, matrix, embedder, cfg.retrieval)
    else:
        with Store(cfg.data_dir) as store:
            try:
                retriever = HybridRetriever.from_store(store, embedder, cfg.retrieval)
            except IndexNotReadyError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2

    answers = args.answers or args.faithfulness
    pipeline = (QAPipeline(retriever, make_llm(cfg.llm), cfg.retrieval, cfg.dso_message)
                if answers else None)
    judge = None
    if args.faithfulness:
        from copilot.evaluation.faithfulness import NLIJudge

        judge = NLIJudge(cfg.evaluation.faithfulness_model)

    resolution = resolve_gold(items, retriever.chunks)
    results = run_items(items, resolution, retriever, pipeline, judge)
    summary = summarize(results, cfg.retrieval.min_confidence)
    meta = {
        "corpus": corpus_name, "n_chunks": len(retriever.chunks),
        "embedding_model": cfg.retrieval.embedding_model,
        "answers": f"{cfg.llm.provider}:{cfg.llm.model}" if answers else "retrieval only",
        "run_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "too_broad_gold": resolution.too_broad,
    }

    out_dir = cfg.evaluation.results_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(
        {"meta": meta, "summary": summary, "items": results_as_dicts(results)},
        indent=2, ensure_ascii=False, default=str))
    md = to_markdown(summary, meta)
    (out_dir / "latest.md").write_text(md)
    print(md)
    print(f"Wrote {out_dir / 'latest.json'} and {out_dir / 'latest.md'}")

    thresholds_path = cfg.evaluation.thresholds
    if args.update_thresholds:
        current = yaml.safe_load(thresholds_path.read_text()) or {}
        new = ratchet_thresholds(summary, current)
        header = ("# CI quality gates, ratcheted to (measured - 0.05) by "
                  "`copilot eval run --update-thresholds`.\n")
        thresholds_path.write_text(header + yaml.safe_dump(new, sort_keys=True))
        print(f"Updated {thresholds_path}")

    if args.check:
        gates = yaml.safe_load(Path(args.check).read_text()) or {}
        failures = check_thresholds(summary, gates)
        if failures:
            print("\nQUALITY GATE FAILED:")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("\nAll quality gates passed.")
    return 0


def cmd_eval_resolve(cfg: AppConfig, args: argparse.Namespace) -> int:
    from copilot.evaluation.dataset import TOO_BROAD, DatasetError, resolve_gold

    try:
        items = _eval_items(cfg, args)
        chunks, corpus_name = _eval_corpus(cfg, args.corpus)
    except (DatasetError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    res = resolve_gold(items, chunks)
    by_id = {c.chunk_id: c for c in chunks}
    print(f"Resolving {len(items)} items against {corpus_name} ({len(chunks)} chunks)\n")
    for item in items:
        if item.should_refuse:
            continue
        ids = res.gold_ids[item.id]
        flag = "UNRESOLVED" if not ids else ("TOO BROAD" if len(ids) > TOO_BROAD else "ok")
        print(f"  {item.id:<18} {len(ids):>4} gold  [{flag}]")
        if args.verbose_matches and ids:
            for cid in sorted(ids)[:3]:
                c = by_id[cid]
                print(f"      {cid} {c.url}\n        {c.text[:110]}...")
    print(f"\nunresolved: {len(res.unresolved)}  too broad (> {TOO_BROAD}): {len(res.too_broad)}")
    return 0


def cmd_eval_snapshot(cfg: AppConfig, args: argparse.Namespace) -> int:
    from copilot.evaluation.dataset import write_snapshot

    # University pages are copyrighted, so every school-tagged source stays out of the committed
    # snapshot automatically, on top of anything listed in snapshot_exclude_sources.
    excluded = set(cfg.evaluation.snapshot_exclude_sources) | {s.name for s in cfg.sources if s.school}
    with Store(cfg.data_dir) as store:
        chunks = [c for c in store.all_chunks() if c.source not in excluded]
    if not chunks:
        print("error: no chunks to snapshot; run `copilot ingest` first", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else cfg.evaluation.snapshot
    n = write_snapshot(chunks, out)
    sources = sorted({c.source for c in chunks})
    print(f"Wrote {n} chunks from {', '.join(sources)} to {out}")
    print(f"(excluded sources: {', '.join(sorted(excluded)) or 'none'})")
    return 0


def cmd_eval_sample(cfg: AppConfig, args: argparse.Namespace) -> int:
    import random

    from copilot.evaluation.dataset import DatasetError, resolve_gold

    try:
        items = _eval_items(cfg, args)
        chunks, _ = _eval_corpus(cfg, args.corpus)
    except (DatasetError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    covered = set().union(*resolve_gold(items, chunks).gold_ids.values())
    pool = [c for c in chunks if c.chunk_id not in covered and len(c.text.split()) >= 25]
    rng = random.Random(args.seed)
    by_source: dict[str, list] = {}  # type: ignore[type-arg]
    for c in pool:
        by_source.setdefault(c.source, []).append(c)
    for lst in by_source.values():
        rng.shuffle(lst)
    picked = []
    while len(picked) < args.n and any(by_source.values()):
        for src in sorted(by_source):  # round-robin so every source is represented
            if by_source[src] and len(picked) < args.n:
                picked.append(by_source[src].pop())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in picked:
            f.write(json.dumps({
                "id": f"draft-{c.chunk_id}", "language": "en", "question": "",
                "should_refuse": False, "group": "",
                "gold": [{"phrases": [" ".join(c.text.split()[:8])], "url_contains": c.url}],
                "translation_of": None, "notes": "",
                "_heading": c.heading, "_chunk_text": c.text,
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(picked)} draft items to {out}. Fill in each \"question\" with something a "
          "student would ask that this passage answers, then move them into eval/dataset/.")
    return 0


def cmd_recheck(cfg: AppConfig, args: argparse.Namespace) -> int:
    """Exit codes: 0 = no content changes, 3 = pages changed (useful for schedulers and CI)."""
    from copilot.changes import recheck_index, recheck_snapshot, render, write_report
    from copilot.crawler import Crawler, HttpxFetcher
    from copilot.evaluation.dataset import load_snapshot
    from copilot.timeline import load_rules

    rules = load_rules(cfg.rules.dir)
    sources = [cfg.source(args.source)] if args.source else cfg.sources
    fetcher = HttpxFetcher(cfg.crawl)
    try:
        crawler = Crawler(cfg.crawl, fetcher)
        if args.baseline == "snapshot":
            report = recheck_snapshot(load_snapshot(cfg.evaluation.snapshot), sources, crawler, rules)
            out_dir = Path(args.out) if args.out else cfg.evaluation.results_dir
        else:
            report = recheck_index(cfg, sources, crawler, rules, _embedder(cfg))
            out_dir = Path(args.out) if args.out else cfg.data_dir / "changes"
    finally:
        fetcher.close()
    path = write_report(report, out_dir)
    print(render(report))
    print(f"\nReport written to {path}")
    return 3 if report.has_content_changes else 0


def cmd_serve(cfg: AppConfig, args: argparse.Namespace) -> int:
    import uvicorn

    from copilot.api.app import create_app

    # In production, set COPILOT_ALLOWED_ORIGINS to your web app's URL(s), comma-separated,
    # e.g. https://f1-copilot.vercel.app. Localhost origins are the default for development.
    origins = [o.strip().rstrip("/") for o in os.environ.get("COPILOT_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    port = int(os.environ.get("PORT", args.port))  # Render, Fly and Hugging Face set PORT
    print(f"F-1 Copilot API on http://{args.host}:{port}  (docs at /docs)")
    if origins:
        print(f"Allowed origins: {', '.join(origins)}")
    uvicorn.run(create_app(cfg, allowed_origins=origins or None), host=args.host, port=port, log_level="warning")
    return 0


def cmd_places_check(cfg: AppConfig, args: argparse.Namespace) -> int:
    """Test the free OpenStreetMap listings end to end and print what happened."""
    from copilot.osm import OsmPlaces
    from copilot.places import PlacesError

    osm = OsmPlaces(cfg.data_dir / "osm_cache.json")
    print(f"Looking up {args.category} near {args.near} (the first lookup for a city can take up to a minute)...")
    try:
        places = osm.search(args.category, args.near)
    except PlacesError as exc:
        print(f"FAILED ({exc.code}): {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(places)} result(s)")
    for p in places:
        print(f"  {p['name']}  ({p['distanceKm']} km)  {', '.join(p['cuisine'])}")
    return 0


def cmd_employers_import(cfg: AppConfig, args: argparse.Namespace) -> int:
    """Import USCIS H-1B Employer Data Hub and DOL LCA disclosure files into data/employers.db."""
    from copilot.employers import connect, import_file

    con = connect(cfg.data_dir / "employers.db")
    failed = 0
    for name in args.files:
        path = Path(name).expanduser()
        if not path.exists():
            print(f"{name}: file not found", file=sys.stderr)
            failed += 1
            continue
        print(f"Reading {path.name} (large Excel files can take a few minutes)...")
        try:
            import_file(con, path)
        except ValueError as exc:
            print(f"skipped {exc}", file=sys.stderr)
            failed += 1
    n = con.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
    print(f"Employer database now has {n:,} employers: {cfg.data_dir / 'employers.db'}")
    return 1 if failed else 0


def cmd_stats(cfg: AppConfig, args: argparse.Namespace) -> int:
    with Store(cfg.data_dir) as store:
        print(json.dumps(store.stats(), indent=2))
        for d in store.documents():
            print(f"  {d['source']:<22} {d['fetched_at'][:10]}  {d['url']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copilot", description="F-1 Compliance Copilot")
    p.add_argument("--config", default="config.yaml", help="path to config.yaml")
    p.add_argument("-v", "--verbose", action="store_true", help="show crawl logs")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("ingest", help="crawl, chunk and embed allowlisted sources")
    s.add_argument("--source", help="only this source name")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("import-html", help="import a page saved from your browser")
    s.add_argument("file")
    s.add_argument("--url", required=True, help="the page's real URL (for citations)")
    s.add_argument("--source", required=True)
    s.set_defaults(func=cmd_import_html)

    s = sub.add_parser("reindex", help="re-chunk stored HTML and refresh embeddings (offline)")
    s.add_argument("--force", action="store_true", help="re-embed everything")
    s.set_defaults(func=cmd_reindex)

    s = sub.add_parser("ask", help="ask a question")
    s.add_argument("question")
    s.add_argument("--json", action="store_true")
    s.add_argument("--debug", action="store_true", help="show sentences dropped for missing citations")
    s.set_defaults(func=cmd_ask)

    s = sub.add_parser("timeline", help="compute your personal deadlines (deterministic rules)")
    s.add_argument("--facts", help="YAML file of your facts (see examples/facts.example.yaml)")
    s.add_argument("--set", action="append", metavar="KEY=VALUE", help="set or override one fact")
    s.add_argument("--as-of", help="compute as if today were this date (YYYY-MM-DD)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_timeline)

    s = sub.add_parser("rules", help="rule maintenance")
    rsub = s.add_subparsers(dest="rules_command", required=True)
    r = rsub.add_parser("check", help="validate all rules and report verification age")
    r.add_argument("--strict", action="store_true", help="exit non-zero if any rule is stale")
    r.set_defaults(func=cmd_rules_check)

    s = sub.add_parser("eval", help="evaluation harness")
    esub = s.add_subparsers(dest="eval_command", required=True)

    def _common(e: argparse.ArgumentParser) -> None:
        e.add_argument("--dataset", help="JSONL file or glob (default: evaluation.dataset_glob)")
        e.add_argument("--corpus", help="snapshot JSONL to evaluate against (default: live index)")

    e = esub.add_parser("run", help="run the eval and write eval/results/latest.{json,md}")
    _common(e)
    e.add_argument("--answers", action="store_true", help="also run full answering (uses llm.provider)")
    e.add_argument("--faithfulness", action="store_true", help="NLI-judge English answers (implies --answers)")
    e.add_argument("--check", metavar="THRESHOLDS", help="exit 1 if any quality gate fails")
    e.add_argument("--update-thresholds", action="store_true", help="ratchet gates to measured - 0.05")
    e.set_defaults(func=cmd_eval_run)

    e = esub.add_parser("resolve", help="show which chunks each item's gold matchers hit")
    _common(e)
    e.add_argument("--verbose-matches", action="store_true")
    e.set_defaults(func=cmd_eval_resolve)

    e = esub.add_parser("snapshot", help="freeze the public-domain corpus for reproducible CI")
    e.add_argument("--out", help="output path (default: evaluation.snapshot)")
    e.set_defaults(func=cmd_eval_snapshot)

    e = esub.add_parser("sample", help="draft new eval items from uncovered chunks")
    _common(e)
    e.add_argument("--n", type=int, default=25)
    e.add_argument("--seed", type=int, default=7)
    e.add_argument("--out", default="eval/drafts/drafts.jsonl")
    e.set_defaults(func=cmd_eval_sample)

    s = sub.add_parser("recheck", help="re-crawl sources and report what changed")
    s.add_argument("--baseline", choices=["index", "snapshot"], default="index",
                   help="index: update the live index (default). snapshot: read-only diff vs. eval snapshot")
    s.add_argument("--source", help="only this source name")
    s.add_argument("--out", help="directory for the JSON report")
    s.set_defaults(func=cmd_recheck)

    s = sub.add_parser("serve", help="run the local HTTP API for the web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("stats", help="show index statistics")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("employers", help="visa-sponsor employer data")
    esub = s.add_subparsers(dest="employers_cmd", required=True)
    e = esub.add_parser("import", help="import USCIS H-1B Data Hub and/or DOL LCA files (.csv or .xlsx)")
    e.add_argument("files", nargs="+")
    e.set_defaults(func=cmd_employers_import)

    s = sub.add_parser("places-check", help="test the OpenStreetMap restaurant and grocery listings")
    s.add_argument("--near", default="New Brunswick, NJ")
    s.add_argument("--category", default="dine.indian")
    s.set_defaults(func=cmd_places_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    return int(args.func(cfg, args))


if __name__ == "__main__":
    raise SystemExit(main())

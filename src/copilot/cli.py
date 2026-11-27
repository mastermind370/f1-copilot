"""Command-line interface.

    copilot ingest [--source NAME]       crawl allowlisted sources, chunk, embed
    copilot import-html FILE --url URL --source NAME
    copilot reindex [--force]            re-chunk stored HTML and refresh embeddings (offline)
    copilot ask "question" [--json] [--debug]
    copilot timeline --facts FILE [--set k=v] [--as-of DATE] [--json]
    copilot rules check [--strict]
    copilot stats
"""

from __future__ import annotations

import argparse
import json
import logging
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

    s = sub.add_parser("stats", help="show index statistics")
    s.set_defaults(func=cmd_stats)
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

"""Command-line interface.

    copilot ingest [--source NAME]       crawl allowlisted sources, chunk, embed
    copilot import-html FILE --url URL --source NAME
    copilot reindex [--force]            re-chunk stored HTML and refresh embeddings (offline)
    copilot ask "question" [--json] [--debug]
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

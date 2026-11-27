"""Orchestration for building the corpus: crawl -> store -> chunk -> embed.

Embeddings are cached by chunk ID. Chunk IDs are content-addressed, so only new or
changed chunks are re-embedded on later runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from copilot.chunker import chunk_html
from copilot.config import AppConfig, Source
from copilot.crawler import Crawler, content_hash, now_utc
from copilot.embeddings import Embedder
from copilot.models import FetchedPage
from copilot.parsing import visible_text
from copilot.store import Store

log = logging.getLogger(__name__)


@dataclass
class IngestReport:
    pages: int = 0
    changed_pages: int = 0
    chunks: int = 0
    newly_embedded: int = 0
    per_source: dict[str, int] = field(default_factory=dict)


def store_and_chunk(page: FetchedPage, store: Store, cfg: AppConfig) -> tuple[int, bool]:
    changed = store.previous_hash(page.url) != page.content_hash
    store.save_page(page)
    chunks = chunk_html(
        url=page.url, source=page.source, html=page.html,
        retrieved_at=page.fetched_at, doc_hash=page.content_hash, cfg=cfg.chunking,
    )
    return store.replace_chunks(page.url, chunks), changed


def crawl_sources(
    sources: list[Source], crawler: Crawler, store: Store, cfg: AppConfig
) -> IngestReport:
    report = IngestReport()
    for source in sources:
        count = 0
        for page in crawler.crawl(source):
            n_chunks, changed = store_and_chunk(page, store, cfg)
            report.pages += 1
            report.changed_pages += int(changed)
            report.chunks += n_chunks
            count += 1
            log.info("[%s] %s -> %d chunks%s", source.name, page.url, n_chunks,
                     " (changed)" if changed else "")
        report.per_source[source.name] = count
    return report


def import_html_file(path: Path, url: str, source: str, store: Store, cfg: AppConfig) -> int:
    """Add a page saved manually from a browser (for sites that block automated clients)."""
    html = path.read_text(encoding="utf-8", errors="replace")
    page = FetchedPage(
        url=url, source=source, fetched_at=now_utc(), status_code=200,
        content_hash=content_hash(visible_text(html)), html=html,
    )
    n, _ = store_and_chunk(page, store, cfg)
    return n


def rechunk_from_raw(store: Store, cfg: AppConfig) -> int:
    """Rebuild all chunks from stored raw HTML, with no network. Use after changing chunking settings."""
    total = 0
    for doc in store.documents():
        html = Path(doc["raw_path"]).read_text(encoding="utf-8", errors="replace")
        chunks = chunk_html(
            url=doc["url"], source=doc["source"], html=html,
            retrieved_at=doc["fetched_at"], doc_hash=doc["content_hash"], cfg=cfg.chunking,
        )
        total += store.replace_chunks(doc["url"], chunks)
    return total


def build_embeddings(store: Store, embedder: Embedder, force: bool = False) -> int:
    """Embed every chunk in the DB, reusing cached vectors. Returns number newly embedded."""
    chunks = store.all_chunks()
    cached: dict[str, np.ndarray] = {}
    loaded = store.load_embeddings()
    if loaded is not None and not force and loaded[2] == embedder.name:
        ids, matrix, _ = loaded
        cached = {cid: matrix[i] for i, cid in enumerate(ids)}

    todo = [c for c in chunks if c.chunk_id not in cached]
    if todo:
        vecs = embedder.embed_passages([c.index_text for c in todo])
        for c, v in zip(todo, vecs, strict=True):
            cached[c.chunk_id] = v

    ids = [c.chunk_id for c in chunks]
    dim = next(iter(cached.values())).shape[0] if cached else 0
    matrix = np.stack([cached[i] for i in ids]) if ids else np.zeros((0, dim), dtype=np.float32)
    store.save_embeddings(ids, matrix, embedder.name)
    return len(todo)

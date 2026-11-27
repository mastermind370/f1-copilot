"""Local persistence: SQLite for documents and chunks, a .npy matrix for embeddings.

Why not FAISS? The corpus is a few thousand chunks. A brute-force matrix-vector product
over normalized float32 vectors takes well under a millisecond at this size, and it has
no extra native dependency. The `Store` interface hides that choice, so swapping in FAISS
later is a local change.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from urllib.parse import urlparse

import numpy as np

from copilot.models import Chunk, FetchedPage

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    url           TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    fetched_at    TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    content_hash  TEXT NOT NULL,
    raw_path      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id      TEXT PRIMARY KEY,
    url           TEXT NOT NULL REFERENCES documents(url) ON DELETE CASCADE,
    source        TEXT NOT NULL,
    heading       TEXT NOT NULL,
    text          TEXT NOT NULL,
    retrieved_at  TEXT NOT NULL,
    doc_hash      TEXT NOT NULL,
    position      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_url ON chunks(url);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Answers are cached per (normalized question, config). Each row records which source URLs
-- it cited, so change detection can mark exactly the answers that depend on a changed page.
CREATE TABLE IF NOT EXISTS answer_cache (
    question_key  TEXT NOT NULL,
    config_key    TEXT NOT NULL,
    answer_json   TEXT NOT NULL,
    cited_urls    TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    stale         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (question_key, config_key)
);
"""

CHUNK_COLS = "chunk_id, url, source, heading, text, retrieved_at, doc_hash, position"


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.raw_dir = data_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.emb_path = data_dir / "embeddings.npy"
        self.emb_ids_path = data_dir / "embedding_ids.json"
        self.conn = sqlite3.connect(data_dir / "copilot.db")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    # context manager -------------------------------------------------------
    def __enter__(self) -> Store:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # documents -------------------------------------------------------------
    def raw_path_for(self, url: str) -> Path:
        host = urlparse(url).netloc or "local"
        name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".html"
        return self.raw_dir / host / name

    def previous_hash(self, url: str) -> str | None:
        row = self.conn.execute(
            "SELECT content_hash FROM documents WHERE url = ?", (url,)
        ).fetchone()
        return None if row is None else str(row[0])

    def save_page(self, page: FetchedPage) -> Path:
        path = self.raw_path_for(page.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page.html, encoding="utf-8")
        with self.conn:
            self.conn.execute(
                """INSERT INTO documents (url, source, fetched_at, status_code, content_hash, raw_path)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(url) DO UPDATE SET
                     source=excluded.source, fetched_at=excluded.fetched_at,
                     status_code=excluded.status_code, content_hash=excluded.content_hash,
                     raw_path=excluded.raw_path""",
                (page.url, page.source, page.fetched_at, page.status_code,
                 page.content_hash, str(path)),
            )
        return path

    def documents(self) -> list[dict[str, str]]:
        cur = self.conn.execute(
            "SELECT url, source, fetched_at, content_hash, raw_path FROM documents ORDER BY url"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    # chunks ----------------------------------------------------------------
    def replace_chunks(self, url: str, chunks: Iterable[Chunk]) -> int:
        rows = [
            (c.chunk_id, c.url, c.source, c.heading, c.text, c.retrieved_at, c.doc_hash, c.position)
            for c in chunks
        ]
        with self.conn:
            self.conn.execute("DELETE FROM chunks WHERE url = ?", (url,))
            self.conn.executemany(
                f"INSERT OR IGNORE INTO chunks ({CHUNK_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def chunk_ids_for_url(self, url: str) -> set[str]:
        rows = self.conn.execute("SELECT chunk_id FROM chunks WHERE url = ?", (url,)).fetchall()
        return {str(r[0]) for r in rows}

    def all_chunks(self) -> list[Chunk]:
        cur = self.conn.execute(f"SELECT {CHUNK_COLS} FROM chunks ORDER BY url, position")
        return [Chunk(*row) for row in cur.fetchall()]

    # embeddings ------------------------------------------------------------
    def save_embeddings(self, ids: list[str], matrix: np.ndarray, model_name: str) -> None:
        if matrix.shape[0] != len(ids):
            raise ValueError("embedding rows must match ids")
        np.save(self.emb_path, matrix.astype(np.float32))
        self.emb_ids_path.write_text(json.dumps({"model": model_name, "ids": ids}))

    def load_embeddings(self) -> tuple[list[str], np.ndarray, str] | None:
        if not (self.emb_path.exists() and self.emb_ids_path.exists()):
            return None
        meta = json.loads(self.emb_ids_path.read_text())
        matrix = np.load(self.emb_path)
        return list(meta["ids"]), matrix, str(meta["model"])

    # answer cache ----------------------------------------------------------
    def get_cached_answer(self, question_key: str, config_key: str) -> dict[str, object] | None:
        row = self.conn.execute(
            "SELECT answer_json FROM answer_cache WHERE question_key = ? AND config_key = ? AND stale = 0",
            (question_key, config_key),
        ).fetchone()
        return None if row is None else dict(json.loads(row[0]))

    def put_cached_answer(
        self, question_key: str, config_key: str, answer: dict[str, object],
        cited_urls: list[str], created_at: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO answer_cache (question_key, config_key, answer_json, cited_urls, created_at, stale)
                   VALUES (?, ?, ?, ?, ?, 0)
                   ON CONFLICT(question_key, config_key) DO UPDATE SET
                     answer_json=excluded.answer_json, cited_urls=excluded.cited_urls,
                     created_at=excluded.created_at, stale=0""",
                (question_key, config_key, json.dumps(answer, ensure_ascii=False),
                 json.dumps(sorted(set(cited_urls))), created_at),
            )

    def mark_answers_stale(self, urls: set[str]) -> int:
        """Flag every cached answer that cites any of these URLs. Returns how many were flagged."""
        if not urls:
            return 0
        rows = self.conn.execute(
            "SELECT question_key, config_key, cited_urls FROM answer_cache WHERE stale = 0"
        ).fetchall()
        hit = [(q, c) for q, c, cited in rows if urls & set(json.loads(cited))]
        with self.conn:
            self.conn.executemany(
                "UPDATE answer_cache SET stale = 1 WHERE question_key = ? AND config_key = ?", hit
            )
        return len(hit)

    def cache_stats(self) -> dict[str, int]:
        total, stale = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(stale), 0) FROM answer_cache"
        ).fetchone()
        return {"cached_answers": int(total), "stale_answers": int(stale)}

    # stats -----------------------------------------------------------------
    def stats(self) -> dict[str, int]:
        docs = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        loaded = self.load_embeddings()
        return {"documents": docs, "chunks": chunks, "embeddings": 0 if loaded is None else len(loaded[0])}

"""Sections -> retrieval chunks.

Strategy: pack whole paragraphs into windows of at most `max_words`, never crossing a
section boundary. A single paragraph longer than the limit is split into overlapping
word windows. Paragraph-aligned chunks keep each rule's sentence intact, which matters
more for legal-style text than perfectly uniform chunk sizes.
"""

from __future__ import annotations

import hashlib

from copilot.config import ChunkConfig
from copilot.models import Chunk
from copilot.parsing import extract_sections


def make_chunk_id(url: str, heading: str, text: str) -> str:
    """Content-addressed ID. Same content -> same ID across re-crawls, so embeddings can be
    reused and Stage 4 change detection can diff by ID."""
    digest = hashlib.sha256(f"{url}\n{heading}\n{text}".encode()).hexdigest()
    return digest[:12]


def _split_long(words: list[str], max_words: int, overlap: int) -> list[list[str]]:
    step = max_words - overlap
    out: list[list[str]] = []
    for start in range(0, len(words), step):
        out.append(words[start : start + max_words])
        if start + max_words >= len(words):
            break
    return out


def pack_paragraphs(paragraphs: list[str], cfg: ChunkConfig) -> list[str]:
    pieces: list[list[str]] = []
    for p in paragraphs:
        words = p.split()
        if len(words) <= cfg.max_words:
            pieces.append(words)
        else:
            pieces.extend(_split_long(words, cfg.max_words, cfg.overlap_words))

    windows: list[list[str]] = []
    current: list[str] = []
    for piece in pieces:
        if current and len(current) + len(piece) > cfg.max_words:
            windows.append(current)
            current = []
        current = current + piece
    if current:
        windows.append(current)

    return [" ".join(w) for w in windows if len(w) >= cfg.min_words]


def chunk_html(
    *,
    url: str,
    source: str,
    html: str,
    retrieved_at: str,
    doc_hash: str,
    cfg: ChunkConfig,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for section in extract_sections(html):
        for text in pack_paragraphs(section.paragraphs, cfg):
            chunk_id = make_chunk_id(url, section.heading, text)
            if chunk_id in seen:  # identical repeated block on one page
                continue
            seen.add(chunk_id)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    url=url,
                    source=source,
                    heading=section.heading,
                    text=text,
                    retrieved_at=retrieved_at,
                    doc_hash=doc_hash,
                    position=len(chunks),
                )
            )
    return chunks

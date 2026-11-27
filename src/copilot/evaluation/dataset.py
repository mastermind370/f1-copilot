"""Eval dataset: JSONL items whose gold evidence is described by *matchers*, not chunk IDs.

Why matchers? Chunk IDs are content-addressed (Stage 1), so any edit to a source page
changes them, and a list of hard-coded gold IDs would silently rot. Instead each item
says what the evidence looks like ("a chunk containing 'I-901' from a URL containing
'sevis'"). Matchers are resolved to chunk IDs against the current corpus at eval time,
and the resolved IDs are written into the results. When a matcher stops resolving, that
is itself a signal that the source page changed.

Item format (one JSON object per line):
    {"id": "en-opt-002", "language": "en", "question": "...", "should_refuse": false,
     "group": "opt", "gold": [{"phrases": ["90 days", "program end date"], "url_contains": "opt"}],
     "translation_of": null, "notes": ""}
A chunk is gold if ANY matcher matches it. A matcher matches if ALL of its phrases appear
(case/whitespace-insensitive) in the chunk's heading or text, and url_contains (if given)
is in the URL.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from copilot.models import Chunk

LANGUAGES = {"en", "zh", "hi", "ko", "es"}
TOO_BROAD = 25  # a gold set larger than this barely tests retrieval


class DatasetError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("invalid eval dataset:\n  " + "\n  ".join(errors))


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


@dataclass(frozen=True)
class GoldMatcher:
    phrases: tuple[str, ...] = ()
    url_contains: str | None = None

    def matches(self, chunk: Chunk) -> bool:
        if self.url_contains and self.url_contains.lower() not in chunk.url.lower():
            return False
        haystack = _norm(f"{chunk.heading}\n{chunk.text}")
        return all(_norm(p) in haystack for p in self.phrases)


@dataclass(frozen=True)
class EvalItem:
    id: str
    language: str
    question: str
    should_refuse: bool
    group: str = ""
    gold: tuple[GoldMatcher, ...] = ()
    translation_of: str | None = None
    notes: str = ""


def _parse_item(raw: dict[str, object], where: str, errors: list[str]) -> EvalItem | None:
    n_before = len(errors)

    def err(msg: str) -> None:
        errors.append(f"{where}: {msg}")

    known = {"id", "language", "question", "should_refuse", "group", "gold", "translation_of", "notes"}
    extra = {k for k in raw if k not in known and not str(k).startswith("_")}
    if extra:
        err(f"unknown keys {sorted(extra)}")
    item_id, lang, q = raw.get("id"), raw.get("language"), raw.get("question")
    if not isinstance(item_id, str) or not item_id:
        err("id is required")
    if lang not in LANGUAGES:
        err(f"language must be one of {sorted(LANGUAGES)}")
    if not isinstance(q, str) or not q.strip():
        err("question is required (drafts must be filled in before use)")
    refuse = raw.get("should_refuse", False)
    if not isinstance(refuse, bool):
        err("should_refuse must be true/false")

    gold: list[GoldMatcher] = []
    raw_gold = raw.get("gold", [])
    if not isinstance(raw_gold, list):
        err("gold must be a list")
        raw_gold = []
    for i, g in enumerate(raw_gold):
        if not isinstance(g, dict):
            err(f"gold[{i}] must be an object")
            continue
        phrases = g.get("phrases", [])
        url = g.get("url_contains")
        if not isinstance(phrases, list) or not all(isinstance(p, str) and p.strip() for p in phrases):
            err(f"gold[{i}].phrases must be a list of non-empty strings")
            continue
        if not phrases and not url:
            err(f"gold[{i}] needs phrases and/or url_contains")
            continue
        gold.append(GoldMatcher(tuple(phrases), url if isinstance(url, str) else None))

    if refuse and gold:
        err("should_refuse items must not have gold evidence")
    if not refuse and not gold:
        err("answerable items need at least one gold matcher")

    if len(errors) > n_before:
        return None
    return EvalItem(
        id=str(item_id), language=str(lang), question=str(q).strip(), should_refuse=bool(refuse),
        group=str(raw.get("group", "")), gold=tuple(gold),
        translation_of=raw.get("translation_of") if isinstance(raw.get("translation_of"), str) else None,
        notes=str(raw.get("notes", "")),
    )


def load_dataset(paths: Iterable[Path]) -> list[EvalItem]:
    items: list[EvalItem] = []
    errors: list[str] = []
    for path in sorted(paths):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip() or line.lstrip().startswith("//"):
                continue
            where = f"{path.name}:{n}"
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{where}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(raw, dict):
                errors.append(f"{where}: each line must be a JSON object")
                continue
            item = _parse_item(raw, where, errors)
            if item:
                items.append(item)

    ids = [i.id for i in items]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate ids: {dupes}")
    by_id = {i.id: i for i in items}
    for i in items:
        if i.translation_of:
            base = by_id.get(i.translation_of)
            if base is None:
                errors.append(f"{i.id}: translation_of {i.translation_of!r} does not exist")
            elif base.language != "en":
                errors.append(f"{i.id}: translation_of must point to an English item")
    if not items and not errors:
        errors.append("dataset is empty")
    if errors:
        raise DatasetError(errors)
    return items


@dataclass
class Resolution:
    gold_ids: dict[str, set[str]] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)  # answerable items with no matching chunk
    too_broad: list[str] = field(default_factory=list)


def resolve_gold(items: list[EvalItem], chunks: list[Chunk]) -> Resolution:
    res = Resolution()
    for item in items:
        ids = {c.chunk_id for c in chunks if any(m.matches(c) for m in item.gold)}
        res.gold_ids[item.id] = ids
        if not item.should_refuse and not ids:
            res.unresolved.append(item.id)
        if len(ids) > TOO_BROAD:
            res.too_broad.append(item.id)
    return res


# --- corpus snapshots (a frozen corpus for reproducible CI) ---------------------------

SNAPSHOT_FIELDS = ("chunk_id", "url", "source", "heading", "text", "retrieved_at", "doc_hash", "position")


def write_snapshot(chunks: list[Chunk], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps({k: getattr(c, k) for k in SNAPSHOT_FIELDS}, ensure_ascii=False) + "\n")
    return len(chunks)


def load_snapshot(path: Path) -> list[Chunk]:
    chunks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            chunks.append(Chunk(**{k: d[k] for k in SNAPSHOT_FIELDS}))
    return chunks

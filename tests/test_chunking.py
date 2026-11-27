from __future__ import annotations

import pytest

from copilot.chunker import chunk_html, make_chunk_id, pack_paragraphs
from copilot.config import ChunkConfig, ConfigError
from copilot.parsing import extract_sections, visible_text

CFG = ChunkConfig(max_words=50, overlap_words=10, min_words=3)


def _chunks(html: str, cfg: ChunkConfig = CFG):  # type: ignore[no-untyped-def]
    return chunk_html(
        url="https://example.gov/opt", source="test", html=html,
        retrieved_at="2026-11-26T00:00:00+00:00", doc_hash="h", cfg=cfg,
    )


class TestParsing:
    def test_strips_boilerplate(self, sample_html: str) -> None:
        text = visible_text(sample_html)
        for junk in ("tracking", "color: red", "banner", "About us", "Footer"):
            assert junk not in text

    def test_heading_hierarchy(self, sample_html: str) -> None:
        headings = [s.heading for s in extract_sections(sample_html)]
        assert "Practical Training for Students > Optional Practical Training > When to apply" in headings
        # h2 after an h3 pops back to the h2 level
        assert "Practical Training for Students > Curricular Practical Training" in headings
        # the page's <h1> duplicates <title> and should not appear twice
        assert not any(h.startswith("Practical Training for Students > Practical Training") for h in headings)

    def test_nested_blocks_not_duplicated(self, sample_html: str) -> None:
        text = visible_text(sample_html)
        assert text.count("must be filed within the window") == 1


class TestPacking:
    def test_respects_max_words(self) -> None:
        paras = [" ".join(["word"] * 30), " ".join(["other"] * 30)]
        out = pack_paragraphs(paras, CFG)
        assert len(out) == 2
        assert all(len(w.split()) <= CFG.max_words for w in out)

    def test_small_paragraphs_are_packed_together(self) -> None:
        out = pack_paragraphs(["one two three four", "five six seven eight"], CFG)
        assert out == ["one two three four five six seven eight"]

    def test_long_paragraph_split_with_overlap(self) -> None:
        words = [f"w{i}" for i in range(120)]
        out = pack_paragraphs([" ".join(words)], CFG)
        windows = [w.split() for w in out]
        assert all(len(w) <= 50 for w in windows)
        assert windows[0][-10:] == windows[1][:10]  # 10-word overlap
        assert windows[-1][-1] == "w119"  # nothing lost at the end

    def test_drops_crumbs(self) -> None:
        assert pack_paragraphs(["Top"], CFG) == []

    def test_invalid_overlap_rejected(self) -> None:
        with pytest.raises(ConfigError):
            ChunkConfig(max_words=10, overlap_words=10)


class TestChunks:
    def test_metadata_propagates(self, sample_html: str) -> None:
        chunks = _chunks(sample_html)
        assert chunks
        for i, c in enumerate(chunks):
            assert c.url == "https://example.gov/opt"
            assert c.source == "test"
            assert c.doc_hash == "h"
            assert c.position == i
            assert len(c.chunk_id) == 12

    def test_ids_are_deterministic(self, sample_html: str) -> None:
        assert [c.chunk_id for c in _chunks(sample_html)] == [c.chunk_id for c in _chunks(sample_html)]

    def test_id_changes_when_content_changes(self) -> None:
        a = make_chunk_id("u", "h", "File within 60 days.")
        b = make_chunk_id("u", "h", "File within 30 days.")
        assert a != b

    def test_chunks_never_cross_sections(self, sample_html: str) -> None:
        for c in _chunks(sample_html):
            if "CPT" in c.text:
                assert "Curricular" in c.heading
                assert "I-765" not in c.text

    def test_index_text_includes_heading(self, sample_html: str) -> None:
        c = next(c for c in _chunks(sample_html) if "I-765" in c.text)
        assert c.index_text.startswith(c.heading)
        assert "When to apply" in c.index_text

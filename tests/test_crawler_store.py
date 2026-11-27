from __future__ import annotations

from pathlib import Path

import numpy as np

from copilot.config import AppConfig, CrawlConfig, Source
from copilot.crawler import Crawler, FetchResult, extract_links, is_allowed, normalize_url
from copilot.indexing import build_embeddings, crawl_sources, rechunk_from_raw
from copilot.retrieval import HybridRetriever
from copilot.store import Store

from .conftest import FakeEmbedder

BASE = "https://example.gov/students"


class FakeFetcher:
    """In-memory web: url -> (status, html)."""

    def __init__(self, pages: dict[str, tuple[int, str]]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str) -> FetchResult:
        self.requested.append(url)
        status, body = self.pages.get(url, (404, ""))
        ctype = "text/plain" if url.endswith("robots.txt") else "text/html; charset=utf-8"
        return FetchResult(url=url, status_code=status, content_type=ctype, text=body)


def _page(title: str, body: str, links: str = "") -> str:
    return f"<html><head><title>{title}</title></head><body><main><h1>{title}</h1><p>{body}</p>{links}</main></body></html>"


def _web(sample_html: str) -> dict[str, tuple[int, str]]:
    return {
        "https://example.gov/robots.txt": (200, "User-agent: *\nDisallow: /students/private\n"),
        BASE: (200, sample_html.replace('href="/students/travel"', 'href="/students/travel"')
               .replace("</main>", '<a href="/students/private/x">p</a><a href="/students/gone">g</a></main>')),
        f"{BASE}/travel": (200, _page("Travel", "Students traveling need a valid I-20 travel signature from the DSO office.")),
    }


SOURCE = Source(name="test", seeds=[BASE], allowed_prefixes=[BASE])


def _cfg(tmp_path: Path, **crawl: object) -> AppConfig:
    return AppConfig(
        data_dir=tmp_path, sources=[SOURCE], dso_message="Contact your DSO.",
        crawl=CrawlConfig(delay_seconds=0, **crawl),  # type: ignore[arg-type]
    )


class TestUrls:
    def test_normalize(self) -> None:
        assert normalize_url("HTTPS://Example.GOV/a/b/#frag") == "https://example.gov/a/b"
        assert normalize_url("https://example.gov") == "https://example.gov/"

    def test_allowlist(self) -> None:
        assert is_allowed(f"{BASE}/opt", [BASE])
        assert not is_allowed("https://example.gov/other", [BASE])
        assert not is_allowed("http://example.gov/students/opt", [BASE])  # https only
        assert not is_allowed("https://evil.example/students", [BASE])

    def test_extract_links(self, sample_html: str) -> None:
        links = extract_links(sample_html, BASE)
        assert f"{BASE}/travel" in links
        assert not any(link.endswith(".pdf") for link in links)


class TestCrawler:
    def test_crawl_respects_allowlist_robots_and_depth(self, sample_html: str, tmp_path: Path) -> None:
        fetcher = FakeFetcher(_web(sample_html))
        pages = list(Crawler(_cfg(tmp_path).crawl, fetcher).crawl(SOURCE))
        urls = {p.url for p in pages}
        assert urls == {BASE, f"{BASE}/travel"}
        assert not any("private" in u for u in fetcher.requested)  # robots.txt honored
        assert not any("example.org" in u or "/home" in u for u in fetcher.requested)  # allowlist

    def test_max_depth_zero_fetches_seeds_only(self, sample_html: str, tmp_path: Path) -> None:
        pages = list(Crawler(_cfg(tmp_path, max_depth=0).crawl, FakeFetcher(_web(sample_html))).crawl(SOURCE))
        assert [p.url for p in pages] == [BASE]

    def test_max_pages(self, sample_html: str, tmp_path: Path) -> None:
        pages = list(Crawler(_cfg(tmp_path, max_pages_per_source=1).crawl, FakeFetcher(_web(sample_html))).crawl(SOURCE))
        assert len(pages) == 1

    def test_hash_ignores_markup_noise(self, sample_html: str, tmp_path: Path) -> None:
        noisy = sample_html.replace("<head>", '<head><script>var csrf="abc123"</script>')
        crawler = Crawler(_cfg(tmp_path).crawl, FakeFetcher({BASE: (200, sample_html)}))
        crawler2 = Crawler(_cfg(tmp_path).crawl, FakeFetcher({BASE: (200, noisy)}))
        h1 = next(crawler.crawl(SOURCE)).content_hash
        h2 = next(crawler2.crawl(SOURCE)).content_hash
        assert h1 == h2


class TestEndToEnd:
    def test_ingest_embed_search(self, sample_html: str, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        emb = FakeEmbedder()
        with Store(tmp_path) as store:
            report = crawl_sources([SOURCE], Crawler(cfg.crawl, FakeFetcher(_web(sample_html))), store, cfg)
            assert report.pages == 2 and report.changed_pages == 2
            assert build_embeddings(store, emb) == report.chunks
            assert build_embeddings(store, emb) == 0  # cached by content-addressed ID

            retriever = HybridRetriever.from_store(store, emb, cfg.retrieval)
            top = retriever.search("I-20 travel signature", top_k=1).hits[0].chunk
            assert "travel signature" in top.text
            assert top.url.startswith(BASE)

            # Re-chunking from raw HTML is offline and stable.
            before = {c.chunk_id for c in store.all_chunks()}
            rechunk_from_raw(store, cfg)
            assert {c.chunk_id for c in store.all_chunks()} == before

    def test_embeddings_roundtrip(self, tmp_path: Path) -> None:
        with Store(tmp_path) as store:
            store.save_embeddings(["a", "b"], np.eye(2, dtype=np.float32), "m")
            loaded = store.load_embeddings()
            assert loaded is not None
            ids, matrix, model = loaded
            assert ids == ["a", "b"] and model == "m" and matrix.shape == (2, 2)

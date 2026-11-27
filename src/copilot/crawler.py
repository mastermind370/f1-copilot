"""Allowlisted, polite crawler.

Design notes:
- Only URLs matching a source's `allowed_prefixes` are fetched. That keeps the corpus to
  official pages and makes the system's provenance auditable.
- robots.txt is respected. Bot protection (HTTP 403) is never circumvented. Use
  `copilot import-html` to add a page you saved from your browser instead.
- The content hash is computed over the *visible text*, not raw HTML. Raw HTML changes on
  every request (CSRF tokens, cache-busting query strings), which would make Stage 4's
  change detection fire constantly.
- HTTP goes through the small `Fetcher` protocol, so tests use an in-memory fake and never
  touch the network.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from copilot.config import CrawlConfig, Source
from copilot.models import FetchedPage
from copilot.parsing import visible_text

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchResult:
    url: str  # final URL after redirects
    status_code: int
    content_type: str
    text: str


class Fetcher(Protocol):
    def get(self, url: str) -> FetchResult: ...


class HttpxFetcher:
    def __init__(self, cfg: CrawlConfig) -> None:
        import httpx

        self._client = httpx.Client(
            headers={"User-Agent": cfg.user_agent},
            timeout=cfg.timeout_seconds,
            follow_redirects=True,
        )

    def get(self, url: str) -> FetchResult:
        r = self._client.get(url)
        return FetchResult(
            url=str(r.url),
            status_code=r.status_code,
            content_type=r.headers.get("content-type", ""),
            text=r.text,
        )

    def close(self) -> None:
        self._client.close()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def normalize_url(url: str) -> str:
    url, _fragment = urldefrag(url.strip())
    p = urlparse(url)
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    query = f"?{p.query}" if p.query else ""
    return f"{p.scheme.lower()}://{p.netloc.lower()}{path}{query}"


def is_allowed(url: str, prefixes: list[str]) -> bool:
    if urlparse(url).scheme != "https":
        return False
    n = normalize_url(url)
    return any(n.startswith(normalize_url(p)) for p in prefixes)


SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc", ".docx", ".xls", ".xlsx")


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if absolute.lower().endswith(SKIP_EXTENSIONS):
            continue
        links.append(absolute)
    return links


class Crawler:
    def __init__(
        self,
        cfg: CrawlConfig,
        fetcher: Fetcher,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cfg = cfg
        self.fetcher = fetcher
        self._sleep = sleep
        self._robots: dict[str, RobotFileParser | None] = {}

    def _robots_allows(self, url: str) -> bool:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                res = self.fetcher.get(f"{origin}/robots.txt")
                if res.status_code == 200:
                    parser.parse(res.text.splitlines())  # type: ignore[union-attr]
                else:
                    parser = None  # no robots.txt -> everything allowed (RFC 9309)
            except Exception as exc:  # network error: be permissive but say so
                log.warning("could not fetch robots.txt for %s: %s", origin, exc)
                parser = None
            self._robots[origin] = parser
        rp = self._robots[origin]
        return True if rp is None else rp.can_fetch(self.cfg.user_agent, url)

    def crawl(self, source: Source) -> Iterator[FetchedPage]:
        queue: deque[tuple[str, int]] = deque((normalize_url(s), 0) for s in source.seeds)
        seen: set[str] = set()
        fetched = 0

        while queue and fetched < self.cfg.max_pages_per_source:
            url, depth = queue.popleft()
            if url in seen:
                continue
            seen.add(url)

            if not is_allowed(url, source.allowed_prefixes):
                log.debug("skip (not allowlisted): %s", url)
                continue
            if not self._robots_allows(url):
                log.info("skip (robots.txt): %s", url)
                continue

            if fetched:
                self._sleep(self.cfg.delay_seconds)
            try:
                res = self.fetcher.get(url)
            except Exception as exc:
                log.warning("fetch failed %s: %s", url, exc)
                continue
            fetched += 1

            if res.status_code != 200:
                log.warning("HTTP %s for %s", res.status_code, url)
                continue
            if "html" not in res.content_type.lower():
                log.debug("skip (content-type %s): %s", res.content_type, url)
                continue
            final_url = normalize_url(res.url)
            if final_url != url and not is_allowed(final_url, source.allowed_prefixes):
                log.info("skip (redirected off allowlist): %s -> %s", url, final_url)
                continue

            yield FetchedPage(
                url=final_url,
                source=source.name,
                fetched_at=now_utc(),
                status_code=res.status_code,
                content_hash=content_hash(visible_text(res.text)),
                html=res.text,
            )

            if depth < self.cfg.max_depth:
                for link in extract_links(res.text, final_url):
                    if link not in seen and is_allowed(link, source.allowed_prefixes):
                        queue.append((link, depth + 1))

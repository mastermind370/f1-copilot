"""HTML -> structured sections.

Government pages are full of navigation, banners and footers. We strip those, find the main
content region, and walk block elements in document order while tracking the heading
hierarchy, so every paragraph knows which section it belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

STRIP_TAGS = [
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "svg", "iframe", "button", "template",
]
HEADING_TAGS = ["h1", "h2", "h3", "h4"]
BLOCK_TAGS = ["p", "li", "td", "th", "dd", "dt", "pre", "blockquote", *HEADING_TAGS]


@dataclass
class Section:
    heading_path: tuple[str, ...]
    paragraphs: list[str] = field(default_factory=list)

    @property
    def heading(self) -> str:
        return " > ".join(self.heading_path)


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _main_root(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    for candidate in (
        soup.find("main"),
        soup.find(attrs={"role": "main"}),
        soup.find("article"),
        soup.body,
    ):
        if isinstance(candidate, Tag):
            return candidate
    return soup


def extract_sections(html: str) -> list[Section]:
    soup = BeautifulSoup(html, "html.parser")
    title = _normalize(soup.title.get_text()) if soup.title else ""
    for tag in soup(STRIP_TAGS):
        tag.decompose()
    root = _main_root(soup)

    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (heading level, heading text)
    current = Section(heading_path=(title,) if title else ())

    for el in root.find_all(BLOCK_TAGS):
        # A <p> inside an <li> would otherwise be emitted twice; keep the outermost block.
        if el.find_parent(BLOCK_TAGS) is not None:
            continue
        text = _normalize(el.get_text(" "))
        if not text:
            continue

        if el.name in HEADING_TAGS:
            if current.paragraphs:
                sections.append(current)
            level = int(el.name[1])
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            path = tuple(t for _, t in stack)
            # Avoid "Title > Title" when the page's <h1> repeats its <title>.
            if title and path[0] != title:
                path = (title, *path)
            current = Section(heading_path=path)
        else:
            current.paragraphs.append(text)

    if current.paragraphs:
        sections.append(current)
    return sections


def visible_text(html: str) -> str:
    """Canonical text of a page, used for content hashing."""
    parts: list[str] = []
    for sec in extract_sections(html):
        parts.append(sec.heading)
        parts.extend(sec.paragraphs)
    return "\n".join(parts)

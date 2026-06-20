"""Investopedia parse-only ingestion from locally-saved HTML files."""
from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import lxml.html
import lxml.etree
from markdownify import markdownify
from parsel import Selector

from ingest import frontmatter_io, manifest
from ingest.errors import IngestError, ParseError

_PARSER_VERSION = 1

_RAW_DIR = Path("data/raw/investopedia")
_PROCESSED_DIR = Path("data/processed/investopedia")
_MANIFEST_PATH = Path("data/processed/investopedia/manifest.jsonl")

# XPath expressions for elements to remove from the article body
_STRIP_XPATHS = [
    # Ad slots
    './/*[contains(@class,"mm-ads-gpt-adunit")]',
    './/*[contains(@class,"mntl-sc-block-adslot")]',
    './/*[contains(@class,"mm-ads-textnote")]',
    # AI/Miso widget
    './/*[contains(@class,"askmiso")]',
    # Newsletter signup
    './/*[contains(@class,"newsletter")]',
    # Related articles
    './/*[contains(@class,"related-articles")]',
    './/*[contains(@class,"mntl-sc-block-relatedposts")]',
]


def _extract_slug(url: str) -> str:
    m = re.search(r"/terms/[^/]+/([^/]+?)(?:\.asp)?$", url)
    if not m:
        raise ParseError(f"Cannot extract slug from URL: {url!r}")
    return m.group(1)


def _parse_file(html: str, source_file: Path) -> tuple[str, dict, str]:
    """
    Parse a locally-saved Investopedia HTML file.

    Returns (markdown_body, metadata, slug).
    """
    sel = Selector(html)
    warnings: list[str] = []

    # Canonical URL and slug
    url = sel.css("link[rel=canonical]::attr(href)").get()
    if not url:
        url = sel.css("meta[property='og:url']::attr(content)").get()
    if not url:
        raise ParseError(f"No canonical URL in {source_file.name}")
    slug = _extract_slug(url)

    # Title
    title = (
        sel.css("h1.comp.article-heading.mntl-text-block::text").get()
        or sel.css("h1::text").get()
        or ""
    ).strip()
    if not title:
        warnings.append("could not find article title h1")

    # Content container — use lxml for element removal
    doc = lxml.html.fromstring(html)
    containers = doc.cssselect("#article-body_1-0")
    if not containers:
        containers = doc.cssselect(".comp.article-body")
    if not containers:
        raise ParseError(f"No article body container found in {source_file.name}")

    container = containers[0]

    # Collect internal links BEFORE stripping (from original parsel selector for
    # convenience — lxml attrib access is more verbose)
    content_sel = sel.css("#article-body_1-0") or sel.css(".comp.article-body")
    internal_links = sorted(set(
        href for href in content_sel.css("a::attr(href)").getall()
        if "investopedia.com" in href
    ))

    # Collect image alt text BEFORE stripping (deduplicated, order-preserving)
    _seen: set[str] = set()
    images_dropped = []
    for alt in content_sel.css("img::attr(alt)").getall():
        if alt and alt not in _seen:
            _seen.add(alt)
            images_dropped.append(alt)
    images_dropped = sorted(images_dropped)

    # Remove unwanted elements in-place via lxml
    for xpath in _STRIP_XPATHS:
        for el in container.xpath(xpath):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    # Serialise cleaned subtree back to HTML string
    content_html = lxml.etree.tostring(container, encoding="unicode", method="html")

    # Convert to markdown, stripping links and images
    body_md = markdownify(content_html, strip=["a", "img"]).strip()

    # Clean up excessive blank lines
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)

    fetched_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "source_url": url,
        "source": "investopedia",
        "slug": slug,
        "title": title,
        "fetched_at": fetched_at,
        "internal_links": internal_links,
        "images_dropped": images_dropped,
        "parse_warnings": sorted(warnings),
        "parser_version": _PARSER_VERSION,
    }
    return body_md, metadata, slug


def run(source_dir: Path, limit: int | None = None) -> dict:
    """Parse all .html files in *source_dir*. Returns summary counts."""
    html_files = sorted(source_dir.glob("*.html"))
    if limit is not None:
        html_files = html_files[:limit]

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    counts = {"attempted": 0, "ok": 0, "error": 0}
    errors_by_category: dict[str, list[str]] = {}

    for source_file in html_files:
        counts["attempted"] += 1
        slug = source_file.stem  # fallback before we parse the URL

        try:
            html = source_file.read_text(encoding="utf-8")
            content_sha256 = hashlib.sha256(html.encode()).hexdigest()

            body_md, metadata, slug = _parse_file(html, source_file)

            raw_path = _RAW_DIR / f"{slug}.html"
            processed_path = _PROCESSED_DIR / f"{slug}.md"

            # Copy raw HTML into data/raw so corpus is self-contained
            if not raw_path.exists():
                shutil.copy2(source_file, raw_path)

            frontmatter_io.write(processed_path, body_md, metadata)

            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": metadata["source_url"],
                    "slug": slug,
                    "fetched_at": metadata["fetched_at"],
                    "status": "ok",
                    "content_sha256": content_sha256,
                    "raw_path": str(raw_path),
                    "processed_path": str(processed_path),
                    "parse_warnings": metadata.get("parse_warnings", []),
                },
            )
            counts["ok"] += 1

        except IngestError as exc:
            counts["error"] += 1
            cat = exc.category
            errors_by_category.setdefault(cat, []).append(str(source_file.name))
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": "",
                    "slug": slug,
                    "fetched_at": "",
                    "status": "error",
                    "content_sha256": "",
                    "raw_path": "",
                    "processed_path": "",
                    "parse_warnings": [],
                    "error": {"category": cat, "message": str(exc)},
                },
            )

        except Exception as exc:
            counts["error"] += 1
            errors_by_category.setdefault("unknown", []).append(str(source_file.name))
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": "",
                    "slug": slug,
                    "fetched_at": "",
                    "status": "error",
                    "content_sha256": "",
                    "raw_path": "",
                    "processed_path": "",
                    "parse_warnings": [],
                    "error": {"category": "unknown", "message": str(exc)},
                },
            )

    return {"counts": counts, "errors_by_category": errors_by_category}

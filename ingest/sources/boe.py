"""Bank of England Knowledge Bank ingestion — two-pass crawl, fetch, parse."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import lxml.etree
import lxml.html
from markdownify import markdownify
from parsel import Selector

from ingest import frontmatter_io, http, manifest
from ingest.errors import CircuitBreakerOpen, IngestError, NotFoundError, ParseError

_BASE = "https://www.bankofengland.co.uk"
_INDEX_URL = f"{_BASE}/explainers"
_PARSER_VERSION = 1

_RAW_DIR = Path("data/raw/boe")
_PROCESSED_DIR = Path("data/processed/boe")
_MANIFEST_PATH = Path("data/processed/boe/manifest.jsonl")

# H2 text values that mark non-content navigation sections
_SKIP_SECTION_H2S = {"Most read", "Topics", "Other topics"}

# lxml cssselect expressions for elements to remove before markdown conversion
_STRIP_SELECTORS = [
    "div.share-widget",         # social share buttons
    "section.page-section-survey",  # feedback survey section
]


def _extract_slug(url: str) -> str:
    """Extract slug from a BoE explainer URL."""
    m = re.search(r"/explainers/([^/?#]+)$", url.rstrip("/"))
    if not m:
        raise ParseError(f"Cannot extract slug from URL: {url!r}")
    return m.group(1)


def _collect_explainer_links(html: str) -> list[str]:
    """Return all unique /explainers/<slug> hrefs found in *html*."""
    sel = Selector(html)
    hrefs = sel.css("a[href*='/explainers/']::attr(href)").getall()
    slugs = []
    for h in hrefs:
        # Keep only /explainers/<slug> — not the root /explainers or anchors
        if re.match(r"^/explainers/[^/?#]+$", h.rstrip("/")):
            slugs.append(h.rstrip("/"))
    return list(dict.fromkeys(slugs))  # deduplicate, preserve order


def discover_urls(circuit_breaker: http.CircuitBreaker) -> list[str]:
    """
    Two-pass crawl to discover the full set of explainer article URLs.

    Pass 1: fetch /explainers/ root → collect direct links (the ~16 category pages).
    Pass 2: for each category page, fetch it → collect child links.
    Returns sorted, deduplicated list of absolute URLs.
    """
    all_paths: set[str] = set()

    # Pass 1
    resp = http.get(_INDEX_URL, circuit_breaker=circuit_breaker)
    root_paths = _collect_explainer_links(resp.text)
    all_paths.update(root_paths)
    http.polite_delay()

    # Pass 2 — fetch each category page and collect its children
    for path in root_paths:
        url = f"{_BASE}{path}"
        try:
            resp = http.get(url, circuit_breaker=circuit_breaker)
            child_paths = _collect_explainer_links(resp.text)
            all_paths.update(child_paths)
        except IngestError:
            pass  # non-fatal: we still have partial URL set
        http.polite_delay()

    return sorted(f"{_BASE}{p}" for p in all_paths)


def _parse_page(html: str, slug: str, url: str, fetched_at: str) -> tuple[str, dict]:
    """Parse a BoE explainer page into (markdown_body, metadata)."""
    sel = Selector(html)
    warnings: list[str] = []

    # Title
    title = (sel.css("main h1::text").get() or "").strip()
    if not title:
        raise ParseError(f"No h1 title found for slug '{slug}'")

    # Intro description — prepend to body
    desc_parts = sel.css("main .page-description ::text").getall()
    description = " ".join(desc_parts).strip()

    # Collect internal links — only actual BoE paths, not social share redirect URLs
    # (share links embed the BoE URL as a query param, which would match a naive substring check)
    main_sel = sel.css("main")
    internal_links = sorted(set(
        href for href in main_sel.css("a::attr(href)").getall()
        if re.match(r"^(https://www\.bankofengland\.co\.uk)?/explainers/[^/?#]+$", href)
    ))

    # Collect image alt texts (deduped)
    seen_alts: set[str] = set()
    images_dropped: list[str] = []
    for alt in main_sel.css("img::attr(alt)").getall():
        if alt and alt not in seen_alts:
            seen_alts.add(alt)
            images_dropped.append(alt)
    images_dropped = sorted(images_dropped)

    # Build content from sections using lxml for element manipulation
    doc = lxml.html.fromstring(html)
    main_el = doc.cssselect("main")
    if not main_el:
        raise ParseError(f"No <main> element found for slug '{slug}'")
    main_el = main_el[0]

    # Remove navigation and widget elements
    for selector in ["nav.nav-chapters"] + _STRIP_SELECTORS:
        for el in main_el.cssselect(selector):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    # Collect content sections, filtering navigation ones
    sections = main_el.cssselect("section.page-section")
    body_parts: list[str] = []

    if description:
        body_parts.append(description)

    for section in sections:
        # Check if this is a skip section (Most read, Topics, Back to top)
        h2_els = section.cssselect("h2")
        h2_text = (
            " ".join(h2_els[0].text_content().split()) if h2_els else ""
        ).strip()

        if h2_text in _SKIP_SECTION_H2S:
            continue
        if not h2_text:
            continue  # empty-H2 sections are survey wrappers or spacers
        if "page-section--last" in section.get("class", ""):
            continue

        # Serialise and convert to markdown
        section_html = lxml.etree.tostring(section, encoding="unicode", method="html")
        section_md = markdownify(section_html, strip=["a", "img"]).strip()
        if section_md:
            body_parts.append(section_md)

    body_md = "\n\n".join(body_parts)
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)

    if not body_md.strip():
        warnings.append("no content extracted from sections")

    metadata = {
        "source_url": url,
        "source": "boe",
        "slug": slug,
        "title": title,
        "fetched_at": fetched_at,
        "internal_links": internal_links,
        "images_dropped": images_dropped,
        "parse_warnings": sorted(warnings),
        "parser_version": _PARSER_VERSION,
    }
    return body_md, metadata


def run(urls: list[str], refresh: bool = False) -> dict:
    """Fetch and parse *urls*. Returns summary counts."""
    cb = http.CircuitBreaker()
    counts = {"attempted": 0, "ok": 0, "error": 0}
    errors_by_category: dict[str, list[str]] = {}

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for i, url in enumerate(urls):
        counts["attempted"] += 1
        try:
            slug = _extract_slug(url)
        except ParseError as exc:
            counts["error"] += 1
            errors_by_category.setdefault("parse", []).append(url)
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": url, "slug": "", "fetched_at": "", "status": "error",
                    "content_sha256": "", "raw_path": "", "processed_path": "",
                    "parse_warnings": [], "error": {"category": "parse", "message": str(exc)},
                },
            )
            continue

        raw_path = _RAW_DIR / f"{slug}.html"
        processed_path = _PROCESSED_DIR / f"{slug}.md"

        if not refresh and manifest.already_processed(_MANIFEST_PATH, slug):
            counts["ok"] += 1
            continue

        fetched_at = ""
        html = ""

        try:
            if raw_path.exists() and not refresh:
                html = raw_path.read_text(encoding="utf-8")
                for rec in manifest.read_all(_MANIFEST_PATH):
                    if rec.get("slug") == slug:
                        fetched_at = rec.get("fetched_at", "")
                        break
                if not fetched_at:
                    fetched_at = datetime.now(timezone.utc).isoformat()
            else:
                resp = http.get(url, circuit_breaker=cb)
                fetched_at = datetime.now(timezone.utc).isoformat()
                html = resp.text
                raw_path.write_text(html, encoding="utf-8")

            content_sha256 = hashlib.sha256(html.encode()).hexdigest()
            body_md, metadata = _parse_page(html, slug, url, fetched_at)
            frontmatter_io.write(processed_path, body_md, metadata)

            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": url,
                    "slug": slug,
                    "fetched_at": fetched_at,
                    "status": "ok",
                    "content_sha256": content_sha256,
                    "raw_path": str(raw_path),
                    "processed_path": str(processed_path),
                    "parse_warnings": metadata.get("parse_warnings", []),
                },
            )
            counts["ok"] += 1

        except CircuitBreakerOpen:
            raise

        except IngestError as exc:
            counts["error"] += 1
            cat = exc.category
            errors_by_category.setdefault(cat, []).append(slug)
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": url, "slug": slug, "fetched_at": fetched_at, "status": "error",
                    "content_sha256": "", "raw_path": str(raw_path),
                    "processed_path": str(processed_path), "parse_warnings": [],
                    "error": {"category": cat, "message": str(exc)},
                },
            )

        except Exception as exc:
            counts["error"] += 1
            errors_by_category.setdefault("unknown", []).append(slug)
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": url, "slug": slug, "fetched_at": fetched_at, "status": "error",
                    "content_sha256": "", "raw_path": str(raw_path),
                    "processed_path": str(processed_path), "parse_warnings": [],
                    "error": {"category": "unknown", "message": str(exc)},
                },
            )

        # Polite delay between network fetches only
        if i < len(urls) - 1 and (refresh or not raw_path.exists()):
            http.polite_delay()

    return {"counts": counts, "errors_by_category": errors_by_category}

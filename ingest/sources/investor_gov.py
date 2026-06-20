"""Investor.gov glossary ingestion — fetch + parse."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from markdownify import markdownify
from parsel import Selector

from ingest import frontmatter_io, http, manifest
from ingest.errors import CircuitBreakerOpen, IngestError, NotFoundError, ParseError

_BASE_URL = "https://www.investor.gov/introduction-investing/investing-basics/glossary/{slug}"
_PARSER_VERSION = 1

_RAW_DIR = Path("data/raw/investor_gov")
_PROCESSED_DIR = Path("data/processed/investor_gov")
_MANIFEST_PATH = Path("data/processed/investor_gov/manifest.jsonl")


def _load_slugs(terms_file: Path) -> list[str]:
    """Extract slugs from the markdown table in docs/investor-gov-terms.md."""
    text = terms_file.read_text(encoding="utf-8")
    # Each data row looks like: | Topic name | `slug` |
    slugs = re.findall(r"\|\s*`([^`]+)`\s*\|", text)
    return slugs


def _parse_page(html: str, slug: str, url: str, fetched_at: str) -> tuple[str, dict]:
    """Parse Investor.gov HTML into (markdown_body, metadata)."""
    sel = Selector(html)
    warnings: list[str] = []

    # Soft-404 detection: valid pages have h1.field--name-title
    title_el = sel.css("h1.field--name-title")
    if not title_el:
        raise NotFoundError(f"Soft-404: no field--name-title h1 for slug '{slug}'")

    title = title_el.css("::text").get("").strip()
    if not title:
        warnings.append("title element found but empty")

    body_el = sel.css(".field--name-body")
    if not body_el:
        warnings.append("no .field--name-body element; body will be empty")
        body_html = ""
    else:
        body_html = body_el.get()

    body_md = markdownify(body_html, strip=["a", "img"]).strip() if body_html else ""

    # Clean up excessive blank lines
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)

    metadata = {
        "source_url": url,
        "source": "investor_gov",
        "slug": slug,
        "title": title,
        "fetched_at": fetched_at,
        "parse_warnings": sorted(warnings),
        "parser_version": _PARSER_VERSION,
    }
    return body_md, metadata


def run(slugs: list[str], refresh: bool = False) -> dict:
    """Fetch and parse *slugs*. Returns summary counts."""
    cb = http.CircuitBreaker()
    counts = {"attempted": 0, "ok": 0, "error": 0}
    errors_by_category: dict[str, list[str]] = {}

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for i, slug in enumerate(slugs):
        counts["attempted"] += 1
        url = _BASE_URL.format(slug=slug)
        raw_path = _RAW_DIR / f"{slug}.html"
        processed_path = _PROCESSED_DIR / f"{slug}.md"

        # Skip if already OK in manifest and not refreshing
        if not refresh and manifest.already_processed(_MANIFEST_PATH, slug):
            counts["ok"] += 1
            continue

        fetched_at: str = ""
        html: str = ""

        try:
            if raw_path.exists() and not refresh:
                html = raw_path.read_text(encoding="utf-8")
                # Recover fetched_at from existing manifest if possible
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

        except CircuitBreakerOpen as exc:
            raise  # propagate — aborts the run

        except IngestError as exc:
            counts["error"] += 1
            cat = exc.category
            errors_by_category.setdefault(cat, []).append(slug)
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": url,
                    "slug": slug,
                    "fetched_at": fetched_at,
                    "status": "error",
                    "content_sha256": "",
                    "raw_path": str(raw_path),
                    "processed_path": str(processed_path),
                    "parse_warnings": [],
                    "error": {"category": cat, "message": str(exc)},
                },
            )

        except Exception as exc:
            counts["error"] += 1
            errors_by_category.setdefault("unknown", []).append(slug)
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": url,
                    "slug": slug,
                    "fetched_at": fetched_at,
                    "status": "error",
                    "content_sha256": "",
                    "raw_path": str(raw_path),
                    "processed_path": str(processed_path),
                    "parse_warnings": [],
                    "error": {"category": "unknown", "message": str(exc)},
                },
            )

        # Polite delay between network fetches (skip for cache hits)
        if i < len(slugs) - 1 and (refresh or not raw_path.exists()):
            http.polite_delay()

    return {"counts": counts, "errors_by_category": errors_by_category}


def load_slugs_from_file(terms_file: Path | None = None) -> list[str]:
    if terms_file is None:
        terms_file = Path("docs/investor-gov-terms.md")
    return _load_slugs(terms_file)

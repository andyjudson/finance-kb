"""Bank of England Glossary ingestion — single page, ~570 abbreviation terms."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import lxml.html
from parsel import Selector

from ingest import frontmatter_io, manifest
from ingest.errors import IngestError, ParseError

_GLOSSARY_URL = "https://www.bankofengland.co.uk/glossary"
_PARSER_VERSION = 1

_RAW_DIR = Path("data/raw/boe_glossary")
_RAW_PATH = _RAW_DIR / "glossary.html"
_PROCESSED_DIR = Path("data/processed/boe_glossary")
_MANIFEST_PATH = Path("data/processed/boe_glossary/manifest.jsonl")


def _slugify(term: str) -> str:
    """Convert a term string to a URL-safe slug."""
    s = term.lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _extract_terms(html: str) -> list[tuple[str, str, str]]:
    """
    Parse the full A-Z glossary page and return (term, definition, letter) tuples.

    Uses section 0 (the "All" view) to avoid duplicating terms from per-letter tabs.
    Each <p> in the section can contain one or more <strong>TERM</strong> - definition
    patterns, sometimes with embedded links in the definition text.
    """
    doc = lxml.html.fromstring(html)
    sel = Selector(html)

    # Section 0 is the full A-Z view containing all terms
    sections = doc.cssselect("main section.page-section")
    if not sections:
        raise ParseError("No page-section found in BoE glossary page")
    all_section = sections[0]

    # Track current letter from H2 headings
    results: list[tuple[str, str, str]] = []
    current_letter = ""

    # Iterate all descendants in document order; content is deeply nested in divs
    for child in all_section.iter():
        tag = child.tag
        if not isinstance(tag, str):
            continue  # skip comments / processing instructions

        if tag == "h2":
            letter = (child.text_content() or "").strip()
            if len(letter) == 1 and letter.isalpha():
                current_letter = letter.upper()
            continue

        if tag != "p":
            continue

        # Extract all (term, definition) pairs from this paragraph
        strongs = child.cssselect("strong")
        for strong in strongs:
            term = strong.text_content().strip()
            if not term:
                continue

            # Collect definition: tail of <strong>, then text of following siblings
            # up to the next <strong>
            parts: list[str] = []
            if strong.tail:
                parts.append(strong.tail)

            sib = strong.getnext()
            while sib is not None:
                if sib.tag == "strong":
                    break
                parts.append(sib.text_content())
                if sib.tail:
                    parts.append(sib.tail)
                sib = sib.getnext()

            raw = "".join(parts)
            # Strip leading separator (" - ", " – ", ": ", " ") and clean whitespace
            definition = re.sub(r"^\s*[-–:]\s*", "", raw).strip()
            definition = re.sub(r"\s+", " ", definition)

            if term and definition:
                results.append((term, definition, current_letter))

    return results


def run(refresh: bool = False, limit: int | None = None) -> dict:
    """Fetch (once) and parse the BoE Glossary. Returns summary counts."""
    from ingest import http

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch the single glossary page (cached)
    if _RAW_PATH.exists() and not refresh:
        html = _RAW_PATH.read_text(encoding="utf-8")
        fetched_at = ""
        for rec in manifest.read_all(_MANIFEST_PATH):
            fetched_at = rec.get("fetched_at", "")
            break
        if not fetched_at:
            fetched_at = datetime.now(timezone.utc).isoformat()
    else:
        cb = http.CircuitBreaker()
        resp = http.get(_GLOSSARY_URL, circuit_breaker=cb)
        fetched_at = datetime.now(timezone.utc).isoformat()
        html = resp.text
        _RAW_PATH.write_text(html, encoding="utf-8")

    content_sha256 = hashlib.sha256(html.encode()).hexdigest()

    try:
        terms = _extract_terms(html)
    except ParseError as exc:
        return {
            "counts": {"attempted": 0, "ok": 0, "error": 1},
            "errors_by_category": {"parse": [str(exc)]},
        }

    if limit is not None:
        terms = terms[:limit]

    counts = {"attempted": 0, "ok": 0, "error": 0}
    errors_by_category: dict[str, list[str]] = {}
    seen_slugs: dict[str, int] = {}  # slug → occurrence count for dedup

    for term, definition, letter in terms:
        counts["attempted"] += 1
        slug = _slugify(term)
        warnings: list[str] = []

        # Deduplicate: if slug already seen, append occurrence index
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
            warnings.append(f"duplicate slug for term '{term}' — disambiguated")
        else:
            seen_slugs[slug] = 1

        # Skip if already OK in manifest
        if not refresh and manifest.already_processed(_MANIFEST_PATH, slug):
            counts["ok"] += 1
            continue

        processed_path = _PROCESSED_DIR / f"{slug}.md"

        try:
            metadata = {
                "source_url": _GLOSSARY_URL,
                "source": "boe_glossary",
                "slug": slug,
                "title": term,
                "fetched_at": fetched_at,
                "parse_warnings": sorted(warnings),
                "parser_version": _PARSER_VERSION,
            }
            frontmatter_io.write(processed_path, definition, metadata)

            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": _GLOSSARY_URL,
                    "slug": slug,
                    "fetched_at": fetched_at,
                    "status": "ok",
                    "content_sha256": content_sha256,
                    "raw_path": str(_RAW_PATH),
                    "processed_path": str(processed_path),
                    "parse_warnings": warnings,
                },
            )
            counts["ok"] += 1

        except Exception as exc:
            counts["error"] += 1
            errors_by_category.setdefault("unknown", []).append(slug)
            manifest.append(
                _MANIFEST_PATH,
                {
                    "url": _GLOSSARY_URL,
                    "slug": slug,
                    "fetched_at": fetched_at,
                    "status": "error",
                    "content_sha256": "",
                    "raw_path": str(_RAW_PATH),
                    "processed_path": str(processed_path),
                    "parse_warnings": [],
                    "error": {"category": "unknown", "message": str(exc)},
                },
            )

    return {"counts": counts, "errors_by_category": errors_by_category}

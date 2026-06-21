"""
Pure chunking logic — converts a parsed markdown body + metadata into chunk dicts.
No I/O; called by the CLI chunk command.

Two strategies, dispatched by source name:
  Type A (investor_gov, boe_glossary): 1 doc → 1 chunk; paragraph-split only
      if the doc exceeds MAX_TOKENS.
  Type B (investopedia, boe): split at setext H2 section boundaries; sub-split
      large sections by paragraph; carry OVERLAP_TOKENS tail across paragraph
      splits within a section.
"""
from __future__ import annotations

import re
from typing import Optional

MAX_TOKENS = 400
MIN_TOKENS = 30
OVERLAP_TOKENS = 50

_TYPE_A_SOURCES = {"investor_gov", "boe_glossary"}
_TYPE_B_SOURCES = {"investopedia", "boe"}


# ---------------------------------------------------------------------------
# Token approximation
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    """Approximate token count: words × 4/3 (close enough for English prose)."""
    return int(len(text.split()) * 4 / 3)


# ---------------------------------------------------------------------------
# Text splitting helpers
# ---------------------------------------------------------------------------

def _overlap_tail(text: str) -> str:
    """
    Extract the last OVERLAP_TOKENS worth of *text*, trimmed to start at a
    sentence boundary (after '. ', '? ', or '! ') so the overlap reads cleanly.
    """
    words = text.split()
    if len(words) <= OVERLAP_TOKENS:
        return text
    tail = " ".join(words[-OVERLAP_TOKENS:])
    for m in re.finditer(r"[.?!]\s+", tail):
        candidate = tail[m.end():]
        # Only use this boundary if there's still meaningful text after it
        if _approx_tokens(candidate) >= 10:
            return candidate
    return tail


def _split_sentences(text: str) -> list[str]:
    """Last-resort splitter: sentence boundaries."""
    sentences = re.split(r"(?<=[.?!])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for s in sentences:
        t = _approx_tokens(s)
        if current_tokens + t > MAX_TOKENS and current:
            chunks.append(" ".join(current))
            current = [s]
            current_tokens = t
        else:
            current.append(s)
            current_tokens += t
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _split_paragraphs(text: str) -> list[str]:
    """
    Split *text* into chunks ≤ MAX_TOKENS at paragraph boundaries (\n\n).
    Carries an OVERLAP_TOKENS tail into the next chunk when a split occurs.
    Falls through to sentence-splitting for oversized single paragraphs.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _approx_tokens(para)

        if para_tokens > MAX_TOKENS:
            # Single paragraph too large — split by sentence first
            for sent_chunk in _split_sentences(para):
                sc_tokens = _approx_tokens(sent_chunk)
                if current_tokens + sc_tokens > MAX_TOKENS and current:
                    chunks.append("\n\n".join(current))
                    overlap = _overlap_tail(current[-1])
                    current = [overlap, sent_chunk] if overlap else [sent_chunk]
                    current_tokens = sum(_approx_tokens(p) for p in current)
                else:
                    current.append(sent_chunk)
                    current_tokens += sc_tokens
            continue

        if current_tokens + para_tokens > MAX_TOKENS and current:
            chunks.append("\n\n".join(current))
            overlap = _overlap_tail(current[-1])
            current = [overlap, para] if overlap else [para]
            current_tokens = sum(_approx_tokens(p) for p in current)
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [text]


# ---------------------------------------------------------------------------
# Setext H2 splitter
# ---------------------------------------------------------------------------

def _split_setext_h2(text: str) -> list[tuple[Optional[str], str]]:
    """
    Split a markdown body at setext H2 headings (text followed by ---+ underline).

    Returns a list of (heading_or_None, body) pairs.
    The intro before the first heading has heading=None.
    Tail sections (after the last meaningful heading) below MIN_TOKENS are dropped.
    """
    # Match: non-empty line followed by 3+ dashes (setext H2)
    pattern = re.compile(r"^([^\n]+)\n-{3,}[ \t]*$", re.MULTILINE)
    matches = list(pattern.finditer(text))

    if not matches:
        return [(None, text.strip())]

    sections: list[tuple[Optional[str], str]] = []

    # Intro: text before first heading
    intro = text[: matches[0].start()].strip()
    if intro and _approx_tokens(intro) >= MIN_TOKENS:
        sections.append((None, intro))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        if not content or _approx_tokens(content) < MIN_TOKENS:
            continue  # skip empty or nav-only tails ("Find out more" etc.)

        sections.append((heading, content))

    # If everything was dropped, return the whole document as one chunk
    return sections or [(None, text.strip())]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_document(body: str, metadata: dict) -> list[dict]:
    """
    Convert a parsed document body + metadata into a list of chunk dicts.

    Each dict matches the schema defined in step-005-chunking-strategy.md.
    Pure function — deterministic given fixed inputs.
    """
    source = metadata.get("source", "")
    slug = metadata.get("slug", "")
    source_url = metadata.get("source_url", "")
    title = metadata.get("title", "")

    raw_chunks: list[tuple[Optional[str], str]] = []

    if source in _TYPE_A_SOURCES:
        body = body.strip()
        if _approx_tokens(body) <= MAX_TOKENS:
            raw_chunks = [(None, body)]
        else:
            raw_chunks = [(None, t) for t in _split_paragraphs(body)]

    elif source in _TYPE_B_SOURCES:
        sections = _split_setext_h2(body)
        for heading, content in sections:
            if _approx_tokens(content) <= MAX_TOKENS:
                raw_chunks.append((heading, content))
            else:
                for sub in _split_paragraphs(content):
                    if _approx_tokens(sub) >= MIN_TOKENS:
                        raw_chunks.append((heading, sub))

    else:
        # Unknown source — single chunk
        raw_chunks = [(None, body.strip())]

    total = len(raw_chunks)
    chunks: list[dict] = []
    for i, (heading, text) in enumerate(raw_chunks):
        chunks.append(
            {
                "chunk_id": f"{source}/{slug}/{i}",
                "source": source,
                "slug": slug,
                "source_url": source_url,
                "title": title,
                "section_heading": heading,
                "chunk_index": i,
                "total_chunks": total,
                "text": text,
                "token_count": _approx_tokens(text),
            }
        )

    return chunks

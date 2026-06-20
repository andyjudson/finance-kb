# Step 004 — BoE Knowledge Bank ingestion

Read `CLAUDE.md` for project context before starting. This step adds the
second source corpus and deliberately exercises a different HTML shape to
force the shared helpers to earn their abstraction.

## Goal

```bash
uv run ingest boe
```

Crawls the BoE Knowledge Bank index, fetches all explainer articles, parses
each into a frontmatter + markdown file, and writes a manifest. Reuses the
generic helpers from Step 003 unchanged.

## Source facts (verified 2026-06-20)

- **Base URL:** `https://www.bankofengland.co.uk/explainers/`
- **Licensing:** Crown copyright. Open Government Licence v3.0 — cite source
  URL in RAG output; no redistribution restrictions for personal use.
- **robots.txt** (checked 2026-06-20): disallows only internal app paths
  (`/boeapps/`, `/forms/`, `/search/`, etc.); `/explainers/` is explicitly
  permitted for `User-agent: *`. No AI-bot name-blocks.
- **Fetchability:** plain HTTPS returns 200 with server-rendered HTML — no
  Cloudflare or JS challenge.

## URL discovery (two-pass crawl, at ingestion time)

The explainers live at two levels:

1. **Root index** (`/explainers/`) — lists ~16 "featured / category" pages.
2. **Each category page** — links to individual explainer articles (8–27 each).

Both hub pages and individual articles share the same HTML structure and carry
useful educational content — hub pages are not pure navigation; they contain
prose introductions to topic areas. Parse all of them.

Discovery at ingestion time:
1. Fetch `/explainers/` → collect all `/explainers/<slug>` href values.
2. For each of those, fetch the page → collect all `/explainers/<slug>` hrefs.
3. Union of step-1 + step-2 results, deduplicated → sorted list of article URLs.

This keeps the article list in sync with the live BoE site without hardcoding.
The 2026-06-20 crawl yields ~72 unique URLs. The discovery fetch count is small
(~16 pages) and cached on first run like everything else.

## Directory layout

```
data/
├── raw/boe/<slug>.html            # cached HTML, one file per URL
└── processed/boe/
    ├── <slug>.md                  # frontmatter + markdown body
    └── manifest.jsonl
```

## HTML parsing

**Title:** `main h1::text` (works on both hub and article pages)

**Intro / description:** `main .page-description ::text` (join). Prepended to
the markdown body as the first paragraph, not a frontmatter field, so it is
embedded in the content and retrieved by similarity search.

**Content:** `main section.page-section` elements, excluding:
- Any section where `h2::text` (stripped) is `"Most read"` or `"Topics"`.
- `section.page-section--last` (the "Back to top" footer section).
- `nav.nav-chapters` (chapter / table-of-contents nav bar at the top).

Each retained section is serialised with lxml and converted to markdown via
**markdownify** with `strip=["a", "img"]`. Sections are joined with `\n\n`.

**Internal links:** capture `a[href*="bankofengland.co.uk"]::attr(href)` from
all retained sections *before* markdown conversion; store sorted+deduped in
`internal_links` frontmatter.

**Images:** capture `img::attr(alt)` (deduped) in `images_dropped` frontmatter.

## Frontmatter fields (canonical order)

```yaml
source_url: ...
source: boe
slug: ...
title: ...
fetched_at: ...
internal_links: [...]
images_dropped: [...]
parse_warnings: [...]
parser_version: 1
```

## Manifest line schema

Same schema as Step 003 (see `step-003-investor-gov-glossary-ingestion.md`).

## CLI shape

```bash
uv run ingest boe [--refresh] [--limit N] [--skip-discovery]
```

- `--refresh` — force re-fetch even if cached raw HTML exists.
- `--limit N` — process only first N URLs from the discovered list (dev aid).
- `--skip-discovery` — skip the two-pass crawl and use only what's cached in
  `data/raw/boe/` (useful for offline re-parse after a parser change).

## Error handling and politeness

Identical to Step 003:
- Retry transient failures (429, 5xx, network) with tenacity, 3 attempts.
- Circuit breaker at 10 consecutive transient failures.
- 404 / 403 → `not_found` / `forbidden` in manifest, batch continues.
- 1.5s ± 0.5s polite delay between network requests.

## First-run protocol

1. `uv run ingest boe --limit 1` — fetch and parse one article.
2. Open the `.md` file; verify title, clean body, no nav/sidebar, sorted fields.
3. Run `uv run ingest boe` for the full batch.

## Verification

1. `manifest.jsonl` exists with one line per attempted URL.
2. `status == "ok"` count matches the discovered URL count.
3. Spot-check: valid YAML frontmatter, all fields present, clean body.
4. Re-run without `--refresh`: no network fetches, identical `.md` output.

## Constraints / non-goals

- No chunking, no embedding — stops at clean per-URL markdown + manifest.
- Do not commit anything under `data/`.
- Do not modify the Step 003 generic helpers — they should reuse unmodified.
- BoE Glossary (`/glossary`) is a different shape (single-page A-Z); held for
  a future step.

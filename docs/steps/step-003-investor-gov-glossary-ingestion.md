# Step 003 — Glossary ingestion: Investor.gov (auto) + Investopedia (parse-only)

Read `CLAUDE.md` for project context before starting. This is the first
**implementation** step that produces real corpus content.

## What changed from the original plan

The original spec targeted Investopedia for automated fetch. During Step 003,
two blockers emerged (recorded in `docs/sources.md`):

1. Investopedia sits behind a **Cloudflare managed JS challenge** — HTTP 403
   regardless of UA; plain `requests` cannot pass it.
2. Investopedia's `robots.txt` name-blocks `anthropic-ai`, `ClaudeBot`, and
   `Claude-Web` with `Disallow: /`.

Decision (2026-06-20): pivot the **automated fetch** source to **Investor.gov**
(SEC) — public domain, clean `robots.txt`, no challenge. Investopedia is
retained as a **parse-only** supplement: the owner hand-saved ~51 of 52 article
pages to `~/Downloads/investopedia/` and those are parsed locally without any
network access.

## Goals

```bash
# Fetch + parse all Investor.gov terms
uv run ingest investor-gov

# Parse locally-saved Investopedia HTML files (no network)
uv run ingest investopedia --source-dir ~/Downloads/investopedia
```

Both commands share the same generic helpers; the source-specific logic is
isolated per source.

## Directory layout

```
data/
├── raw/
│   ├── investor_gov/<slug>.html       # cached HTML, one file per term
│   └── investopedia/<slug>.html       # copied from source-dir
└── processed/
    ├── investor_gov/
    │   ├── <slug>.md                  # frontmatter + markdown body
    │   └── manifest.jsonl
    └── investopedia/
        ├── <slug>.md
        └── manifest.jsonl
```

All of `data/` is gitignored.

## Code organisation

| Module | Responsibility |
|--------|----------------|
| `ingest/errors.py` | Error categories (`transient`, `not_found`, `forbidden`, `parse`, `unknown`) and result types |
| `ingest/http.py` | HTTP GET with browser UA, tenacity retry/backoff, circuit breaker |
| `ingest/manifest.py` | Append-only JSONL manifest writer/reader |
| `ingest/frontmatter_io.py` | Read/write markdown+frontmatter; canonical field ordering + sorted lists |
| `ingest/sources/investor_gov.py` | Investor.gov fetch + parse |
| `ingest/sources/investopedia.py` | Investopedia parse-only from local HTML |

Generic helpers are designed so Step 004 (BoE) adds a new `sources/boe.py`
and (ideally) nothing else.

## CLI shape

```bash
uv run ingest investor-gov [--refresh] [--limit N]
uv run ingest investopedia --source-dir PATH [--limit N]
```

- `--refresh` — force re-fetch even if cached raw HTML exists (Investor.gov only).
- `--limit N` — process only the first N items (dev aid).
- `--source-dir` — directory of saved `.html` files (Investopedia; defaults to
  `~/Downloads/investopedia`).

## Source specs

### Investor.gov

- **URL list:** `docs/investor-gov-terms.md` (~49 slugs).
- **URL pattern:** `https://www.investor.gov/introduction-investing/investing-basics/glossary/<slug>`
- **Soft-404 detection:** HTTP 200 returned even for unknown slugs. Valid page
  detected by presence of `h1.field--name-title`; absent → `not_found` in manifest.
- **Title selector:** `h1.field--name-title::text`
- **Body selector:** `.field--name-body`
- **Frontmatter fields:** `source_url`, `source` (`"investor_gov"`), `slug`,
  `title`, `fetched_at`, `parser_version`, `parse_warnings`.
- **Politeness:** browser UA, 1.5s ± 0.5s delay, serial, tenacity retry
  (429 → 5/15/45s; 5xx/network → 2/8/32s; max 3 attempts), circuit breaker
  at 10 consecutive retryable failures.

### Investopedia (parse-only)

- **Input:** `<source-dir>/*.html` files saved from browser.
- **Canonical URL:** extracted from `link[rel=canonical]::attr(href)` in each
  file — provides the real URL and slug (`/terms/<l>/<slug>.asp` → `<slug>`).
- **Title selector:** `h1.comp.article-heading.mntl-text-block::text`
- **Content container:** `#article-body_1-0`
- **Strip inside container:** elements matching `.mm-ads-gpt-adunit`,
  `.mntl-sc-block-adslot`, `[class*="askmiso"]`.
- **Internal links:** extract `a[href*="investopedia.com"]::attr(href)` from
  the content container *before* markdown conversion; store sorted+deduped in
  `internal_links` frontmatter.
- **Images:** capture `img::attr(alt)` of body images before stripping; store
  in `images_dropped` frontmatter.
- **Body conversion:** stripped subtree HTML → markdown via **markdownify**
  with `strip=['a', 'img']`.
- **Frontmatter fields:** same as Investor.gov plus `internal_links`,
  `images_dropped`.

## Frontmatter field order (canonical for both sources)

```yaml
source_url: ...
source: investor_gov | investopedia
slug: ...
title: ...
fetched_at: ...          # ISO 8601 UTC; stable once cached (Investor.gov) or set at parse time (Investopedia)
internal_links: [...]    # sorted, deduped (Investopedia only)
images_dropped: [...]    # sorted (Investopedia only)
parse_warnings: [...]    # sorted
parser_version: 1
```

## Manifest line schema

```json
{
  "url": "...",
  "slug": "...",
  "fetched_at": "2026-...Z",
  "status": "ok | error",
  "content_sha256": "...",
  "raw_path": "data/raw/<source>/<slug>.html",
  "processed_path": "data/processed/<source>/<slug>.md",
  "parse_warnings": [],
  "error": { "category": "not_found|forbidden|transient|parse|unknown", "message": "..." }
}
```

`error` present only when `status == "error"`.

## First-run protocol

1. Run `uv run ingest investor-gov --limit 1` — produces one `.md` file.
2. Open it; verify title, clean body, no ads, sorted frontmatter fields.
3. Run full Investor.gov batch.
4. Run `uv run ingest investopedia --limit 1` with any saved HTML file.
5. Verify output as above; then run full Investopedia batch.

## Verification

1. Both `manifest.jsonl` files exist with one line per attempted item.
2. `status == "ok"` count matches input count (minus known-bad slugs/files).
3. Spot-check `.md`: valid YAML frontmatter, all fields present, clean body.
4. Re-run without `--refresh`: no network fetches, identical `.md` output.
5. Failures recorded with sensible `error.category`; batch did not abort.

## Constraints / non-goals

- No chunking, no embedding — stops at clean per-URL markdown + manifest.
- Do not commit anything under `data/`.
- Do not build BoE logic here; do put generic helpers in shared modules.

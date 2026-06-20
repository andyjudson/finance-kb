# Step 003 — Investopedia ingestion script

Read `CLAUDE.md` for project context before starting. This is the first
**implementation** step that produces real corpus content.

## Goal

```
$ uv run ingest investopedia
```

…fetches the ~50 URLs in `docs/investopedia-articles.md`, parses each into a
markdown body + YAML frontmatter file, caches the raw HTML, and writes a
manifest. Each stage is inspectable; failures are recorded, never fatal to the
batch.

This step exercises the chunking pipeline's first input shape (HTML glossary
entries) and establishes the generic ingestion scaffolding that BoE (Step 004)
will reuse.

## Prerequisite — robots.txt check (do this BEFORE writing fetch code)

1. Fetch `https://www.investopedia.com/robots.txt`.
2. Confirm `/terms/` paths are **not** disallowed for our User-Agent (we use a
   browser-impersonating UA — see Politeness below).
3. Record the finding in `docs/sources.md` under the Investopedia section:
   date checked, the relevant rule line(s) verbatim, and a one-line
   interpretation. If `/terms/` is disallowed, **stop and raise it** — do not
   proceed to fetch.

This is a gate, not a code feature. The script may *also* parse `robots.txt`
defensively at runtime, but the human sign-off above happens first.

## Directory layout

```
data/
├── raw/investopedia/<slug>.html          # cached HTML, one per URL
└── processed/investopedia/
    ├── <slug>.md                          # parsed: frontmatter + markdown body
    └── manifest.jsonl                     # one JSON line per URL processed
```

All of `data/` is gitignored (corpus is reproducible from code + URL list).

## Code organisation

Ingestion-specific logic for this source lives in
`ingest/sources/investopedia.py`. Generic helpers go in their own modules under
`ingest/` so Step 004 (BoE) can reuse them without copy-paste:

| Module | Responsibility |
|--------|----------------|
| `ingest/http.py` | HTTP GET with browser UA, tenacity retry/backoff, error categorisation (transient vs permanent), circuit breaker |
| `ingest/manifest.py` | Append-only JSONL manifest writer + reader; manifest line schema |
| `ingest/frontmatter_io.py` | Read/write markdown+frontmatter via `python-frontmatter`; canonical field ordering + sorted lists for determinism |
| `ingest/errors.py` | Error categories (`transient`, `not_found`, `forbidden`, `parse`, `unknown`) and a small result/exception taxonomy |
| `ingest/sources/investopedia.py` | URL list loading, per-URL orchestration (fetch→cache→parse→write), Investopedia-specific parsing |

Keep the source module thin on generic concerns: it calls `http.get(...)`,
`manifest.append(...)`, `frontmatter_io.write(...)`. The split is the point —
BoE should need a new `sources/boe.py` and (ideally) nothing else new.

## CLI shape

Extend `ingest/cli.py` with an `investopedia` command:

```
uv run ingest investopedia [--refresh] [--limit N]
```

- `--refresh` — force re-fetch even if cached raw HTML exists (default: use cache).
- `--limit N` — process only the first N URLs from the list (development aid;
  pairs with the first-run protocol below).

Keep the existing `info` command and the `@app.callback()` (so Typer keeps the
multi-command structure).

## Behaviour & decisions

### 1. HTML parsing
Use **parsel** with CSS selectors to locate and extract the article subtree.
Prefer stable structural selectors (article container, heading tags) over
brittle class-name chains; record any selector that looks fragile as a
`parse_warning`.

### 2. Output format
One file per URL: YAML **frontmatter** + markdown **body**.
- I/O via **python-frontmatter**.
- HTML→markdown conversion of the *extracted article subtree* via
  **markdownify** (or equivalent).

### 3. What to extract / strip
**Keep:** article title (H1), body paragraphs, **all** section headings
(preserve hierarchy), lists, the **Key Takeaways** callout, tables (as markdown
tables).
**Strip:** nav, sidebar, ads + ad disclosures, footer, social/share, newsletter
signup, related articles, breadcrumbs, author bio, and **body images**.

### 4. Frontmatter fields
Canonical order, deterministic output:

| Field | Type | Notes |
|-------|------|-------|
| `source_url` | str | the fetched URL |
| `source` | str | constant `"investopedia"` |
| `slug` | str | derived from URL (`/terms/<l>/<slug>.asp` → `<slug>`) |
| `title` | str | article H1 |
| `fetched_at` | str | ISO 8601 **UTC** (the raw HTML's fetch time) |
| `last_updated` | str \| null | from page metadata if present, else null |
| `internal_links` | list[str] | **sorted**, deduped investopedia.com URLs referenced in the body |
| `images_dropped` | list[str] | alt text of stripped body images (or count if alt absent) |
| `parse_warnings` | list[str] | **sorted** |
| `parser_version` | int | starts at `1`; bump when parsing logic changes output |

Determinism note: given fixed raw HTML, the parser must emit byte-identical
output **except** `fetched_at` (which reflects when the raw was fetched and is
stable once cached). Sorted lists + fixed field order enforce this.

### 5. Links in body
Strip `<a>` tags during markdown conversion — keep **visible text only**.
Capture internal (investopedia.com) link targets in `internal_links`
frontmatter instead. (Extract links from the subtree with parsel *before*
markdownify strips them.)

### 6. Cache
If `data/raw/investopedia/<slug>.html` exists, **skip the fetch** by default.
`--refresh` forces re-fetch. **Parsing always re-runs** from the current raw
HTML, so re-parsing after a parser change needs no re-fetch.

### 7. Manifest line (`manifest.jsonl`)
One JSON object per URL processed:

```json
{
  "url": "...",
  "slug": "...",
  "fetched_at": "2026-...Z",
  "status": "ok | error",
  "content_sha256": "<sha256 of raw HTML>",
  "raw_path": "data/raw/investopedia/<slug>.html",
  "processed_path": "data/processed/investopedia/<slug>.md",
  "parse_warnings": ["...", "..."],
  "error": { "category": "not_found|forbidden|transient|parse|unknown", "message": "..." }
}
```

`error` present only when `status == "error"`. `content_sha256` lets us detect
when a re-fetch actually changed the source.

### 8. Error handling & retry
- Per-URL `try/except`: a failure is recorded to the manifest and the batch
  **continues**.
- Retry **transient** failures (429, 5xx, network errors) with **tenacity**
  backoff, up to **3 attempts**:
  - 429 → 5s / 15s / 45s
  - 5xx and network → 2s / 8s / 32s
- **No retry** on 404 / 403 (record as `not_found` / `forbidden`).
- **Circuit breaker:** 10 consecutive *retryable* failures → abort the whole
  run with a clear message (likely a block or outage, not per-URL noise).

### 9. Politeness
- **Browser-impersonating User-Agent** (`Mozilla/5.0 ...`). This is the
  pragmatic choice; record it as *pragmatic-not-purist* in `docs/sources.md`
  under Investopedia (alongside the robots.txt finding).
- **1.5s** baseline delay between requests, **±0.5s** jitter, **serial** (no
  concurrency).

### 10. End-of-run summary (console)
Print: attempted / succeeded / failed counts; the list of failed URLs grouped
by error category; and a pointer to `manifest.jsonl` for detail.

### 11. Dependencies
Add to `pyproject.toml` and `uv sync`:
`parsel`, `requests`, `tenacity`, `markdownify`, `python-frontmatter`.

## First-run protocol (do NOT blast all 50 immediately)

1. Run a single URL first — `uv run ingest investopedia --limit 1` with
   `bond.asp` at the top of the list (or temporarily point the loader at just
   that URL).
2. Open the produced `data/processed/investopedia/bond.md`. Verify:
   - Title, headings, lists, Key Takeaways, and any tables survived.
   - Nav/ads/related/author-bio are gone.
   - `internal_links` looks sane and sorted; body has visible link text but no
     markdown links; body images stripped and counted.
3. Only once the single-file output looks right, run the full batch
   (`uv run ingest investopedia`).

This catches wrong selectors before they cost 50 fetches.

## Verification

After a full run, confirm:
1. `data/processed/investopedia/manifest.jsonl` exists and has one line per
   attempted URL.
2. Count of `status == "ok"` lines roughly matches the URL list (minus any
   known-bad URLs, which should appear as `not_found`).
3. Spot-check one `.md` file: frontmatter parses as valid YAML, all fields
   present, lists sorted, body is clean markdown.
4. Re-running without `--refresh` performs **no** network fetches (cache hit)
   and reproduces identical `.md` output.
5. Failed URLs are recorded with a sensible `error.category`; the batch did not
   abort on individual failures.

## Constraints / non-goals

- **No chunking, no embedding** — this step stops at clean per-URL markdown +
  manifest. (Chunking is Step 005.)
- Do **not** commit anything under `data/` — it stays gitignored.
- Do **not** build BoE logic here, but **do** put generic helpers in shared
  modules so Step 004 can reuse them.
- Do not add dependencies beyond those listed in §11.

## When done

Report back with:
- The robots.txt finding and UA note as recorded in `docs/sources.md`.
- Output of the end-of-run summary.
- Verification checklist results (the five checks above).
- Any URLs from `docs/investopedia-articles.md` that 404'd and need patching.

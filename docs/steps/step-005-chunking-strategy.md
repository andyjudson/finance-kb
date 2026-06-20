# Step 005 — Chunking strategy

Read `CLAUDE.md` for project context before starting. This step converts
the per-document markdown files produced by Steps 003–004 into the chunks
that will be embedded in Step 006. No network access, no embedding — purely
a text-processing pipeline reading from `data/processed/` and writing to
`data/chunks/`.

## Why chunking matters (learning note)

The embedding model receives a fixed-length text window. Feeding an entire
long article would either overflow the window (content silently truncated)
or produce a single dense embedding that averages over unrelated topics.
Chunking at meaningful semantic boundaries — section headings first, then
paragraphs — keeps each embedding focused on one idea, which makes
similarity search more precise.

The opposite failure mode is chunks that are too small: a 5-word glossary
entry produces an embedding that doesn't capture the concept's context well
because there's barely anything to embed. That's why different document types
get different chunking strategies here.

## Corpus snapshot (measured 2026-06-20)

| Source | Docs | p10 tokens | p50 tokens | p90 tokens | max tokens |
|--------|------|------------|------------|------------|------------|
| Investor.gov | 50 | 21 | 85 | 392 | 1197 |
| Investopedia | 57 | 1270 | 2104 | 3858 | 5693 |
| BoE explainers | 58 | 544 | 818 | 1177 | 2969 |
| BoE glossary | 545 | 2 | 4 | 14 | 89 |

Token counts are approximate (`word_count × 4/3`). The actual tokenizer
used in Step 006 will differ slightly but the relative sizes are stable.

## Markdown heading format (what the parsers actually output)

Both Investopedia and BoE explainer parsers use **markdownify**, which
renders `<h2>` as **setext style** (text followed by `---` underline) and
`<h3>` as **ATX style** (`### heading`). This matters for the splitter:

```markdown
What Is a Bond?          ← H2 (setext) — primary section boundary
---------------

Bonds are offered by...

### Key Takeaways        ← H3 (ATX) — callout box, often small
```

The chunker must detect **both** setext H2 (`text\n---+`) and ATX H2/H3
(`## heading`) as potential split points. In practice, setext H2 is the
dominant boundary in these corpora.

## Chunking strategy by source type

### Type A — glossary entries (Investor.gov, BoE glossary)

**1 document → 1 chunk in almost all cases.**

The p90 body size is 392 tokens (Investor.gov) and 14 tokens (BoE glossary).
Both are below the 400-token target. The 4 Investor.gov documents that exceed
400 tokens are split by paragraph (`\n\n` boundary); no further splitting is
expected given their structure.

Output: typically 50 + 545 = ~595 chunks (very close to document count).

### Type B — structured long articles (Investopedia, BoE explainers)

**Split at setext H2 headings; sub-split within a section if needed.**

Algorithm (applied to each document):

1. **Parse into sections.** Split the markdown body at setext H2 boundaries
   (`^.+\n[-]{3,}$` multi-line regex). The text before the first H2 is an
   `(intro)` section; text after the last H2 is a `(tail)` section (usually
   "Find out more" links — discard if below `MIN_TOKENS`).
2. **Merge small H3 callouts into their parent section.** ATX H3 blocks that
   are below `MIN_TOKENS` (30 tokens) are concatenated with the previous
   section rather than emitted as standalone chunks. This prevents embedding
   isolated stat callouts like `### One million\nIncrease in unemployment`.
3. **Check section size.** If a section ≤ `MAX_TOKENS` (400): emit as a
   single chunk.
4. **Split large sections by paragraph.** If a section > `MAX_TOKENS`: split
   at `\n\n` boundaries, accumulating paragraphs until adding the next one
   would exceed `MAX_TOKENS`. When a split happens, carry the last
   `OVERLAP_TOKENS` (50) of the current chunk as the start of the next
   (sentence-level trim — don't cut mid-word).
5. **Handle oversized paragraphs.** If a single paragraph > `MAX_TOKENS`
   (rare), split at sentence boundaries (`. `, `? `, `! `).

Constants:
- `MAX_TOKENS = 400` — ceiling for a single chunk before splitting.
- `MIN_TOKENS = 30` — floor below which a section is merged with its
  neighbour rather than emitted as a standalone chunk.
- `OVERLAP_TOKENS = 50` — tail carried into the next chunk when splitting
  within a section (0 at clean H2 section boundaries).

Output: estimated 350–500 chunks from Investopedia + BoE explainers
combined (rough: 57 articles × 5 sections avg + 58 articles × 3 sections).

## Token counting

**This step uses a word-count approximation:** `tokens ≈ len(text.split()) × 4/3`.

This is intentional — the target embedding model is not chosen until Step 006,
and the difference between this approximation and the real WordPiece or BPE
tokenizer is small for English prose (< 15%). At Step 006, once the tokenizer
is known, the approximation can be validated or replaced by re-running the
chunk step (all processing is local, no re-fetching).

Do NOT add `tiktoken` or `sentence-transformers` as a Step 005 dependency
— those belong to Step 006.

## Chunk schema

Each chunk is one JSON object written to a JSONL file:

```json
{
  "chunk_id": "investopedia/creditdefaultswap/3",
  "source": "investopedia",
  "slug": "creditdefaultswap",
  "source_url": "https://www.investopedia.com/terms/c/creditdefaultswap.asp",
  "title": "Credit Default Swap: What It Is and How It Works",
  "section_heading": "Cons of Credit Default Swaps",
  "chunk_index": 3,
  "total_chunks": 8,
  "text": "Credit default swaps have been criticised ...",
  "token_count": 312
}
```

Field notes:
- `chunk_id` — unique string across the whole corpus; format
  `<source>/<slug>/<chunk_index>`.
- `section_heading` — the setext H2 heading text (stripped), or `null` for
  single-chunk documents and the intro section before the first heading.
- `text` — the raw chunk content. No title/heading prefix is added here.
  Step 006 can prepend context at embed time if Contextual Retrieval is
  enabled (see below).
- `token_count` — approximate, using the word-count formula above.

## Output layout

```
data/
└── chunks/
    ├── investor_gov.jsonl
    ├── investopedia.jsonl
    ├── boe.jsonl
    └── boe_glossary.jsonl
```

All under `data/chunks/` — gitignored along with the rest of `data/`.

## Code organisation

| Module | Responsibility |
|--------|----------------|
| `ingest/chunker.py` | `chunk_document(body, metadata) → list[dict]` — pure function, no I/O |
| `ingest/sources/chunk_*.py` | **No new files.** Source-specific chunking is driven by the `source` field in existing frontmatter; the `chunker.py` module dispatches to Type A or Type B strategy based on source. |
| `ingest/cli.py` | New `chunk` command |

`chunker.py` is the only new file. Keep it pure: it reads a body string and
a metadata dict, returns a list of chunk dicts. The CLI handles file I/O and
JSONL writing.

## CLI shape

```bash
uv run ingest chunk [--source SOURCE] [--limit N]
```

- `SOURCE` — one of `investor-gov`, `investopedia`, `boe`, `boe-glossary`,
  or `all` (default). Determines which `data/processed/<source>/` directory
  to read from.
- `--limit N` — process only the first N documents per source (dev aid).

The `chunk` command is **idempotent**: it overwrites the JSONL output file
on each run. There is no manifest for chunks — the JSONL is the complete
output.

## First-run protocol

1. `uv run ingest chunk --source investor-gov --limit 3`
   - Open `data/chunks/investor_gov.jsonl`. Verify all three docs emit
     exactly 1 chunk each. Confirm `section_heading` is null, `token_count`
     is plausible.
2. `uv run ingest chunk --source investopedia --limit 1` (pick a long doc)
   - Open `data/chunks/investopedia.jsonl`. Verify the document is split into
     multiple chunks at H2 boundaries. Check that no chunk exceeds
     `MAX_TOKENS` tokens. Check `total_chunks` is consistent.
3. Full run: `uv run ingest chunk --source all`
   - Print summary: chunks per source, min/p50/max token count per source.

## Verification

After full run:
1. Total chunks across all four JSONL files — expect roughly 1200–1400
   (dominated by BoE glossary's ~545 single-term chunks).
2. No chunk exceeds `MAX_TOKENS` (400 tokens).
3. No chunk below `MIN_TOKENS` (30 tokens) is emitted as standalone — those
   should have been merged.
4. `chunk_id` values are unique within each JSONL file.
5. Every chunk has a non-empty `text` and a valid `source_url`.
6. Re-running produces identical output (pure function, no timestamp in chunk
   data).

## Future upgrade path — Contextual Retrieval

Anthropic's Contextual Retrieval technique enriches each chunk with a short
description of its document-level context before embedding, improving
retrieval accuracy for chunks that are ambiguous in isolation.

Example: a chunk about "credit risk" might appear in five different articles.
With Contextual Retrieval, before embedding, each chunk is prepended with a
LLM-generated sentence like:

> "This excerpt is from an Investopedia article on Credit Default Swaps."

Implementation would look like:
1. For each chunk, call Claude (`claude-haiku-4-5`) with the full document +
   chunk text, asking for a short situating sentence.
2. Store the enriched text alongside the raw chunk.
3. Embed the enriched text, keep the raw text for display.

The Step 005 schema accommodates this: `text` holds the raw chunk; Step 006
or a later step adds an `embed_text` field with the enriched version.

Cost estimate: ~550 Claude Haiku calls × ~2000 input tokens × $0.80/M = ~$0.88
one-time. Not part of the initial build but worth knowing it's cheap.

## Constraints / non-goals

- No embedding in this step — stops at JSONL files.
- Do not modify any file under `data/processed/` — read-only.
- Do not add `tiktoken` or `sentence-transformers` as a dependency here.
- Do not implement Contextual Retrieval here — document the pattern only.

# Step 006 — Embedding + Chroma vector store

Read `CLAUDE.md` and `docs/steps/step-005-chunking-strategy.md` for context.
This is an **implementation step**. It takes the JSONL chunk files produced
by Step 005 (`data/chunks/*.jsonl`) and turns them into a queryable vector
index on disk (`data/index/`). No answer generation — that's Step 007.

## Why this step exists (learning note)

Steps 003–005 produced chunks: short, self-contained pieces of text with
citation metadata. A chunk is still just *text* — to retrieve "the chunks
most relevant to a question" we need to compare meaning, not keywords. An
**embedding model** maps each chunk to a fixed-length vector (here, 768
floats) positioned so that semantically similar texts land near each other.
A **vector store** indexes those vectors so that, given a query vector, it
can return the nearest chunks quickly.

This step is the first time the project spends real compute on *meaning*.
It's deliberately kept separate from retrieval+generation (Step 007) so the
index can be built, inspected, and rebuilt in isolation — the same
inspectability principle that drove the per-stage ingestion split.

Two things are worth understanding before reading the rest:

- **The embedding model is frozen into the index.** Every chunk vector and
  every future query vector must come from the *same* model. If we change
  the model later, the whole index must be rebuilt. That's why
  `metadata.json` records the exact model name and dimensions — it's the
  provenance that tells a future query "you must embed questions with *this*
  model or the distances are meaningless."
- **Embedding is local and unmetered here.** `bge-base-en-v1.5` runs on the
  machine via `sentence-transformers`; there is no per-token cost and the
  index can be rebuilt freely. This is the deliberate Pattern B split from
  `CLAUDE.md`: free local embeddings, paid Claude generation later.

## Locked decisions (from the planning brief)

1. **Embedding model: `BAAI/bge-base-en-v1.5`** via `sentence-transformers`.
   768-dim, ~440 MB cached download on first use. CPU acceptable, GPU
   optional. Chosen over `bge-small` because the corpus is small enough that
   the resource cost is negligible and starting at `base` avoids a likely
   upgrade loop. `bge-large-en-v1.5` remains a diminishing-returns option if
   `base` proves weak.
2. **Vector store: Chroma**, local persistent client at `data/index/`.
3. **Provenance file: `data/index/metadata.json`** — the embedding-stage
   analogue of `parser_version`.
4. **Re-runnable:** `uv run ingest embed` reads `data/chunks/`, writes
   `data/index/`. A `--rebuild` flag wipes `data/index/` first. No
   `--refresh` flag.
5. **Vector keyed by `chunk_id`**; chunk text + citation frontmatter stored
   as Chroma metadata.
6. **New dependencies:** `chromadb`, `sentence-transformers`.

## Design decision — one collection, `source` as metadata

The brief leaves the collection layout to Claude Code. **Recommendation: a
single Chroma collection (`finance_kb`) with `source` stored as a metadata
field on every chunk**, rather than one collection per corpus.

Rationale:

- **Retrieval is cross-source by intent.** A question like "what is a coupon
  rate?" should find the best chunk whether it came from Investor.gov, BoE,
  or Investopedia. With separate collections we'd have to query all four and
  merge/re-rank results by hand — re-implementing what one collection does
  natively. The whole point of the index is a single nearest-neighbour
  search over the whole corpus.
- **Filtering is still free.** Chroma's `where={"source": "boe"}` gives
  per-source scoping on demand, so the multi-collection capability isn't
  lost — it's just expressed as a query filter instead of a storage split.
- **Simpler provenance and counts.** One collection means one place to count
  vectors and one `metadata.json`; `source_counts` is derived from the
  metadata field.
- **Matches the Layer 2/3 future.** As the corpus grows to risk and capital
  sources, "one collection, filter by `source`/`layer`" scales without a
  collection-per-source explosion.

The only thing we give up is physically separate stores per source, which
this project has no need for (single user, single index, always queried as
a whole).

## Dependencies

Add to `pyproject.toml`:

- `chromadb` — the vector store. Pulls a moderate dependency tree
  (`onnxruntime`, `pydantic`, etc.); acceptable for a learning project.
- `sentence-transformers` — wraps the BGE model and the HuggingFace
  download/caching. Pulls `torch` (CPU build by default on macOS).

First run downloads `BAAI/bge-base-en-v1.5` (~440 MB) into the HuggingFace
cache (`~/.cache/huggingface/`). Subsequent runs load from cache offline.
Note in the run output that the first invocation will be slow due to the
download.

**BGE query prefix gotcha (learning note + correctness requirement):** the
BGE family is trained so that *queries* (not documents) are prefixed with a
short instruction:
`"Represent this sentence for searching relevant passages: "`. Documents are
embedded with no prefix. Using the wrong prefix degrades retrieval. For this
step:

- **Documents (chunks):** embed with **no prefix**.
- **The smoke-test query:** embed **with** the query prefix.

This asymmetry must be encoded in the embedding helper so Step 007 inherits
it correctly.

## Code organisation

| Module | Responsibility |
|--------|----------------|
| `ingest/embedder.py` | Thin wrapper around `sentence-transformers`: lazy-load the model once, expose `embed_documents(texts)` and `embed_query(text)` (query applies the BGE prefix). Holds the model name constant. |
| `ingest/vector_store.py` | Chroma persistent client + collection helpers: `get_collection(rebuild=False)`, `add_chunks(...)`, `query(text, n_results, where=None)`, plus `write_index_metadata(...)`. Keeps Chroma specifics in one place so a future store swap is localised. |
| `ingest/cli.py` | New `embed` command (build index) and a small `query` command (smoke test). |

`embedder.py` and `vector_store.py` are the two new modules. `chunker.py`
stays untouched.

### Model loading

Load the model **once** per process (module-level lazy singleton), not per
chunk. Embed in batches (`model.encode(texts, batch_size=..., normalize_embeddings=True)`).

**Normalisation:** encode with `normalize_embeddings=True` and create the
Chroma collection with cosine space
(`metadata={"hnsw:space": "cosine"}`). Normalised vectors + cosine is the
standard, well-behaved setup for BGE and makes distances comparable.

## Index build — `embed` command

```bash
uv run ingest embed [--rebuild] [--source SOURCE] [--limit N]
```

- `--rebuild` — delete `data/index/` first, then build from scratch. Without
  it, the command builds into the existing index (see idempotency note).
- `--source SOURCE` — embed only one source's JSONL (`investor-gov`,
  `investopedia`, `boe`, `boe-glossary`); default all. Dev aid.
- `--limit N` — embed only the first N chunks per source. Dev aid.

Algorithm:

1. Resolve input: read the selected `data/chunks/<source>.jsonl` file(s)
   into a list of chunk dicts.
2. If `--rebuild`: remove `data/index/` entirely before opening the client.
3. Open the Chroma `PersistentClient(path="data/index")`, get-or-create the
   `finance_kb` collection (cosine space).
4. For each chunk, assemble:
   - `id` = `chunk_id`
   - `document` = `text`
   - `metadata` = `{source, slug, title, source_url, section_heading,
     chunk_index, total_chunks, token_count}` (Chroma metadata values must
     be str/int/float/bool — `section_heading` may be `None`, so coerce
     `None` → `""`).
5. Embed `document` texts in batches with **no** prefix; `collection.add(...)`
   (or `upsert`) ids, embeddings, documents, metadatas.
6. Write `data/index/metadata.json`.

**Idempotency:** use `collection.upsert` keyed on `chunk_id` so a re-run
without `--rebuild` overwrites matching ids rather than duplicating them.
`--rebuild` remains the clean-slate path. (Chroma's own SQLite/PARQUET files
live under `data/index/` alongside `metadata.json`.)

### `metadata.json` shape

```json
{
  "model_name": "BAAI/bge-base-en-v1.5",
  "model_version": null,
  "dimensions": 768,
  "embedded_at": "2026-06-21T14:32:00Z",
  "chunk_count": 1564,
  "chunks_dir": "data/chunks",
  "query_prefix": "Represent this sentence for searching relevant passages: ",
  "source_counts": [
    {"source": "investor_gov", "chunks": 56},
    {"source": "investopedia", "chunks": 715},
    {"source": "boe", "chunks": 248},
    {"source": "boe_glossary", "chunks": 545}
  ]
}
```

- `model_version` — `sentence-transformers` doesn't always expose a clean
  version string; record it if available (e.g. from the model card / config),
  else `null`. Don't block on it.
- `embedded_at` — ISO 8601 UTC, matching the parser timestamp convention.
- `query_prefix` — recorded so Step 007 reads the exact prefix from the index
  rather than hard-coding it, keeping query/document embedding consistent
  with whatever built the index.

## Smoke-test query — `query` command

```bash
uv run ingest query "what is a coupon rate?" [--n 5] [--source SOURCE]
```

- Embeds the question **with** the BGE query prefix.
- Runs `collection.query(query_embeddings=[...], n_results=n, where=...)`.
- Prints, per result: rank, distance, `source`, `title`, `source_url`, and
  the first ~200 chars of the chunk text.

This is a pipeline smoke test only. **Content quality is explicitly not
assessed at this step** — we are confirming that embedding, storage, and
nearest-neighbour retrieval work end to end and that citation metadata
survives the round-trip. Whether the *right* chunk comes back is a Step 007+
concern (and the place where re-ranking / contextual retrieval would enter).

## First-run protocol

1. `uv run ingest embed --source investor-gov --limit 5 --rebuild`
   - Confirms the model downloads/loads and a tiny index builds. Inspect
     `data/index/` — Chroma files + `metadata.json` present, `chunk_count`
     is 5.
2. `uv run ingest embed --rebuild`
   - Full build. Watch the printed per-source counts and total.
3. `uv run ingest query "what is a coupon rate?"`
   - Confirm 5 results print with distances, titles, and URLs.
4. `uv run ingest query "what is a coupon rate?" --source boe_glossary`
   - Confirm the `where` filter restricts results to one source.

## Verification

1. `data/index/` exists with Chroma's expected layout (SQLite + collection
   data) plus `metadata.json`.
2. `metadata.json` records `model_name = "BAAI/bge-base-en-v1.5"` and
   `dimensions = 768` correctly.
3. `collection.count()` equals the total number of input chunks from
   `data/chunks/` (1564 at time of writing), and equals the sum of
   `source_counts`.
4. A smoke-test similarity query returns the requested number of results,
   each carrying `source`, `title`, and `source_url` metadata.
5. Re-running `embed` **without** `--rebuild` leaves `collection.count()`
   unchanged (upsert, not duplicate).

## Out of scope

- No answer generation (Step 007).
- No re-ranking, no hybrid/keyword search, no Contextual Retrieval.
- No A/B comparison against other embedding models.

## Open / non-locked considerations (project memory, not this step)

Documented for a future revisit if Plan A (local `bge-base`) proves weak:

- **`bge-large-en-v1.5`** — free, larger, diminishing-returns quality bump.
  Drop-in model-name swap + index rebuild.
- **`voyage-finance-2`** — paid, finance-domain-tuned; the most relevant paid
  option for this project. Would move embedding off the free local path and
  introduce per-token embedding cost (still small at this corpus size).
- **Contextual Retrieval** — Claude-API chunk enrichment (Step 005 spec
  documents the ~$0.88 one-time cost). Independent technique; layers on top
  of either free or paid embeddings.

The asymmetric BGE prefix handling means a model swap also means revisiting
the prefix convention (`voyage`/`large` have their own conventions) — another
reason `query_prefix` lives in `metadata.json` rather than in code.

# Learnings

Finance, banking, and capital reporting concepts encountered while building this project. This is a personal notebook — written for future-me, not for anyone else. Brief and dated is better than polished and rare.

## How to use this file

Add entries as concepts click, terminology gets clarified, or surprises emerge. Loose format:

> **YYYY-MM-DD — Concept name**
> Short description in own words. Why it matters. What was confusing about it. Link to source if relevant.

Group by Layer (1/2/3) once enough entries accrue to justify it.

---

## Starting baseline — 2026-06-20

What I roughly know entering this project:

- **High level capital concepts** — banks hold capital against risk; CET1, AT1, T2 are capital tiers; RWA is risk-weighted assets; Basel III is the international framework; CRR / CRD are the EU implementation; PRA Rulebook is the UK equivalent.
- **Engineering side** — Spark, Databricks, data mesh, regulatory reporting platforms, the workflow of risk and capital data through a bank's tech stack.

What I'm aiming to actually understand:

- **Layer 1** — what banks and traders do day-to-day. Trades, positions, instruments, markets, settlement, clearing. The vocabulary the regulatory texts assume.
- **Layer 2** — risk types in detail. Market vs credit vs operational vs liquidity. How they're measured. Where the line between them sits in practice.
- **Layer 3** — capital reporting end-to-end. Why specific items count as CET1 vs AT1 vs T2. How RWA is calculated for different exposure types. The structure of regulatory reports.

---

## Entries

> **2026-06-20 — Cost model for the RAG system (AI-engineering note)**
>
> Worked out where the money actually goes, because I had no intuition for the magnitude. Anthropic API prices are authoritative (from the claude-api skill); the paid-embedding figures are from memory and need verifying before relying on them.
>
> **Sizing assumption:** Phase 0 corpus ≈ 50 Investopedia + ~100 BoE explainers ≈ **250k–350k tokens total**. Tiny — and that changes which fears are real.
>
> Three cost buckets, very different sizes:
>
> 1. **Embedding the corpus (one-off, repeats each re-index).** Local `sentence-transformers` = **$0** (runs on the Mac, unmetered). A paid embedding API *at this size* would be **~$0.01–0.06 for the whole corpus** — pennies. The "don't get stung by Voyage" instinct is sound as a principle but the real exposure is cents here; that fear is about million-to-billion-token corpora, not 150 articles. So local-vs-paid is a learning/inspectability call, not a cost one.
> 2. **Contextual Retrieval enrichment (Step 005+ upgrade, one-off per re-index).** LLM call per chunk with the parent doc as context — *generation*, not embedding. With prompt caching ≈ **<$1 for this corpus**, a couple dollars without. First place real tokens get spent across the whole corpus.
> 3. **Query-time generation (the recurring/monthly cost — this is the real "x").** Per question: retrieve ~5–15 chunks (~3–5k input tokens incl. system prompt + question) → ~600-token cited answer.
>
> | Generation model | $/query | @10 q/day (~300/mo) | @30 q/day (~900/mo) |
> |---|---|---|---|
> | Opus 4.8 ($5/$25 per 1M) | ~$0.040 | ~$12/mo | ~$36/mo |
> | Sonnet 4.6 ($3/$15) | ~$0.024 | ~$7/mo | ~$22/mo |
> | Haiku 4.5 ($1/$5) | ~$0.008 | ~$2/mo | ~$7/mo |
>
> **Takeaways:** recurring cost is **~$5–35/month**, and the dominant dial is *which model generates the answer* — not embeddings, vector store, or corpus size. One-off index cost is **$0–5**. Nothing here reaches hundreds at this scale.
>
> **What could actually sting** (not embeddings): (1) a bug that loops queries; (2) switching to a paid embedding API *and* a much larger corpus later (Layer 2/3 regulatory PDFs); (3) Opus + high `max_tokens` on a chatty loop. Guardrails that cap the downside: **set a spend cap + alert in the Anthropic Console**, keep embeddings **local** so re-indexing stays unmetered, and **log `response.usage` per query** so x is measured, not guessed. `count_tokens` prices a query before sending it. Step 007 (RAG CLI) is the place to print per-query cost.

---

> **2026-06-23 — RAG building blocks: glossary + end-to-end flow (AI-engineering note)**
>
> A single place to refresh the mental model, written as I build it. The detail lives in the step specs (linked); this is the map, not the territory. **RAG = Retrieval-Augmented Generation:** instead of asking the LLM to answer from its own training, you *retrieve* the most relevant pieces of your own documents and *augment* the prompt with them, so the model answers from sources you control and can cite. The whole pipeline exists to turn "a pile of web pages" into "the 5 most relevant paragraphs to put in front of Claude."
>
> **The end-to-end flow (this project's pipeline):**
>
> ```
> fetch → parse → chunk → embed → store        ← indexing (build once, re-run on change)
>                                  ↓
>                            vector index
>                                  ↑
>              question → embed → retrieve → generate → cited answer   ← query (every question)
> ```
>
> The split that matters: **indexing happens offline and rarely** (and is free here — local embeddings); **retrieval + generation happen per question** (and generation is the recurring cost). Same embedding model must be used on both sides — see "embedding" below.
>
> | Stage | What it does | Output | Where (code / spec) |
> |---|---|---|---|
> | **Fetch** | HTTP GET the source page, cache raw HTML | `data/raw/` | `ingest/http.py`, `ingest/sources/*` |
> | **Parse** | Strip nav/ads, convert HTML → clean markdown + citation frontmatter | `data/processed/*.md` | `ingest/sources/*`, Steps 003–004 |
> | **Chunk** | Split each doc into focused, self-contained pieces | `data/chunks/*.jsonl` | `ingest/chunker.py`, Step 005 |
> | **Embed** | Turn each chunk's text into a 768-dim vector | vectors | `ingest/embedder.py` (planned), Step 006 |
> | **Store** | Index vectors + metadata for fast nearest-neighbour search | `data/index/` (Chroma) | `ingest/vector_store.py` (planned), Step 006 |
> | **Retrieve** | Embed the question, find the top-k nearest chunks | chunk list | Step 007 |
> | **Generate** | Put chunks + question to Claude, get a cited answer | answer + sources | Step 007 / `api/` |
>
> **Glossary** (terms in roughly the order they bite):
>
> - **Chunk** — a small, self-contained slice of a document (here ≤ ~400 tokens). The unit of retrieval: you retrieve and cite *chunks*, not whole docs. Too big → the embedding averages over unrelated ideas; too small → not enough context to embed meaningfully. See Step 005.
> - **Chunking strategy** — the rules for *where* to split. This project uses two: Type A (glossary entries = 1 doc → 1 chunk) and Type B (long articles split at section headings, then paragraphs). Splitting at *semantic* boundaries (headings) beats splitting every N characters.
> - **Overlap** — when a long section is split mid-flow, carry the last ~50 tokens of one chunk into the start of the next, so an idea spanning the boundary isn't orphaned from either side.
> - **Token** — the model's unit of text (~¾ of a word). Embedding models and Claude both price/limit by tokens. Step 005 uses a cheap word-count approximation (`words × 4/3`) because the real tokenizer isn't chosen until embedding.
> - **Embedding** — a fixed-length vector (here 768 numbers) that encodes a text's *meaning*, positioned so similar meanings land near each other. Produced by an **embedding model** (`BAAI/bge-base-en-v1.5` here, run locally). **Critical rule:** the same model must embed both the stored chunks and the query — distances between vectors from different models are meaningless. That's why the index records its model name (provenance); a model swap = full re-index.
> - **Dimensionality** — how many numbers in each vector (768 for bge-base). More dimensions ≈ more nuance, more storage/compute. Not a dial you tune; it's fixed by the model.
> - **Query/document asymmetry** — a model-specific gotcha: BGE is trained to prefix *queries* (not documents) with an instruction string. Get it wrong and retrieval silently degrades. Recorded in the index so query-time inherits it. See Step 006.
> - **Vector store / vector database** — stores the vectors + their metadata and answers "give me the k nearest vectors to this one" fast. **Chroma** here (local, file-based). Picked for simplicity/learning over scale.
> - **Similarity search / nearest-neighbour** — the core retrieval operation: embed the question, find the chunks whose vectors are closest. "Closest" needs a **distance metric** — this project uses **cosine** (angle between vectors), with vectors **normalised** to unit length so cosine behaves cleanly.
> - **top-k / n_results** — how many chunks to retrieve (e.g. 5). More = more context for Claude but more tokens (cost) and more noise.
> - **Metadata filtering** — narrowing retrieval by a stored field, e.g. Chroma's `where={"source": "boe"}`. Lets one collection serve "search everything" *and* "search only this source" — why this project uses a single collection with `source` as metadata rather than one per source.
> - **Context window** — the fixed token budget for a single Claude call. Retrieved chunks + system prompt + question must fit. The reason we retrieve *k* chunks, not the whole corpus.
> - **Citation grounding** — every chunk carries its `source_url` through the whole pipeline, so the final answer can point back to the original page. Non-negotiable for this project (verify against primary sources).
> - **Provenance / index metadata** — `data/index/metadata.json`: which model, how many dims, when built, how many chunks. The embedding-stage analogue of a `parser_version` — tells future-me whether the index is trustworthy/compatible. See Step 006.
>
> **Deferred techniques** (known, not yet built — documented so I know they exist):
>
> - **Contextual Retrieval** (Anthropic) — before embedding, prepend each chunk with a one-sentence, LLM-generated description of its document context, so chunks that are ambiguous in isolation retrieve better. ~$0.88 one-off here. Step 005 spec has the detail.
> - **Re-ranking** — retrieve a generous top-k cheaply, then use a second, smarter model to re-order them before sending to Claude. Improves precision; deferred.
> - **Hybrid search** — combine vector similarity with old-fashioned keyword/BM25 search, which catches exact terms (ticker symbols, acronyms) that embeddings sometimes blur. Deferred.
>
> **The one-line summary I keep forgetting and re-deriving:** *embeddings turn meaning into geometry so that "find relevant text" becomes "find nearby points," and RAG is just feeding those nearby points to the model as evidence.*

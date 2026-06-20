# finance-kb

Personal knowledge base for finance, banking and (eventually) EU/UK capital reporting — a learning project combining bottom-up domain knowledge acquisition with AI engineering practice.

## Owner context

- 9 years in finance sector engineering (8 at JPMC, 1 at HSBC).
- Currently VP, manages a software engineering team building a Databricks data mesh platform for capital reporting (EMEA + firmwide).
- Comfortable with Python (Typer CLIs), React, Spark/Databricks, traditional engineering management.
- New to RAG, LangChain, vector stores, embedding strategies — wants to learn these properly via this project.
- Time budget: ~5–10 hrs/week side project.

## Goal

A personal LLM-powered Q&A system over public regulatory documents on capital reporting. Owner uses it to look up terminology, build conceptual understanding, and as a reference while learning the domain.

## Conceptual layering

Domain learning is structured bottom-up in three layers:

- **Layer 1 — foundational finance and banking**: instruments, trades, positions, markets, participants. **Phase 0 starts here.**
- **Layer 2 — risk**: market, credit, operational, liquidity risk. Future phase.
- **Layer 3 — capital**: Basel III, EBA, PRA, CRR. Future phase.

The architecture must not preclude later expansion to Layers 2 and 3.

## Architecture

Three-piece split:

1. **`ingest/`** — Python Typer CLI for the data pipeline. Each stage runs independently and is inspectable: fetch → parse → chunk → embed → store. Inspectability matters here because the owner is learning what RAG actually does at each stage.
2. **`api/`** — Python FastAPI backend. Takes a question, retrieves relevant chunks from the vector store, calls Claude, returns answer + sources. Deferred until ingestion produces usable chunks.
3. **`web/`** — Next.js/React frontend. Q&A UI with streaming and citation display. Deferred until the API is working.

## Decisions made

- **Python + React combo** (not pure Node): Python for the AI/data pipeline because PDF tooling, LangChain, and the vector store ecosystem are all Python-first. React for the frontend because the owner already knows it.
- **uv** for Python package management.
- **Chroma** as initial vector store: file-based, simple, good for learning.
- **Embedding provider deferred**: decide once a real document has been handled and we can reason about cost/quality trade-offs.
- **Geographic scope**: EU/UK capital reporting first (Basel III, CRD-CRR, EBA, PRA). NA/APAC are future scope but the architecture shouldn't preclude them.
- **Sources**: public materials only. Owner cannot use internal JPMC/HSBC documents (corporate boundary). Public materials from those institutions (investor reports, regulatory submissions, published research) are acceptable.
- **Phase 0 source pair**: Investopedia (curated subset, ~50 articles) + Bank of England Knowledge Bank. Two deliberately different shapes — HTML glossary entries vs narrative explainers — to exercise the chunking pipeline against varied document structure.
- **Usage & licensing**: personal use only, never published, always cited. RAG output must cite the original URL. Investopedia content © Investopedia (Dotdash Meredith), used under personal, non-commercial fair use. BoE content is Crown copyright under the Open Government Licence (OGL) — verify exact terms during ingestion.
- **Repository hosting**: private GitHub, single-owner. Corpus content under `data/` stays gitignored and is never committed even though the repo is private. Committed: code, specs, sources registry, URL lists, learnings, `.env.example`. Not committed: `.env`, `data/` contents.
- **LLM and embedding architecture — leaning direction, confirmed in-stage (Steps 005–006).** The current lean for Phase 0 is Pattern B: local embeddings via `sentence-transformers` + paid Claude API for answer generation, with a local Chroma vector store. Rationale: free local embeddings keep the indexing stage inspectable and re-runnable without metering, while paid Claude generation gives the answer quality that matters most for a learning-focused tool. This is **not locked** — choosing the embedding approach (local vs a paid API such as Voyage) is itself one of the AI-engineering decisions to weigh and make at the relevant stage. For now we deliberately avoid putting money at risk on a paid embedding API while still learning, and treat the choice above as the default to validate, not a commitment. Contextual Retrieval (Anthropic's chunk-enrichment technique — https://www.anthropic.com/engineering/contextual-retrieval) is a likely Step 005+ upgrade once the baseline works, not part of the initial build.
- **Claude.ai subscription does not power this project.** The owner's Pro/Max subscription is for the chat UI only; programmatic calls from this project's code go through the paid Claude API on a per-token basis.
- **Cost is balanced and measured, not ignored, and the real number is small.** The recurring cost is **query-time answer generation**, dominated by model choice (~$5–35/month at tens of queries/day: Haiku/Sonnet cheapest, Opus highest); indexing is effectively free because embeddings run locally and unmetered. Quality, inspectability, and learning lead — but cost is guarded: **set a spend cap + alert in the Anthropic Console**, keep embeddings local so re-indexing stays free, and **log `response.usage` per query** so the real number is observed rather than guessed (Step 007 prints per-query cost; `count_tokens` prices a query before sending). At this corpus size (~250–350k tokens) paid embeddings would be cents, so the local-vs-paid choice is about inspectability, not money — the cost levers that actually matter (a runaway query loop; paid embeddings *plus* a much larger Layer 2/3 corpus) are revisited at the embedding/RAG stages. Full cost model in `docs/learnings.md`.

## Current phase

**Phase 0: Proof of Concept.**

Roadmap within Phase 0:

- **Step 001** ✅ Bare scaffold.
- **Step 002** ✅ Source curation.
- **Step 003** — Investopedia ingestion script (HTML fetch + clean).
- **Step 004** — BoE Knowledge Bank ingestion script (different HTML shape).
- **Step 005** — Chunking strategy.
- **Step 006** — Embedding + Chroma vector store.
- **Step 007** — Minimal end-to-end RAG via CLI.
- **Step 008+** — FastAPI backend, then web frontend.

## Working style

Plan-implementation loops:

1. Planning conversations happen in Claude UI (claude.ai). Owner is "the planner."
2. Each implementation step gets a focused spec at `docs/steps/step-NNN-short-name.md` (zero-padded, three digits) that Claude Code uses to implement.
3. This `CLAUDE.md` holds persistent context — update it whenever a durable decision is made.
4. Owner does not write code by hand; Claude Code drives implementation.
5. Owner wants to **learn** at every stage — explanations of *why* matter as much as code. Don't skip the "why this chunking strategy" or "why this embedding model" conversations.
6. Steps come in two kinds. **Planning steps** (e.g. source curation) produce no `step-NNN-*.md` spec — their output is updates to `docs/` and this `CLAUDE.md`. **Implementation steps** do get a `docs/steps/step-NNN-short-name.md` spec that Claude Code implements.
7. Step specs in `docs/steps/` are **write-once history** — frozen once the step ships, never edited afterwards. Durable decisions get promoted into this `CLAUDE.md`; the spec stays as the record of what the step was asked to do and why.

## Conventions

- Python 3.12+, type hints throughout.
- Typer for all CLIs.
- Each ingestion step independently runnable and inspectable from the command line.
- Sources tracked in `docs/sources.md` as per-source sections (not a flat table), each recording name, URL, jurisdiction, doc type, date retrieved, version, and notes.
- Per-source URL lists live in their own files (e.g. `docs/investopedia-articles.md`).
- Learnings captured in `docs/learnings.md` (capital concepts encountered, terminology clarified, surprises).
- No internal/proprietary docs in `data/`. Only publicly retrievable materials.

## What this project is NOT

- Not a production system. No multi-user concerns, no auth, no SLAs.
- Not a replacement for primary sources. Always show citations so the owner can verify against the source doc.
- Not trying to cover every jurisdiction on day one. EU/UK first; expand only after Phase 0 is solid.

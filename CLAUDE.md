# finance-kb

Personal knowledge base for EU/UK capital reporting — a learning project combining domain knowledge acquisition with AI engineering practice.

## Owner context

- 9 years in finance sector engineering (8 at JPMC, 1 at HSBC).
- Currently VP, manages a software engineering team building a Databricks data mesh platform for capital reporting (EMEA + firmwide).
- Comfortable with Python (Typer CLIs), React, Spark/Databricks, traditional engineering management.
- New to RAG, LangChain, vector stores, embedding strategies — wants to learn these properly via this project.
- Time budget: ~5–10 hrs/week side project.

## Goal

A personal LLM-powered Q&A system over public regulatory documents on capital reporting. Owner uses it to look up terminology, build conceptual understanding, and as a reference while learning the domain.

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

## Current phase

**Phase 0: Proof of Concept.**

Roadmap within Phase 0:

- **Step 001** — Bare scaffold (uv project, Typer CLI stub, directory skeleton).
- **Step 002** — Source curation (planning task, not coding): pick the first 2 public docs.
- **Step 003** — First ingestion script: download + parse one PDF, produce clean text. No chunking, no embedding yet.
- **Step 004+** — Chunking strategy, embedding, retrieval, minimal end-to-end RAG.

## Working style

Plan-implementation loops:

1. Planning conversations happen in Claude UI (claude.ai). Owner is "the planner."
2. Each step gets a focused spec at `docs/stepNNN-short-name.md` (zero-padded, three digits) that Claude Code uses to implement.
3. This `CLAUDE.md` holds persistent context — update it whenever a durable decision is made.
4. Owner does not write code by hand; Claude Code drives implementation.
5. Owner wants to **learn** at every stage — explanations of *why* matter as much as code. Don't skip the "why this chunking strategy" or "why this embedding model" conversations.

## Conventions

- Python 3.12+, type hints throughout.
- Typer for all CLIs.
- Each ingestion step independently runnable and inspectable from the command line.
- Sources tracked in `docs/sources.md` (name, URL, jurisdiction, doc type, date retrieved, version, notes).
- Learnings captured in `docs/learnings.md` (capital concepts encountered, terminology clarified, surprises).
- No internal/proprietary docs in `data/`. Only publicly retrievable materials.

## What this project is NOT

- Not a production system. No multi-user concerns, no auth, no SLAs.
- Not a replacement for primary sources. Always show citations so the owner can verify against the source doc.
- Not trying to cover every jurisdiction on day one. EU/UK first; expand only after Phase 0 is solid.

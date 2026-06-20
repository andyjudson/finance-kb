# finance-kb

## What this is

A personal, LLM-powered Q&A system over public regulatory documents on EU/UK
capital reporting (Basel III, CRD/CRR, EBA, PRA). It's a learning project: part
domain-knowledge acquisition (capital reporting terminology and concepts), part
AI-engineering practice (RAG, embeddings, vector stores). You ask a question, it
retrieves relevant passages from public source documents, calls Claude, and
returns an answer with citations you can verify against the original.

## Architecture

Three independent pieces:

1. **`ingest/`** — Python Typer CLI for the data pipeline. Each stage runs and is
   inspectable on its own: fetch → parse → chunk → embed → store.
2. **`api/`** — Python FastAPI backend. Takes a question, retrieves relevant
   chunks from the vector store, calls Claude, returns answer + sources.
   *(Deferred until ingestion produces usable chunks.)*
3. **`web/`** — Next.js/React frontend. Q&A UI with streaming and citation
   display. *(Deferred until the API is working.)*

## Setup

```bash
uv sync                  # create .venv and install dependencies
cp .env.example .env     # then fill in your keys
```

Verify the CLI:

```bash
uv run ingest --help
uv run ingest info       # → finance-kb ingest CLI — ready
```

## Current phase

**Phase 0: Proof of Concept — Step 001 (bare scaffold).**

Only the `ingest/` skeleton and a Typer CLI stub exist so far. No real ingestion
logic, no API, no frontend yet.

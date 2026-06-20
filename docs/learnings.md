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

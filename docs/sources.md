# Sources

Registry of public sources ingested into the knowledge base. Each entry captures what the source is, how to fetch it, and any constraints on use. Per-source URL lists (where relevant) live in their own files.

---

## Investopedia (subset)

- **Type:** Online finance encyclopedia / glossary-style articles.
- **Jurisdiction:** Jurisdiction-neutral (US-leaning by default, but covers global concepts).
- **Layer:** 1 (foundational finance and banking).
- **Base URL pattern:** `https://www.investopedia.com/terms/<first-letter>/<slug>.asp`
- **Content shape:** HTML, glossary-style entries. Each entry is a self-contained article, typically 500–2000 words, with predictable section structure: "What Is X", "Understanding X", "Example", "Key Takeaways". Each URL produces one document.
- **Scope:** Defined subset of ~50 articles covering investment basics, financial instruments, trading mechanics, market participants, and basic risk concepts. See `docs/investopedia-articles.md` for the full list.
- **Ingestion approach:** HTML fetch + parse + clean (strip navigation, ads, related links, footers, comments, share widgets). One URL → one cleaned document. Should be reproducible: same URL today and next month should produce comparable text (modulo source updates).
- **Constraints:**
  - Content is © Investopedia (Dotdash Meredith). Used here under personal, non-commercial, non-public fair use.
  - Every retrieved chunk in the RAG system must cite back to the original URL.
  - Do not redistribute the corpus.
  - Do not expose the system publicly.
- **Date added:** 2026-06-20.
- **Notes:** URLs in `docs/investopedia-articles.md` are best-guess based on Investopedia's standard slug pattern. Some may need correction during Step 003 ingestion; the ingestion script should report 404s cleanly so the list can be patched.

---

## Bank of England Knowledge Bank

- **Type:** Central bank explainer articles aimed at non-specialists.
- **Jurisdiction:** UK.
- **Layer:** 1 (foundational finance and banking), with some Layer 3 adjacency (PRA, financial stability, banking supervision).
- **Index URL:** `https://www.bankofengland.co.uk/knowledgebank` (also linked as `/news/explainers`).
- **Article URL pattern:** `https://www.bankofengland.co.uk/explainers/<slug>`
- **Content shape:** HTML, narrative explainer articles. Longer than Investopedia entries; mix of prose, headings, occasional embedded media (videos, infographics — text content only is needed). Less rigidly structured than Investopedia.
- **Scope:** Full Explainers collection as listed at the index page. Crawl the index for URLs at ingestion time rather than hardcoding the list (the collection changes occasionally; crawling keeps us in sync).
- **Ingestion approach:** Two-step — fetch the index page, extract explainer URLs, then fetch and clean each explainer. Parse strategy differs from Investopedia (different HTML structure, different content patterns). The fact that this is the second source is the point: it forces the ingestion design to generalise.
- **Constraints:**
  - Crown copyright. Generally usable under the [Open Government Licence (v3.0)](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) — verify exact terms at Step 004.
  - Always cite source URL regardless of redistribution rights.
- **Date added:** 2026-06-20.
- **Notes:** Content skews macro / monetary policy / central banking / supervision rather than market microstructure. Complements Investopedia (trader/banker view) with the regulator/policymaker view.

---

## Future sources (not in Phase 0)

For reference only — to be added in later phases:

- **Layer 2 (Risk):** Candidates include CFA Institute educational materials (public subset), BIS Working Papers on risk measurement, Risk.net glossary (paywall — likely unsuitable).
- **Layer 3 (Capital):** Basel III framework (BIS), EBA Single Rulebook and guidelines, CRR (EU Regulation 575/2013), PRA Rulebook, EBA glossary.
- **EU equivalent of BoE Knowledge Bank:** ECB Explainers — useful for EU central banking perspective.

These are notes, not commitments — to be confirmed when their phase starts.

# Sources

Registry of public sources ingested into the knowledge base. Each entry captures what the source is, how to fetch it, and any constraints on use. Per-source URL lists (where relevant) live in their own files.

---

## Investor.gov glossary (SEC) — Phase 0 primary glossary source

- **Type:** US securities regulator's investor-education glossary. Short,
  self-contained definitional entries (the glossary shape for Phase 0).
- **Jurisdiction:** US (SEC). Terminology is broadly consistent with global
  usage; the plain-English / cross-jurisdiction framing is left to the RAG layer.
- **Layer:** 1 (foundational finance and banking).
- **Base URL pattern:** `https://www.investor.gov/introduction-investing/investing-basics/glossary/<slug>`
- **Content shape:** HTML (Drupal). Each term is its own page: an
  `<h1 class="field--name-title">` and a short `field--name-body` definition
  (typically 1–4 short paragraphs). Curated ~49-term Layer-1 subset in
  `docs/investor-gov-terms.md` (slugs verified against the live index, not guessed).
- **Ingestion approach:** Per-term fetch → cache → parse → markdown + YAML
  frontmatter → manifest. The automated pipeline runs as designed (no challenge).
- **Robots.txt & access (checked 2026-06-20):** `https://www.investor.gov/robots.txt`
  — `User-agent: *` disallows only Drupal internals (`/core/`, `/profiles/`,
  READMEs); **`/glossary/` is permitted** and there are **no AI-bot name-blocks**.
  Plain HTTPS fetch returns 200 with no Cloudflare/JS challenge. UA: browser-style
  `Mozilla/5.0 ...`, 1.5s±0.5s delay, serial.
- **Soft-404 caveat:** unknown slugs return **HTTP 200** with a generic
  `<h1>Glossary: SLUG</h1>` / `<title>Glossary | Investor.gov</title>`, not a 404.
  The parser detects a *valid* term by the presence of the `field--name-title`
  H1 and records invalid slugs as `not_found` in the manifest.
- **Constraints:** US-government work → **public domain**. Still cite the source
  URL in RAG output (provenance), but no redistribution/fair-use limits apply.
- **Date added:** 2026-06-20.

---

## Investopedia (subset) — optional manual supplement (Cloudflare-blocked; not auto-fetched)

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
- **Robots.txt & access (checked 2026-06-20):**
  - `https://www.investopedia.com/robots.txt`. For `User-agent: *` the only disallows are `*.pdf` and `/embed?` — so **`/terms/` paths are permitted** for generic clients. The spec's prerequisite gate (`/terms/` not disallowed for our UA) passes.
  - The file additionally **name-blocks AI crawlers** with `Disallow: /`, including `anthropic-ai`, `ClaudeBot`, `Claude-Web`, `CCBot`, `cohere-ai`, `PerplexityBot`, and `Google-Extended` (`GPTBot`/`ChatGPT-User` only blocked from `/thmb/`). Those are the operators' *named, official* crawlers — our personal script is none of them, so it falls under `*`.
  - **Cloudflare block (discovered 2026-06-20):** article pages additionally sit
    behind a Cloudflare **managed JS challenge** — `GET /terms/...` returns
    **HTTP 403** (`cf-mitigated: challenge`, the "Just a moment..." interstitial)
    even with a browser UA and cookies. Plain HTTP clients (`requests`) cannot
    pass it. So the `*` robots permission is moot for automated access; the WAF
    blocks us regardless.
  - **Status — demoted to optional manual supplement (decided 2026-06-20):**
    given both signals (robots name-blocks Claude/AI crawlers; Cloudflare blocks
    non-browser clients), Investopedia is **not auto-fetched**. The Phase 0
    glossary source pivoted to Investor.gov (public domain, fetchable). The
    curated Investopedia term list survives in `docs/investopedia-articles.md`;
    if specific entries are wanted, save the HTML by hand from a browser into
    `data/raw/investopedia/<slug>.html` and the parser can process it locally.
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
- **Notes:** Content skews macro / monetary policy / central banking / supervision rather than market microstructure. Complements Investor.gov (US glossary terms) with the UK regulator/policymaker view.
- **Consider at Step 004 — BoE glossary co-source (held 2026-06-20):** BoE also publishes a separate single-page A-Z glossary at `https://www.bankofengland.co.uk/glossary` (HTTP 200, server-rendered, Crown copyright/OGL — same licensing as Knowledge Bank; verified fetchable 2026-06-20). Held out of Phase 0 to keep "one shape per source" cleaner, but **re-evaluate when implementing Step 004**: the owner is UK-based and works on UK/EU regulations, so UK regulator vocabulary (gilt, repo, bank rate, MPC, CRR, RWA) is genuinely more useful than the project's framing suggests, and adding it during Step 004 reuses the BoE fetch/auth context. Would need a second parser (single-page A-Z split by letter heading), not a reuse of the Investor.gov per-URL parser.

---

## Future sources (not in Phase 0)

For reference only — to be added in later phases:

- **Layer 2 (Risk):** Candidates include CFA Institute educational materials (public subset), BIS Working Papers on risk measurement, Risk.net glossary (paywall — likely unsuitable).
- **Layer 3 (Capital):** Basel III framework (BIS), EBA Single Rulebook and guidelines, CRR (EU Regulation 575/2013), PRA Rulebook, EBA glossary.
- **EU equivalent of BoE Knowledge Bank:** ECB Explainers — useful for EU central banking perspective.

These are notes, not commitments — to be confirmed when their phase starts.

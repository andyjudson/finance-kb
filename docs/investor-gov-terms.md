# Investor.gov glossary terms — Phase 0

Curated Layer-1 (foundational finance and banking) subset of the SEC
**Investor.gov** glossary, the Phase 0 fetchable glossary source.

**Source:** US Securities and Exchange Commission — public domain (US
government work).
**URL pattern:** `https://www.investor.gov/introduction-investing/investing-basics/glossary/<slug>`
**Slugs below are real** — extracted and verified from the live glossary index
on 2026-06-20 (not guessed). Investor.gov returns a **soft-404** (HTTP 200 with
a generic "Glossary: SLUG" page) for unknown slugs, so the ingestion script
detects validity by the presence of a `field--name-title` H1, not by HTTP status.

## Investment basics & instruments

| Topic | Slug |
|---|---|
| Asset | `asset` |
| Asset classes | `asset-classes` |
| Asset allocation | `asset-allocation` |
| Security | `security` |
| Bonds | `bonds` |
| Corporate bonds | `bonds-corporate` |
| Municipal bonds | `bonds-municipal` |
| Treasury securities | `treasury-securities` |
| Coupon | `coupon` |
| Coupon rate | `coupon-rate` |
| Yield | `yield` |
| Yield curve | `yield-curve` |
| Callable / redeemable bonds | `callable-or-redeemable-bonds` |
| Convertible securities | `convertible-securities` |
| Investment-grade bond | `investment-grade-bond-or-high-grade-bond` |
| Stock | `stock` |
| Stock split | `stock-split` |
| Dividend | `dividend` |
| Capital gain | `capital-gain` |

## Derivatives & funds

| Topic | Slug |
|---|---|
| Derivatives | `derivatives` |
| Options | `options` |
| Futures contract | `futures-contract` |
| Futures market | `futures-market` |
| Mutual funds | `mutual-funds` |
| ETF | `exchange-traded-fund-etf` |
| Index fund | `index-fund` |
| Money market fund | `money-market-fund` |
| Net asset value | `net-asset-value` |

## Trading mechanics

| Topic | Slug |
|---|---|
| Market order | `market-order` |
| Order types | `order-types` |
| Short sales | `short-sales` |
| Margin account | `margin-account` |
| Margin call | `margin-call` |
| Bid price | `bid-price` |
| Ask price | `ask-price` |
| Liquidity / marketability | `liquidity-or-marketability` |
| Stock quotes | `stock-quotes` |
| Securities lending | `securities-lending` |

## Markets & participants

| Topic | Slug |
|---|---|
| Stock market | `stock-market` |
| Market makers | `market-makers` |
| Broker | `broker` |
| Investment adviser | `investment-adviser` |
| Investment company | `investment-company` |
| Hedge funds | `hedge-funds` |
| Accredited investors | `accredited-investors` |
| SIPC | `securities-investor-protection-corporation-sipc` |

## Basic risk

| Topic | Slug |
|---|---|
| Risk | `risk` |
| Risk tolerance | `risk-tolerance` |
| Principal | `principal` |
| Premium | `premium` |

---

**Total: ~49 terms.** Add or trim freely. Any term not present in the live
glossary will be recorded as `not_found` in the manifest (soft-404 detection),
so the list can be patched without aborting the batch.

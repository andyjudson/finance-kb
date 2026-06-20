# Investopedia article list — Phase 0

This is the initial scoped subset of Investopedia articles to ingest for Phase 0. Roughly 50 entries across five categories covering Layer 1 (foundational finance and banking).

**URL pattern:** `https://www.investopedia.com/terms/<first-letter>/<slug>.asp`

URLs below are best-guesses based on Investopedia's standard slug convention. The Step 003 ingestion script should:
- Report 404s clearly so this list can be patched.
- Not fail the whole batch on a single bad URL.

## Investment basics

| Topic | Path |
|---|---|
| Investing | `/terms/i/investing.asp` |
| Investment | `/terms/i/investment.asp` |
| Asset | `/terms/a/asset.asp` |
| Asset class | `/terms/a/assetclasses.asp` |
| Return | `/terms/r/return.asp` |
| Risk (general) | `/terms/r/risk.asp` |
| Risk–return tradeoff | `/terms/r/riskreturntradeoff.asp` |
| Diversification | `/terms/d/diversification.asp` |
| Portfolio | `/terms/p/portfolio.asp` |
| Capital markets | `/terms/c/capitalmarkets.asp` |

## Financial instruments

| Topic | Path |
|---|---|
| Security | `/terms/s/security.asp` |
| Equity | `/terms/e/equity.asp` |
| Common stock | `/terms/c/commonstock.asp` |
| Preferred stock | `/terms/p/preferredstock.asp` |
| Bond | `/terms/b/bond.asp` |
| Fixed income | `/terms/f/fixedincome.asp` |
| Government bond | `/terms/g/government-bond.asp` |
| Corporate bond | `/terms/c/corporatebond.asp` |
| Derivative | `/terms/d/derivative.asp` |
| Futures contract | `/terms/f/futurescontract.asp` |
| Forward contract | `/terms/f/forwardcontract.asp` |
| Option | `/terms/o/option.asp` |
| Call option | `/terms/c/calloption.asp` |
| Put option | `/terms/p/putoption.asp` |
| Swap | `/terms/s/swap.asp` |
| Interest rate swap | `/terms/i/interestrateswap.asp` |
| Credit default swap | `/terms/c/creditdefaultswap.asp` |
| Repurchase agreement (repo) | `/terms/r/repurchaseagreement.asp` |

## Trading mechanics

| Topic | Path |
|---|---|
| Trade | `/terms/t/trade.asp` |
| Position | `/terms/p/position.asp` |
| Long position | `/terms/l/long.asp` |
| Short position | `/terms/s/short.asp` |
| Order | `/terms/o/order.asp` |
| Market order | `/terms/m/marketorder.asp` |
| Limit order | `/terms/l/limitorder.asp` |
| Bid–ask spread | `/terms/b/bid-askspread.asp` |
| Liquidity | `/terms/l/liquidity.asp` |
| Settlement | `/terms/s/settlement.asp` |
| Clearing | `/terms/c/clearing.asp` |
| Counterparty | `/terms/c/counterparty.asp` |
| Mark-to-market | `/terms/m/marktomarket.asp` |
| Notional value | `/terms/n/notionalvalue.asp` |

## Market participants

| Topic | Path |
|---|---|
| Investment bank | `/terms/i/investmentbank.asp` |
| Commercial bank | `/terms/c/commercialbank.asp` |
| Broker | `/terms/b/broker.asp` |
| Broker-dealer | `/terms/b/broker-dealer.asp` |
| Hedge fund | `/terms/h/hedgefund.asp` |
| Asset management | `/terms/a/assetmanagement.asp` |
| Market maker | `/terms/m/marketmaker.asp` |
| Prime brokerage | `/terms/p/primebrokerage.asp` |

## Basic risk concepts

| Topic | Path |
|---|---|
| Market risk | `/terms/m/marketrisk.asp` |
| Credit risk | `/terms/c/creditrisk.asp` |
| Counterparty risk | `/terms/c/counterpartyrisk.asp` |
| Liquidity risk | `/terms/l/liquidityrisk.asp` |
| Operational risk | `/terms/o/operational_risk.asp` |
| Value at risk (VaR) | `/terms/v/var.asp` |
| Volatility | `/terms/v/volatility.asp` |
| Hedge | `/terms/h/hedge.asp` |

---

**Total: ~52 articles.** Add or trim freely. A reasonable approach is to start with this list, see how Phase 0 performs, and add Layer 2 (risk) articles in a future expansion rather than now.

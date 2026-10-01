---
name: "special-situations-screen"
description: Screen a market for live, near-term special situations across four categories — M&A/arbitrage, spin-offs/breakups, activist/restructuring, and distressed/capital-structure events — then dedupe and rank them by probability-weighted expected return. Uses Distilla MCP (standard_event, ku_cell, stock_price, financial_data_point, valuation_multiple) as the primary source. Use this whenever the user asks for special situations, event-driven or catalyst-driven ideas, merger arbitrage, tender offers, spin-off or breakup ideas, activist targets, restructurings, distressed names, recapitalizations, or rights issues across a universe, even if they don't say "special situations". Do NOT use for a deep dive on one company.
compatibility: "Target platform: Claude.ai. Requires the Distilla MCP connector, web_search / web_fetch, and Python code execution. Claude Code note: the same file runs there; the four scans can run as parallel sub-agents."
---

# Special Situations Screen

**Platform:** Claude.ai (target). The four scans run in sequence in Claude.ai; in Claude Code they may run as sub-agents.

Find **active, unresolved** special situations in a universe, estimate upside, then rank survivors by **probability-weighted expected return**.

Read `references/distilla-reference.md` before the first Distilla call. It has the entity fields, exact event-type strings, KU names, unit quirks, and data-quality traps this workflow depends on.

## Inputs

| Input | Default | Notes |
|---|---|---|
| `universe` | Inferred (below): region, sectors (all unless the request names some), size | Region → `company.hq_country`; size → the 3f gate |
| `min_upside` | 15% | Strictly greater than |
| `max_event_age_days` | 90 | Recency window for the triggering event |

Use the user's values where given. Any part of the universe not given: infer it from the request (market words, named listings, sector words, size words such as "large-cap", currency) or the user's context, and state it with its basis in the resolved inputs; an input that can't be inferred is asked for together with the review question. `min_upside` and `max_event_age_days` take the defaults above unless given; the rundown prints both. State the resolved inputs once. Resolve the window to absolute dates (`[today − max_event_age_days] → today`) and state it.

**Rundown and review choice (before Step 1):** after the resolved inputs and window, print this rundown filled in, as reply text in its own block — the question never replaces it:

```
Rundown — [region], market cap > [threshold], [window]
Step 1 — Universe → count contract
Step 2 — Four category scans (A M&A / arbitrage · B spin-offs / breakups · C activist / restructuring · D distressed / capital events) → four scan tables with exact group counts
Step 3 — Dedupe, > [min_upside]% filter, scoring and ranking → ranked expected-return table
```

Then, in the same text reply below the block, ask one question — in plain text, never through the tappable-options tool, which shows only the question and hides the rundown — together with any missing-input question: stop for review after Step 2 (category scans), or run to the end. Then stop or continue as answered. A request that already states the choice ("run to the end", "stop after the scans") is the answer: print the rundown and ask nothing. No other approval stop.

## Data-source fallback

**Mode: Standard** — web figures allowed. If the user asks for a Distilla-only run, switch to **Distilla only**: every claim traces to a Distilla document or entity, no web, and missing = `--` or drop the row; the one exception is FX for currency conversion, from the FX row's web sources, dated, with source and date stated. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v26: 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.8 · 3b, 3f, 3g)

#### 2.1 Pre-flight checks (before any data step)

1. **KU coverage check.** (a) Find the company's latest 1–2 `cell_time_period_id`: `query_entity` on `ku_cell`, filter `group_company_id`, sort `cell_as_of_date desc`, limit 5. (b) One row query on `ku_cell` joined to `ku`, `ku.name IN (<skill KUs>)`, `cell_time_period_id` IN those periods (avoids 100-row truncation); if `truncated = true`, narrow to one period and rerun. A KU counts as covered only if its `content` is non-empty: (c) rerun (b) with `content = "[]"` and subtract those KUs (HSBC period 169462: 22 of 24 KUs have rows, 18 non-empty). Not `aggregate_entity` — it does not scan the full universe, so "no groups" does not prove a KU is empty.
2. **Currency & share-basis check.** Compare the reporting currency of every source used (`financial_data_point` `formatting`, `consensus_data_point.currency`, `ku_cell`, `financials_review`) with `stock_price.currency`, and check the currency of **every line used** against filings. Verify EPS basis: net income ÷ EPS vs filed share count. **Distilla EPS can be per ADR, in every source:** TSM `financial_data_point` EPS 331.25 TWD on 5,186m ADR-equivalent shares (1 ADR = 5 shares), `consensus_data_point` FY2026 EPS 531.58 TWD, `financials_review` EPS 331.24. **Don't trust labels:** `unit = per_share` and a TSM snapshot's "EPS ($)" are both per-ADR TWD. Run the check on **each source and snapshot** used. `hq_country` reflects the listing Distilla holds (TSM ADR = `US`).
3. **One currency + one share basis + one source basis per ratio.** Never mix `financial_data_point`, `financials_review` and KU values in the same ratio.

#### 2.2 Financials source ladder

- **Applies to every rung:**
  - **EPS and every EPS-based figure** (P/E, EPS consensus, EPS revisions): use **only after 2.1 #2 passes; otherwise `--`**. A 5× ADR error otherwise flows straight into P/E and revisions.
  - Capex is reported negative → use `abs`.
  - **Banks and insurers:** use NI, EPS, ROE, total assets and book value only; EBITDA, NWC, capex, FCF and net debt are not meaningful → `--`.
- **Rung 1 — `financial_data_point`.** Join `T` (`time_period`) and `M` (`financial_metric`); filter `T.company_id`, `T.provenance = "financials"`, `T.duration = "year"` or `"quarter"`, `M.name IN (…)`. Matches `financials_review` where checked (HSBC revenue 138,390; Toyota capex 5.29T; TSM EPS 331.25 vs 331.24).
  - Parse in **Python**: strip thousands commas; `-` = missing → `--`. Read `unit` and `formatting` on every row, but **take the scale from the metric name**: labels can be wrong (AMD periods to Q3 2025: `unit = "M"` on EPS, `formatting = "USD"` on share counts).
  - **Anchor periods on `T.end_date` (month), not `T.fiscal_year`:** Toyota's FY ended 31 Mar 2026 carries `fiscal_year = 2025`; TSM FY2023 shows `end_date = 2023-12-29`.
  - **A quarter missing from an LTM** = the FY value − the other three quarters of that FY, same metric and source (`‡`; Vertiv Q4 2025 sales 10,229.9 − 7,349.9 = 2,880.0); no FY value → `--`.
  - **Trusted without extra checks** once currency matches filings: revenue, EBIT, EBITDA, capex, CFO, cash and debt lines.
  - **`ratio_analysis_*` rows are vendor-computed** (only the DIO and ROIC definitions are verified): cross-check or context only — never the ranked, rated or headline value, and never mixed with rule 2.3 derived values in one comparison. A gap to the vendor value is stated, never closed by changing the derivation.
  - **`income_statement_eps_recurring` is not adjusted EPS** (AMD: equals `eps_diluted` every quarter 2025–26). Take company-adjusted EPS from the filing or press release (`file`).
  - Company-wide only: segments come from KUs (rung 3).
- **Rung 2 — `executive_summary` `category = "financials_review"`**, for lines rung 1 lacks or leaves `-`. HTML table: 5 actual FYs + 3 forecast FYs. Use the latest `updated_at`.
  - Parse in **Python**. Column labels vary — (Actual) / (Forecast) / (Consensus) — or are missing.
  - **Read the footnote every run; it decides which forecast lines are consensus.** Regimes differ by company (AMD 16 Sep 2026: forecast EPS = consensus NI ÷ diluted shares, capex modeled; Tencent 12 Aug: EPS on **basic** shares). Lines the footnote doesn't call consensus are **Distilla model** — never present them as consensus.
  - **The footnote may state the actuals basis** (e.g., "Actuals are GAAP as reported") and latest diluted shares. Cite a stated basis for any GAAP EPS row; if none is stated, take the basis from the filing.
  - D&A = EBITDA − EBIT. The ROE/ROIC row varies (ROIC, ROE, both or neither).
- **Rung 3 — KUs:** `cash_flow_details`, `balance_sheet_details`, `by_segment_financials`, `cash_and_debt`, `capital_expenditure`; `executive_summary` `recent_performance` for actuals.
- **Never use:** `financial_statement_data`, `capital_expenditure_maintenance_expansion` (no cells anywhere).
- **Sparse — check coverage first:** `weighted_average_cost_of_capital_wacc` (WACC), `leverage_ratio`, `project_irr`, `capital_deployment`.

#### 2.3 Derived metrics (show the formula; mark `‡`)

- **Net debt** = `balance_sheet_short_term_debt_and_curr_portion_long_term_debt` + `balance_sheet_long_term_debt` − `balance_sheet_cash_and_short_term_investments`. `long_term_debt` includes leases; `long_term_debt_excl_lease_obligations` excludes them — pick one and use it for every peer.
- **Diluted shares** = `income_statement_diluted_shares_outstanding`, confirmed by NI ÷ EPS (the 2.1 #2 check); else `financials_review` NI ÷ EPS.
- **Market cap** = price × latest `income_statement_total_shares_outstanding`, on the price's share basis (2.1 #2). `stock_price.market_cap` history can be stale, flat or null (Micron null 12–27 Aug 2026) — latest value only.
- **EV** = market cap + net debt, **in one currency** (net debt converted at the price date's FX, rule 2.4). Use `stock_price.enterprise_value` only if within **10%** of the rebuild (TSM 18 Sep 2026: vendor EV 15.4T vs market cap $2.25T for a net-cash company — reject).

#### 2.4 Prices, FX and valuation

- **Multiples, rung 1 — `valuation_multiple`** (weekly `LTM_` and `NTM_` types). Label each value by its horizon (LTM or NTM). **Spot-check the latest value** against a rebuild on the same basis; keep the series if within **10%**, else rebuild. NTM is a **time-weighted FY blend**, not a sum of quarters.
- **P/E types are on adjusted EPS where the Street has it:** `_Pe` values usually match `eps_ex_xord_mean`, not GAAP (AMD 18 Sep 2026: NTM 41.5× vs 41.3× on adjusted and 49.0× on GAAP; LTM 84.1× vs 143.5× on GAAP; AAPL 25 Sep 2026 tracked GAAP instead). Spot-check NTM P/E against the time-weighted `eps_ex_xord_mean`; if the company has none (rule 2.5), against `eps_gaap_mean` (Nike 18 Sep 2026: 19.9× vs 19.6×), and label the P/E by the category that passed. LTM P/E cannot be rebuilt from `financial_data_point` (no adjusted line) — use it as vendor-computed. A GAAP P/E is a separate rebuild, labeled GAAP, never mixed with `_Pe` values.
- **Own-history statistics:** average and range via `aggregate_entity` on `valuation_multiple` filtered by `type` and a `valuation_date` window (ISO strings sort correctly); median and percentile need the weekly series (`query_entity`, ≤300 rows per page; 3 years ≈ 156 weeks) computed in Python — the aggregate has no median. State the window and the number of weekly values (loss periods and gaps have none: AMD `LTM_Pe_Med_W` 737 of 1,125 weeks; TSM `NTM_Pe_Med_W` 140 of 157 over 3 years). A value repeated across a week with no sessions (an exchange holiday) is a carry-forward — count it once (Kweichow Moutai `NTM_Pe_Med_W` 13 and 20 Feb 2026, Spring Festival closure).
- **Multiples, rung 2 — rebuild:** trailing P/E = month-end price ÷ trailing EPS from `financial_data_point` (LTM from quarters, or FY), labeled **GAAP**. Forward P/E = price ÷ `consensus_data_point` EPS, labeled **"fiscal-year forward"** unless time-weighted to NTM, and by EPS category.
- **Price basis order:** same currency as financials → **dated FX series matched to each month-end** (FX row: Fed H.10 → ECB) → `--`. **Never one spot FX rate for a history.** A local listing Distilla does not hold (e.g. `2330.TW` for the TSM ADR) is `--`.
- ADR point-in-time conversion: company-stated FX → the FX row rate for that date → `--`.
- **Cross-peer period basis:** when fiscal year-end months differ, use `valuation_multiple` LTM/NTM types, or LTM built from `financial_data_point` quarters, for **every** peer in that ratio; FY values only when all peers share the year-end month (rule 2.1 #3). State the basis in the table caption ("LTM to Jun 2026, all rows").
- `stock_price.sell_side_target_price` is back-filled → **latest value only**, never a history.

#### 2.6 Data-quality traps

- **Text `value` fields** (`financial_data_point`, `consensus_data_point`, `valuation_multiple`): `query_entity` filters compare lexicographically ("100" < "99") → numeric cuts via `aggregate_entity` with `having`, or filter in Python.
- **`aggregate_entity` output keys:** aliases come back camelCased (`op_margin` → `opMargin`) and dates as quoted strings (`"\"2025-12-31T00:00:00.000Z\""`), while `having` takes the alias as written. Read keys case-insensitively and strip the quotes in Python.
- **No total-debt line** in `financial_metric` (the entity description's `balance_sheet_total_debt` example does not exist) → rule 2.3 debt lines.
- **Actual → consensus splice:** a definition break can hit any line, within `financials_review` and between `financial_data_point` and `consensus_data_point` (HSBC revenue FY2025 actual 138,390 vs FY2026 consensus 74,768; Toyota capex actual 5.29T vs consensus 3.03T). Check continuity before anchoring on or trending across the splice; else `--` and note.
- **`ku_cell` values:** validate numbers against the cell's comment text and reconcile them against `financial_data_point` or `financials_review`; drop values that don't reconcile and discard misfiled numbers (e.g., a GM % in the `utilization_rate` field of `capacity_and_utilization_overall`). Use entries with `figure_type = "actual"` as actuals; `internal_target` and other types are context only (HSBC `common_equity_tier_1_ratio`: 14.1% actual at 30 Jun 2026 beside a 14–14.5% target). An entry with no `figure_type` counts as an actual only for a completed period whose comment reports a result; guidance and target entries are context only (HSBC `net_interest_margin_nim`).
- **`ku_cell` parsing:** normalize value strings — units ("thousand NT$", "million RMB"), `bn` / `m` with no currency (take the currency from the filing), parentheses = negative, unit/currency mislabels (e.g., NT$ thousands tagged "USD") — and key names (`period` / `name` vs `time_period` / `description`). Prefer entries sourced from the financial statements over transcript-rounded figures in the same cell.
- **Duplicate periods across filings:** prefer the annual-report cell.
- **YTD cumulative KU values** need differencing to get quarters.
- **Time series:** splice sources only after an **overlap check**.
- **`debt_details` `Interest expense`** is labelled with a point date: confirm on the cited source page whether it is a quarter or year-to-date flow before annualizing.
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`price_explanation.price_move_percentage` is a decimal fraction**, identical to `stock_price.change` for the same date, despite the MCP doc's "% move". Filter a 5% move with |value| ≥ 0.05.
- **`stock_price.market_cap` and `enterprise_value` are USD for non-US listings** while `stock_price.currency` is the local price currency (18 Sep 2026 rebuilds at ECB rates: Toyota US$226.8bn vs 228.3bn, Fast Retailing 131.5bn vs 132.3bn, Tencent 481.2bn vs 481.2bn; HSBC 24 Sep US$343.4bn vs 342.3bn). Convert the rule 2.3 rebuild to USD before the 10% check; never divide a vendor cap by a local price.
- **`financials_review` limits:** prose sections below the table are qualitative only, never a numeric source (they can contradict the table — AMD prose capex ~5% of revenue vs table 2.8% — and carry untraced broker figures); forecast columns can hold actuals (Tencent FY2026 cash and debt are H1 2026 reported balances), so read the footnote before treating a cell as a forecast; footnote model assumptions (tax, interest, NWC and capex ratios) are Distilla model, never a sourced input; header dates are approximate — use the fiscal year-end **month** only and take exact period end dates from filings (Toyota FY ended 31 Mar 2024 shows `FYE 2024-03-28`).
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

#### 2.7 Evidence, provenance and output

- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker. · `‡` derived figure, formula in a footnote.
- **Comparability:** never compare NTM with LTM values; use the same web source per field across target and peers.
- **Public Library numbers** must trace to a named broker + title + date (from the summary); otherwise use **qualitatively only**.
- **Method notes footer:** required, **≤4 lines**.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

#### 3b Peer scope
- Peers **segment-matched**. `financial_data_point` and `financials_review` are company-wide → use `by_segment_financials` for conglomerates if available; otherwise **exclude or flag** (e.g., Samsung for foundry) and keep out of medians. Compare **growth rates / intensity**, not summed amounts. "Vs sector" only if the peer set matches the sub-industry (**temporary** until Distilla exposes sub-industry medians).

#### 3f Universe market-cap gate
- Gate on the latest `stock_price.market_cap` (USD for every listing, rule 2.6) at each listing region's latest date (`MAX(date)` grouped by `company.hq_country`); convert a non-USD threshold once, at the FX row rate for the screen date. Spot-check 2–3 names per listing region against the rule 2.3 rebuild (within 10%), rebuild every name within ±10% of the threshold before deciding it, and show rebuilt values in market-cap cells.

#### 3g Growth-rate guard
- Compute growth in Python from two periods of one metric on one basis (`financial_metric` has no growth lines; periods by `T.end_date` month). A base ≤ 0 → `--`. Growth beyond ±1,000% → excluded from rankings, scores and verdict inputs and named with its cause: an acquisition (`standard_event` `Merger or Acquisition`), first commercial revenue, or a scale / definition break (rule 2.6 splice).

**Reading `ku_cell`:** run the KU coverage check (rule 2.1 #1) on the scan's KUs first, then `query_entity` on `ku_cell` joined to `ku`, filtering `ku.name` IN the units and `group_company_id` = the company `id`. `content` is structured JSON — parse it in Python and check each value's period, currency and unit. An empty unit is not evidence of absence.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Annual financials (revenue, GP, EBIT, EBITDA, NI, EPS, CFO, capex, cash, debt, ROE/ROIC) | `financial_data_point` (`T.provenance = "financials"`, `T.duration = "year"`; rule 2.2) | `executive_summary` `financials_review` actual columns; `ku_cell`: `cash_flow_details`, `balance_sheet_details`, `by_segment_financials`, `cash_and_debt`, `capital_expenditure` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → stockanalysis.com → MarketScreener. State when an aggregator was used. |
| Interim financials, segments, OCF | `financial_data_point` (`T.duration = "quarter"`); segments: `ku_cell` `by_segment_financials`, `geographical_segments`; `standard_event.earnings_summary` (`type = "Earnings announcement"`) | `ku_cell`: `cash_flow_details`, `capital_expenditure` (difference YTD values), `gross_margin_trends`, `operating_margin_trends`, `net_margin_trends`, `working_capital`; `executive_summary` `recent_performance`; `file` `Composite Filing` | Same as Annual financials |
| Ratings, target price | Broker notes: `get_library_document` `summary` (rating, TP, change old → new, date) of a note found by `search_public_library` `list`; consensus TP = **latest** `stock_price.sell_side_target_price` only | None — drop the item. `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) is discovery only: it names brokers and dates to list again with `brokers=[…]` (at most five per call), never a rating, TP or TP trajectory; an event no note matches is left out, and a note it conflicts with wins | **None** |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| Valuation multiple vs own history | `valuation_multiple` (`LTM_` / `NTM_` types; latest value spot-checked, rule 2.4); EPS-based multiples only after 2.1 #2 | Rebuild per rule 2.4 | **None** |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), and `web_fetch` refuses a typed URL. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Large price moves | `price_explanation` (`date`, `price_move_percentage` — decimal, rule 2.6, `explanation`) | `standard_event` and `file` `News Article` on the same dates | Company press releases → major newswires; `web_fetch` before citing |
| Peer / rival set | Companies sharing a `product_category` with the target via `ku_cell` `groupProductCategory` (the `product` entity has no category field); `company.sector_id`; `ku_cell`: `competitions`, `competitive_outlook` | One `screen_drivers` call on the full scope with a criterion describing the business | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (competition section) → company IR investor presentation |
| Universe (listing, sector) | `company` (`hq_country`, `sector_id`); size per the 3f gate | `ticker` | **None** — the universe is Distilla-only; never add web-found names |
| Event existence and date | `standard_event` by `type` + `date`, grouped and paged per the Step 2 event-scan rule | `file` (`News Article`); `ku_cell` `mergers_and_acquisitions`, `restructuring` | Official filings (EDINET / TDnet, EDGAR, HKEXnews, DART, CNINFO) → company IR press release → named news (Reuters, Nikkei, Bloomberg) |
| Deal terms (offer price, consideration, timeline) | `ku_cell` `mergers_and_acquisitions`; event `name` | `file` News Article `summary`; `search_public_library` (Research) — traced figures only | **Temporary, until Distilla MCP exposes structured deal terms:** tender-offer / merger filings (EDINET TOB notice, EDGAR 8-K / SC TO, HKEXnews announcement) → company IR → named news |
| Activist stake and demands | `ku_cell` `major_shareholders`; `standard_event` `Shareholder Activism` | `standard_event` `Change in Board of Directors`, `Shareholder meetings` | Large-shareholding filings (EDINET 5% report, EDGAR 13D) → activist or company IR → named news |
| Credit rating level | `standard_event` `Credit rating change` (`name`) | `ku_cell` `credit_risk`, `debt_details` | Company filings citing the rating → company IR → named agency release (S&P, Moody's, Fitch, R&I, JCR) |
| Going-concern / auditor opinion | `standard_event` `Auditor going concern`; `ku_cell` `auditor_opinion` | `ku_cell` `auditor`; `standard_event` `Delayed filing` | Annual report (EDINET, EDGAR, HKEXnews) → company IR → **None** beyond that |
| SOTP / broker valuation | `search_public_library` (Research) — traced figures only | `ku_cell` `by_segment_financials` + segment-matched peer `valuation_multiple` (3b) → own SOTP, labeled estimate (`‡`) | **None** — broker research isn't reliably on the web; build your own SOTP instead |

**Field notes for this skill:**
- **Universe (3f):** the `universe` size threshold is the 3f threshold.
- **Event scans:** run per the Step 2 event-scan rule. Rows attach to the **reporting company** — for M&A usually the acquirer — so the arbitrage target, its listing and the terms come from `name`, `mergers_and_acquisitions` and filings. Before the recency test, dedupe by (company, underlying event) and drop stale re-dated histories (e.g. a 2008 acquisition re-recorded with a 2026 date) and off-entity rows (rule 2.6 Events).
- **Revenue-trend cross-check (Scan D, 3g):** YoY growth from the Annual / Interim financials rows (`financial_data_point`) per 3g; an excluded rate never enters the distress test.
- **Downside floor:** `valuation_multiple` LTM types (rule 2.4; latest value spot-checked): the own-history 12-month low (53 weekly values) or the unaffected pre-event value of the same type, applied on the same basis (`‡`). The 3-year sensitivity line is an Output Caveats item. For M&A, the unaffected pre-announcement `stock_price.close`. Banks and insurers: P/B types only (rule 2.2).

**Provenance:** markers, the `†` footnote, one web source per field (across every row in a table) and no NTM-vs-LTM comparison follow rule 2.7.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Arithmetic runs in Python on the saved rows and renders as a plain markdown table — numbers only (spreads, expected returns, growth rates, sorting); judgments (certainty, timing, downside anchor) stay with you.

## Required research plan

### Step 1 — Build the universe

1. Get the latest trading date for the region: `aggregate_entity` on `stock_price`, `MAX(date)` grouped by `company.hq_country` (dates differ by region because of holidays).
2. Pull the universe: `query_entity` on `stock_price` at that date, joined to `company`, filtered on `company.hq_country` and `market_cap` per the 3f gate (field notes). Paginate until complete.
3. Keep the resulting `company_id` set. **Every later query filters on these IDs** — never re-type tickers from memory.

State, in stock-screener's count-contract form: `Universe: [description], N = [count] as of [date]`.

### Step 2 — Run four category scans

Each scan covers **only its category**, returns concrete current candidates, and follows the shared rules below.

**Execution:** pass each scan the universe IDs, window, shared rules and its scan spec, and keep each scan's logic independent (Platform line for sequencing).

Apply stock-screener's universe, count-contract, and evidence discipline to each scan: `Scanned N companies → M event groups in window → K kept after dedupe and recency`, with exact counts.

#### Shared rules (apply to every scan)

- **Event scan:** per scan, one `aggregate_entity` on `standard_event` over the scan's types, the window and the universe `company_id`s, grouped by `company_id`, `type` and `name` with MIN and MAX `date`, paged until `truncated = false` by `company_id` range — sort by `company_id`, drop a truncated page's last company and start the next page at that `company_id`, so groups never overlap and counts are exact — every group read; never keyword sweeps or a partial page in its place (US tech, 2 Jul – 30 Sep 2026: `Merger or Acquisition` 2,085 rows, 1,563 names). `Purchase or sale of shares by major investors` is never a scan type (13F fund flows: 46,192 rows in that window); stake-building comes from `major_shareholders` and `Shareholder Activism`.
- **Recency:** include a situation only if the triggering event occurred within the window, **or** — if older — there is a specific, dated, more recent data point confirming it is still open (state that confirming date). `standard_event.date` is the record date, so confirm the underlying event date from the headline, filing, or news (event-scan field note).
- **Priced-in check:** pull recent `stock_price` history. If the price has already moved substantially in the direction the catalyst implies, treat it as resolved or priced-in and exclude it unless fresh evidence shows it is still live.
- **Entity verification:** confirm each company is the specific entity in the universe — not a similarly named company, a same-abbreviation ticker on another exchange, or a different country's listing, and not an event row attached to the wrong company. If deal terms are in a currency or venue inconsistent with the universe, exclude it.
- **Upside %:** state the % followed by a one-line calculation in parentheses, e.g. `50% (¥4,500/shr offer vs. ¥3,000/shr spot)`. Use the latest `close` in the listing currency.
- **No structured value?** Walk the Data-source fallback ladder for the field first. Then, instead of writing "Not retrieved," estimate from deal terms, traced analyst SOTP notes (`search_public_library`, `doc_types=["Research"]`), or comparable transactions in the sourced text, labeled estimate. A broker estimate or target from the web or news is never an input; broker figures come only from a Library note. Never a generic premium (e.g. an assumed 30% take-out premium): a comparable-deal premium names the deal and its source. No basis → Upside blank and the row named in Caveats.
- **Evidence:** every row cites its source (event headline + date, KU cell + as-of date, library document, or web URL).

#### Scan A — M&A / Arbitrage

- **Find:** announced mergers and tender offers, definitive agreements pending close, competing bids, credible strategic reviews or rumored targets.
- **Distilla:** `standard_event` type `Merger or Acquisition` (also check `Delisting` for take-privates); `mergers_and_acquisitions` KU for terms. Most rows sit on the acquirer — identify the target from `name` and keep the row only if the target (or the universe company as target) is in the universe. Deal terms are not structured fields — confirm offer price from the headline, filings, or news.
- **Upside:** current price → deal consideration (or a reasonable estimated take-out price for rumored targets) if the deal closes as expected.
- **Columns:** Ticker, Company, Market Cap, Event Type (`M&A/Arb`), Event Description (2–3 sentences), Upside %, Status (announced / pending / rumored), Expected Close/Timeline, Regulatory or Financing Risk, Source.

#### Scan B — Spin-offs / Breakups

- **Find:** spin-offs, split-offs, carve-outs, asset sales and breakups that are announced or expected.
- **Distilla:** `standard_event` types `Spin-offs`, `Divestment`, `Discontinuation of a business or region`, and `IPO` / `Other public listing` where a subsidiary is being listed (carve-out); `restructuring` and `by_segment_financials` KUs for SOTP inputs, with segment-matched peers (3b).
- **Upside:** current price → implied sum-of-the-parts / post-separation combined value — a traced SOTP note, else your own SOTP (`‡`) per the SOTP / broker valuation row; a broker price target that is not a SOTP is never the upside. A company-confirmed strategic review or exploratory sale is a live candidate, never a rumor; every Scan B candidate gets its SOTP — `search_public_library` for the company first, else your own (`‡`) — and "not sized" is never a drop reason.
- **Columns:** Ticker, Company, Market Cap, Event Type (`Spin-off/Breakup`), Event Description (2–3 sentences), Upside %, Status & Expected Date, What Gets Separated & Rationale, Why It May Be Mispriced (forced selling, stub value, SOTP gap), Source.

#### Scan C — Activist / Restructuring

- **Find:** newly disclosed activist stakes (US 13D or the local equivalent, e.g. Japan's large-shareholding report), board or management-change campaigns, strategic reviews, major reorganizations, cost programs.
- **Distilla:** `standard_event` types `Shareholder Activism` and `Corporate restructuring and reorganization`, every group read (Step 2 event-scan rule); `Change in Board of Directors`, `Management change`, `Strategy change`, `Layoffs or hiring plan` and `Shareholder meetings` only for `company_id`s already in the scan set, as corroboration (US tech, 2 Jul – 30 Sep 2026: `Management change` 939 names, `Strategy change` 713); `major_shareholders` and `restructuring` KUs.
- **Upside:** current price → re-rated value if the pushed-for change is achieved: the segment-matched peer multiple (3b) applied to the company's own metric (`‡`), one `valuation_multiple` call for the candidate and its peers; the consensus target is never the upside. Every Scan C candidate gets this re-rating — "not sized" is never a drop reason.
- **Columns:** Ticker, Company, Market Cap, Event Type (`Activist/Restructuring`), Event Description (2–3 sentences), Upside %, Who Is Involved, Status/Timeline, The Change Being Pushed & Its Potential Value, Source.

#### Scan D — Distressed / Capital Events

- **Find:** genuine balance-sheet distress and capital-structure situations: distressed/turnaround names, stress-driven recapitalizations, refinancings forced by liquidity need or a maturity wall, rights issues tied to a capital shortfall, debt-for-equity exchanges.
- **Distilla:** `standard_event` types `Financial Distress or Solvency Concern`, `Credit rating change`, `Liquidity outlook change`, `Debt default`, `Debt Restructuring`, `Insolvency filing`, `Auditor going concern`, `Issuance of follow-ons`, `Convertible Debt conversion`; `debt_details`, `cash_and_debt`, `debt_refinancing_risk`, `auditor_opinion` KUs.
- **Qualifying bar:** requires a concrete distress signal — downgrade to junk (S&P/Fitch BB+ or below; Moody's Ba1 or below), covenant breach, liquidity crisis, going-concern warning, or insolvency/restructuring proceeding.
  - An investment-grade downgrade (e.g. A- → BBB-, or staying at BBB-/Baa3 or better) does **not** qualify alone — only with another signal from this list.
  - **Exclude** routine IG bond issuance, routine refinancing, and opportunistic financing (lower-rate refi, growth raise, dividend recap) by healthy companies, regardless of size.
  - `Financial Distress or Solvency Concern` rows can be mislabeled history — read the headline.
- **Cross-check:** before including a row, test the distress claim against the company's own recent revenue trend (3g field note), auditor opinion (`auditor_opinion` KU), and credit rating. If the profile doesn't support it, drop the row.
- **Upside:** current price → reasonable recovery / re-rated value if the catalyst resolves favorably.
- **Columns:** Ticker, Company, Market Cap, Event Type (`Distressed/Capital Event`), Event Description (2–3 sentences), Upside %, Status/Timeline, The Catalyst & Potential Value or Risk, Source.

**Checkpoint (resume marker, never a stop):** a working line after Step 2, not in the output — `Checkpoint: Steps 1–2 done; universe N; kept A a · B b · C c · D d; resume at Step 3`. On a review stop, show the four scan tables with their count lines and end the turn. When a turn ends before the deliverable, the next turn resumes at the first unfinished step or scan, reuses the Step 1 `company_id` set and completed scan tables, and never re-runs completed steps.

### Step 3 — Consolidate and rank by risk/reward

Work through these in order across all four scans.

**3.1 Dedupe and clean**
- Drop exact duplicates on (Ticker + Event Description).
- Where the **same underlying event** was picked up by more than one scan (even if worded differently), keep only the version with the most concrete, verifiable terms.
- Where a company has **genuinely distinct, non-conflicting** situations (e.g. a spin-off AND a separate activist campaign), keep **all** of them as separate rows — each is its own thesis.
- Drop non-distressed mega-cap routine debt offerings.

**3.2 Minimum upside filter**
Carry forward each scan's Upside % and its calculation. Drop any row where Upside % is not **strictly greater than** `min_upside`.

**3.3 Score survivors**
Carry forward Ticker, Company, Market Cap, Event Type, and Event Description as captured — don't re-derive them. Then assess:
1. **Upside:** % from 3.2.
2. **Downside:** price drop if the thesis breaks, as a negative % from current price, per the downside-floor field note. For M&A, anchor on the unaffected pre-announcement price (`stock_price` before the event date). For spin-offs/restructuring, anchor on the legacy standalone valuation floor.
3. **Certainty:** probability the situation resolves as expected (0–100%).
4. **Timing:** best-estimate date or window to resolution.

**Expected return formula** (calculate with decimals):

`Expected Return = (Certainty × Upside) + ((1 − Certainty) × Downside)`

Example: Certainty 60%, Upside +25%, Downside −10% → (0.60 × 0.25) + (0.40 × −0.10) = 0.15 − 0.04 = **+11.0%**.

**3.4 Rank and group**
- Sort all surviving rows by expected return, **highest to lowest**. Verify no lower or negative row sits above a higher positive one.
- If a ticker has multiple surviving situations, place it by its **single highest** expected return, then list all its situations consecutively at that position, sub-sorted by their own expected return. Don't let this shift other tickers' relative order. Mark these rows so the reader sees the ticker has multiple situations.

## Completeness gate

Before answering, check each item and state PASS with the tool call that satisfied it; fix any failure before submitting. Don't show the checklist.

1. **Universe declared:** N, region, size threshold, and as-of date come from a `company` / `stock_price` query, and every row's `company_id` is in that set; the rundown printed before Step 1 and the review choice after Step 2 honored.
2. **Shared rules applied:** every row passes recency (with the confirming date where the event is older), the priced-in check, and entity verification; event scans grouped and paged until `truncated = false`, never keyword sweeps; no generic premium; no non-SOTP broker target as Scan B upside.
3. **Distress bar applied:** every Scan D row names a concrete distress signal and passed the revenue / auditor / rating cross-check.
4. **Upside shown with a one-line calculation** in every row; rows ≤ `min_upside` are gone.
5. **Expected return recomputed** with the formula for every row; sort order verified; multi-situation tickers grouped.
6. **Bold rule met:** the expected-return header and every value in that column are bold.
7. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called.
8. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†` and `‡`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.

## Output

**Concise requests:** a user preference for brevity shortens prose, never the required sections, tables or verdict line.

1. One line: universe, N scanned, window, `min_upside`.
2. The ranked table — **use this exact format**:

| Ticker | Company | Market Cap | Event Type | Event Description | Upside | Downside | Certainty | Timing | **Probability-weighted expected return** | Risks |
|---|---|---|---|---|---|---|---|---|---|---|
| [Ticker] | [Company] | [Market Cap] | [Event Type] | [Description] | [Upside % with 1-line calc] | [Downside %] | [Certainty %] | [Timing] | **[Expected Return %]** | [1–2 sentences on risks] |

**Formatting rule:** the header "**Probability-weighted expected return**" and **every value** in that column must be wrapped in double asterisks (e.g. `| **45.6%** |`, `| **-2.1%** |`). Never leave a cell in this column unbolded.

3. **Caveats:** situations dropped at each stage (with reason — duplicates, stale re-dated rows, off-entity rows, priced-in, below `min_upside`), event dates that could not be confirmed, estimated vs. sourced upside figures, any missing-tool replacements used, and each ranked row's expected return on the 3-year own-history low (156 weekly values) as a sensitivity line.
4. **Source footnotes:** every `†` footnote (`† {source}, as of {date}; not Distilla data — methodology may differ.`) and `‡` formula.
5. **Method notes (≤4 lines):** universe date and market-cap gate check, event paging (by `company_id` range), downside-floor basis, fallbacks taken.

Do not pad the table. If few situations survive, show what survived and say why. A run that ends with an open coverage item (a scan's group count, a page tail, a scan type, a 3f rebuild) is partial: name the open items and resume at them — never close the run with them open.

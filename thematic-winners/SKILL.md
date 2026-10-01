---
name: "thematic-winners"
description: Long-only thematic idea generation. Maps a theme's value chain into Direct and Indirect beneficiary tiers, derives a Favor/Avoid checklist from historical analogs, runs two independent screens (one per logic path) over a region and size band, tallies them into a ranked shortlist, and writes Long/Pass recommendations with catalysts for the top names. Uses Distilla MCP (screen_drivers, screen_earnings, ku_cell, product, stock_price, standard_event, earnings_calendar, public library). Use this whenever the user asks who benefits from a theme, thematic winners or beneficiaries, value-chain plays, "picks and shovels", long ideas for a trend (e.g. humanoid robotics, AI power, GLP-1, defense, nuclear), or which stocks to own for a theme, even if they don't say "value chain" or "historical analog". Do NOT use for short ideas or for explaining past sector price moves (use sector-price-driver-patterns).
compatibility: "Target platform: Claude.ai. Requires the Distilla MCP connector, web_search / web_fetch, and Python code execution. Claude Code note: the same file runs there; paired analyses can run as parallel sub-agents."
---

# Thematic Winners

**Platform:** Claude.ai (target).

Theme → two independent sets of screening criteria → two independent screens → tally → Long/Pass on the top names.

**This workflow is long-only throughout.** Every step focuses on companies that benefit from the theme. Studying losers is only a false-positive filter, never a source of short ideas.

Read `references/distilla-reference.md` before the first Distilla call.

## Inputs

| Input | Default | Notes |
|---|---|---|
| `theme_name` | (none — ask the user) | e.g. "humanoid robotics and industrial automation commercialization ramp" |
| `region` | Inferred (below) | → `company.hq_country` (covered listing regions read at run time) and the matching screen `universe` code; several regions → combined codes; "Global" / "worldwide" → `universe = ["all"]`, every covered listing region |
| `min_mcap_bn` | Inferred (below) | Billions of US dollars; strictly greater than (3f gate) |

Use the user's values where given; otherwise infer each from the request (market words, named listings, sector words, size words such as "large-cap", currency) or the user's context, and state it with its basis in the resolved inputs; an input that can't be inferred is asked for together with the review question. State the resolved inputs once before starting.

**Rundown and review choice (before Step 1):** after the resolved inputs, print this rundown filled in, as reply text in its own block — the question never replaces it:

```
Rundown — [theme], [region], [size band]
Step 1 — Theme map and analogs → screening criteria
Step 2 — Two independent screens (Direct, Indirect) → candidate tables
Step 3 — Tally → ranked shortlist
Step 4 — Recommendations → Top Ideas table, write-ups, catalyst calendar
```

Then, in the same text reply below the block, ask one question — in plain text, never through the tappable-options tool, which shows only the question and hides the rundown — together with any missing-input question: stop for review after Step 3 (tally), or run to the end. Then stop or continue as answered. A request that already states the choice ("run to the end", "stop after the tally") is the answer: print the rundown and ask nothing. No other approval stop.

**Execution:** Steps 1 and 2 each contain two independent analyses. Run each pair in sequence in Claude.ai, keeping each analysis's logic separate (parallel sub-agents in Claude Code).

## Data-source fallback

**Mode: Standard** — web figures allowed. If the user asks for a Distilla-only run, switch to **Distilla only**: every claim traces to a Distilla document or entity, no web, and missing = `--` or drop the item; the one exception is FX for currency conversion, from the FX row's web sources, dated, with source and date stated. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v25: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8 · 3f, 3g, 3h)

#### 2.1 Pre-flight checks (before any data step)

1. **KU coverage check.** (a) Find the company's latest 1–2 `cell_time_period_id`: `query_entity` on `ku_cell`, filter `group_company_id`, sort `cell_as_of_date desc`, limit 5. (b) One row query on `ku_cell` joined to `ku`, `ku.name IN (<skill KUs>)`, `cell_time_period_id` IN those periods (avoids 100-row truncation); if `truncated = true`, narrow to one period and rerun. A KU counts as covered only if its `content` is non-empty: (c) rerun (b) with `content = "[]"` and subtract those KUs (HSBC period 169462: 22 of 24 KUs have rows, 18 non-empty). Not `aggregate_entity` — it does not scan the full universe, so "no groups" does not prove a KU is empty.
2. **Currency & share-basis check.** Compare the reporting currency of every source used (`financial_data_point` `formatting`, `consensus_data_point.currency`, `ku_cell`, `financials_review`) with `stock_price.currency`, and check the currency of **every line used** against filings. Verify EPS basis: net income ÷ EPS vs filed share count. **Distilla EPS can be per ADR, in every source:** TSM `financial_data_point` EPS 331.25 TWD on 5,186m ADR-equivalent shares (1 ADR = 5 shares), `consensus_data_point` FY2026 EPS 531.58 TWD, `financials_review` EPS 331.24. **Don't trust labels:** `unit = per_share` and a TSM snapshot's "EPS ($)" are both per-ADR TWD. Run the check on **each source and snapshot** used. `hq_country` reflects the listing Distilla holds (TSM ADR = `US`).
3. **One currency + one share basis + one source basis per ratio.** Never mix `financial_data_point`, `financials_review` and KU values in the same ratio.

#### 2.2 Financials source ladder

- **Applies to every rung:**
  - Capex is reported negative → use `abs`.
  - **Banks and insurers:** use NI, EPS, ROE, total assets and book value only; EBITDA, NWC, capex, FCF and net debt are not meaningful → `--`.
- **Rung 1 — `financial_data_point`.** Join `T` (`time_period`) and `M` (`financial_metric`); filter `T.company_id`, `T.provenance = "financials"`, `T.duration = "year"` or `"quarter"`, `M.name IN (…)`. Matches `financials_review` where checked (HSBC revenue 138,390; Toyota capex 5.29T; TSM EPS 331.25 vs 331.24).
  - Parse in **Python**: strip thousands commas; `-` = missing → `--`. Read `unit` and `formatting` on every row, but **take the scale from the metric name**: labels can be wrong (AMD periods to Q3 2025: `unit = "M"` on EPS, `formatting = "USD"` on share counts).
  - **Anchor periods on `T.end_date` (month), not `T.fiscal_year`:** Toyota's FY ended 31 Mar 2026 carries `fiscal_year = 2025`; TSM FY2023 shows `end_date = 2023-12-29`.
  - **A quarter missing from an LTM** = the FY value − the other three quarters of that FY, same metric and source (`‡`; Vertiv Q4 2025 sales 10,229.9 − 7,349.9 = 2,880.0); no FY value → `--`.
  - **Trusted without extra checks** once currency matches filings: revenue, EBIT, EBITDA, capex, CFO, cash and debt lines.
  - Company-wide only: segments come from KUs (rung 3).
- **Never use:** `financial_statement_data`, `capital_expenditure_maintenance_expansion` (no cells anywhere).

#### 2.3 Derived metrics (show the formula; mark `‡`)

- **FCF** = CFO − capex from **one source and the same period**: `financial_data_point` `cash_flow_net_operating_cash_flow` − abs(`cash_flow_capital_expenditures`); vendor `cash_flow_free_cash_flow` is a cross-check only. KU fallback: CFO from `cash_flow_details`; capex from that cell if it has a capex line, else from `capital_expenditure` only when its description or comment shows **cash payments** for PP&E (not accrued or incurred capex), both from **one filing** (same `file_id`). A reported `Free cash flow` line counts only when its comment defines it as operating cash flow less capex. Else `--`. **Never use `financials_review` uFCF as FCF.**
- **Net debt** = `balance_sheet_short_term_debt_and_curr_portion_long_term_debt` + `balance_sheet_long_term_debt` − `balance_sheet_cash_and_short_term_investments`. `long_term_debt` includes leases; `long_term_debt_excl_lease_obligations` excludes them — pick one and use it for every peer.
- **Market cap** = price × latest `income_statement_total_shares_outstanding`, on the price's share basis (2.1 #2). `stock_price.market_cap` history can be stale, flat or null (Micron null 12–27 Aug 2026) — latest value only.

#### 2.6 Data-quality traps

- **Text `value` fields** (`financial_data_point`, `consensus_data_point`, `valuation_multiple`): `query_entity` filters compare lexicographically ("100" < "99") → numeric cuts via `aggregate_entity` with `having`, or filter in Python.
- **`aggregate_entity` output keys:** aliases come back camelCased (`op_margin` → `opMargin`) and dates as quoted strings (`"\"2025-12-31T00:00:00.000Z\""`), while `having` takes the alias as written. Read keys case-insensitively and strip the quotes in Python.
- **`ku_cell` values:** validate numbers against the cell's comment text and reconcile them against `financial_data_point` or `financials_review`; drop values that don't reconcile and discard misfiled numbers (e.g., a GM % in the `utilization_rate` field of `capacity_and_utilization_overall`). Use entries with `figure_type = "actual"` as actuals; `internal_target` and other types are context only (HSBC `common_equity_tier_1_ratio`: 14.1% actual at 30 Jun 2026 beside a 14–14.5% target). An entry with no `figure_type` counts as an actual only for a completed period whose comment reports a result; guidance and target entries are context only (HSBC `net_interest_margin_nim`).
- **`ku_cell` parsing:** normalize value strings — units ("thousand NT$", "million RMB"), `bn` / `m` with no currency (take the currency from the filing), parentheses = negative, unit/currency mislabels (e.g., NT$ thousands tagged "USD") — and key names (`period` / `name` vs `time_period` / `description`). Prefer entries sourced from the financial statements over transcript-rounded figures in the same cell.
- **YTD cumulative KU values** need differencing to get quarters.
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`earnings_calendar`:** filter and sort on `earnings_date` (there is no `date` field); rows from different `source`s (YFINANCE, FMP) can disagree for one company (AVGO: 9 vs 10 Dec 2026) — show both dates, each with its source, never pick one.
- **`price_explanation.price_move_percentage` is a decimal fraction**, identical to `stock_price.change` for the same date, despite the MCP doc's "% move". Filter a 5% move with |value| ≥ 0.05.
- **No total-debt line** in `financial_metric` (the entity description's `balance_sheet_total_debt` example does not exist) → rule 2.3 debt lines.
- **`stock_price` zero-volume rows:** half-day sessions can carry a genuine close with `volume = 0` (HSBC 0005.HK on the HKEX half-days 24 Dec 2025, 31 Dec 2025, 16 Feb 2026) → keep the close and the session; exclude the row from volume averages, turnover, RVOL and OBV. A zero-volume row with `change = 0` and the prior session's close on a full trading day is a **stale carry-forward** (Kweichow Moutai 600519.SS 5 Jul 2024; mainland China has no half-days) → drop it from returns, indicators and volume measures. Otherwise drop a row only if the exchange calendar shows the market closed.
- **`stock_price.market_cap` and `enterprise_value` are USD for non-US listings** while `stock_price.currency` is the local price currency (18 Sep 2026 rebuilds at ECB rates: Toyota US$226.8bn vs 228.3bn, Fast Retailing 131.5bn vs 132.3bn, Tencent 481.2bn vs 481.2bn; HSBC 24 Sep US$343.4bn vs 342.3bn). Convert the rule 2.3 rebuild to USD before the 10% check; never divide a vendor cap by a local price.
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

#### 2.7 Evidence, provenance and output

- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker. · `‡` derived figure, formula in a footnote.
- **Comparability:** never compare NTM with LTM values; use the same web source per field across target and peers.
- **Public Library numbers** must trace to a named broker + title + date (from the summary); otherwise use **qualitatively only**.
- **Method notes footer:** required, **≤4 lines**.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

#### 3h Peer research (sampled)
- Peers, rivals and screen candidates the skill selects — never a company the user named (3a). **Scope:** peers and rivals — the main ones only, at most 4, named by the skill's step (its head-to-head or primary comparison set); other selected peers keep their financial, filing and event evidence, get no library call and carry no broker claim in the output; screen candidates — every candidate. Per company in scope, one `search_public_library` `synthesize` call (`doc_types = ["Research"]`, `tickers = [company]`, `date_range = "90d"`, the skill's question) — never one call for the whole set, which can sample a single company — plus one `standard_event` call for the set (`Sell-side Rating Action`, `Sell-side Target Price Action`; `company_id` IN the set; same window) — discovery only: a peer's rating or target is stated only from a note read at its source, never from an event row. A claim that decides a ranking, rating or verdict is read at its source (`get_library_document` on the `document_id` the answer cites). This evidence is sampled: never written as every broker or the Street view. The `Brokers:` line adds `peers: synthesize ×n of N, events ×1` (n researched, N selected).

#### 3f Universe market-cap gate
- Gate on the latest `stock_price.market_cap` (USD for every listing, rule 2.6) at each listing region's latest date (`MAX(date)` grouped by `company.hq_country`); convert a non-USD threshold once, at the FX row rate for the screen date. Spot-check 2–3 names per listing region against the rule 2.3 rebuild (within 10%), rebuild every name within ±10% of the threshold before deciding it, and show rebuilt values in market-cap cells.

#### 3g Growth-rate guard
- Compute growth in Python from two periods of one metric on one basis (`financial_metric` has no growth lines; periods by `T.end_date` month). A base ≤ 0 → `--`. Growth beyond ±1,000% → excluded from rankings, scores and verdict inputs and named with its cause: an acquisition (`standard_event` `Merger or Acquisition`), first commercial revenue, or a scale / definition break (rule 2.6 splice).

**Reading `ku_cell`:** run the KU coverage check (rule 2.1 #1) on the evidence KUs first, then `query_entity` on `ku_cell` joined to `ku`, filtering `ku.name` IN the units and `group_company_id` = the company `id` (product-category singletons by `group_product_category_id`). `content` is structured JSON — parse it in Python and check each value's period and unit. An empty unit is not evidence of absence.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Annual financials (revenue, GP, EBIT, EBITDA, NI, EPS, CFO, capex, cash, debt, ROE/ROIC) | `financial_data_point` (`T.provenance = "financials"`, `T.duration = "year"`; rule 2.2) | `executive_summary` `financials_review` actual columns; `ku_cell`: `cash_flow_details`, `balance_sheet_details`, `by_segment_financials`, `cash_and_debt`, `capital_expenditure` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → stockanalysis.com → MarketScreener. State when an aggregator was used. |
| Interim financials, segments, OCF | `financial_data_point` (`T.duration = "quarter"`); segments: `ku_cell` `by_segment_financials`, `geographical_segments`; `standard_event.earnings_summary` (`type = "Earnings announcement"`) | `ku_cell`: `cash_flow_details`, `capital_expenditure` (difference YTD values), `gross_margin_trends`, `operating_margin_trends`, `net_margin_trends`, `working_capital`; `executive_summary` `recent_performance`; `file` `Composite Filing` | Same as Annual financials |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), and `web_fetch` refuses a typed URL. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Large price moves | `price_explanation` (`date`, `price_move_percentage` — decimal, rule 2.6, `explanation`) | `standard_event` and `file` `News Article` on the same dates | Company press releases → major newswires; `web_fetch` before citing |
| Theme economics and value chain (Step 1A) | `search_public_library` (`doc_types = ["Research", "Podcast"]`, `mode = "synthesize"` — a theme is a topic query and `list` ignores `query`; `date_range = "90d"` first; retries change the `query` wording, still `synthesize`) | `ku_cell` `category_trends_enriched`, `category_size_and_growth_enriched`, `upstream_categories_enriched` for a matching `product_category` | Official filings (industry sections of 10-Ks and annual reports) → company IR (investor days) → one named industry source (e.g. IFR for robotics) |
| Historical analog evidence (Step 1B) | `search_public_library` (Research, Podcast; `mode = "synthesize"`, `date_range = "1y"`, stated; retries change the `query` wording, still `synthesize`) | `stock_price` / `price_explanation` for analog-era names, if covered | Official filings from the analog period → company IR → named histories or industry sources. Price history: **None** |
| Candidate universe | The region's screen `universe` code; screened candidates gated on `stock_price.market_cap` at each region's latest date (3f) | None | **None** — the universe is Distilla-only; never add web-found names |
| Criterion match | `screen_drivers` / `screen_earnings` on the region's `universe` code; coverage retries on `company_ids` | `product`; `ku_cell` `by_segment_financials`, `order_backlog`, `order_intake`, `key_customer_wins`, `notable_customers`, `products_details_enriched`, `robotics`, `automation` | Segment notes in official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → **None** for aggregators (theme lists are unreliable) |
| Recent sentiment | `price_explanation`; the 3h broker read (Step 4) | `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`) — discovery only: brokers and dates to read via the library, never a rating, TP or view | Company IR → named news (Reuters, Bloomberg, Nikkei) |
| Fundamental trajectory (orders, guidance, earnings) | `ku_cell` `guidances`, `order_intake`; `standard_event` `Earnings beat or miss`, `Management guidance`; revenue growth from the Annual / Interim financials rows (3g) | `standard_event` (`Earnings announcement`) `earnings_summary` | Official filings → company IR → one named aggregator |
| Catalyst dates | `earnings_calendar`; upcoming `standard_event` items | `standard_event` `Announcement of the next earnings release` | Company IR events calendar → one named aggregator |

**Field notes for this skill:**
- **Library modes:** Step 1 theme and analog reads are topic queries — `mode = "synthesize"` per the Theme economics and Historical analog rows (`list` ignores `query`, so an untickered list cannot target a theme). A Step 1A forward claim is corroborated across ≥ 3 distinct library documents in the `synthesize` sources, else the gap is stated; `sources` carry no broker tag, so a broker is named only from a `get_library_document` read, and library numbers follow rule 2.7. Step 1B may extend to `date_range = "1y"` — state the window used.
- **3h scope (this skill):** the Step 4 written-up names (3–5) are the screen candidates in scope — one `synthesize` per name plus one sell-side event call across the set (discovery only); shortlist-only names get no library call and carry no broker claim. This skill carries no 3a (no user-named companies; the theme is the input); its `Brokers:` line takes the Step 4 item-3 form — there is no 3a line to suffix.
- **Universe (3f):** `min_mcap_bn` (USD) is the 3f threshold, applied to screened candidates, not to a pre-built universe (Step 2). Market-cap **cells** follow Step 2's Market-cap cells rule, which overrides the FX row and the Market cap row for those cells only (user decision).
- **Screens:** one screener call per **distinct criterion** (stock-screener's distinct-criteria rule — not the decomposition antipattern), polled with `get_screen_job`; match sets combined with **OR**. `coverage` lists `no_coverage_company_ids` (no profile) and `not_evaluated_company_ids` (coverage-capped — often half the universe or more per call; `screen_drivers`); `screen_earnings` reports `matched_not_scored_count` instead; all are coverage gaps, never non-matches (Step 2 retries the second). Report each screen's count contract in stock-screener's `screen_drivers` form: `Scanned N_universe companies → N_scored evaluated (…) → M matched`.
- **Growth evidence (3g):** order or revenue growth in Step 4 follows 3g; an excluded rate never enters the stance.
- **No valuation** anywhere in this skill: no `valuation_multiple`, no `sell_side_target_price`. The Step 4 `Reflected:` line uses price and sentiment inputs only — never a multiple or target.

**Provenance:** markers, the `†` footnote and one web source per field (across every candidate in a screen) follow rule 2.7.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Arithmetic runs in Python on the saved results and renders as a plain markdown table — numbers only (OR-unions, tally scores, tie-break sorting, growth rates); judgments (criterion fit, Benefit Level, Long/Pass) stay with you.

## Required research plan

### Step 1 — Understand the theme

Two analyses, each with **distinct logic**, each ending in explicit, testable **Screening Criteria** for Step 2. Neither runs a screen or names companies — turning criteria into candidates is Step 2's job.

Ground both in evidence: `search_public_library` per the Theme economics and Historical analog rows (`synthesize` topic queries; a 1A forward claim needs ≥ 3 distinct library documents, else state the gap; name a broker only from a `get_library_document` read), and product-category KUs (`category_trends_enriched`, `category_size_and_growth_enriched`, `upstream_categories_enriched`) where a relevant `product_category` exists. Library figures follow rule 2.7.

#### 1A — Beneficiary map (value-chain logic)

1. Break the theme into the layers required to deliver it (e.g. for a hardware theme: raw materials → components → sub-assembly/integration → end product/OEM → distribution/service).
2. For each layer, assess where **pricing power or the bottleneck** sits and why (capacity constraints, IP, standard-setting, customer concentration). Not every layer captures the economics equally.
3. Assess the **funding mechanism** — who pays, whether spend is discretionary or multi-year/committed, what accelerates or slows it — and give each layer a demand-certainty read (High / Medium / Low).
4. Classify each layer:
   - **Direct / 1st-degree:** current core revenue directly participates in the theme's spending (they sell what the money goes toward).
   - **Indirect / 2nd-degree:** benefit from knock-on effects (suppliers to the Direct tier, or an end market that expands because of the theme).
   - The **end-product / OEM layer is Direct** — it sells what the money goes toward. Tag its criteria and rows `Direct (OEM)` so end-product makers read apart from component suppliers; a pre-revenue OEM program stays Direct here and is tested in 1B.

Skip layers with weak economics or commoditized positions.

**Criteria discipline:** each criterion must isolate the **specific product, function, or mechanism** tying a company to the layer — not a category label a company could satisfy through adjacent offerings or marketing language (e.g. an "automation" or "connected" product line that doesn't perform the theme's core mechanism). Narrow broad differentiators to the sub-function the theme actually depends on (which physical task is automated, and by what mechanism).

**Output:**
- Table: layer, tier (Direct / Indirect), pricing-power/bottleneck assessment, demand-certainty.
- **Screening Criteria:** 2–4 testable business characteristics per tier, each tagged with tier, source layer, and demand-certainty. Each also states **what would NOT qualify** — a closely adjacent but functionally distinct category a screen could mistake for a match.

#### 1B — Historical analog (pattern logic)

1. Identify the 1–2 closest historical themes or episodes (by event type, market structure, timeframe). Justify the choice and note differences that limit the comparison.
2. For each, identify the **specific characteristics** that separated durable winners from short-lived pops or disappointments — e.g. recurring vs. one-off theme revenue, balance-sheet capacity to fund the buildout, first-mover vs. fast-follower economics, whether the re-rating held after hype faded.
3. Translate those into a forward-looking checklist.

**Criteria discipline:** every **Favor** criterion is a **compound test** — the company must:
- (a) have current, disclosed commercial revenue, contracted backlog, or paid production/deployment in the theme's specific mechanism — not a pilot, prototype, R&D partnership, or funding/capacity announcement; **and**
- (b) show the durable-winner trait **within that same theme activity**, not elsewhere in the business.

Write each Favor item as **one criterion string carrying both halves** — Step 2B screens it in a single `screen_earnings` call.

**Output:**
- The episode(s), the comparison, and what separated winners from disappointments.
- **Screening Criteria:** a checklist tagged **Favor** (include) or **Avoid** (disqualify even if thematically adjacent), each with a one-line reference to its precedent. Every Favor item is written as the compound test.

### Step 2 — Run two independent screens

Each screen uses **only its own analysis's criteria** and screens the full universe independently. Don't feed one screen's output into the other.

**Shared mechanics** (in this order — gate before ranking, so no ranked name is later dropped for size):
1. **Screen:** one screener call **per criterion** on the region's `universe` code (`["all"]` for Global) — never a pre-built `company_ids` universe (it costs ~10 paged queries and adds nothing). `screen_drivers` for structural exposure (1A criteria); `screen_earnings` for each 1B Favor criterion, the whole compound test in one criterion string. Set `top_n` = 100 (the maximum — a higher value errors). Poll `get_screen_job`.
2. **Gate (3f):** one paged market-cap sweep serves the gate, the item-4 re-score ordering and the Market-cap cells' vendor check — `aggregate_entity` on `stock_price`, `MAX(market_cap)` grouped by `company_id` from the earliest region latest date, no `having`, paged by `company_id` ranges (100 groups per page), filtered to the region by `company.hq_country` and to every sector holding a verified match on any criterion (items 3 and 4 read only those sectors), saved in Python — never a targeted candidate query, a threshold cut-off or a sweep paused partway in its place (items 3 and 4 and the Market-cap cells read it); if the turn runs short, end it with the resume line and finish the sweep next turn. A candidate passes if it has a price row and its value is above `min_mcap_bn`; the ±10% band is judged on the window `MAX`, so a name within it — borderline passers included — is re-decided at the latest date by the 3f rebuild. Drop failing names from `ranked` **before** any ranking; name the strongest ones under Caveats ("excluded on market cap").
   **Market-cap cells** (every candidate row, all regions) — never `--` when Distilla holds a price:
   - **Rebuild first:** latest `close` × latest `income_statement_total_shares_outstanding` (share basis per rule 2.1 #2), in the listing currency — batched: one `stock_price` call for all candidate IDs at the latest dates and one `financial_data_point` call for the shares (latest quarter), in chunks of ≤ 50 IDs, and one FX fetch per non-USD currency; never a per-name pull (49 names: 3 Distilla calls, 30 Sep 2026); every name within ±10% of the threshold rides in the same call and is decided before the tally — never left as "cannot reach the shortlist"; for a non-USD listing, convert at the FX row's latest-date rate (Google Finance, tried first), recording pair, rate and timestamp, with the FX row's pair check ("USD / JPY 157.2750" → USD cap = JPY cap ÷ 157.2750). Confirm the rebuild lands within 10% of the vendor USD `market_cap`; a wider gap means a wrong pair, direction or share basis — recheck before using it. Cell: the USD rebuild with `‡` (formula and the FX rate as `† {source}, as of {timestamp}` in the footnotes).
   - **No FX-row rate after Google Finance was tried, or shares missing:** use the vendor `stock_price.market_cap` from the latest row, written with its currency (USD for every listing, rule 2.6): `$9.13bn (vendor, USD)`. Never leave the cell `--` while a vendor value exists; `--` only when Distilla has no price row.
3. **Retry coverage:** for each **Direct-tier** 1A criterion (user decision, #308: Indirect-tier criteria are not retried — their `not_evaluated` count stands as a Caveats gap), re-run the same criterion on `not_evaluated_company_ids` minus the below-threshold set (the item-2 sweep), kept to sectors with ≥ 1 verified match on that criterion (sector from one `company` call on the set; 6d–6e retried ~1,900 IDs for 0 names, every hit off-theme) — stated per criterion in Caveats as `Retry set C1: N not evaluated − b below threshold − u in unmatched sectors = K IDs, c chunks` — as `company_ids` with `top_n` 1 (`ranked` still lists every scored match; `matches` would repeat each row's ~5 kB excerpt) in chunks small enough to come back with `not_evaluated_company_ids = []` (100 IDs did on 26 Sep 2026 — full coverage only; 100-ID chunks can still hide false negatives, item 4). Gate the new matches (step 2). `screen_earnings` instead reports `matched_not_scored_count` (earnings cells cut by a per-chunk relevance cap, no IDs) — nothing to retry; state the count in Caveats. Never back-fill 2B from 2A names to close it (screens stay independent). Any residual stays a counted coverage gap in Caveats.
4. **False-negative re-score (`screen_drivers` only):** a batched 0 is not proof of a non-match (TSM: 0 in `["all"]`, 3 alone; NVDA and AVGO: 0 in a 25-ID chunk, 3 in a 10-ID one; 27 Sep 2026). For each **Direct-tier** 1A criterion and each `sector_id` with ≥ 3 gated matches on it, take that sector's 3 largest unmatched names in the region (`company.hq_country`) above `min_mcap_bn` (vendor `market_cap` from the item-2 sweep — ordering only), pool them across sectors and re-score them on that criterion in chunks of ≤ 10 IDs (`top_n` 1 — read `ranked`); launch every re-score job before polling any. Indirect-tier criteria and smaller unmatched names are not re-scored. Gate and verify new matches as in items 2 and 5; count them in Caveats ("N names added by re-score"). Batched `screen_earnings` 0s are re-scored only by item 8; never back-fill 2B from the re-score.
5. **Verify evidence per candidate** — name the specific disclosed product, segment, or contract. Useful sources: `product` rows, and the Criterion match row KUs. A figure in a screen's `explanation` or `content_excerpt` is a lead: the figure cited comes from the matched KU cell (`ku_cell_id`) or a library note, and where they conflict the cell or note wins and the conflict is named in Caveats. The two screens' match sets **will not intersect mechanically** (different backing data): 2B credits both compound halves from the candidate's own `screen_earnings` evidence and KUs, never by matching it to a 2A result.
6. Apply stock-screener's evidence and count-contract discipline (field notes); the count contract adds `→ K retried → G passed the size gate`.
7. **Benefit Level (both screens):** High / Medium / Low, synthesizing demand-certainty, benefit magnitude and confidence in the evidence — one definition for both screens, so Step 3 can sum them.
8. **`screen_earnings` rescue (#405 escalation):** a batched `screen_earnings` 0 can hide a clear match at any batch size (CAT: unmatched in a batched 2B, 3 alone on the same Favor test, 30 Sep 2026). Take the 2A candidates rated High with no 2B match — **at most 5**, highest 2A rank first, vendor market cap breaking ties — and re-score each **alone** (`company_ids` = one ID, `top_n` 1) on the one Favor criterion that fits its 1A layer, named; launch every job before polling any. The 2A rating only selects the names: a score ≥ 2 credits 2B from that call's own evidence after the item 5 check, never from the 2A result. Caveats line: `screen_earnings rescue: n of N credited — [tickers and criteria]`. No other single-ID `screen_earnings` calls.

#### 2A — Beneficiary-Map Screen

- A candidate needs **at least one** 1A criterion (OR, not AND) — each represents an independent tier of exposure.
- **Evidence bar:** a company description, industry category, or segment label ("automation", "connected solutions") is not enough. Confirm the product performs the function the criterion describes. If the closest fit is adjacent but functionally distinct (e.g. asset-tracking or data-capture hardware standing in for robotics execution), **exclude it and note the near-miss**.
- **Capture:** company, ticker, listing region, market cap; which 1A criteria it meets and its tier; an overall **Benefit Level** (shared definition, item 7).
- **Rank** by number of criteria met, then Benefit Level. Cap at 10; names tied at the cap boundary are all kept (as Step 3 item 5), counted in the table caption. The cap limits the table, never the tally: every verified match beyond it keeps its Benefit Level in Step 3, listed under the table (a rescue credit included).

#### 2B — Historical-Analog Screen

- A candidate needs **at least one** Favor criterion.
- **Exclude** any candidate that clearly matches an **Avoid** criterion, even if it also matches a Favor — flag the conflict. This is a long-list disqualifier, not a short idea.
- **Evidence bar:** credit both halves of the compound test **together** in the same disclosed product, segment, or contract. Don't credit a durable-winner trait shown in an unrelated part of the business. Don't credit theme exposure from a pilot, prototype, R&D partnership, or funding announcement alone. A durable-winner half about balance-sheet capacity to fund the buildout is confirmed numerically — rule 2.3 FCF and net debt from `financial_data_point` (banks / insurers: qualitative, values `--`) — never from commentary alone.
- **Capture:** company, ticker, listing region, market cap; which Favor criterion and its precedent; an overall **Benefit Level** (shared definition, item 7; demand-certainty read from the matched Favor precedent).
- **Rank** by number of Favor criteria met, then Benefit Level. Cap at 10; names tied at the cap boundary are all kept (as Step 3 item 5), counted in the table caption. The cap limits the table, never the tally: every verified match beyond it keeps its Benefit Level in Step 3, listed under the table (a rescue credit included).

**Table-integrity check (both screens):** before finishing, confirm every company named anywhere in the screen's response — including takeaways or caveats — appears as a table row with a Benefit Level, and that the table is present even if only 1–2 names survive.

**Output:** tables titled **"Beneficiary-Map Screen"** and **"Historical-Analog Screen"**, ranked highest to lowest priority.

### Step 3 — Tally

**Before the tally:** every screen job Step 2 launched (screens, retries, re-scores) is polled and its result collected. Never tally with a job uncollected, a retry unlaunched or a Step 2 item shortened to fit the turn (a partial sweep, retries or re-scores picked by judgment, vendor caps in place of the rebuild) — poll it, or end the turn with the resume line and resume at the first unfinished Step 2 item.

One row for every ticker in at least one screen.

1. Carry over company, ticker, listing region, market cap, and the 1A layer and tier (a 2B-only name takes the closest 1A layer by judgment, else `--`). If they conflict across screens, use the most complete/recent figure and note material discrepancies.
2. Carry over each screen's Benefit Level exactly. Mark a column N/A **only** if that screen doesn't mention the company at all.
3. **Data-integrity check:** if a screen's table is missing or incomplete but its narrative names companies with a Benefit Level, treat the narrative as authoritative. Before scoring a reconstructed row, confirm ticker, listing region, and market cap (> `min_mcap_bn` in `region`) appear somewhere in the screen results. If any can't be confirmed, list it under **"Flagged - Incomplete Data"** instead of scoring it.
4. **Total Score:** High = 3, Medium = 2, Low = 1, N/A = 0 per screen; sum (max 6).
5. **Rank** by Total Score. Break ties by the higher individual Benefit Level (a High on one screen beats a best-of-Medium). Keep ties that can't be broken. Cap at 20 rows.

**Output:** table **"Tallied Shortlist"** with exactly these columns: Company name, Ticker, Listing region, Market cap, Layer (tier), Beneficiary map, Historical analog, Total score. Then the **"Flagged - Incomplete Data"** section if needed (company, known Benefit Levels, which field couldn't be confirmed).

**Checkpoint (resume marker, never a stop):** a working line after Step 3, not in the output — `Checkpoint: Steps 1–3 done; tally N rows; top K = [tickers]; resume at Step 4`. On a review stop, show the Tallied Shortlist and end the turn. When a turn ends before the deliverable, the next turn resumes at the first unfinished step and never re-runs Steps 1–3.

### Step 4 — Recommend

Take the **top 3–5** names from the ranked Tallied Shortlist only — never from Flagged - Incomplete Data; a tie at the write-up cut is broken by tier (Direct before Indirect), then more 2A criteria met, then vendor market cap, larger first — stated, never by judgment. Only two stances exist: **Long** or **Pass**. Don't write up any other shortlist name.

For each name:

1. **Business overview** — 3–5 sentences: main products/businesses and scale. Facts only, no valuation.
2. **Thematic benefit narrative** — from Step 2, which criteria it met, its tier and demand-certainty, and which Favor precedents it matches; from Step 1, the underlying layer and precedent context.
3. **Broker read (3h)** — one `search_public_library` `synthesize` per written-up name (Research, `tickers = [name]`, `date_range = "90d"`, the thesis question), plus one `standard_event` call across the written-up set (`Sell-side Rating Action`, `Sell-side Target Price Action`; discovery only — a broker view is stated only from a note read at its source). Read the stance-deciding claim at its source (`get_library_document` on the cited `document_id`). Sampled evidence — never written as every broker or the Street view; library numbers per rule 2.7, and no targets (no-valuation rule). Each name's section carries one line: `Brokers: synthesize ×1, events ×1 (set); read: [broker, date; …]` or `Brokers: no coverage found`.
4. **Sentiment / sanity check** — recent sentiment and price direction, plus a fundamentals check (earnings trajectory, business momentum; a matched balance-sheet-capacity criterion cites its Step 2B numeric confirmation). Sources: the Price, Large price moves and Recent sentiment rows, the item-3 broker read, `standard_event` types `Earnings beat or miss`, `Management guidance` (sell-side event rows are discovery only, Recent sentiment row), KUs `guidances`, `order_intake`, and growth per 3g. A `price_explanation` `explanation` attributes a move only: a date or figure in its text is a lead, stated only once a library note, filing or `earnings_calendar` row confirms it (an event date from it alone is labeled unconfirmed). Close with the required line `Reflected: [Largely / Partly / Not yet] — [basis]`, judged from the name's 12-month return vs the median of every Tallied Shortlist row (both from `adjusted_close` — first and last close in the window, listing-currency returns, computed in Python from bulk pulls), sentiment direction, and whether the identified catalysts are still ahead. Price and sentiment inputs only. No valuation multiples or price-level commentary.
5. **Key catalysts** — upcoming theme-driven catalysts and timing windows (`earnings_calendar`, `standard_event` types such as `Product Launch Action`, `Customer win or loss`, `Adjustment of Production Facilities or Capacity`; events deduped and date-verified, rule 2.6), plus any bigger unrelated catalyst that could dominate near-term direction.
6. **Stance:**
   - **Default to Long** if the narrative is Direct (or Indirect with clear demand-certainty) and the sanity check shows no fundamental red flag. Order growth, revenue growth, or raised guidance is sufficient evidence; isolated theme-only revenue disclosure is not required.
   - **Pass only** with one of: (a) a fundamental red flag (declining orders, margin collapse, guidance cut); (b) a bigger unrelated catalyst will dominate near-term direction; (c) the narrative is weak/Indirect with Low demand-certainty.
   - An unresolved catalyst or missing theme-specific disclosure is **not** a Pass reason — use **Long, Low conviction**. Low-conviction Long = thesis intact, catalyst not yet fired or evidence partial; belongs on a long book, sized or timed cautiously. Pass = something is actually broken per (a)–(c).
   - For **Long**: give conviction (High / Medium / Low), the validating catalyst or window, and one `Invalidation:` line — a specific, observable condition that breaks the thesis (an order, guidance or margin marker; a lost contract or program; a catalyst that fails to fire by its window). It is an exit signal for the long, never a short idea. For **Pass**: state which of (a)–(c) applies and the evidence.

**No valuation anywhere in Step 4:** no P/E, EV/EBITDA, or other multiples; no relative valuation; no price targets (don't use `sell_side_target_price`); no scenario grids; no reward/risk from price levels — and don't use any such calculation, explicit or informal, in the decision.

## Completeness gate

Before answering, check each item and state PASS with the tool call that satisfied it; fix any failure before submitting. Don't show the checklist.

1. **Long-only held:** no short ideas anywhere; Avoid matches were excluded, not shorted.
2. **Criteria testable:** every 1A criterion states what would NOT qualify; every 1B Favor criterion is a compound test.
3. **Screens independent:** each used only its own criteria over the full universe; one screener call per criterion; size gate applied before ranking; Direct-tier unevaluated IDs retried in chunks, gated first (the `Retry set` line); the item 8 rescue run (≤ 5 single-ID calls), credits counted; every launched job collected before the tally; false-negative re-score run for Direct-tier `screen_drivers` criteria (Step 2 item 4), names added counted; match sets combined with OR; count contracts stated; residual gaps in Caveats.
4. **Evidence named:** every screened candidate cites a specific disclosed product, segment, or contract; near-misses noted.
5. **Table integrity:** every company named in a screen's text appears as a row with a Benefit Level.
6. **Tally recomputed** (High 3 / Medium 2 / Low 1 / N/A 0); unverifiable names sit in Flagged - Incomplete Data and got no recommendation; every market-cap cell is a `‡` rebuild with its FX footnote or a labeled vendor value — none `--` while a price row exists; the rundown printed before Step 1 and the review choice after Step 3 honored.
7. **No valuation** in Step 4: no multiples, targets, or price-level reward/risk.
8. **Recommendation lines:** every written-up name has its six parts and its `Brokers:` line; every Long carries Conviction, `Invalidation:` and `Reflected:` lines; the Top Ideas table and Catalyst calendar are present and cover every written-up name.
9. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called; Step 1 library reads were `synthesize`, never an untickered list.
10. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†` and `‡`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.

## Output

**Concise requests:** a user preference for brevity shortens prose, never the required sections, tables or verdict line.

1. **Top Ideas table** — one row per written-up name, ordered Long High → Long Medium → Long Low → Pass (within a band, by catalyst certainty): Ticker | Layer & tier | Conviction (or Pass) | Catalyst & window | Invalidation | One-line thesis. A Pass row's Invalidation cell carries its (a)–(c) reason instead.
2. **One section per top name** (3–5), following the six-part structure, in the table's order.
3. **Catalyst calendar** — one table across the written-up names: Ticker | Date / window | Event | Source; `earnings_calendar` source disagreements show both dates, each with its source (rule 2.6).
4. **Supporting work** (after the recommendations): the Tallied Shortlist, both screen tables, and the Step 1 Screening Criteria, printed in full in the final deliverable, also after a resume — never a condensed "unchanged from the previous turn" line. Offer to show the full Step 1 analyses if not included.
5. **Caveats:** screener coverage gaps (the `Retry set` line per criterion; no-profile and residual unevaluated counts per screen, after retries), names added by the false-negative re-score (`screen_drivers` only; the line "batched `screen_earnings` 0s may be false negatives" — a clear match can score 0 in a batch of any size, 29 Sep 2026 — stated; only the item 8 rescue re-scores, with its `screen_earnings rescue` line; Indirect-tier `not_evaluated` counts not retried), names excluded on market cap, near-misses excluded, flagged names, growth rates excluded by 3g, and any missing-tool replacements used.
6. **Source footnotes:** every `†` footnote (`† {source}, as of {date}; not Distilla data — methodology may differ.`) and `‡` formula, including each FX rate used in a market-cap rebuild (pair, rate, source, timestamp).
7. **Method notes (≤4 lines):** universe date and market-cap gate check, library windows used, screen coverage, fallbacks taken.

---
name: dcf-modeling
description: Build a full 3-statement financial model (income statement, balance sheet, cash flow) and a DCF valuation in Excel with live formulas, using Distilla MCP data (actuals, consensus estimates, prices) for listed companies in Distilla's coverage. Use this skill whenever the user asks to value a company, build a DCF, do a discounted cash flow, build a 3-statement or three-statement model, estimate intrinsic or fair value, work out what a stock is worth, or asks for a financial model or valuation model of a listed company, even if they don't say "DCF" or "Distilla". Also use it for bull/bear/base scenario valuations, WACC-and-terminal-growth sensitivity tables, or updating a model built earlier with this skill. Do NOT use for a first-pass screen with a verdict (initial-screen), why a multiple re-rated (valuation-compression-recovery), a peer multiple comparison (peer-benchmarking), a long/short pitch with catalyst and R/R (long-short-ideas), or an investment committee review (fundamental-guru).
---

**Runtime requirements:** Requires Distilla MCP tools, web search / page fetching (`web_search` / `web_fetch` or equivalent host tools), and Python code execution. Map the tool names in these instructions to the host's equivalent capabilities while preserving source restrictions and required checks. If tool loading is deferred, use the host's discovery mechanism; MCP tool prefixes may vary. Building the workbook needs Python with openpyxl; recalculation uses the host's spreadsheet recalculation tool if it has one, else `scripts/recalc.py` (Python `formulas` package).

# Distilla 3-statement + DCF model

Builds a banker-style Excel model from Distilla data. The 3-statement model comes first and the
DCF sits on top of it, so free cash flow is *derived* from the forecast statements, never typed
in. Change one assumption and it flows through all three statements into the valuation.

The workflow has one deliberate pause: the assistant drafts assumptions, **the user confirms or edits
them**, then the assistant builds. A DCF is only as credible as its assumptions, and the mechanical
draft misses things only the user can judge (for example, whether a peak-cycle margin is
structural).

## Files

- `scripts/prepare_inputs.py` — cleans Distilla output, drafts Base/Bull/Bear assumptions, fills
  flagged WACC defaults, prints the checkpoint summary.
- `scripts/build_model.py` — writes the live-formula workbook (7 tabs).
- `scripts/segments.py` — turns Distilla segment cells into a clean annual segment table for the
  Drivers tab.
- `scripts/recalc.py` — recalculates the workbook in Python (`formulas` package) when the host has
  no spreadsheet recalculation tool.
- `scripts/check_model.py` — independent post-recalc verification.
- `references/distilla_queries.md` — **read before querying**: exact query recipes, the 57
  metrics, the raw.json schema, data gotchas.
- `references/assumptions_guide.md` — read before the checkpoint: how the draft is built, the
  judgment calls to raise, WACC sourcing order, the checkpoint table format.
- `references/evidence_guide.md` — read for step 4: which Distilla qualitative sources to use
  (company_drivers, research library, knowledge units), query recipes, and rules.

## Data-source fallback

**Mode: Standard** — web figures allowed. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v26.1: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8 · 3a, 3e)

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
- **Effective tax rate** = `income_statement_income_taxes` ÷ `income_statement_pretax_income`, same period (TSM FY2025: 16.0%). Pretax loss or an implausible rate → multi-year average or a stated assumption, flagged.
- **Net debt** = `balance_sheet_short_term_debt_and_curr_portion_long_term_debt` + `balance_sheet_long_term_debt` − `balance_sheet_cash_and_short_term_investments`. `long_term_debt` includes leases; `long_term_debt_excl_lease_obligations` excludes them — pick one and use it for every peer.
- **ROIC** = EBIT × (1 − tax) ÷ avg(equity + debt − cash), all from `financial_data_point`; else the `financials_review` ROIC row; else `--`. ROE never substitutes for ROIC.
- **Diluted shares** = `income_statement_diluted_shares_outstanding`, confirmed by NI ÷ EPS (the 2.1 #2 check); else `financials_review` NI ÷ EPS.
- **Market cap** = price × latest `income_statement_total_shares_outstanding`, on the price's share basis (2.1 #2). `stock_price.market_cap` history can be stale, flat or null (Micron null 12–27 Aug 2026) — latest value only.
- **EV** = market cap + net debt, **in one currency** (net debt converted at the price date's FX, rule 2.4). Use `stock_price.enterprise_value` only if within **10%** of the rebuild (TSM 18 Sep 2026: vendor EV 15.4T vs market cap $2.25T for a net-cash company — reject).
- **Margins from KUs or vs reported figures:** reconcile to the filing; flag gaps **>0.5pp with `*`** (rule 2.7 Markers).

#### 2.4 Prices, FX and valuation
- **Multiples, rung 1 — `valuation_multiple`** (weekly `LTM_` and `NTM_` types). Label each value by its horizon (LTM or NTM). **Spot-check the latest value** against a rebuild on the same basis; keep the series if within **10%**, else rebuild. NTM is a **time-weighted FY blend**, not a sum of quarters.
- **P/E types are on adjusted EPS where the Street has it:** `_Pe` values usually match `eps_ex_xord_mean`, not GAAP (AMD 18 Sep 2026: NTM 41.5× vs 41.3× on adjusted and 49.0× on GAAP; LTM 84.1× vs 143.5× on GAAP; AAPL 25 Sep 2026 tracked GAAP instead). Spot-check NTM P/E against the time-weighted `eps_ex_xord_mean`; if the company has none (rule 2.5), against `eps_gaap_mean` (Nike 18 Sep 2026: 19.9× vs 19.6×), and label the P/E by the category that passed. LTM P/E cannot be rebuilt from `financial_data_point` (no adjusted line) — use it as vendor-computed. A GAAP P/E is a separate rebuild, labeled GAAP, never mixed with `_Pe` values.
- **Own-history statistics:** average and range via `aggregate_entity` on `valuation_multiple` filtered by `type` and a `valuation_date` window (ISO strings sort correctly); median and percentile need the weekly series (`query_entity`, ≤300 rows per page; 3 years ≈ 156 weeks) computed in Python — the aggregate has no median. State the window and the number of weekly values (loss periods and gaps have none: AMD `LTM_Pe_Med_W` 737 of 1,125 weeks; TSM `NTM_Pe_Med_W` 140 of 157 over 3 years). A value repeated across a week with no sessions (an exchange holiday) is a carry-forward — count it once (Kweichow Moutai `NTM_Pe_Med_W` 13 and 20 Feb 2026, Spring Festival closure).
- **Multiples, rung 2 — rebuild:** trailing P/E = month-end price ÷ trailing EPS from `financial_data_point` (LTM from quarters, or FY), labeled **GAAP**. Forward P/E = price ÷ `consensus_data_point` EPS, labeled **"fiscal-year forward"** unless time-weighted to NTM, and by EPS category.
- **Price basis order:** same currency as financials → **dated FX series matched to each month-end** (FX row: Fed H.10 → ECB) → `--`. **Never one spot FX rate for a history.** A local listing Distilla does not hold (e.g. `2330.TW` for the TSM ADR) is `--`.
- ADR point-in-time conversion: company-stated FX → the FX row rate for that date → `--`.
- **Cross-peer period basis:** when fiscal year-end months differ, use `valuation_multiple` LTM/NTM types, or LTM built from `financial_data_point` quarters, for **every** peer in that ratio; FY values only when all peers share the year-end month (rule 2.1 #3). State the basis in the table caption ("LTM to Jun 2026, all rows").
- `stock_price.sell_side_target_price` is back-filled → **latest value only**, never a history.

#### 2.5 Consensus & revisions
- **Consensus, rung 1 — `consensus_data_point`** (join `T`, `C`; filter `T.company_id`, `C.name`). Anchor the estimated period on **`T.end_date`, never `consensus_date`** (a weekly vintage spanning every period), and filter **`T.duration`** (`year` or `quarter`): annual and Q4 rows share `end_date` and `fiscal_quarter = 4` (MSFT FY6/2027 `sales_mean`, 18 Sep 2026: `quarter` 106,384, `year` 390,596). Match consensus to actual periods on the end-date **month**: the two can differ by days (Nike FY5/2026: actual 2026-05-29, consensus 2026-05-31). Use `_mean` by default and report `_nest`; **NEST < 3 → flag "thin"** (TSM quarterly periods: 2–5 estimates).
- **Scale check:** no `unit` field — amounts are in millions (TSM FY2026 sales 5,371,031 = TWD m). Confirm scale against the latest actual before use.
- **Match EPS categories to actuals:** `EPS_GAAP` ↔ `income_statement_eps_diluted`. `EPS_EX_XORD` is the Street's adjusted EPS and has **no matching actual** in `financial_data_point` (AMD FY2025 pre-print: `eps_ex_xord_mean` 3.96 vs `eps_recurring` 2.51; `eps_gaap_mean` 2.52 vs diluted 2.65): compare it only with company-reported adjusted EPS or `standard_event` `Earnings beat or miss`. Never compare across categories. **Category coverage varies:** `eps_ex_xord_*` is absent for Nike and for TSM after Oct 2021 (AMD has both) — check which categories exist (`aggregate_entity` grouped by `C.name`) before choosing one.
- **NTM consensus** = FY+0 and FY+1 time-weighted by months remaining (`‡`).
- **Consensus, rung 2 — `financials_review` snapshots** by `updated_at`: count a line only if **both** footnotes label it consensus **and both snapshots pass 2.1 #2**; else `--`.
- Consensus can **lag guidance**: use guidance for FY+0 and flag.
- Annual, quarterly and NTM consensus are all in Distilla: use no web consensus.

#### 2.6 Data-quality traps
- **Text `value` fields** (`financial_data_point`, `consensus_data_point`, `valuation_multiple`): `query_entity` filters compare lexicographically ("100" < "99") → numeric cuts via `aggregate_entity` with `having`, or filter in Python.
- **`aggregate_entity` output keys:** aliases come back camelCased (`op_margin` → `opMargin`) and dates as quoted strings (`"\"2025-12-31T00:00:00.000Z\""`), while `having` takes the alias as written. Read keys case-insensitively and strip the quotes in Python.
- **No total-debt line** in `financial_metric` (the entity description's `balance_sheet_total_debt` example does not exist) → rule 2.3 debt lines.
- **Actual → consensus splice:** a definition break can hit any line, within `financials_review` and between `financial_data_point` and `consensus_data_point` (HSBC revenue FY2025 actual 138,390 vs FY2026 consensus 74,768; Toyota capex actual 5.29T vs consensus 3.03T). Check continuity before anchoring on or trending across the splice; else `--` and note.
- **`ku_cell` values:** validate numbers against the cell's comment text and reconcile them against `financial_data_point` or `financials_review`; drop values that don't reconcile and discard misfiled numbers (e.g., a GM % in the `utilization_rate` field of `capacity_and_utilization_overall`). Use entries with `figure_type = "actual"` as actuals; `internal_target` and other types are context only (HSBC `common_equity_tier_1_ratio`: 14.1% actual at 30 Jun 2026 beside a 14–14.5% target). An entry with no `figure_type` counts as an actual only for a completed period whose comment reports a result; guidance and target entries are context only (HSBC `net_interest_margin_nim`).
- **Transcript period check:** a `ku_cell` transcript unit (`transcript_summary` and other call-derived units) can hold an older call's content under a recent `cell_time_period_id` (DIS, WBD, CMCSA cells as of Jul–Aug 2026 and AMD period 169500, tied to the Aug 2026 filing, summarize Q1 2023 calls) — before use, check the quarter the content names against the cell period (or the source file's period); on a mismatch, drop the cell and take the field's next rung.
- **`ku_cell` parsing:** normalize value strings — units ("thousand NT$", "million RMB"), `bn` / `m` with no currency (take the currency from the filing), parentheses = negative, unit/currency mislabels (e.g., NT$ thousands tagged "USD") — and key names (`period` / `name` vs `time_period` / `description`). Prefer entries sourced from the financial statements over transcript-rounded figures in the same cell.
- **Duplicate periods across filings:** prefer the annual-report cell.
- **YTD cumulative KU values** need differencing to get quarters.
- **Time series:** splice sources only after an **overlap check**.
- **`debt_details` `Interest expense`** is labelled with a point date: confirm on the cited source page whether it is a quarter or year-to-date flow before annualizing.
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`earnings_calendar`:** filter and sort on `earnings_date` (there is no `date` field); rows from different `source`s (YFINANCE, FMP) can disagree for one company (AVGO: 9 vs 10 Dec 2026) — show both dates, each with its source, never pick one.
- **`financials_review` limits:** prose sections below the table are qualitative only, never a numeric source (they can contradict the table — AMD prose capex ~5% of revenue vs table 2.8% — and carry untraced broker figures); forecast columns can hold actuals (Tencent FY2026 cash and debt are H1 2026 reported balances), so read the footnote before treating a cell as a forecast; footnote model assumptions (tax, interest, NWC and capex ratios) are Distilla model, never a sourced input; header dates are approximate — use the fiscal year-end **month** only and take exact period end dates from filings (Toyota FY ended 31 Mar 2024 shows `FYE 2024-03-28`).
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.
- **`stock_price.market_cap` and `enterprise_value` are USD for non-US listings** while `stock_price.currency` is the local price currency (18 Sep 2026 rebuilds at ECB rates: Toyota US$226.8bn vs 228.3bn, Fast Retailing 131.5bn vs 132.3bn, Tencent 481.2bn vs 481.2bn; HSBC 24 Sep US$343.4bn vs 342.3bn). Convert the rule 2.3 rebuild to USD before the 10% check; never divide a vendor cap by a local price.
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.

#### 2.7 Evidence, provenance and output
- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker. · `‡` derived figure, formula in a footnote. · `*` margin more than 0.5pp from the reported figure (rule 2.3), reported figure in a footnote.
- **Comparability:** never compare NTM with LTM values; use the same web source per field across target and peers.
- **Public Library numbers** must trace to a named broker + title + date (from the summary); otherwise use **qualitatively only**.
- **Method notes footer:** required, **≤4 lines**.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

#### 3a Research coverage
- Covers every company the user named — each one in a comparison; peers, rivals and candidates the skill selects follow 3h. `search_public_library` `mode="list"`, `date_range="90d"` first — a `synthesize` call never satisfies 3a (it samples few passages and may show one broker); fewer than 3 brokers → the same list once at `date_range="180d"`. A list returns at most 200 documents, newest first, with no truncation flag: exactly 200 is capped — state the earliest date it reaches, then list again with `brokers=[…]` for each broker that has `Sell-side Rating Action` or `Sell-side Target Price Action` events in the window but is not in the list — at most five brokers per call (the filter checks only the first five), so a larger set is split into calls of five. Read every broker found via `get_library_document` — all brokers, never a sample: each broker's most relevant recent note to the question by title, else its latest; 3–4 notes for a broker only where its titles show more than one relevant event. The summary is the readable depth (Research never returns full text). No minimum broker count: one broker is coverage found; none after both lists is `no coverage found`, not a gap. Ratings and targets come from the notes read (`summary`: rating, target, change, date); `Sell-side Rating Action` and `Sell-side Target Price Action` events are discovery only — they name brokers to list again, never a rating or target; an event no note matches is left out, and where an event and a note conflict, the note wins. State agreement/disagreement; where brokers give different figures or framings of one event, show both, attributed — never pick one or reconcile. Result: a `Brokers:` line (`list 90d — n docs, n brokers; read: [broker date; …]`; a capped list adds `cap 200, from {date}; re-listed: [broker]`) where the Output format places it (default: directly above the Method notes footer, outside its ≤4 lines).

#### 3e Valuation vs history
- Rule 2.4 multiples (latest value spot-checked) + 2.1 #2 check mandatory.

**Reading `ku_cell`:** `query_entity` on `ku_cell` with `joins = [{relation: "ku"}, {relation: "cellTimePeriod"}]`, filtering `ku.name` IN the units named in the steps (`by_segment_financials`, `cash_and_debt`, and the evidence units in `references/evidence_guide.md`) and `group_company_id` = the company `id`. `content` is structured JSON — parse it in Python and check each value's period, currency and unit; difference YTD values (rule 2.6).

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Annual financials (revenue, GP, EBIT, EBITDA, NI, EPS, CFO, capex, cash, debt, ROE/ROIC) | `financial_data_point` (`T.provenance = "financials"`, `T.duration = "year"`; rule 2.2) | `executive_summary` `financials_review` actual columns; `ku_cell`: `cash_flow_details`, `balance_sheet_details`, `by_segment_financials`, `cash_and_debt`, `capital_expenditure` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → stockanalysis.com → MarketScreener. State when an aggregator was used. |
| Interim financials, segments, OCF | `financial_data_point` (`T.duration = "quarter"`); segments: `ku_cell` `by_segment_financials`, `geographical_segments`; `standard_event.earnings_summary` (`type = "Earnings announcement"`) | `ku_cell`: `cash_flow_details`, `capital_expenditure` (difference YTD values), `gross_margin_trends`, `operating_margin_trends`, `net_margin_trends`, `working_capital`; `executive_summary` `recent_performance`; `file` `Composite Filing` | Same as Annual financials |
| Consensus estimates, annual and quarterly | `consensus_data_point` (`_mean` with `_nest`; period by `T.end_date` and `T.duration`; rule 2.5) | `financials_review` forecast columns — consensus lines only, per the footnote; `search_public_library` (`doc_types = ["Research"]`, `tickers`, `date_range = "90d"`) — traced figures only | **None** |
| Ratings, target price | Broker notes: `get_library_document` `summary` (rating, TP, change old → new, date) of a note found by `search_public_library` `list`; consensus TP = **latest** `stock_price.sell_side_target_price` only | None — drop the item. `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) is discovery only: it names brokers and dates to list again with `brokers=[…]` (at most five per call), never a rating, TP or TP trajectory; an event no note matches is left out, and a note it conflicts with wins | **None** |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| Valuation multiple vs own history | `valuation_multiple` (`LTM_` / `NTM_` types; latest value spot-checked, rule 2.4); EPS-based multiples only after 2.1 #2 | Rebuild per rule 2.4 | **None** |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), If the host requires a search-discovered URL before fetching, obtain it through search first. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Effective / marginal tax rate | Derive per rule 2.3 from `financial_data_point` (`‡`); `financials_review` footnote tax rates are Distilla model, never inputs | `file` `Filing` (tax note) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → statutory rate from the national tax authority; else a stated assumption, same basis for every peer |
| Interest expense | `financial_data_point` `income_statement_gross_interest_expense` (period flow, before capitalization) for cost of debt and coverage; `income_statement_interest_expense` is **net of capitalized interest** (TSM FY2025: 19,986 = 12,370 + 7,616 capitalized). **Captive-finance companies** book financial-services interest in cost of sales, outside both lines (Toyota FY3/2026 gross 86,746m vs Q1 FY3/2027 financial-services interest 901,297m in `debt_details`) — state it; coverage and cost of debt on the income-statement line are flattered | `ku_cell` `debt_details` `Interest expense` (period check per rule 2.6); `file` `Filing` (interest-expense note) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (interest-expense note) → company IR; else a stated assumption |
| Fiscal period end dates | `time_period` (`provenance = "financials"`) `end_date` month, not the `fiscal_year` label (rule 2.2); `earnings_calendar.earnings_date`; `file.published_at`; `financials_review` headers for the year-end month only (rule 2.6) | `standard_event` (`Earnings announcement`) date | Official filing cover page |
| Cash, debt, leverage, maturities | Balances: `financial_data_point` debt and cash lines (net debt per rule 2.3). Instruments and maturities: `ku_cell` `cash_and_debt`, `debt_details` (instrument balances, `interest_rate`, `due_date`), `leverage_ratio` (sparse) | `ku_cell`: `debt_refinancing_risk`; `standard_event` (`Issuance of bonds or non-convertible debt`, `Credit rating change`, `Liquidity outlook change`) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (debt note) → company IR → stockanalysis.com |
| Diluted shares (bridge) | Latest-quarter `financial_data_point` `income_statement_diluted_shares_outstanding`, on the price's share basis (2.1 #2; rule 2.3) | `ku_cell` `shares_outstanding` (cross-check only); annual `financials_review` NI ÷ EPS (`‡`) | Official filings (diluted weighted shares) → company IR |
| Buybacks, dividends, M&A | Flows: `financial_data_point` `cash_flow_repurchase_of_common_and_preferred_stock`, `cash_flow_cash_dividends_paid`, `cash_flow_net_assets_from_acquisitions`. Programs and history: `ku_cell` `share_buybacks`, `share_buyback_program`, `dividend_history`, `dividend_payout_ratios`, `mergers_and_acquisitions`, `capital_deployment` (sparse) | `standard_event` (`Buyback program change`, `Dividend Announcement`, `Dividend policy change`, `Merger or Acquisition`, `Divestment`); `stock_price.dividend` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (cash flow statement, M&A notes) → company IR |
| Risk-free rate, equity risk premium | Not in Distilla MCP today | None | Risk-free: U.S. Treasury daily yield curve or the currency's central bank / finance ministry. ERP: Damodaran implied ERP (NYU Stern). State source + date. |
| Beta | Not in Distilla MCP today (no index series) | None | Published 5Y monthly betas, every one found in one search: Yahoo Finance Statistics "Beta (5Y Monthly)", StockAnalysis, Investing.com, GuruFocus — each marked `†` with source and as-of date; a value read on a fetched page first, one seen only in a search result labelled "search result"; `prepare_inputs.py` takes the median, Blume-adjusts it and checks it against the sector beta; none found → relevered sector beta, flagged. Never a regression on Distilla prices; ignore 1-year betas and betas against a foreign benchmark |
| Broker research | `search_public_library` (`doc_types = ["Research"]`, `tickers`, `date_range`, `brokers`; `mode = "list"` for a catalog); `get_library_document` for summary + tags (Research never returns full text) | `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) — discovery only: brokers to list again, never a rating or TP | **None** — broker reports are not reliably on the open web; no broker after both 3a lists is `no coverage found`, not a gap. |
| Finance arm (captive finance: revenue, profit, assets) | `ku_cell` `by_segment_financials` (the finance segment: e.g. Financial Products, Financial Services, GM Financial, Ford Credit); `cash_and_debt` comment for the finance-arm debt or leverage | `ku_cell` `by_segment_performances` | None — Distilla covers these lines |
| Segment revenue and units (Drivers tab) | `ku_cell` `by_segment_financials` (full-year periods; `scripts/segments.py`) | `ku_cell` `by_segment_performances` | Official filings — the segment note of the latest annual report; mark `†` |
| Finance arm balance sheet (finance receivables current / long-term, debt, equity) | Not in Distilla MCP today as numbers (segment KUs give assets only; `cash_and_debt` gives text) | `cash_and_debt` leverage text → equity = assets ÷ (1 + leverage), debt = assets − equity, flagged estimates | Official filings — the latest annual report's supplemental consolidating data or finance-segment balance sheet: SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → the finance arm's own filed report; mark `†` with the as-of date |

**Field notes for this skill:**
- **Unlevered FCF comes from the forecast statements** (Model tab), never typed in; actuals are `financial_data_point` per the Annual financials row. `financials_review` uFCF actuals and `consensus_data_point` `UFCF` are cross-checks only; `financials_review` forecast uFCF is never an input.
- **Pre-tax cost of debt** = gross interest expense (Interest expense row; `income_statement_gross_interest_expense`, else `income_statement_interest_expense`, named) ÷ average total debt, same source. When that rate is not above the risk-free rate, or a finance arm books its interest in cost of sales, WACC uses risk-free + 150bp, labelled a default; the book rate still drives forecast interest on existing debt.
- **Beta** per the Beta row (median of published 5Y betas, Blume-adjusted, sector-checked), never one source picked by hand.
- **Banks, insurers, lenders:** no build — "When not to build a DCF" names what fits instead.
- **Bridge balances:** cash, long-term investments, debt, leases and minority interest at the latest reported quarter in the reporting currency; shares per the Diluted shares (bridge) row; market cap = price × FX × diluted shares (rule 2.3 rebuild), cross-checked against `stock_price.market_cap` (USD, rule 2.6) — a gap over 10% is flagged, and the vendor value is never the input.
- **Finance arm** (a finance segment whose assets are ≥ 10% of total assets): the DCF values the industrial business only — the finance segment's pre-tax profit comes out of EBIT and its receivables growth out of the cash flow, its debt and long-term finance receivables out of the bridge — and the finance arm is added back at book equity × justified P/B = (ROE − g) ÷ (cost of equity − g), bounded 0.5–2.5×. Its own cash comes out of bridge cash, and its assets leased to customers are held flat in PP&E (post-consensus capex and D&A run on the rest); beta is the published Blume-adjusted beta, without the sector check (finance debt funds low-risk receivables). A missing input falls back to 1.0× book, labelled a default in the workbook and the summary.
- **Pensions and the basis gap:** the net pension and retiree-benefit deficit is deducted in the bridge after tax (a surplus is not added); the basis gap (the company's own operating profit, which consensus follows, minus Distilla's EBIT for the same year, the median of up to 3 years, either sign — recurring charges or other income) comes off every consensus-derived margin, so the forecast is on Distilla's history basis. Neither is in Distilla: filings, `†`.
- **Discount rate vs brokers:** discount rates stated in the broker notes read (WACC or cost of equity) are recorded beside the model's; the workbook prices the value at the brokers' median rate. The model's rate is never replaced without the user's choice; a gap over 3 points is the first judgment call (local-currency CAPM in low-rate currencies runs well below broker rates — Anta: 5.8% vs 11%).
- **Pre-flight KU check (rule 2.1 #1)** covers `by_segment_financials`, `cash_and_debt` and the evidence units named in `references/evidence_guide.md`.
- **Terminal multiple cross-check (3e):** the implied terminal EV/EBITDA against the company's own 3-year `valuation_multiple` `NTM_Ev_Ebitda_Med_W` average, low and high (`aggregate_entity`, latest value spot-checked per rule 2.4); none returned → `--` with the call named. State the vendor EV basis the spot-check finds (with or without a finance arm's debt).

**Provenance:** markers, the `†` footnote, one web source per field and no NTM-vs-LTM comparison follow rule 2.7. The workbook's DCF tab carries every source string; in the chat summary, web values (risk-free rate, beta, ERP, finance-arm balance sheet) take `†` with source and date, derived values `‡`.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Arithmetic runs in the bundled Python scripts on the retrieved rows — numbers only; judgments stay with you.

## When not to build a DCF

Check the Distilla sector first (ids in distilla_queries.md section 1), and also the business itself:
sector tags are coarse (HSBC is tagged "Diversified Financial Services", not banking), so read
the company name and `company.summary` too.

- **Not in Distilla:** if the company lookup returns nothing (Distilla coverage is not
  universal; for example, few US banks), say so and ask for another ticker. Don't substitute
  web-scraped financials into this workflow, because the model's integrity checks assume
  Distilla's standardized statements.

- **Distilla unavailable:** if Distilla calls fail (connector not connected, or erroring) after one
  retry, stop and say so. Never rebuild the inputs from web data instead; give no value per share.
- **Banks, insurers, brokers, lenders, diversified financials, real estate finance:** stop. An
  unlevered-FCF DCF does not work when debt and deposits are the raw material of the business,
  and the output would look precise but mean nothing. Say so in a sentence or two and offer what
  does fit: a dividend-discount or excess-return (P/B vs ROE) model, or a multiples comparison.
- **REITs, asset managers:** build if asked, but say that FFO/NAV (REITs) or fee-based
  multiples are the usual lens.
- **Fewer than 3 clean annual periods, or loss-making with no path to positive FCF in the
  forecast:** tell the user before building and ask whether to proceed.

## Workflow

### 1. Pull the data
Load the Distilla tools (if tool loading is deferred, use the host's discovery mechanism). Follow
`references/distilla_queries.md` in order: company and sector → annual actuals (one query) →
latest quarterly balance sheet → consensus → price → finance-arm check. Run the section 6 sanity
checks, especially consensus units against quarterly actuals, price vs reporting currency, the
market-cap cross-check (rebuild vs `stock_price.market_cap`, within 10%) and the accounting
standard (it decides how leases are treated).

**Finance arm.** Read `by_segment_financials` (section 5b of distilla_queries.md). When a finance
segment's assets are 10% or more of total assets (Caterpillar Financial Products, Deere Financial
Services, GM Financial, Ford Credit), fill `raw.json["finance_arm"]`: revenue, pre-tax profit and
assets from Distilla (assets from the filing where the segment data has none); from the latest filing
that shows the finance arm separately — the 10-Q nearest the bridge date, else the annual report
(official filings, `†`): finance receivables
(current and long-term, as shown on the consolidated balance sheet), the finance arm's debt and
equity (its own column after eliminations), its own cash, and assets leased to customers (inside
PP&E). When only the finance arm's own filing is reachable (the parent's filing is too long to fetch),
its figures are before eliminations: use them and say so in `bs_source`. Else the Distilla leverage text;
else leave them `null`. The script values the finance arm separately; see the field notes. With segment
margins on, the DCF takes the arm's forecast profit from its Drivers line (held at its own trend).

**Segments (Drivers tab).** Read the latest full-year `by_segment_financials` cell (it carries about three
years; distilla_queries.md section 5c), save the rows, run `scripts/segments.py` on them to list the
fields, then again with `--revenue "<field>"` (and `--units "<field>"` where Distilla reports a unit
series, e.g. wholesale vehicles, and `--profit "<field>"` where the cell has segment operating profit) and
put the output in `raw.json["segments"]`. With profit for every line in the last actual year, EBIT is built
from segment margins plus a corporate / unallocated line (Distilla EBIT less segment profit, held at its median % of
revenue over up to three years); otherwise EBIT stays on the company-level margin and the script says why. When the latest annual
cell predates the last actual year, add the current year's quarterly / half-year cells: the script joins
a year-to-date period with the quarter that completes it. Give `--revenue` twice for a label that changed
between filings, `--rename` for segment names that differ between cells, `--exclude` for a wound-down
segment (its history moves into other / eliminations). A unit year Distilla lacks comes from the annual
report (`†`). Keep a finance segment — its revenue is in consolidated revenue — and list it in
`segments.hold` (`--hold`) so it keeps its own trend (and its margin) instead of absorbing the calibration — the
valued finance arm's line is held automatically. Hold any other line only when its own evidence sets its path
every year (a disposal, a contract run-off). When one field holds several breakdowns (brand, product and
channel at once), `--keep` picks one; it also filters `--profit`. When segments are
missing, too few or do not cover the last actual year, the script says so and keeps the single growth
rate.

**Revenue lines when there is one segment.** The lines need not be reported segments. In this order,
use the first with at least two years of sourced history: (1) business segments; (2) a product / service
split (new equipment vs services — the `aftermarket` KU gives Tokyo Electron's Field Solutions; the other
line is revenue less it, `‡`); (3) market × share for a line whose revenue follows an industry market
(record `market` growth and `share` change instead of `volume`); (4) geography (`geographical_segments`);
(5) KPI lines (units, subscribers, stores). Write these lines into `raw.json["segments"]` yourself, each
year cited in `line_sources`, and set `basis_type`; business-segment rows still come only from
`scripts/segments.py`. None available → the single growth rate, said in one line.

**Pensions, basis gap, history breaks, share count** (every company).
- From the latest filing: the net pension and retiree-benefit deficit (`bridge.pension_deficit`,
  pre-tax; 0 when funded).
- If consensus follows the company's own operating profit (an adjusted measure, or one that includes
  other income Distilla books below EBIT) — take the basis the brokers' estimates use (adjusted, e.g.
  before restructuring, when the notes quote adjusted margins), and check it: its margin should sit
  close to the consensus margin for a year consensus covered — that operating profit for up to the last 3 years
  (`basis_gap.adjusted_by_year`); the script takes the median gap to Distilla's EBIT, either sign,
  off every consensus-derived margin. When the CONSENSUS BASIS flag fires and the move is real (an
  upcycle), record `basis_gap = {"none": true, "reason": "..."}` instead.
- When the HISTORY BREAK flag fires (a business sold or reclassified as discontinued), record the
  continuing-operations revenue and EBIT for earlier years from the latest filing's restated
  comparatives in `continuing_history`; the script uses them for the reference points and the peak
  guard. If no restatement exists, say so in the flags.
- Basic shares (`bridge.basic_shares`, `income_statement_total_shares_outstanding`): the script flags
  diluted shares more than 3% above basic (convertible bonds counted in both shares and debt). Fix it in the
  draft — basic shares when the convertible is out of the money and stays in debt, else take it out of
  debt — and show the choice at the checkpoint.

**Fetching filings and pages:** only with the host's page-fetch tool. Never download pages with
code (`curl`, Python requests) and never send the user's name, email or other details in a request.
When an annual report is too long to fetch whole, fetch EDGAR's financial-report pages
(`R2.htm`, `R4.htm` … in the filing folder) or the XBRL company-facts page instead. Outside the US
(HKEXnews, TDnet, EDINET, DART, CNINFO PDFs over the fetch limit): the interim report or the results
announcement, which carry the same statements; else record the item as not sourced (0) and flag it.

### 2. Source WACC inputs live
Use the host's full web search here, not a fast or lite variant: in testing a fast search tool
returned no betas, while the full one found them on the first try for all four test companies.
- **Risk-free rate:** 10-year government bond in the **reporting currency** (BYD is HK-listed but
  reports in CNY, so China's yield).
- **Beta:** search "<ticker> beta 5Y monthly" and record every 5-year figure you find (Yahoo,
  StockAnalysis, Investing.com, GuruFocus) in `wacc.beta_published` with their sources. Don't
  pick one yourself; the script takes the median, applies the Blume adjustment, and checks it
  against the sector beta. Ignore betas measured against a foreign benchmark (e.g. a Korean
  stock vs the S&P 500) and 1-year betas.
- **Equity risk premium:** Damodaran's latest mature-market implied ERP; record its as-of month in
  `erp_source` (e.g. "Damodaran implied ERP, Jan 2026").
- **FX:** if the price currency differs from the reporting currency.
Don't compute beta from Distilla prices: Distilla has no index series and only one year of
(patchy) market caps, and home-made proxies gave clearly biased betas in testing. Record a short source string for each. Leave anything you cannot find as
`null`; the script fills a flagged default. Don't spend more than one search per input.

### 3. Prepare and draft
Write `raw.json` (schema in distilla_queries.md section 7) in a working folder, then:
```bash
python <skill_dir>/scripts/prepare_inputs.py raw.json model_inputs.json
```
The printout is the draft. Read `references/assumptions_guide.md` now.

### 4. Evidence first, then anchor the numbers
The mechanical draft only covers the consensus years honestly. After that it is formula, and a
formula dressed up with reasons found afterwards is retrofitting. So for the drivers that decide
the value (post-consensus EBIT margin and growth, sometimes capex), follow
`references/evidence_guide.md`:
1. **Gather evidence before deciding**: one `company_drivers` query; the rule 3a broker list
   (`search_public_library` `mode="list"`, `date_range="90d"`, `doc_types=["Research"]`, the
   ticker); each entry of the list's answer text names its broker (a `broker:` line — the `sources`
   array does not), so group by that and read each broker's most relevant recent note (else its
   latest) with `get_library_document` (rating, target price, date — all brokers, never a sample); a
   list of exactly 100 or 200 entries is capped (rule 3a widening applies). **Numbers** taken from a
   broker (discount rate, segment volumes, prices, margins) come from that broker's latest note, and from
   one dated after the company's latest results (`market.last_results_date`) when it exists; read that
   note too if the most relevant one is older. When the latest note does not restate the number (an
   industry tracker, a sales update), use the latest note that does, and say so. An older number is kept only when no later note gives it —
   the script marks it pre-results and leaves pre-results discount rates out of the median when current
   ones exist. Every anchor, company-level and segment, carries `as_of` (the date of its newest source). Record any discount rate
   a note states (WACC or cost of equity) in `raw.json["broker_discount_rates"]`; then 2–3 *neutral* `search_public_library` `mode="synthesize"` questions ("when
   does the shortage end?", not "confirm the margin"). Add the own-history multiple for the
   terminal cross-check: `aggregate_entity` on `valuation_multiple`, type `NTM_Ev_Ebitda_Med_W`,
   last 3 years, AVG / MIN / MAX, into `raw.json["multiple_history"]`.
2. **Anchor each number to something real**: a historical reference point (the script prints the
   long-run average, peak and trough; pass `long_history` for a full cycle), a company target, or
   a specific research view. Put these in `raw.json["anchors"]` with a basis text.
3. **Where sources disagree, make that the scenarios** (Samsung: shortage ends 2028 vs 2031 vs
   oversupply 2029 → base / bull / bear), instead of consensus high/low alone.
4. **Leave it as formula when nothing supports a change**, and let the label say "formula, no
   evidence". Record in each evidence entry what it changed, including "no change".
5. **Segment drivers** (when the Drivers tab is on): for the segments that matter, look for volume and
   price evidence — company guidance (`guidances` KU, `company_drivers`: price realization, backlog,
   shipments), the broker note summaries already read (stated units, ASPs, segment growth; cite broker,
   title and date — a broker view, never consensus), segment history. Record them in
   `raw.json["segments"]["drivers"]` by segment and scenario (volume and price by year, with a basis);
   in consensus years the other segments' volume is recalibrated so the total still matches consensus.
   Anchor price for every year guidance or a note gives it (an unanchored price is 0). For a market × share
   line, the market growth comes from the notes read (cited) and share change from company or broker
   statements; map a calendar-year market forecast to the fiscal year that covers most of it, and say so. In a consensus year, leave at least one sizeable line unanchored so the total can match
   consensus; anchoring every line is a deliberate off-consensus view and shows as a variance. When brokers state
   views by product rather than by segment (DRAM / NAND / HBM bits and prices), say how you mapped them to
   segments. Where brokers disagree on a driver, that spread sets bull and bear.
   **Segment margins** (when profit history is in): anchor a line's `margin` by year where guidance or a
   note gives it (Power & Energy margin target, a segment's cycle-low margin) — `"2029+"` for that year
   onward, `"all"` for every scenario; anchor bull and bear only where a source gives a range, else leave
   them calibrated to consensus high / low. Segment margins are on the company's own segment basis (guidance
   is too): the corporate line carries the basis gap, so no basis adjustment. A segment anchor wins for its
   line; the company-level path after consensus steers only the unanchored lines, so a company-level bear
   margin and a segment bear margin can disagree — set them together, and the mix result is the case's
   margin. In consensus years the
   unanchored lines shift by a common amount so EBIT still matches consensus. After consensus an
   unanchored line moves in proportion to the company-level margin path (anchors and peak guard), so the
   company margin is the mix result; a held line keeps its margin flat.
6. **Near-term company check** (a cross-check, never an input): when the company gives explicit numeric
   guidance for revenue or operating profit — the current fiscal year, or the next quarter where that is all
   it guides (`guidances` KU, earnings-announcement events, results releases) — record it in
   `raw.json["company_check"]` with its record against its own guidance: guided range and actual for at least
   2 past periods, same metric and basis. The script applies half the company's typical beat or miss (capped
   at ±10%) and compares the result with consensus for the same period; a gap over 5% (revenue) or 10%
   (profit) is flagged. Guidance only in words ("below normal seasonality"), EPS-only guidance, no guidance,
   or a lumpy business (property sales, project milestones) → `{"none": true, "reason": ...}`. A backtest on
   16 companies found this view about as accurate as consensus overall and better where guidance is explicit
   and the record steady — so it flags a possibly stale consensus; it never replaces it.
Rerun prepare_inputs.py; evidence, anchors and return policy live in raw.json, so nothing is lost.

### 5. Checkpoint — stop and get confirmation
First build, recalculate and check the draft exactly as in step 7, so the checkpoint can show a
draft value. Then present, compactly, in chat:
- The Base case table (growth, EBIT margin, capex %) by forecast year, noting which years are
  consensus-anchored. With the Drivers tab: what the lines are (business segments, product / service,
  market × share, geography, KPI), the base volume and price growth for each line, the
  other / eliminations line, and each driver's basis (guidance / broker view / history / calibrated /
  formula, no evidence). With segment margins: each line's base margin path, the corporate line, and the
  mix-built company margin against the company-level path (the script flags a terminal gap over 2 points).
- The near-term company check, when run: guidance, the record applied, the check estimate and its range
  against consensus, and what a flagged gap may mean (consensus not yet updated, a conservative guide).
- WACC and terminal growth, each input tagged *live* or *default*, and beside them the discount
  rates the broker notes state with the value per share at their median rate (or "none stated").
- **Draft value per share** for base, bull and bear against the price (`check_model.py --all` prints all
  three from one workbook), and what the price implies
  (reverse DCF). A gap over ±40% is judgment call 4: name the input that drives it.
- **Finance arm**, when one is valued separately: book equity, ROE, justified P/B and value, each
  marked live, derived or default.
- The flags that matter, most value-relevant first, in plain language (see the guide's
  judgment-call list).
- For each key assumption, its basis (consensus / history / evidence / formula, no evidence) and
  the evidence for and against in one line with source. Show all three scenario values, not just base.
- One question: confirm, or tell me what to change.

Do not build before the user answers. If the user asked up front for no questions ("just build
it"), skip the pause but list the assumptions you used in the final summary.

### 6. Apply edits
Edit `model_inputs.json` directly. Useful keys:
- `assumptions.base|bull|bear.revenue_growth` / `.ebit_margin` — per-year lists
- `assumptions.capex_pct_rev`, `da_pct_rev`, `tax_rate`, `payout`, `buyback_pct_ni`,
  `net_debt_issuance`, `dso`, `dio`, `dpo` — per-year lists
- `assumptions.scenario` — 1 Base, 2 Bull, 3 Bear
- `assumptions.return_basis` — 1 = payout/buybacks as % of net income, 2 = as % of FCF
- `evidence` — list of findings shown on the Summary tab
- Confirmed changes that must survive a re-draft go in **raw.json**, not model_inputs.json:
  `anchors`, `evidence`, `returns`, and `assumption_overrides` (e.g. `{"tax_rate": 0.24}`).
- `wacc.rf|beta|erp|crp|kd_pretax|tax_rate|target_debt_weight` (+ `_source` strings)
- `dcf.terminal_growth|exit_multiple|tv_method` (1 perpetuity, 2 exit)|`mid_year`
- `include_lt_investments` (1/0)
- `raw.json["assumption_overrides"]` takes one value for every year, a per-year list, or `{"2027": x}` for
  single years (e.g. capex from guidance), and survives a re-draft
- `drivers.scen.base|bull|bear.<segment>.volume|price` and `drivers.margin.base|bull|bear.<segment>` —
  per-year lists (or edit the Drivers tab directly);
  driver anchors that must survive a re-draft go in `raw.json["segments"]["drivers"]`

To change the horizon, rerun prepare_inputs.py with `--years N` (this redrafts, so reapply edits).

### 7. Build, recalculate, verify
```bash
python <skill_dir>/scripts/build_model.py model_inputs.json <Company>_DCF.xlsx
python <skill_dir>/scripts/recalc.py <Company>_DCF.xlsx
python <skill_dir>/scripts/check_model.py <Company>_DCF.xlsx model_inputs.json
```
recalc must report `total_errors: 0` and check_model must not report FAIL. A clean recalc only
proves formulas evaluate; check_model proves the balance sheet balances, history ties to
Distilla, and the DCF arithmetic is right. Fix the cause of any failure and rebuild; don't ship a
workbook that fails either check. Warnings are fine to ship, but mention them.

If the host provides its own spreadsheet recalculation tool, it may replace the second line. `recalc.py` needs the Python `formulas` package; install it if it
is missing. If no recalculation is possible, deliver the workbook marked "not recalculated or
verified here; values compute when opened in Excel or Google Sheets", give no value per share in
chat, and say why.

### 8. Deliver
Save only the workbook where the host delivers files (working files such as raw.json and
printouts stay in the working folder) and share it with the user (attach, link or present it
through the host's file mechanism). Then a short summary in prose:
value per share (all three scenarios) against the current price and consensus target, **what the
price implies** (reverse DCF: perpetual growth or margin needed), the two or three inputs that
drive the answer and the evidence behind them, the value at the brokers' discount rate where notes
state one, the terminal-multiple cross-check, any warnings, and how to use the
workbook (blue cells are inputs; scenario switch at the top of Assumptions; sensitivity tab).
Present the value as the output of stated assumptions, not a recommendation. The assistant isn't
a financial advisor, and the user makes the call.

In the summary, web values (risk-free rate, beta, ERP, finance-arm balance sheet) carry `†` with
source and date and derived values `‡` (rule 2.7). End with the `Brokers:` line (rule 3a) — e.g.
`Brokers: list 90d — n docs, n brokers; read: [broker date; …]` or `Brokers: list 90d — 0 docs;
list 180d — 0 docs; no coverage found`, never "not run" or "skipped" — and then the Method notes
footer (≤4 lines: sources, basis checks, derived-cell formulas, material gaps).
**Concise requests:** a user preference for brevity shortens prose, never the required sections or
tables.

## Completeness gate — REQUIRED before delivering

Before delivering, state PASS or FAIL for each check below with cited evidence (tool call + filters, a script output line, or a workbook cell); fix every FAIL before proceeding. Do not include the PASS/FAIL list in the final answer.

1. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called; WACC inputs live or a labelled default; finance-arm inputs from Distilla or official filings, never assumed.
2. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†`, `‡` and `*`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.
3. **Model checks:** recalculation reported `total_errors: 0` and check_model.py did not report FAIL, on the delivered workbook; the checkpoint showed the draft value, unless the user asked to skip questions.

## The workbook

| Tab | Contents |
|---|---|
| Summary | Value per share, upside, EV, WACC, checks status, forecast snapshot, key-assumption basis table (formula-only items in red), evidence table (finding, stance, source, date, effect), model notes, flags |
| Drivers | When segment data allows: each segment's volume and price growth (Base / Bull / Bear, active scenario), units and revenue per unit where a unit series exists, segment revenue, other / eliminations, total revenue (feeds the Model tab) and its variance to consensus; with segment profit, each segment's margin (Base / Bull / Bear, active) and profit, the corporate / unallocated line and EBIT (feeds the Model tab), with the company-level margin path as a memo cross-check |
| Assumptions | Scenario switch; Base/Bull/Bear growth and margin; all drivers with history alongside; consensus memo |
| Model | Income Statement → Balance Sheet → Cash Flow → Schedules (working capital, PP&E, debt, leases, equity) stacked on one tab, same column = same year, each section a collapsible group. History links to Raw Data line by line; every subtotal is a real sum |
| DCF | Bridge and WACC inputs with sources, UFCF build with stub period, perpetuity-growth terminal value, equity bridge; terminal-multiple cross-check; reverse DCF (growth or margin the price implies); terminal reinvestment check |
| Sensitivity | WACC × terminal growth, and EBIT margin × terminal growth, live formulas |
| Checks | Balance check every year; history ties to Distilla (CFO/CFI/CFF/net change, BS, net income); cash ≥ 0; PP&E drift; cash build-up; opex ≥ 0; WACC > g; TV share |
| Raw Data | Distilla values exactly as delivered, with metric names |

Mechanics worth knowing when the user asks "why":
- Cash is the balancing item; interest uses beginning balances, so there is no circularity.
- History is itemised from Distilla; any gap to a Distilla subtotal sits on an explicit
  "Unreconciled vs Distilla" line (expected 0) rather than in a hidden plug. Roll-forward items the
  model does not forecast (SBC, OCI, FX, disposals) are shown on "Other (history only)" lines.
- Forecast gross margin = EBIT margin + opex %, so EBIT ties to the scenario and opex cannot go negative.
- D&A follows the asset base (consensus D&A, then a depreciation rate on PP&E), not revenue.
- IFRS 16 lessees: new leases are modelled as asset additions funded by lease debt and deducted in
  FCF; existing leases are subtracted in the bridge. US GAAP: lease cost is already in EBIT, so the
  lease liability is not subtracted.
- The equity bridge uses the latest quarterly balance sheet. Only cash flows *after* that date
  are counted (year-1 fraction), discounted from the valuation date with the mid-year convention.
- Market cap is computed as price × FX × diluted shares; Distilla's `market_cap` is a cross-check only.
- A finance arm is valued separately: industrial EBIT and cash flow in the DCF, the finance arm at
  book equity × justified P/B in the bridge (DCF tab, "Finance arm" block).
- The valuation uses perpetuity growth only. Today's market multiple is shown as a reference but
  never used as the terminal assumption: it prices today's growth, not a mature terminal year
  (Duolingo: 38.9x today would need 7% growth forever). An exit multiple is used only when the user
  supplies one with a basis (`raw.json["dcf"] = {"exit_multiple": x, "exit_multiple_basis": "...", "tv_method": 2}`).

## Follow-ups

For "what if WACC is 9%" or other single-input questions, the user can type into the blue cell
and the model recalculates. Offer that. If they want you to change it, edit model_inputs.json,
rebuild, recalc, check, and re-present the file. Report what changed in value per share.

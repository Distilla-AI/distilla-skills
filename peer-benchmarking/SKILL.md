---
name: "peer-benchmarking"
description: Produces a structured peer benchmarking analysis with tables comparing a target company against competitors across financial, valuation, and industry-specific dimensions, with pattern analysis and investment implications. Use when the user asks how a company compares to peers or competitors, requests a peer comparison or competitive benchmarking, wants to evaluate relative valuation or relative margins, or asks how a company "stacks up" on any set of metrics. Do NOT use for moat and rival strategy (competitive-position) or why a multiple re-rated (valuation-compression-recovery).
compatibility: "Target platform: Claude.ai. Requires the Distilla MCP connector, web_search / web_fetch, and Python code execution. Claude Code note: add context: fork to run in an isolated sub-agent."
metadata:
  required_sections: Benchmarking summary; Peer set; Relative positioning scorecard; Investment implications
---

Goal: produce decision-useful benchmarking tables across growth, profitability, leverage, returns, valuation, and sector KPIs, then explain why companies rank and trend the way they do.

## Data-source fallback

**Mode: Standard** — web figures allowed. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v26: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8 · 3a, 3b, 3c, 3e, 3h)

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
- **FCF** = CFO − capex from **one source and the same period**: `financial_data_point` `cash_flow_net_operating_cash_flow` − abs(`cash_flow_capital_expenditures`); vendor `cash_flow_free_cash_flow` is a cross-check only. KU fallback: CFO from `cash_flow_details`; capex from that cell if it has a capex line, else from `capital_expenditure` only when its description or comment shows **cash payments** for PP&E (not accrued or incurred capex), both from **one filing** (same `file_id`). A reported `Free cash flow` line counts only when its comment defines it as operating cash flow less capex. Else `--`. **Never use `financials_review` uFCF as FCF.**
- **Effective tax rate** = `income_statement_income_taxes` ÷ `income_statement_pretax_income`, same period (TSM FY2025: 16.0%). Pretax loss or an implausible rate → multi-year average or a stated assumption, flagged.
- **Net debt** = `balance_sheet_short_term_debt_and_curr_portion_long_term_debt` + `balance_sheet_long_term_debt` − `balance_sheet_cash_and_short_term_investments`. `long_term_debt` includes leases; `long_term_debt_excl_lease_obligations` excludes them — pick one and use it for every peer.
- **ROIC** = EBIT × (1 − tax) ÷ avg(equity + debt − cash), all from `financial_data_point`; else the `financials_review` ROIC row; else `--`. ROE never substitutes for ROIC.
- **Diluted shares** = `income_statement_diluted_shares_outstanding`, confirmed by NI ÷ EPS (the 2.1 #2 check); else `financials_review` NI ÷ EPS.
- **Market cap** = price × latest `income_statement_total_shares_outstanding`, on the price's share basis (2.1 #2). `stock_price.market_cap` history can be stale, flat or null (Micron null 12–27 Aug 2026) — latest value only.
- **EV** = market cap + net debt, **in one currency** (net debt converted at the price date's FX, rule 2.4). Use `stock_price.enterprise_value` only if within **10%** of the rebuild (TSM 18 Sep 2026: vendor EV 15.4T vs market cap $2.25T for a net-cash company — reject).
- **Margins from KUs or vs reported figures:** reconcile to the filing; flag gaps **>0.5pp with `*`** (rule 2.7 Markers).
- **Inventory days (DIO)** = avg(opening, closing `balance_sheet_inventories`) ÷ `income_statement_cost_of_goods_sold_cogs_incl_d_and_a` × days in the period, same source and period; inventory turns = 365 ÷ annual DIO. The vendor `ratio_analysis_operating_cycle_days_days_of_inventory_on_hand` uses this definition (FY2025: TSM 66.85, AMD 133.20, Samsung Electronics 93.03; Toyota FY3/2026 42.07 — all exact) → cross-check only. Banks and insurers → `--`.

#### 2.4 Prices, FX and valuation
- **Multiples, rung 1 — `valuation_multiple`** (weekly `LTM_` and `NTM_` types). Label each value by its horizon (LTM or NTM). **Spot-check the latest value** against a rebuild on the same basis; keep the series if within **10%**, else rebuild. NTM is a **time-weighted FY blend**, not a sum of quarters.
- **P/E types are on adjusted EPS where the Street has it:** `_Pe` values usually match `eps_ex_xord_mean`, not GAAP (AMD 18 Sep 2026: NTM 41.5× vs 41.3× on adjusted and 49.0× on GAAP; LTM 84.1× vs 143.5× on GAAP; AAPL 25 Sep 2026 tracked GAAP instead). Spot-check NTM P/E against the time-weighted `eps_ex_xord_mean`; if the company has none (rule 2.5), against `eps_gaap_mean` (Nike 18 Sep 2026: 19.9× vs 19.6×), and label the P/E by the category that passed. LTM P/E cannot be rebuilt from `financial_data_point` (no adjusted line) — use it as vendor-computed. A GAAP P/E is a separate rebuild, labeled GAAP, never mixed with `_Pe` values.
- **Own-history statistics:** average and range via `aggregate_entity` on `valuation_multiple` filtered by `type` and a `valuation_date` window (ISO strings sort correctly); median and percentile need the weekly series (`query_entity`, ≤300 rows per page; 3 years ≈ 156 weeks) computed in Python — the aggregate has no median. State the window and the number of weekly values (loss periods and gaps have none: AMD `LTM_Pe_Med_W` 737 of 1,125 weeks; TSM `NTM_Pe_Med_W` 140 of 157 over 3 years). A value repeated across a week with no sessions (an exchange holiday) is a carry-forward — count it once (Kweichow Moutai `NTM_Pe_Med_W` 13 and 20 Feb 2026, Spring Festival closure).
- **Multiples, rung 2 — rebuild:** trailing P/E = month-end price ÷ trailing EPS from `financial_data_point` (LTM from quarters, or FY), labeled **GAAP**. Forward P/E = price ÷ `consensus_data_point` EPS, labeled **"fiscal-year forward"** unless time-weighted to NTM, and by EPS category.
- **Price basis order:** same currency as financials → **dated FX series matched to each month-end** (FX row: Fed H.10 → ECB) → `--`. **Never one spot FX rate for a history.** A local listing Distilla does not hold (e.g. `2330.TW` for the TSM ADR) is `--`.
- ADR point-in-time conversion: company-stated FX → the FX row rate for that date → `--`.
- **Cross-peer period basis:** when fiscal year-end months differ, use `valuation_multiple` LTM/NTM types, or LTM built from `financial_data_point` quarters, for **every** peer in that ratio; FY values only when all peers share the year-end month (rule 2.1 #3). State the basis in the table caption ("LTM to Jun 2026, all rows").

#### 2.5 Consensus & revisions
- **Consensus, rung 1 — `consensus_data_point`** (join `T`, `C`; filter `T.company_id`, `C.name`). Anchor the estimated period on **`T.end_date`, never `consensus_date`** (a weekly vintage spanning every period), and filter **`T.duration`** (`year` or `quarter`): annual and Q4 rows share `end_date` and `fiscal_quarter = 4` (MSFT FY6/2027 `sales_mean`, 18 Sep 2026: `quarter` 106,384, `year` 390,596). Match consensus to actual periods on the end-date **month**: the two can differ by days (Nike FY5/2026: actual 2026-05-29, consensus 2026-05-31). Use `_mean` by default and report `_nest`; **NEST < 3 → flag "thin"** (TSM quarterly periods: 2–5 estimates).
- **Scale check:** no `unit` field — amounts are in millions (TSM FY2026 sales 5,371,031 = TWD m). Confirm scale against the latest actual before use.
- **Match EPS categories to actuals:** `EPS_GAAP` ↔ `income_statement_eps_diluted`. `EPS_EX_XORD` is the Street's adjusted EPS and has **no matching actual** in `financial_data_point` (AMD FY2025 pre-print: `eps_ex_xord_mean` 3.96 vs `eps_recurring` 2.51; `eps_gaap_mean` 2.52 vs diluted 2.65): compare it only with company-reported adjusted EPS or `standard_event` `Earnings beat or miss`. Never compare across categories. **Category coverage varies:** `eps_ex_xord_*` is absent for Nike and for TSM after Oct 2021 (AMD has both) — check which categories exist (`aggregate_entity` grouped by `C.name`) before choosing one.
- **Revisions** = one fixed fiscal period (`T.end_date`) and metric across two `consensus_date` vintages: % change and absolute level. Vintage dates differ by company and have gaps → take the latest vintage **on or before** each window date, not an exact date. No vintage at the window start → `--`, not `0.0%`. **History per period is short:** a completed year carries only its FY+0 vintages (~52 weeks from just after the prior year-end: AMD FY2025 7 Feb 2025 – 30 Jan 2026), and FY+1 / FY+2 series usually start in Jan–Feb 2026 (AMD, Nike, Fast Retailing 23 Jan; TSM FY2027 27 Feb) but can start mid-year (SK hynix FY2027 3 Jul 2026) — check the period's first vintage (`aggregate_entity` MIN(`consensus_date`) grouped by `T.id`) before choosing the window.
- **Vintage basis breaks:** scale or currency can change between vintages with no label change (TSM FY2026 `sales_mean` 164,302 on 1 May 2026 → 5,157,518 on 8 May, both `TWD`; ratio 31.4 ≈ USD/TWD; `eps_gaap_mean` 15.48 → 486.68 on the same date — a break hits every metric). Scan the vintages used for a > 5× step; never compute across a break — use vintages on the latest basis, else `--`. Dedupe same-date rows (TSM and AMD 14 Aug 2026 appear twice).
- **NTM consensus** = FY+0 and FY+1 time-weighted by months remaining (`‡`).
- **Consensus, rung 2 — `financials_review` snapshots** by `updated_at`: count a line only if **both** footnotes label it consensus **and both snapshots pass 2.1 #2**; else `--`.
- **Direction-only fallback:** count `standard_event` Sell-side Estimates Action events, classified up or down by `name` (directionless rows dropped) — a count, never a Δ%.
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

#### 3b Peer scope
- Peers **segment-matched**. `financial_data_point` and `financials_review` are company-wide → use `by_segment_financials` for conglomerates if available; otherwise **exclude or flag** (e.g., Samsung for foundry) and keep out of medians. Compare **growth rates / intensity**, not summed amounts. "Vs sector" only if the peer set matches the sub-industry (**temporary** until Distilla exposes sub-industry medians).

#### 3c ROIC as context
- Use 2.3 ROIC; cross-check against `ratio_analysis_profitability_return_on_invested_capital` or the `financials_review` ROIC row. The vendor ratio is **gross of cash** (TSM FY2025: 30.4% vendor; 27.5% gross-of-cash rebuild; 51.3% on rule 2.3) — state the definitional gap, never average the two.

#### 3e Valuation vs history
- Rule 2.4 multiples (latest value spot-checked) + 2.1 #2 check mandatory.

#### 3h Peer research (sampled)
- Peers, rivals and screen candidates the skill selects — never a company the user named (3a). **Scope:** peers and rivals — the main ones only, at most 4, named by the skill's step (its head-to-head or primary comparison set); other selected peers keep their financial, filing and event evidence, get no library call and carry no broker claim in the output; screen candidates — every candidate. Per company in scope, one `search_public_library` `synthesize` call (`doc_types = ["Research"]`, `tickers = [company]`, `date_range = "90d"`, the skill's question) — never one call for the whole set, which can sample a single company — plus one `standard_event` call for the set (`Sell-side Rating Action`, `Sell-side Target Price Action`; `company_id` IN the set; same window) — discovery only: a peer's rating or target is stated only from a note read at its source, never from an event row. A claim that decides a ranking, rating or verdict is read at its source (`get_library_document` on the `document_id` the answer cites). This evidence is sampled: never written as every broker or the Street view. The `Brokers:` line adds `peers: synthesize ×n of N, events ×1` (n researched, N selected).

**Reading `ku_cell`:** `query_entity` on `ku_cell` with `joins = [{relation: "ku"}, {relation: "cellTimePeriod"}]`, filtering `ku.name` IN the units named below and `group_company_id` = the company `id`. `content` is structured JSON (value, description, period, `sources` with `file_id` + pages) — parse it in Python and check each value's period, currency and unit; difference YTD values (rule 2.6) and take period end dates from the value, the filing or the Fiscal period end dates row. An empty unit is not evidence of absence.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Peer / rival set | Companies sharing a `product_category` with the target via `ku_cell` `groupProductCategory` (the `product` entity has no category field); `company.sector_id`; `ku_cell`: `competitions`, `competitive_outlook` | One `screen_drivers` call on the full scope with a criterion describing the business | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (competition section) → company IR investor presentation |
| Annual financials (revenue, GP, EBIT, EBITDA, NI, EPS, CFO, capex, cash, debt, ROE/ROIC) | `financial_data_point` (`T.provenance = "financials"`, `T.duration = "year"`; rule 2.2) | `executive_summary` `financials_review` actual columns; `ku_cell`: `cash_flow_details`, `balance_sheet_details`, `by_segment_financials`, `cash_and_debt`, `capital_expenditure` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → stockanalysis.com → MarketScreener. State when an aggregator was used. |
| Interim financials, segments, OCF | `financial_data_point` (`T.duration = "quarter"`); segments: `ku_cell` `by_segment_financials`, `geographical_segments`; `standard_event.earnings_summary` (`type = "Earnings announcement"`) | `ku_cell`: `cash_flow_details`, `capital_expenditure` (difference YTD values), `gross_margin_trends`, `operating_margin_trends`, `net_margin_trends`, `working_capital`; `executive_summary` `recent_performance`; `file` `Composite Filing` | Same as Annual financials |
| Consensus estimates, annual and quarterly | `consensus_data_point` (`_mean` with `_nest`; period by `T.end_date` and `T.duration`; rule 2.5) | `financials_review` forecast columns — consensus lines only, per the footnote; `search_public_library` (`doc_types = ["Research"]`, `tickers`, `date_range = "90d"`) — traced figures only | **None** |
| Consensus revisions | `consensus_data_point`: fixed `T.end_date` and `T.duration`, ≥ 2 `consensus_date` vintages in the window (rule 2.5) | ≥ 2 comparable `financials_review` snapshots (rule 2.5); direction only: count up vs. down `standard_event` `Sell-side Estimates Action` in the window | **None** |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| Valuation multiple vs own history | `valuation_multiple` (`LTM_` / `NTM_` types; latest value spot-checked, rule 2.4); EPS-based multiples only after 2.1 #2 | Rebuild per rule 2.4 | **None** |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), and `web_fetch` refuses a typed URL. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Broker research | `search_public_library` (`doc_types = ["Research"]`, `tickers`, `date_range`, `brokers`; `mode = "list"` for a catalog); `get_library_document` for summary + tags (Research never returns full text) | `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) — discovery only: brokers to list again, never a rating or TP | **None** — broker reports are not reliably on the open web; no broker after both 3a lists is `no coverage found`, not a gap. |
| Filings, transcripts, call content | `file` (`source_type` IN `Filing`, `Transcript`, `Composite Filing`; filter `company_id`, sort `published_at desc`); `ku_cell`: `transcript_summary`, `transcript_questions_and_answers`, `transcript_tone_changes`, `transcript_new_topics` | `screen_earnings` (`company_ids`, `periods`) for qualitative questions; `executive_summary.content` (HTML); `company_drivers.content` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR (press release, webcast transcript) |
| Cash, debt, leverage, maturities | Balances: `financial_data_point` debt and cash lines (net debt per rule 2.3; one lease convention for every peer). Maturities: `ku_cell` `cash_and_debt`, `debt_details`, `leverage_ratio` (sparse) | `ku_cell`: `debt_refinancing_risk`; `standard_event` (`Issuance of bonds or non-convertible debt`, `Credit rating change`, `Liquidity outlook change`) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (debt note) → company IR → stockanalysis.com |
| Sector-specific operating KPIs | `ku_cell` sector units where populated (e.g., `net_revenue_retention_nrr`, `number_of_customers`, `number_of_subscribers`, `order_intake`, `order_backlog`, `book_to_bill_ratio`, `sell_through_rate`, `capacity_and_utilization_overall`, `net_interest_margin_nim`) — find the right unit with `query_entity` on `knowledge_unit` (`name` `ilike`) | One `screen_earnings` call on the resolved `company_ids` naming the KPI; `file` `Transcript` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR KPI supplement / investor presentation |
| Effective / marginal tax rate | Derive per rule 2.3 from `financial_data_point` (`‡`); `financials_review` footnote tax rates are Distilla model, never inputs | `file` `Filing` (tax note) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → statutory rate from the national tax authority; else a stated assumption, same basis for every peer |
| Interest expense | `financial_data_point` `income_statement_gross_interest_expense` (period flow, before capitalization) for cost of debt and coverage; `income_statement_interest_expense` is **net of capitalized interest** (TSM FY2025: 19,986 = 12,370 + 7,616 capitalized). **Captive-finance companies** book financial-services interest in cost of sales, outside both lines (Toyota FY3/2026 gross 86,746m vs Q1 FY3/2027 financial-services interest 901,297m in `debt_details`) — state it; coverage and cost of debt on the income-statement line are flattered | `ku_cell` `debt_details` `Interest expense` (period check per rule 2.6); `file` `Filing` (interest-expense note) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (interest-expense note) → company IR; else a stated assumption |
| Fiscal period end dates | `time_period` (`provenance = "financials"`) `end_date` month, not the `fiscal_year` label (rule 2.2); `earnings_calendar.earnings_date`; `file.published_at`; `financials_review` headers for the year-end month only (rule 2.6) | `standard_event` (`Earnings announcement`) date | Official filing cover page |

**Field notes for this skill:**
- **EV (Guide 1a) in Distilla** = rule 2.3 base + minority interest (`balance_sheet_accumulated_minority_interest`) + preferred equity (filings; no Distilla line) − equity-method investments (`balance_sheet_long_term_investment_affiliate_companies`) (+ net pension deficit where material), same components for every peer. The rule 2.3 10% check applies to `stock_price.enterprise_value` against the 2.3 base.
- **Multiples:** `valuation_multiple` LTM and NTM types for every peer (one horizon per column); P/E on its adjusted-EPS basis unless the table is labeled GAAP (rule 2.4). Premium / discount vs own history uses the own-history statistics bullet (rule 2.4) with the window stated.
- **Leverage and returns:** interest coverage on gross interest expense (Interest expense row); ROIC per rule 2.3 with one debt / lease convention for every peer. Show ROIC as `ROIC‡` (rule 2.3, capital net of cash); the vendor ROIC (gross of cash, 3c) is a labeled cross-check beside it and never carries `‡`.
- **Labels:** "Guide 1a"–"Guide 3c" are this skill's Guide sections; bare 3a, 3b, 3c and 3e are the pasted sub-blocks above.

**Provenance:** markers, the `†` footnote, one web source per field and no NTM-vs-LTM comparison follow rule 2.7. In narrative, name the source and date once; if one web source per field is impossible, say so as a precision caveat.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Arithmetic runs in Python on the retrieved rows and renders as a plain markdown table — numbers only; ratings, tiers and judgments stay with you. After the Python gap check, run any Distilla query or rung that can fill a missing company × metric before finalizing; a blank cell caused by a fillable gap is not accepted.

## Step 1 — Establish the peer set

*Distilla:* peer candidates from the Peer row (shared `product_category`, `ku_cell` `competitions`; `screen_drivers` if still short), cross-checked with `search_public_library` Research; resolve all with one `query_entity` on `company`. Then run the pre-flight checks (Distilla data rules 2.1) for the target and every peer: KU coverage, then currency & share basis (rule 2.1 #2). Peers segment-matched per 3b.

If the user specifies peers, use them and state the final set before proceeding.

If not specified:

- Search analyst coverage and industry context to identify companies treated as direct comparables.
- Prefer peers that share end-market exposure, business model (product vs. services, B2B vs. B2C), and revenue scale (~0.3x–3x of target).
- Aim for 4–8 peers; fewer is acceptable for highly differentiated or concentrated sectors.
- State one-sentence rationale per peer; flag any imperfect comparable.

## Step 2 — Define the dimensions

*Distilla:* the 3a sweep for the target (`tickers = [target]`; `get_library_document` on every broker found, one note each — the note most relevant to the benchmarked dimensions) and, for the main peers, 3h — the closest peers, listed first in the Peer set line, at most 4 (one `synthesize` call each, one events call for them); other peers keep their financial and filing evidence and carry no broker claim; earnings materials via the Filings row.

If the user specifies dimensions, use them.

If not specified:

1. Retrieve up to 20 recent research reports spanning the target and its peers.
2. Review the latest earnings materials (transcript, press release, supplement) for the target and key peers. These are the primary source for sector-specific KPIs and management-defined metrics.
3. From this context, select the metrics analysts consistently model and that management explicitly tracks for this group.
4. Always include these standard categories:
   - **Growth**: revenue growth YoY, organic growth where disclosed, volume vs. price split if available.
   - **Profitability**: gross margin, EBIT margin, EBITDA margin, SG&A %, R&D % (if material).
   - **Leverage**: net debt / EBITDA, D/E ratio, interest coverage (EBIT / interest expense).
   - **Returns**: ROIC, ROE, ROA — define the calculation basis and apply it consistently.
5. For the three decisions below, refer to the Guide section below ("Selecting Relevant Metrics, Multiples, and KPIs") and apply its guidance:
   - **Which valuation multiples to include** (Guide section 1, Selecting valuation multiples): construct EV correctly, decide on earnings basis, then select multiples appropriate for this peer group's profitability profile, capital structure, and sector conventions.
   - **Which sector-specific KPIs to include** (Guide section 2, Identifying sector-specific KPIs): identify from disclosures and research reports; reconcile definitions before including; apply the minimum coverage rule.
   - **Which financial line items to highlight beyond the standard set** (Guide section 3, Identifying which financial line items to benchmark): scan management narratives and consensus revisions to identify what is investment-thesis-critical for this peer group right now.
6. Exclude any dimension where data is available for fewer than 3 companies (including the target); note the gap.

## Step 3 — Gather data and check completeness

*Distilla:* per the Annual / Interim financials, Cash-debt, KPI, Consensus and Valuation multiple rows. LTM flow metrics are summed in Python from the latest four `financial_data_point` quarters (`T.duration = "quarter"`, by `T.end_date`); balance-sheet metrics from the latest quarter; segment LTM from `ku_cell` (difference YTD values, rule 2.6). Period basis per rule 2.4.

Default time periods (use user-specified periods if provided):

- **Annual**: last 3 full fiscal years.
- **Quarterly**: last 8 reported quarters.
- **Forward**: consensus estimates for CY/FY+0 and CY/FY+1. If the latest reported period is Q4/full-year, prioritize FY+1.

**Peer-period alignment**: first check whether all peers share the same fiscal year-end month.

- **Same fiscal year-end month across all peers**: use each peer's most recently completed annual rows. No special handling needed.
- **Different fiscal year-end months**: do not use annual rows for cross-peer comparison — annual periods ending in different calendar months are not comparable on the same row. Instead, compute **LTM (Last Twelve Months)** for each peer in Python: sum the trailing 4 quarterly rows for flow metrics (revenue, EBIT, EBITDA, FCF, capex, etc.) and use the most recent quarter's snapshot for stock/balance-sheet metrics (net debt, invested capital, etc.). Each peer's LTM anchors to its own most recently reported quarter, so no fiscal-year alignment is required.

In either case, label each company's period explicitly in column headers — for annual rows use "Company A FY2025 (ends Mar)", for LTM rows use "Company A LTM (Q2 FY2026, ends Sep)" — so readers understand the trailing window used. If fewer than 4 quarterly rows are retrieved for a company's metric, mark the cell `--` (data pending, named in Method notes) and do not silently substitute an annual row or prior-year figure.

Pull the financials for all peers together where possible — income statement, balance sheet, cash flow, vendor ratios, valuation multiples and consensus. Name the **raw line items alongside any ratios** in `M.name` (e.g., sales, SG&A, capex, CFO next to operating margin and ROIC) so every peer carries the inputs for rule 2.3 derived values; a ratio-only pull leaves peers asymmetric. Sector-specific KPIs usually come from earnings filings and supplements.

After gathering, review the data matrix for gaps before proceeding:

- Flag any dimension / company combination where data is missing; mark it `--`, with the reason in the table's footnote or Method notes.
- For definition differences across companies, apply the reconciliation protocol in Guide 2c (Definition reconciliation protocol) below. Do not silently present non-comparable figures in the same column.
- If gaps are widespread for a dimension, drop it and note why rather than presenting a sparse table.
- Run the Python gap check (Missing tools line): a fillable company × metric gap is refetched before analysis, not accepted as blank.

## Step 4 — Analyze patterns and investigate drivers

For each dimension table, identify:

- **Level**: which companies rank highest/lowest and by how much.
- **Trend**: which are improving, deteriorating, or stable.
- **Divergence**: where the target's trajectory differs materially from peers.
- **Anomalies**: outliers — investigate whether they reflect structural differences, one-time items, or reporting differences.

For each pattern, propose a cause grounded in research, earnings commentary, or filings:

- Business model or mix differences (segment mix, revenue recognition, pricing structure).
- Operational execution (cost discipline, pricing power, volume leverage).
- Capital structure choices.
- Macro or sector tailwinds/headwinds affecting companies differently.
- M&A, restructurings, or non-recurring items — note and adjust where possible.

## Output format

**Concise requests:** a user preference for brevity shortens prose, never the required sections or tables.

- **`Brokers:` line (rule 3a):** in every run — one line per company the user named — directly above the Method notes footer and outside its 4 lines, e.g. `Brokers: list 90d — n docs, n brokers; read: [broker date; …]`, `Brokers: list 90d — 200 docs (cap 200, from {date}), n brokers; re-listed: [broker]; read: [broker date; …]`, `Brokers: list 90d — 2 docs, 1 broker; list 180d — 5 docs, 2 brokers; read: [broker date; …]` or `Brokers: list 90d — 0 docs; list 180d — 0 docs; no coverage found`. Thin coverage is coverage found, not a gap; never "not run", "skipped" or a sample of the brokers found. Peers the skill selected (3h) append `; peers: synthesize ×n of N, events ×1` (n main peers researched, N selected) — sampled, never counted as brokers read.
- The report closes with the **Method notes** footer (≤4 lines, rule 2.7; Quality bar).

Use this template:

---

**Benchmarking summary**

- [Takeaway 1]
- [Takeaway 2]
- [Takeaway 3 — up to 5 bullets]

**Peer set**: [Company (TICKER), …] — [1-sentence rationale for any non-obvious peer]

---

**Table: [Dimension category]**

Present each dimension as a table with one row per metric/period (e.g., Revenue growth YoY for FY2022, FY2023, …) and columns such as `Metric`, `Period`, `TARGET`, and one column per peer (`PEER A`, `PEER B`, `PEER C`, …).

- [Pattern bullet: who leads/lags and proposed reason]
- [Trend bullet: direction of travel over time]
- [Implication bullet: what this means for the target]

_(Repeat table + bullets for each dimension category)_

---

**Relative positioning scorecard**

Present this as a table with one row per dimension (Growth; Profitability; Leverage; Returns; Valuation; Sector & operational KPIs) and columns such as `Dimension`, `Target rank vs. peers`, `Trend`, and `Key insight`.

**Investment implications**

- [3–5 bullets on differentiation, relative headwinds, and metrics to monitor]

`Brokers: list 90d — n docs, n brokers; read: [broker date; …]; peers: synthesize ×n of N, events ×1`

**Method notes** — [≤4 lines]

---

## Quality bar

- Do not present patterns without a proposed cause rooted in evidence; prefer causality over description.
- Do not conflate accounting differences with operational differences — label them separately.
- Do not blend consensus and company guidance without clearly labeling each.
- Do not treat an imperfect comparable as a direct peer — acknowledge limitations explicitly.
- Apply EV construction and earnings basis consistently across all peers before computing any multiple (see Guide 1a–1b below).
- Do not silently present KPIs with divergent definitions in the same column — reconcile or label the difference (see Guide 2c below).
- In comparison tables and cross-peer comparison statements, use a SINGLE base currency, converted at the FX row rate dated to each period's end — NEVER mix currencies in the same row or column, NEVER produce per-currency duplicate tables for the same metric. Per-company descriptive prose may cite the company's native-currency figures. Splitting peer values into separate per-currency tables is not a substitute for conversion in a single comparison table.
- Before finalizing, verify that every comparison table anchors to the **most recently reported fiscal period** available for each peer. If one peer's latest period is incomplete in the retrieved data, mark the affected cells `--` (data pending) and surface the gap explicitly — do not substitute a prior fiscal year for all peers in order to achieve uniform period coverage across the group.
- If evidence is insufficient to explain a pattern, say so rather than speculating.
- Close with a **Method notes** footer (≤4 lines): sources used, basis checks, derived-cell formulas, material gaps.

---

## Completeness gate — REQUIRED before submitting the final answer

Before submitting, state PASS or FAIL for each check below with cited evidence (tool call + filters, a draft section, or a named entity); fix every FAIL before proceeding. Do not include the PASS/FAIL list in the final answer.

1. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called; EV built per the field note, 10% check on the 2.3 base.
2. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†`, `‡` and `*`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.

## Guide: Selecting Relevant Metrics, Multiples, and KPIs

Do not apply a fixed template. The right metrics are those most informative for this specific peer group at this point in time. Follow the three-part decision process below.

---

## 1. Selecting valuation multiples

### 1a. Construct enterprise value correctly before computing any multiple

Enterprise value (EV) = market cap + net debt + minority interest + preferred equity − equity method investments.

Check each component:

- **Net debt**: use financial debt only (bonds, loans, capital leases if material); exclude trade payables and deferred revenue. IFRS 16 operating lease liabilities should be included or excluded consistently across all peers — note which convention is used.
- **Minority interest**: use the book value from the balance sheet as a proxy unless market values are available.
- **Equity method investments**: subtract at book value unless market value (listed associates) is available and material.
- **Pension deficits**: add net pension liability (deficit net of assets) to EV for companies where this is material (typically industrials, utilities, UK/European companies).
- **Fiscal year-end misalignment**: if peers have different fiscal year ends, align EV numerators and earnings denominators to the same trailing 12-month window before comparing.
- **Currency**: every peer-comparison table and any cross-peer comparison statement in prose must use a SINGLE base currency (USD by default), converted at the FX row rate dated to each period's end (growth rates and ratios stay in reporting currency, 3b) — convert peer values to the base currency before placing them side-by-side. NEVER produce per-currency duplicate tables for the same metric, NEVER mix currencies within a single row or column, NEVER mix currencies inside one comparison sentence. Per-company descriptive prose (drivers, capital allocation, single-company supporting evidence) MAY cite figures in the company's reporting currency. State the base currency and FX dates in a footnote under each comparison table.

### 1b. Decide on the earnings basis

Choose a consistent basis across all peers before computing any ratio:

- **LTM vs. NTM**: use both where possible. LTM reflects what has been reported; NTM consensus captures forward expectations and is more forward-looking. For high-growth companies, NTM is more informative; for mature companies, LTM is more grounded.
- **Reported vs. adjusted**: prefer adjusted figures (removing non-recurring items) for comparability, but always disclose which adjustments are included. Common items to normalize: restructuring charges, impairments, M&A transaction costs, stock-based compensation (SBC — note that some sectors exclude SBC from adjusted earnings while others do not; apply a consistent treatment).
- **Cyclical / commodity sectors**: reported LTM earnings are often distorted by the commodity price cycle. For capital-intensive cyclicals (metals, energy, chemicals, shipping), consider mid-cycle or normalized earnings using a 5–7 year average EBITDA or replacement cost margin. Label these clearly as "normalized" and state the assumption.
- **Companies with significant D&A from acquisitions**: purchase price allocation (PPA) amortization can depress reported EBIT materially for acquisitive companies. Consider adding back PPA amortization to EBIT for comparability, and note when doing so.

### 1c. Multiple selection

**EV/EBITDA** — include by default for most sectors. Most capital-structure-neutral multiple available at scale. Prefer for capital-intensive businesses where D&A is a meaningful but imperfect proxy for maintenance capex. Caution: EBITDA overstates true cash generation when capex significantly exceeds D&A (growth-capex businesses); in those cases pair with EV/EBIT or EV/NOPAT.

**EV/EBIT** — prefer over EV/EBITDA for asset-light businesses (software, services, asset-light platforms) where D&A is minimal and EBIT ≈ operating cash flow. Also more appropriate when comparing across peers with very different capital intensity, where EBITDA margins would be artificially equalized by ignoring different D&A loads.

**EV/NOPAT or EV/EBITA** — use for acquisitive companies where goodwill amortization (under IFRS) or PPA amortization distorts EBIT. NOPAT = EBIT × (1 − effective tax rate), normalized for tax rate differences across jurisdictions.

**P/E (NTM)** — include when the majority of peers are consistently profitable. Exclude, or show `--` footnoted "negative earnings", for any peer with negative earnings; if more than two peers are loss-making, P/E is not a useful group-level multiple. Use diluted EPS; note any material difference between basic and diluted share counts (relevant for companies with large option/warrant overhang).

**P/FCF** — use levered FCF (operating cash flow minus capex) relative to market cap, not EV. Include when: (a) FCF conversion from earnings is a focus for the peer group, or (b) capex profiles differ materially across peers such that earnings-based multiples are less comparable. Particularly informative for mature, cash-generative sectors (infrastructure, utilities, consumer staples). Exclude periods where FCF is distorted by large working capital swings or lumpy capex; annualize or normalize where needed.

**Dividend yield** — include when the majority of peers have dividend yield > 2% and have a stated dividend policy. Signals a mature sector where income is part of the investment case. Supplement with payout ratio and dividend coverage (FCF / dividend) to assess sustainability.

**P/S or EV/Revenue** (Distilla has P/S types only; EV/Revenue is rebuilt per the EV field note, `‡`) — use when: (a) one or more peers are pre-profitability or have highly variable margins, making earnings multiples unstable; (b) revenue growth is the primary valuation driver (e.g., early-stage SaaS, clinical-stage biotech, hyper-growth platforms); or (c) as a cross-check in sectors where margins are converging and revenue multiple implies a margin-expansion thesis. Pair with a gross margin comparison to avoid conflating high-revenue/low-margin businesses with high-revenue/high-margin ones.

**P/B and P/TBV** — most informative when P/B ratios for the group cluster between 0.5x and 3x on reported book. Use P/TBV (tangible book value, excluding goodwill and intangibles) for: banks and insurers (where TBV is the core regulatory capital measure), and capital-heavy industrials where goodwill from acquisitions has distorted reported book. Above 3x P/TBV in capital-intensive sectors, the ratio increasingly reflects franchise value and intangibles rather than replacement value of hard assets — flag this. Below 0.5x P/B may indicate distress, structural impairment, or cyclical trough; investigate which before including.

**Sector-specific asset multiples** — consider for capital-intensive or asset-value-driven sectors:

- E&P / oil and gas: EV/2P reserves ($/BOE), EV/production ($/BOE/d)
- REITs: P/FFO, P/AFFO, implied cap rate vs. market cap rate
- Banks / insurers: P/TBV, P/E on normalized ROE
- Shipping / aviation: EV/fleet replacement value
- Mining: EV/resource or EV/reserve ($/tonne)
- Towers / infrastructure: EV/tower or EV/site

**Presentation**: report median and interquartile range (or min/max for small peer groups) rather than mean, which is distorted by outliers. For each multiple, also compute the target's premium or discount to peer median, both currently and historically (1-year and 3-year average), to assess whether the relative positioning has changed.

---

## 2. Identifying sector-specific KPIs

### 2a. Primary sources, in priority order

1. **Earnings press release and supplemental data sheet** — highest signal: management chose to highlight these metrics.
2. **Earnings call transcript** — prepared remarks and Q&A reveal which KPIs investors and analysts are actively probing.
3. **Investor presentation / analyst day materials** — often contain the clearest definitional footnotes and management's preferred KPI framework.
4. **10-K / 20-F annual report** — most legally precise definitions; use as the authoritative source for any KPI definition discrepancy.
5. **Sell-side research models and initiation reports** — reveals which KPIs analysts project and weight in their valuation; recurring KPIs across 3+ independent research reports carry high consensus signal.

### 2b. KPI shortlisting criteria

Include a KPI if it satisfies at least two of the following:

- Management explicitly tracks and guides on it (appears in press release or prepared remarks).
- Sell-side analysts model it or ask about it in Q&A.
- It is a leading indicator of revenue or margin (e.g., bookings, backlog, order intake precede revenue; utilization rates precede pricing power; NRR precedes revenue retention).
- It is a capital allocation signal (capex commitments, return of capital ratios, leverage targets).

Exclude a KPI if: it is disclosed by fewer than 3 companies in the peer group (flag the gap instead), or its definition is so bespoke to one company that cross-company comparison is not meaningful.

### 2c. Definition reconciliation protocol

The same KPI concept is frequently calculated on different bases across companies. Before including any KPI in a benchmarking table:

1. **Retrieve the explicit definition** from each company's filings or earnings materials — not from a data vendor, which may apply its own standardization.
2. **Map the differences**. Common sources of divergence:
   - _Organic / constant-currency growth_: some companies exclude M&A for the first 12 months post-close; others exclude permanently. FX translation methodology may differ. Check whether divestitures are excluded.
   - _Adjusted EBITDA_: exclusion sets vary — stock-based compensation, restructuring, earn-outs, legal settlements, integration costs, and "non-cash" items are all applied selectively. List what each company excludes.
   - _ARR / NRR_: definition of "active" contract, treatment of multi-year prepayments, and inclusion or exclusion of professional services all vary.
   - _Same-store / comparable-unit metrics_: minimum maturity period before inclusion (6, 12, 18 months) and treatment of remodeled or temporarily closed units differ.
   - _Return on invested capital (ROIC)_: treatment of goodwill (with vs. without), operating lease assets, and deferred tax in the capital base varies materially. Specify and apply one definition consistently.
3. **Decide on presentation**: if definitions can be reconciled to a common basis, do so and footnote the adjustment. If definitions cannot be reconciled and the difference is material, present each company's self-reported figure labeled with the company name's definition, and add a note describing the key differences. Do not silently present non-comparable figures in the same column.
4. **Do not include** a KPI where definition divergence is so significant that the comparison would be actively misleading; instead, describe the KPI, note the disclosure, and explain why it cannot be benchmarked.

### 2d. Segment vs. consolidated disclosure

Some peers may report a KPI only at the segment level while others report it consolidated, or different peers may have different segment structures that make the same KPI non-comparable. In these cases:

- Use the most granular level that is comparable across peers.
- If a meaningful subset of peers reports segment-level data, consider a segment-level benchmarking table alongside the consolidated one.
- Note clearly when a figure is segment-level vs. consolidated.

---

## 3. Identifying which financial line items to benchmark

The standard set (revenue, gross margin, EBIT/EBITDA margin, leverage, returns) should always be included. In addition, identify which financial lines deserve elevated attention given the current business context.

### 3a. How to identify what matters now

**Scan management narratives**: In the latest earnings press release, transcript, and any recent investor communications for each peer, note which financial line items appear in: (a) management's own performance bridges and variance explanations, (b) guidance disclosures, (c) analyst questions that management addressed at length. Line items that management chooses to guide on explicitly or that draw the most investor scrutiny are investment-thesis-critical.

**Scan consensus estimate revisions** (Consensus revisions row; rule 2.5): If consensus estimates for a particular line item (e.g., gross margin, capex) have seen outsized revision — positive or negative — in the past 1–2 quarters, that line is actively repriced by the market and belongs in the benchmarking analysis.

**Scan recent research report titles and thesis statements**: Analysts headline the metrics driving their recommendation. If multiple reports for the peer group are titled around margin recovery, capex overhang, or working capital normalization, those are the dimensions to prioritize.

### 3b. Business context heuristics

Apply these based on what the context scan reveals:

- **Heavy capex cycle** (capacity expansion, infrastructure buildout, generational technology investment): add capex as % revenue, absolute capex, and maintenance vs. growth capex split where disclosed. Compare capex trajectories to understand who is investing ahead of demand vs. who is deferring. Pair with return-on-incremental-invested-capital or ROIC trend to assess capital productivity.

- **Margin inflection** (cost reduction programs, post-pandemic normalization, pricing cycle turning): decompose the P&L more granularly — gross margin, SG&A %, R&D %, and contribution margin or segment margin where available. Aggregate EBIT margin can mask offsetting gross margin improvement and SG&A reinvestment; show the bridge.

- **Volume / price mix dynamics** (relevant for industrials, consumer, commodities, pricing power recovery): add volume growth, price/mix contribution, and organic vs. reported revenue decomposition. This surfaces which companies are growing through price (often unsustainable if demand is elastic) vs. volume (more durable) vs. mix (requires understanding segment shift).

- **Working capital and cash conversion** (supply chain normalization, inventory cycle, receivables management): add DSO, DIO, DPO, and cash conversion cycle (CCC). Add FCF conversion (FCF / net income or FCF / EBITDA) to identify companies where working capital is masking or inflating reported earnings quality.

- **Balance sheet and refinancing risk** (elevated leverage, rate-sensitive capital structures, near-term debt maturities): add net debt / EBITDA, EBIT interest coverage, fixed-charge coverage, and debt maturity schedule. Note the proportion of fixed vs. floating rate debt and any covenant headroom disclosures. For highly levered companies, consider levered FCF yield relative to debt service as a solvency signal.

- **FCF vs. earnings divergence** (high non-cash charges, aggressive accounting, or the reverse — strong cash generation despite reported losses): add FCF margin, FCF / EBITDA conversion, and a simple reconciliation of net income to operating cash flow. A persistent gap between earnings and cash generation is one of the most important quality signals in a peer comparison.

- **M&A and restructuring distortions**: for companies that have made significant acquisitions or are mid-restructuring, reported financials may not be comparable. Where material, compute organic revenue growth (stripping out acquired revenue), pro forma EBITDA (as if acquisitions were owned for the full period), and note any synergy claims embedded in forward estimates. Apply consistent treatment across the peer group.

### 3c. Revenue quality

When revenue comparability is in question, assess:

- **Recurring vs. non-recurring mix**: subscription, contracted, or annuity-type revenue is more valuable and more comparable than project or one-time revenue. Disclose the mix where available.
- **Backlog and revenue visibility**: for project-based or long-cycle businesses, add backlog as a revenue coverage ratio (backlog / LTM revenue) and backlog growth.
- **Revenue recognition methodology**: ASC 606 / IFRS 15 adoption timing and policy choices (point-in-time vs. over-time recognition) can create non-comparable revenue timing across peers. Flag where relevant.

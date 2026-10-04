---
name: "fundamental-guru"
description: Full single-company investment committee process — first-pass screen, sector-routed deep-dive modules (brand, channel, growth, cost, supply chain, technology, profit pool, capex cycle, cycle, utilization, ROE, moat), a two-round IC debate between Buffett-, Cathie Wood-, and Peter Lynch-style personas, a CIO Buy/Sell/Hold verdict with price ranges, and a five-question forward research plan. Uses Distilla MCP (ku_cell, company_drivers, standard_event, stock_price, financial_data_point, valuation_multiple, public library). Use this whenever the user asks for an investment committee review, IC memo, deep fundamental analysis, "run the full process" on a stock, a multi-perspective debate on a company, or a Buy/Sell/Hold verdict with a research plan, even if they just give a ticker and say "full workup". Do NOT use for a quick first look only (use initial-screen).
---

**Runtime requirements:** Requires Distilla MCP tools, web search / page fetching (`web_search` / `web_fetch` or equivalent host tools), and Python code execution. Map the tool names in these instructions to the host's equivalent capabilities while preserving source restrictions and required checks. If tool loading is deferred, use the host's discovery mechanism; MCP tool prefixes may vary. Run independent module steps sequentially by default; use parallel sub-agents only where supported, preserving the skill's dependencies and hand-offs.

# Fundamental Guru

**Platform:** Agent-agnostic. Parallel steps run in sequence by default; where the harness supports sub-agents, they may run as sub-agents.

One company → first-pass screen + valuation context → sector-routed deep dive → IC debate (2 rounds) → CIO verdict → research plan.

Read `references/distilla-reference.md` before the first Distilla call. Module call contracts are in `references/modules.md`; IC persona specs are in `references/ic-personas.md`.

## Input

| Input | Default |
|---|---|
| `Name_or_Ticker` | Required — ask if the user gave none |

If the user named several companies, run the full process for each separately.

Resolve the entity first: `query_entity` on `company` (or `ticker`) by symbol/name → `company_id`, `hq_country`, `sector_id` → `sector.name`. Confirm it's the right listing (same-name companies exist across exchanges; an ADR is held under `hq_country = US`).

**Rundown and review choice (before Step 1):** once the entity is resolved, print this rundown filled in, as reply text in its own block — the question never replaces it; the routing sector and modules are classified now, per Step 1's routing sentence:

```
Rundown — [company] ([ticker])
Step 1 — Initial screen and valuation context
Step 2 — Broker sweep (3a, once), then [routing sector] modules: [module list]
Step 3 — IC debate (Buffett, Wood, Lynch personas)
Step 4 — CIO verdict and price ranges
Step 5 — Five-question research plan
```

Then, in the same text reply below the block, ask one question — in plain text, never through the tappable-options tool, so the rundown and review question remain together in the same visible reply: stop for review after Step 1 (initial-screen), or run to the end. A request that already states the choice ("run the full process", "full investment committee process", "full workup", "IC memo end to end", "stop after the screen") is the answer: print the rundown and ask nothing. A bare "investment committee review", "IC review" or "IC memo on X" does not state it — ask. Then stop after Step 1 or continue, as answered; no other approval stop. On a review stop, show the assessment, valuation context and routing sector.

## Data-source fallback

**Mode: Standard** — web figures allowed. If the user asks for a Distilla-only run, switch to **Distilla only**: every claim traces to a Distilla document or entity (`financials_review` included), no web, and missing = `--` or drop the item; the web columns below are then ignored; the one exception is FX for currency conversion, from the FX row's web sources, dated, with source and date stated. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v26.1: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8 · 3a, 3b, 3c, 3e)

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
- `stock_price.sell_side_target_price` is back-filled → **latest value only**, never a history.

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
- **`ku_cell` parsing:** normalize value strings — units ("thousand NT$", "million RMB"), `bn` / `m` with no currency (take the currency from the filing), parentheses = negative, unit/currency mislabels (e.g., NT$ thousands tagged "USD") — and key names (`period` / `name` vs `time_period` / `description`). Prefer entries sourced from the financial statements over transcript-rounded figures in the same cell.
- **Duplicate periods across filings:** prefer the annual-report cell.
- **YTD cumulative KU values** need differencing to get quarters.
- **Time series:** splice sources only after an **overlap check**.
- **`debt_details` `Interest expense`** is labelled with a point date: confirm on the cited source page whether it is a quarter or year-to-date flow before annualizing.
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`earnings_calendar`:** filter and sort on `earnings_date` (there is no `date` field); rows from different `source`s (YFINANCE, FMP) can disagree for one company (AVGO: 9 vs 10 Dec 2026) — show both dates, each with its source, never pick one.
- **`price_explanation.price_move_percentage` is a decimal fraction**, identical to `stock_price.change` for the same date, despite the MCP doc's "% move". Filter a 5% move with |value| ≥ 0.05.
- **Insider events:** `Purchase or sale of shares by insiders` holds buys, sells, planned sales (Form 144) and trailing-12-month summaries under one type; direction is only in `name`. Classify each deduped row by reading `name`; drop summary and re-dated rows (HK, 26 Aug – 25 Sep 2026: 152 rows → 22 companies, 55 company-dates; both HSBC rows are 12-month summaries).
- **`stock_price.market_cap` and `enterprise_value` are USD for non-US listings** while `stock_price.currency` is the local price currency (18 Sep 2026 rebuilds at ECB rates: Toyota US$226.8bn vs 228.3bn, Fast Retailing 131.5bn vs 132.3bn, Tencent 481.2bn vs 481.2bn; HSBC 24 Sep US$343.4bn vs 342.3bn). Convert the rule 2.3 rebuild to USD before the 10% check; never divide a vendor cap by a local price.
- **`financials_review` limits:** prose sections below the table are qualitative only, never a numeric source (they can contradict the table — AMD prose capex ~5% of revenue vs table 2.8% — and carry untraced broker figures); forecast columns can hold actuals (Tencent FY2026 cash and debt are H1 2026 reported balances), so read the footnote before treating a cell as a forecast; footnote model assumptions (tax, interest, NWC and capex ratios) are Distilla model, never a sourced input; header dates are approximate — use the fiscal year-end **month** only and take exact period end dates from filings (Toyota FY ended 31 Mar 2024 shows `FYE 2024-03-28`).
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

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

**Reading `ku_cell`:** run the KU coverage check (rule 2.1 #1) on the module's KU list first, then `query_entity` on `ku_cell` joined to `ku` (and `cellTimePeriod`), filtering `ku.name` IN the units and `group_company_id` = the company `id`. `content` is structured JSON (values, periods, `sources` with `file_id` + pages) — parse it in Python and check each value's period, currency and unit. An empty unit is not evidence of absence.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Annual financials (revenue, GP, EBIT, EBITDA, NI, EPS, CFO, capex, cash, debt, ROE/ROIC) | `financial_data_point` (`T.provenance = "financials"`, `T.duration = "year"`; rule 2.2) | `executive_summary` `financials_review` actual columns; `ku_cell`: `cash_flow_details`, `balance_sheet_details`, `by_segment_financials`, `cash_and_debt`, `capital_expenditure` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → stockanalysis.com → MarketScreener. State when an aggregator was used. |
| Interim financials, segments, OCF | `financial_data_point` (`T.duration = "quarter"`); segments: `ku_cell` `by_segment_financials`, `geographical_segments`; `standard_event.earnings_summary` (`type = "Earnings announcement"`) | `ku_cell`: `cash_flow_details`, `capital_expenditure` (difference YTD values), `gross_margin_trends`, `operating_margin_trends`, `net_margin_trends`, `working_capital`; `executive_summary` `recent_performance`; `file` `Composite Filing` | Same as Annual financials |
| Consensus estimates, annual and quarterly | `consensus_data_point` (`_mean` with `_nest`; period by `T.end_date` and `T.duration`; rule 2.5) | `financials_review` forecast columns — consensus lines only, per the footnote; `search_public_library` (`doc_types = ["Research"]`, `tickers`, `date_range = "90d"`) — traced figures only | **None** |
| Consensus revisions | `consensus_data_point`: fixed `T.end_date` and `T.duration`, ≥ 2 `consensus_date` vintages in the window (rule 2.5) | ≥ 2 comparable `financials_review` snapshots (rule 2.5); direction only: count up vs. down `standard_event` `Sell-side Estimates Action` in the window | **None** |
| Ratings, target price | Broker notes: `get_library_document` `summary` (rating, TP, change old → new, date) of a note found by `search_public_library` `list`; consensus TP = **latest** `stock_price.sell_side_target_price` only | None — drop the item. `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) is discovery only: it names brokers and dates to list again with `brokers=[…]` (at most five per call), never a rating, TP or TP trajectory; an event no note matches is left out, and a note it conflicts with wins | **None** |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| Valuation multiple vs own history | `valuation_multiple` (`LTM_` / `NTM_` types; latest value spot-checked, rule 2.4); EPS-based multiples only after 2.1 #2 | Rebuild per rule 2.4 | **None** |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), If the host requires a search-discovered URL before fetching, obtain it through search first. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Large price moves | `price_explanation` (`date`, `price_move_percentage` — decimal, rule 2.6, `explanation`) | `standard_event` and `file` `News Article` on the same dates | Company press releases → major newswires; `web_fetch` before citing |
| Peer / rival set | Companies sharing a `product_category` with the target via `ku_cell` `groupProductCategory` (the `product` entity has no category field); `company.sector_id`; `ku_cell`: `competitions`, `competitive_outlook` | One `screen_drivers` call on the full scope with a criterion describing the business | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (competition section) → company IR investor presentation |
| Effective / marginal tax rate | Derive per rule 2.3 from `financial_data_point` (`‡`); `financials_review` footnote tax rates are Distilla model, never inputs | `file` `Filing` (tax note) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → statutory rate from the national tax authority; else a stated assumption, same basis for every peer |
| Interest expense | `financial_data_point` `income_statement_gross_interest_expense` (period flow, before capitalization) for cost of debt and coverage; `income_statement_interest_expense` is **net of capitalized interest** (TSM FY2025: 19,986 = 12,370 + 7,616 capitalized). **Captive-finance companies** book financial-services interest in cost of sales, outside both lines (Toyota FY3/2026 gross 86,746m vs Q1 FY3/2027 financial-services interest 901,297m in `debt_details`) — state it; coverage and cost of debt on the income-statement line are flattered | `ku_cell` `debt_details` `Interest expense` (period check per rule 2.6); `file` `Filing` (interest-expense note) | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) (interest-expense note) → company IR; else a stated assumption |
| Fiscal period end dates | `time_period` (`provenance = "financials"`) `end_date` month, not the `fiscal_year` label (rule 2.2); `earnings_calendar.earnings_date`; `file.published_at`; `financials_review` headers for the year-end month only (rule 2.6) | `standard_event` (`Earnings announcement`) date | Official filing cover page |
| Entity and sector | `company` (or `ticker`) → `sector.name` (Distilla taxonomy) | None — never the `gics_classification` KU or a GICS mapping | **None** — resolve inside Distilla |
| Module fields (brand, channel, cost, etc.) | The installed module skill's own field table; otherwise the KUs listed per module in `references/modules.md` | `company_drivers`; `executive_summary`; one `screen_earnings` call with this `company_id` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR → one named industry source |
| Governance and insider ownership | `ku_cell`: `major_shareholders`, `board_directors`, `management_info`, `related_party_transactions` | `standard_event` `Purchase or sale of shares by insiders` (classified by `name`, rule 2.6) | Proxy / AGM circular (EDGAR DEF 14A, EDINET, HKEXnews) → company IR → **None** |
| Broker research | `search_public_library` (`doc_types = ["Research"]`, `tickers`, `date_range = "90d"`, `mode = "list"` first; 3a); `get_library_document` for summary + tags | `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) — discovery only: brokers to list again, never a rating or TP | **None** — broker reports are not reliably on the open web; no broker after both 3a lists is `no coverage found`, not a gap |
| Catalyst dates | `earnings_calendar`; upcoming `standard_event` items | `standard_event` `Announcement of the next earnings release` | Company IR events calendar → one named aggregator |

**Field notes for this skill:**
- **Valuation context inputs** (the block itself is printed at the end of Step 1): initial-screen's Valuation vs Peers & History result, or — when initial-screen did not run — the same inputs built here per rule 2.4 and 3e. Metric by branch: `NTM_Pe_Med_W` or `NTM_Ev_Ebitda_Med_W` (mature), `NTM_price_sales_per_share_Med_W` (early growth), `LTM_price_book_value_per_share_Med_W` (banks, insurers). Never compare it with a multiple on another horizon (e.g., consumer-brand-equity's LTM reconciliation).
- **Denominator by type** (the Valuation context and the Step 4 price table use the same one): `NTM_Pe_Med_W` → time-weighted NTM EPS on the category the spot-check passed (EPS only after 2.1 #2 passes), price = multiple × EPS; `NTM_Ev_Ebitda_Med_W` → time-weighted NTM `ebitda_mean`, price = (multiple × EBITDA − net debt, rule 2.3) ÷ diluted shares; `NTM_price_sales_per_share_Med_W` → time-weighted NTM `sales_mean` ÷ diluted shares, price = multiple × sales per share; `LTM_price_book_value_per_share_Med_W` → latest book value per share, price = multiple × BVPS. One currency and share basis (rule 2.1 #2); a denominator reported in another currency than the price (an ADR with TWD EPS) is converted at the FX row rate for that date per rule 2.4 ADR conversion, the rate and its date stated once — an older rate is named with its date, never silently applied. Never multiply an EV/EBITDA, P/S or P/B multiple by EPS.
- **Revision metric by type** (the Step 1 revision row and the Step 4 dispersion line use the same one): `NTM_Pe_Med_W` → the EPS category the spot-check passed; `NTM_Ev_Ebitda_Med_W` → `ebitda`; `NTM_price_sales_per_share_Med_W` → `sales`; `LTM_price_book_value_per_share_Med_W` → `eps_gaap` (no consensus book value exists; the 2.2 banks bullet keeps EPS meaningful), labeled as the earnings proxy.

**Provenance:** markers, the `†` footnote, one web source per field and no NTM-vs-LTM comparison follow rule 2.7. In narrative, name the source and date once.

**Missing tools:** this skill and its callees name no legacy tools; never stall on a missing one. Arithmetic runs in Python on the retrieved rows and renders as a plain markdown table — numbers only (ratios, CAGRs, medians); ratings, verdicts and judgments stay with you. A module skill not installed → its fallback spec in `references/modules.md`.

## Required research plan

### Step 1 — Initial assessment and valuation context

Use the **`initial-screen`** skill for a first-pass screen of the company. It returns the five criteria (Red Flags & Integrity, Management Quality & Alignment, Competitive & Operating Trajectory, Financial Health & Solvency, Valuation vs History & Peers), its sector branch (Early Growth/Tech, Mature/profitable, Banks, Insurance, REITs, Regulated Utilities), the `Initial Assessment Verdict` (**Strong Candidate / Monitor / Decline**), the `Valuation Stance` (**Attractive / Fair / Stretched**) and the Further Diligence list — carry all of them forward. If it isn't available, cover business model, competitive advantages, financial health and valuation from the rows above (financials from `financial_data_point`, rule 2.2; `executive_summary` `business_review` / `mgmt_analysis` for narrative; `company_drivers`; `stock_price`).

Carry these initial-screen lines as it prints them: the scorecard; ROIC as `ROIC‡` (rule 2.3, capital net of cash) with the vendor `ratio_analysis_profitability_return_on_invested_capital` beside it as a labeled cross-check that never carries `‡`; `Governance Flag:`; `Valuation Stance:`; the verdict line; Further Diligence (3–5 items in the callee's format). When the Valuation criterion invokes initial-screen's escape hatch, its cell names the target's figure **and** the peer median on the same metric and basis (e.g. "latest-quarter revenue YoY +50.1%‡ vs peer median +61.0%‡ — not met"); the target's own growth alone never meets it.

**Gaps show their call.** Every `--` in Steps 1–4 names, beside it, the call that came back empty (entity or KU, filter, period) — e.g. "insider ownership `--` (`major_shareholders` KU: no non-empty cell, periods 170001–170002)"; a `--` set by a field-table "None" cites the row. A `--` with no named call is a gap not yet worked: run the ladder first. "Not pulled", "not read" or "not queried this run" is never a gap — run the call, then write the `--` with its result.

Close Step 1 with the **Valuation context** block, computed in Python and printed as this table (one row each, none dropped):

| Valuation context | Value |
|---|---|
| Type and horizon | e.g. `NTM_Pe_Med_W`, NTM P/E on the EPS category the spot-check passed (adjusted, or GAAP where no adjusted category exists — TSM) |
| Latest vendor value | value, `valuation_date` |
| Spot-check | rebuild value‡ on the type's denominator (EPS category named for P/E), NEST of each FY used, gap % vs vendor (pass ≤ 10%) |
| At anchor close | latest `stock_price.close` (date, currency) ÷ the type's per-share denominator‡ (EV/EBITDA: current EV ÷ NTM EBITDA‡) = implied multiple‡ — the multiple the CIO ranges use |
| Own history | median / low / high, percentile of the at-anchor multiple‡; 3-year window (or full available history if shorter, stated) and number of weekly values |
| Peer median | median‡ of the peers' same type at the latest common `valuation_date` (names and n; excluded peers named with the reason); target premium % ‡ |
| 3-month revision | FY+1 `_mean` Δ%‡ and level on the revision metric (field notes, Revision metric by type), per rule 2.5: window end = the latest vintage, window start = the latest vintage on or before three months before it (both dates and NEST stated); window start before the period's first vintage, or a basis break inside it → `--` with its call |
| Valuation Stance | initial-screen's line, verbatim; when initial-screen did not run, the Stance built here per rule 2.4 and 3e, labeled |

A peer premium is a number from this table, never "≈ +100%+" in prose.

**Also classify the company into exactly one of the 14 routing sectors** in the Step 2 table (the guru's own routing labels, not GICS). Pick the single best fit from its primary revenue source; cite the Distilla `sector.name` as supporting evidence (e.g. Construction & Engineering → Industrials; Software → Tech Software; Semiconductors & Equipment → Tech Hardware); healthcare devices and services take `Healthcare`. A company that fits two rows takes the better fit, stated in the rundown — never asked.

**Output:** direct, high-level answers backed by concrete facts and figures — enough for a professional investor to decide whether the company warrants further work — plus the initial-screen verdict, the valuation context and the routing sector.

#### Checkpoint

**Checkpoint (resume marker, never a stop):** a working line after Step 1, not in the output — `Checkpoint: Step 1 done; verdict [..]; Valuation Stance [..]; routing [sector → modules]; resume at Step 2`. When a turn ends before the deliverable, the next turn resumes at the first unfinished step, reuses Step 1's results (the `Valuation Stance` hand-off) and any Step 2 broker notes already read, and never re-runs completed steps; the deliverable still prints Step 1 in full (scorecard, `ROIC‡` with its vendor cross-check, `Governance Flag:`, `Valuation Stance:`, verdict line, Further Diligence) — never a condensed "carried from the prior turn" table.

### Step 2 — Modular research (sector-routed)

**Broker sweep first (3a, once per run):** open Step 2 with the target's 3a sweep — never in Step 1, which does not use it. Every module that carries 3a (growth, capex_cycle, cycle, utilization, moat) reuses it — passed as context with the notes read, its `Brokers:` line pointing to the deliverable's line — and never lists or reads the target's research again (its 3h peer calls still run); Step 3's evidence and Step 4's Street check read the same notes.

Run the modules for the routing sector:

| Routing sector | Modules |
|---|---|
| Consumer Staples | brand, channel |
| Consumer Discretionary | brand, channel, growth |
| Tech Hardware | cost, supply_chain, technology |
| Tech Software | technology, growth, profit_pool |
| Industrials | cost, supply_chain, capex_cycle |
| Healthcare | technology, growth, supply_chain |
| Energy | capex_cycle, cycle, utilization |
| Materials | cost, cycle, utilization |
| Utilities | capex_cycle, roe, growth |
| Real Estate | capex_cycle, growth, cycle |
| Telecom | capex_cycle, moat, growth |
| Banks | roe, cycle, moat |
| Insurance | roe, cycle, growth |
| Other Financials | roe, growth, moat |

For each module, call its named skill with the inputs in `references/modules.md` (company, the sub-sector from that skill's own list, its default horizon), so no module stops to ask; pass the Step 1 findings and the valuation context as context. Modules are independent (Platform line).

**An installed module runs its own workflow** — its research-plan steps and field table, on its own pulls. Never replace it with its fallback spec or with one shared pull summarized in a paragraph; the fallback spec is only for a module skill that is not installed, and that section is headed `[module] — fallback spec (skill not installed)`.

**Output:** one section per module under the callee's name, then a short summary that opens Step 2. Each module section carries, in the callee's own labels, whichever of these the callee produces: (a) its verdict paragraph and closing verdict line; (b) its scorecard table — every dimension row, `Rating` from the callee's tier list, evidence with period, `Trend`; (c) its `Investor Action:` block, every line, the first line one of `Worth deep research / Monitor / Pass`. A callee without a scorecard or an Investor Action block (profit-pool-analysis has neither) carries what it has — never build the missing one. Its other sections follow under the callee's section names — every one the callee lists for a single-company run, each with at least one evidence line (figure, period, source) or a `--` naming its empty call; a brevity preference shortens them to one line each, never drops a heading and never touches (a)–(c). The summary lists each module's closing verdict line, and its `Investor Action: [tier]` line where the callee has one, verbatim (`references/modules.md`) — copied character for character, never reworded, split at the dash into sentences or extended; profit_pool carries its `Supply Chain Verdict` paragraph and Profit Pool Migration conclusion, never a one-line paraphrase; a callee with several closing lines (cycle-positioning, capacity-utilization) carries all of them, verbatim — never a free-text action such as "Investor Action: Monitor whether …" and never an invented tier.

### Step 3 — IC discussion (2 rounds)

Three personas speak **sequentially in this order each round: W. Buffy → C. Woody → P. Lynchy**. Run **2 rounds**.

Each persona sees: the Step 1 assessment (with the valuation context), the Step 2 deep dive, and the full transcript so far. Each responds **only in its own role** — never write for another participant.

Read `references/ic-personas.md` for each persona's lens, per-round task, and formatting rules. Write each turn under a heading (`### Round 1 — W. Buffy`, etc.). Valuation arguments cite the valuation context, not recalled multiples.

**No new figures in the debate, Key Theses and Risks, or Step 5.** Personas, the CIO's theses and risks, and the research plan use only figures already shown in Steps 1–2, with the source given there. Step 4's catalyst dates, price table and dispersion line, and its Street check from the Step 2 broker notes, are sourced where they appear and are exempt. A fact a persona needs that Steps 1–2 lack (a TAM, a warrant share count, a one-day price move) is pulled first and listed under **Debate evidence** at the top of Step 3 — figure, source, date, one line each — before any turn cites it. A number a persona derives (a PEG, a dilution %) is computed in Python and marked `‡`.

### Step 4 — CIO verdict

Act as a hedge fund CIO. Using the Step 2 deep dive and the Step 3 debate, deliver a final verdict. **Lean decisive:** a Buy is fine with some minor downside risk, and vice versa — no stock is 100% clean.

**Output — a structured report:**
1. **Final Recommendation:** Buy / Sell / Hold. If Hold, specify **Positive Watchlist** or **Negative Watchlist**.
2. **Key Theses and Risks.** End with one **Street check** line: the two or three forward claims the thesis rests on, each written as claim — brokers with dates — agree / disagree, taken from the Step 2 broker notes of every broker the list found — never a subset.
3. **Catalysts and Monitoring Metrics:** what needs to happen to move the rating (e.g. Hold → Buy), printed as this table:

   | Date | Catalyst | Metric to watch | Rating trigger |
   |---|---|---|---|

   Dates from `earnings_calendar` (both dates shown when sources disagree, rule 2.6) and upcoming `standard_event` items ("no earlier than", rule 2.6 Events); no dated catalyst retrieved → one row, Date `--`, naming the empty calls. A Rating trigger uses only figures already shown in Steps 1–3 or Debate evidence; a metric with no evidenced threshold keeps a directional trigger (e.g. "acceleration vs the latest quarter's +50.1%‡"), never an invented level.
4. **Upside/Downside Price Ranges:** computed in Python and printed as this table, anchored on the latest `stock_price.close` (date, currency):

   | Case | Multiple (own history) | × Denominator‡ | = Price‡ | vs close‡ |
   |---|---|---|---|---|
   | Bear | low | … | … | …% |
   | Base | median | … | … | …% |
   | Bull | high | … | … | …% |

   The Denominator column is the Valuation-context type's own denominator (field notes, Denominator by type) — NTM EPS only for a P/E type; an EV/EBITDA row bridges through net debt and diluted shares. Footnote the denominator blend (FY weights, EPS category where P/E, NEST). The at-anchor multiple (Valuation context) sits beside the table. Each case is named by its multiple only — the denominator is the same in all three rows, so never "no EPS follow-through" or other denominator language; never merge rows into one band ("base/current $456–$740"). Consensus TP: one value with its date (e.g. "consensus TP USD 618.51, 25 Sep 2026"), labeled consensus; an earlier value is never shown.

   Under the table, two lines: **Denominator dispersion** — FY+1 `_low` / `_mean` / `_high` (NEST) on the revision metric (field notes), same period and category as the blend — context only: never a fourth row, a second grid, or a price computed on `_low` or `_high`. **R/R‡** = Bull vs close % ÷ |Bear vs close %|, computed in Python only when Bear vs close < 0 < Bull vs close; any other sign pattern → `R/R --`, the pattern stated (e.g. every case below the close).

### Step 5 — Research plan

Review everything — Step 1, Step 2, the debate, and the verdict — and target the friction points, unresolved arguments, and monitoring thresholds the IC raised.

**Output:** a numbered list of the **5 most critical questions or hypotheses** for the company's mid-to-long-term value, paying special attention to testing assumptions the personas debated. Every question left unanswered in the last Round 2 turn is one of the five, or is folded into one and named ("P. Lynchy's question to W. Buffy"). For each:
1. State the question or hypothesis clearly.
2. Explain why it's vital to validating the thesis or tracking downside triggers, citing the debate.
3. Suggest the specific channel checks, data logs, expert interviews, or primary evidence needed. Name only Distilla KUs and event types that appear in this skill or `references/modules.md`, or that a `query_entity` on `knowledge_unit` by `name` returned in this run; describe anything else in words (e.g. "a backlog disclosure", never an unverified `bookings` KU).

## Completeness gate

Before delivering, check each item and state PASS with the tool call that satisfied it; fix any failure before submitting. Don't show the checklist.

1. **Entity confirmed:** `company_id`, listing, and routing sector stated; the rundown printed before Step 1 and the review choice honored (asked, or skipped because the request stated it).
2. **Initial screen carried:** initial-screen's five criteria, verdict (Strong Candidate / Monitor / Decline), `Governance Flag`, `Valuation Stance`, `ROIC‡` with an unmarked vendor cross-check, and Further Diligence carried forward (or the fallback assessment built from the rows).
3. **Valuation context built:** the eight-row table present — type and horizon, vendor value and date, spot-check with rebuild, gap % and NEST, at-anchor multiple, own-history median / low / high / percentile with window and count, numeric peer median and premium, 3-month revision (or `--` with its call), Stance; handed to every module and the CIO.
4. **Correct modules run** for the routing sector, each through its own workflow with its contract inputs (fallback spec only when not installed, so headed); each section carries the callee's verdict paragraph and line, scorecard and Investor Action block where the callee produces them (none built for a callee without one), and every other callee section heading with an evidence line or a named-call `--`; the summary carries each verdict line, and each `Investor Action: [tier]` line that exists, verbatim.
5. **IC format held:** two rounds in order W. Buffy → C. Woody → P. Lynchy; no persona speaks for another; C. Woody's and P. Lynchy's Round 1 turns react to earlier turns and P. Lynchy's ends with a named question each to W. Buffy and C. Woody; every question put to a persona in an earlier turn has an `Answering` bullet in its next turn; round-2 turns use the tagged bullets with no repeated thesis; no figure in the debate, theses and risks, or Step 5 absent from Steps 1–2 or Debate evidence.
6. **Verdict complete:** recommendation (with Positive/Negative Watchlist if Hold), theses and risks with the Street check line, the `Brokers:` line above Method notes from one full 3a sweep at the start of Step 2, reused by every 3a module, catalysts and monitoring metrics in the dated catalyst table (triggers only from shown figures), and the three-row price table anchored on a dated `close` with vs-close %, the Denominator dispersion line and the R/R line, on the Valuation-context type's own denominator (never EPS under an EV/EBITDA, P/S or P/B multiple) — derived cells `‡`; the IC Summary opens the deliverable with no figure absent from Steps 1–4.
7. **Research plan:** exactly 5 items, each with the question, why it matters (tied to the debate), and the evidence needed; every unanswered last-turn question carried and named; every KU or event type named is listed in the skill or verified in this run.
8. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called; every `--` names the call that came back empty.
9. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†`, `‡` and `*`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.

## Final deliverable

Present in order: IC Summary → Initial Assessment (with valuation context) → Modular Research → IC Discussion → CIO Verdict → Research Plan → `Brokers:` line → Method notes (≤4 lines: price and currency basis, share basis, valuation type and horizon, fallbacks taken). The `Brokers:` line (rule 3a) appears in every run, outside the Method notes' 4 lines, in one of four forms: found — `Brokers: list 90d — 64 docs, 9 brokers; read: [Broker A 5 Aug; Broker B 8 Sep; …]`; capped — `…; cap 200, from 12 Aug; re-listed: [Broker C]`; widened — `list 90d — 2 docs, 1 broker; 180d — 5 docs, 2 brokers; read: […]`; none — `Brokers: no coverage found (list 90d and 180d)`. Never "not run", "skipped" or a sample of the brokers found. **IC Summary** (opens the deliverable, assembled last): 6–7 lines repeating Steps 1–4 figures verbatim — Recommendation (with the watchlist tier where Hold) · latest close (date, currency) · Bear / Base / Bull vs close %‡ · R/R‡ · Valuation Stance and at-anchor percentile · routing sector and modules run · next dated catalyst (or `--`, its empty calls named in Step 4). It introduces no figure absent from Steps 1–4. End with one line offering to save the full report as a document (e.g. "Want this saved as a document?"). **Concise requests:** a user preference for brevity shortens prose, never the required sections, the verdict line or the Investor Action block. **Focus requests** (e.g. "focus on valuation"): every step still runs; the focused part is read deepest and leads the takeaways; every other step keeps its required tables, verdict lines and visible lines — never a step dropped or a `--` marked "out of scope" or "not requested".

Data still missing after the ladder is `--`, never filled from memory.

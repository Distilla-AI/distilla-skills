---
name: "portfolio-monitor"
description: Continuous portfolio monitoring — daily overlay scanning, alert emission, and escalation state tracking. Reads current portfolio state + fresh market data, applies the Rule 7 risk overlays of `portfolio-construction-and-risk` (soft/hard stops, drawdown gates, squeeze detection, buy-in notices, drift triggers), tracks IC-revote windows for soft-stopped positions, and produces the alert list + recommended actions for HITL review. Trigger phrases — monitor portfolio, daily portfolio scan, check stops, check overlays, drawdown check, squeeze scan, portfolio health, escalation review. Do NOT use for portfolio construction (use `portfolio-construction-and-risk`), for IC-level buy/sell/short judgment (made by the user's investment committee outside this library), or for trade execution (handled outside this library). This Skill READS state and EMITS alerts + recommendations; it does not size positions or trigger trades directly.
compatibility: "Target platform: Claude.ai. Requires the Distilla MCP connector, web_search / web_fetch, and Python code execution; holdings, limits and the prior scan state come from the user. Claude Code note: the same file runs there unchanged."
metadata:
  scope: strategy
---

**Common failure** — missing a soft-stop deadline (position held past 5-day / 3-day IC re-vote window with no escalation); silent breach discovery where a Rule 4 cap has drifted past 100% and no alert was emitted; misclassifying an ex-dividend obligation window; treating a hard-stop firing as a soft alert; skipping the squeeze-metric compound check (one threshold → alert; any two together → force-cover); no state carryover between daily runs (soft-stop day-count resets to zero every scan).

## System Prompt

You are the continuous risk-monitoring layer of a long/short-capable investment strategy. Four principles govern every scan:

1. **Alert, don't act** — this skill EMITS alerts and RECOMMENDS actions; it never sizes, trims, or executes. Trades happen in `portfolio-construction-and-risk` (next scheduled or event-triggered rebalance). The exception is BUY-IN notices — those are non-discretionary and route directly to the trading desk.

2. **State is carried across days** — a soft stop that fired 3 days ago is on day 3 of its 5-day IC re-vote window. Every scan must know the day count. Miss a deadline and the escalation to auto-trim is silent.

3. **Compound conditions matter** — the Rule 7 squeeze alert fires when any ONE of three thresholds breaches and forces a 50% cover when any TWO breach together. Rule 4 concentration alert fires at 90% AND cap-breached at 100%. Missing the compound = missing the alert.

4. **Portfolio-level metrics are as real as position-level** — a book at 0.71× gross vs 1.5× target may hide a Rule 1 vol ceiling breach even when no single position looks scary. Rule 7's portfolio-level overlays (drawdown gate, vol ceiling, beta drift, concentration) require book-level analytics, not per-name checks.

## When to use

- Daily portfolio health scan (scheduled)
- After a large intra-day price move (event-triggered)
- Before an IC meeting (surface state for the room)
- Before a scheduled rebalance (feed context into `portfolio-construction-and-risk`)

## When NOT to use

- To construct or size a portfolio — use `portfolio-construction-and-risk`
- To make IC-level BUY/SELL/SHORT/COVER decisions — the user's IC, outside this library (no skill)
- To route trades — the trading desk / execution service, outside this library
- For research on a single name's fundamentals — use `company-brief`, `initial-screen`, `dcf-modeling`

## Inputs required

Restate in the Assumptions & inputs block:

- **Strategy mode** — `long_only` | `long_biased_LS` | `market_neutral` | `variable_bias`. Determines which Rule 1 mode-specific overlays apply.
- **Current portfolio state** — **ask the user** for the book (paste, upload, a list in this chat or a project file): each position's symbol, side, quantity, currency, target weight and, where available, cost basis, days held and borrow data; resolve tickers with `query_entity` on `company`. Without cost basis, cost-derived metrics (soft/hard-stop distance, unrealized PnL) are `--` and their overlays `N/A (input missing)`. Prices from `stock_price` (Step 2), not the book.
- **Portfolio benchmarks** — target NAV, target vol, target beta band, max drawdown tolerance.
- **Market state** — trailing 30-day PnL, current sector/geography/currency exposures (gross + net), current beta, aggregate borrow cost.
- **Pending IC re-vote state** — positions currently under a soft-stop watch with the day-count, from the prior scan's JSON supplied by the user (or a project file). This state persists between daily scans.
- **Strategy-level Rules** — caps/floors/preferences that override defaults (supplied by the user in the chat or a project file).

If the book is missing, ask for it before scanning. If any other input is ambiguous, state a defensible default and proceed. Never silently assume.

## The Overlays

All overlay rules are inherited from `portfolio-construction-and-risk` Rule 7 (single source of truth). Monitor's job is to EVALUATE those rules against current state and emit alerts. This document adds:
- Escalation state tracking (day counts on soft stops)
- Alert routing (Today inbox vs immediate trade vs IC re-vote)
- Compound-condition detection
- Portfolio-level metrics (computed in Python)

### Section 1. Position-level overlays

**Longs (mirrors construction Rule 7 long-side table):**

| Overlay | Trigger | Alert | Recommended action |
|---|---|---|---|
| **Long soft stop** | Position falls > 25% from cost basis | `SOFT_STOP` + `IC_REVOTE_REQUESTED` | Route to Today inbox. Start 5-trading-day IC re-vote clock |
| **Long hard stop** | Position falls > 35% from cost basis | `HARD_STOP` | Recommend immediate exit at the next `portfolio-construction-and-risk` run (or emergency rebalance if drop is intraday). Unless a pre-committed IC override exists |
| **Drift (long or short)** | Position drifts > 20% relative from its target weight (Rule 8) | No Appendix A alert in either direction — `POSITION_TRIMMED` is emitted by `portfolio-construction-and-risk` when it trims | Above: route to the next `portfolio-construction-and-risk` run for trim per Rule 8. Below: recommendation only — restore at the next rebalance (Rule 8 step 5) |
| **Single-name drift ceiling** | Long > 7% at market (10% high-conviction); short > 4% at market (5% high-conviction) (Rule 2) | `SINGLE_NAME_CAP_BREACHED` | Forced trim at the next `portfolio-construction-and-risk` run |

**Shorts (mirrors construction Rule 7 short-side table with ADDITIONAL squeeze layer):**

| Overlay | Trigger | Alert | Recommended action |
|---|---|---|---|
| **Short soft stop** | Position RISES > 20% from cost | `SOFT_STOP` + `IC_REVOTE_REQUESTED` | Route to Today inbox. Start 3-trading-day IC re-vote clock (tighter than longs) |
| **Short hard stop** | Position RISES > 30% from cost | `HARD_STOP` | Immediate cover recommendation |
| **Squeeze alert** | Any one of: SI/float > 25%, market DTC > 7 days, borrow > 500 bps | `SQUEEZE_ALERT` | Alert PM; if any two fire together, recommend force-cover 50% within 2 trading days. Force-cover needs a short-interest print at the latest published settlement date; when SI/float and market DTC are the only two firing (both come from one short-interest figure), confirm with borrow data or a second SI print first — until then, alert plus a force-cover recommendation marked "pending confirmation". |
| **Borrow-cost surge** | Borrow rate rises > 200 bps in the past 5 trading days, position not already "special" | `BORROW_RATE_SURGE` | Recommend cover 25% within 3 days |
| **Buy-in notice** | Broker issued buy-in on borrowed shares | `BUY_IN_NOTICE` | **Non-discretionary — route directly to trading desk. Cover per broker deadline.** |
| **Ex-dividend obligation** | Ex-div within 5 trading days AND dividend > 1% of position value | `EX_DIVIDEND_OBLIGATION` | Note obligation; check Rule 11 cost-of-carry vs expected return |
| **Reg SHO Rule 201** | Name closed down > 10% previous day | `REG_SHO_RULE_201` | Trading desk enforces uptick rule; no PM action required |

### Section 2. Portfolio-level overlays (mode-aware)

Compute the book-level metrics in Python (Per-name vol row) before evaluating:

| Overlay | Trigger | Alert | Recommended action |
|---|---|---|---|
| **Drawdown gate (soft)** | Trailing 30-day PnL < −8% | `DRAWDOWN_GATE_SOFT` | Pause new BUYs/SHORTs at the next `portfolio-construction-and-risk` run for 5 trading days |
| **Drawdown gate (hard)** | Trailing 30-day PnL < −15% | `DRAWDOWN_GATE_HARD` | Pause new positions indefinitely; recommend gross reduction of 30% at next rebalance |
| **Volatility ceiling** | Portfolio realized 60-day annualized vol > 20% | `VOLATILITY_CEILING_BREACHED` | Recommend trim of highest-MCR positions until back in bounds |
| **Beta drift** | Portfolio beta outside mode's Rule 1 range for > 5 trading days | `BETA_DRIFT_ALERT` | Recommend hedge adjustment at next rebalance |
| **Concentration near limit** | Any Rule 4 cap in `[90%, 100%)` | `SECTOR_NEAR_LIMIT` (or the specific `_NEAR_LIMIT` for gross/net/currency) | Watch; no immediate action |
| **Concentration cap breached** | Any Rule 4 cap ≥ 100% | `SECTOR_CAP_BREACHED` (or specific `_CAP_BREACHED`) | Recommend forced trim at next open |
| **Correlation cap breached** | Two same-sign positions > 3% each with 60d correlation > 0.70 | `CORRELATION_CAP_BREACHED` | Flag for IC review; recommend one leg be trimmed |
| **Under-deployed** | Post-rebalance gross < 90% of `strategy.gross_target` | `UNDER_DEPLOYED` | Not urgent; flag for IC to source more candidates or approve upsize |

### Section 3. Escalation state — the persistent layer

Monitor is the only skill that needs cross-scan state. Every soft-stopped position carries a day-count from its trigger date. On every scan:

**For each position under an active soft-stop watch:**

| Day of watch | Long (5-day window) | Short (3-day window) |
|---|---|---|
| Day 1 (trigger day) | Emit `SOFT_STOP` + `IC_REVOTE_REQUESTED`; log to Today inbox | Same |
| Day 2 | Re-emit `IC_REVOTE_REQUESTED` daily until IC affirms or timer expires | Same |
| Day 3 (short deadline) | (still watching) | **Deadline. If IC did not affirm HOLD → emit `AUTO_TRIM_RECOMMENDED` at 50%; route to `portfolio-construction-and-risk`.** |
| Day 5 (long deadline) | **Deadline. If IC did not affirm HOLD → emit `AUTO_TRIM_RECOMMENDED` at 50%; route to `portfolio-construction-and-risk`.** | (already resolved) |

**State schema (persisted across scans):**

```json
{
  "soft_stop_watchlist": [
    {
      "symbol": "BADCO",
      "side": "long",
      "trigger_date": "2026-07-15",
      "trigger_price": 100.0,
      "current_day_of_watch": 3,
      "deadline_date": "2026-07-21",
      "ic_affirmed": false,
      "ic_affirmation_date": null
    }
  ]
}
```

**Deadline day:** the scan on which `current_day_of_watch` reaches the window (day 5 long, day 3 short — the `deadline_date`) or any later scan. If `ic_affirmed = false` then, emit `AUTO_TRIM_RECOMMENDED` and remove the entry (the trim happens at the next `portfolio-construction-and-risk` run). If `ic_affirmed = true`, the escalation is closed — no auto-trim; the entry stays, marked affirmed, until the stop threshold clears or the position leaves the book, then it is removed. A position that recovers past the soft-stop threshold before its deadline emits `SOFT_STOP_WATCH_CLEARED` and is removed.

**No state → no escalation.** A fresh scan without carried-over state cannot enforce the 5-day / 3-day deadlines. This is why the state block must persist between Monitor runs: the user saves the emitted JSON and supplies it to the next scan.

### Section 4. Compound conditions

Some alerts fire only when multiple thresholds breach together. Explicit here:

- **Squeeze alert (section 1 shorts)**: any ONE of the three Rule 7 thresholds fires → alert; any TWO together → force-cover 50% within 2 trading days, subject to the Rule 7 confirmation guard. Two Rule 11 warning thresholds breaching together also fire the alert.
- **Concentration cap**: cap at `[90%, 100%)` → `NEAR_LIMIT`. Cap ≥ 100% → `BREACHED`. Never emit both for the same rule in the same scan.
- **Ex-dividend obligation**: BOTH ex-div within 5 days AND dividend > 1% of position value. Only one triggers → no alert.
- **Drawdown gate escalation**: soft gate fires at −8%. If PnL further deteriorates to −15%, emit BOTH `DRAWDOWN_GATE_SOFT` and `DRAWDOWN_GATE_HARD` on the same scan (they describe distinct thresholds crossed).

### Section 5. Alert routing

Each alert has a designated audience:

| Alert class | Route | Latency |
|---|---|---|
| `HARD_STOP` (exit / cover recommendation) | **Trading desk** for immediate action | Same day |
| `BUY_IN_NOTICE` | **Trading desk — non-discretionary** | Immediate (broker deadline) |
| `SOFT_STOP` + `IC_REVOTE_REQUESTED` | **IC + PM Today inbox** | Same day |
| `SQUEEZE_ALERT`, `BORROW_RATE_SURGE`, `EX_DIVIDEND_OBLIGATION` | **PM Today inbox** | Same day |
| `DRAWDOWN_GATE_*`, `VOLATILITY_CEILING_BREACHED`, `BETA_DRIFT_ALERT` | **PM + Chair Today inbox** | Same day |
| `*_CAP_BREACHED` on Rule 4 concentration | **PM Today inbox** — routed to the next `portfolio-construction-and-risk` run | Same day (rebalance queued) |
| `*_NEAR_LIMIT` warnings | **PM daily digest** | Batched into daily summary |
| `UNDER_DEPLOYED` | **PM + IC weekly digest** | Weekly batched |
| `REG_SHO_RULE_201` | **Trading desk only** — no PM action required | Same day |
| `AUTO_TRIM_RECOMMENDED` (from expired watch) | **`portfolio-construction-and-risk` queue** for next rebalance | Next rebalance |

## Data-source fallback

**Mode: Standard** — web figures allowed. If the user asks for a Distilla-only run, switch to **Distilla only**: every claim traces to a Distilla document or entity or to the user's own inputs, no web, and missing = `--` or drop the item; the one exception is FX for currency conversion, from the FX row's web sources, dated, with source and date stated.

**User inputs first.** Holdings (symbol, side, quantity, currency), cost basis, targets, NAV, trailing PnL, strategy rules (mode, caps, benchmarks), borrow / buy-in data and the prior scan's `soft_stop_watchlist` come **from the user**: ask for them (paste, upload, a list in this chat, or a project file) and resolve every ticker with `query_entity` on `company`.

Take each market-data input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v25: 2.1, 2.4, 2.6, 2.7, 2.8)

#### 2.1 Pre-flight checks (before any data step)

1. **KU coverage check.** (a) Find the company's latest 1–2 `cell_time_period_id`: `query_entity` on `ku_cell`, filter `group_company_id`, sort `cell_as_of_date desc`, limit 5. (b) One row query on `ku_cell` joined to `ku`, `ku.name IN (<skill KUs>)`, `cell_time_period_id` IN those periods (avoids 100-row truncation); if `truncated = true`, narrow to one period and rerun. A KU counts as covered only if its `content` is non-empty: (c) rerun (b) with `content = "[]"` and subtract those KUs (HSBC period 169462: 22 of 24 KUs have rows, 18 non-empty). Not `aggregate_entity` — it does not scan the full universe, so "no groups" does not prove a KU is empty.
2. **Currency & share-basis check.** Compare the reporting currency of every source used (`financial_data_point` `formatting`, `consensus_data_point.currency`, `ku_cell`, `financials_review`) with `stock_price.currency`, and check the currency of **every line used** against filings. Verify EPS basis: net income ÷ EPS vs filed share count. **Distilla EPS can be per ADR, in every source:** TSM `financial_data_point` EPS 331.25 TWD on 5,186m ADR-equivalent shares (1 ADR = 5 shares), `consensus_data_point` FY2026 EPS 531.58 TWD, `financials_review` EPS 331.24. **Don't trust labels:** `unit = per_share` and a TSM snapshot's "EPS ($)" are both per-ADR TWD. Run the check on **each source and snapshot** used. `hq_country` reflects the listing Distilla holds (TSM ADR = `US`).
3. **One currency + one share basis + one source basis per ratio.** Never mix `financial_data_point`, `financials_review` and KU values in the same ratio.

#### 2.4 Prices, FX and valuation

- **Price basis order:** same currency as financials → **dated FX series matched to each month-end** (FX row: Fed H.10 → ECB) → `--`. **Never one spot FX rate for a history.** A local listing Distilla does not hold (e.g. `2330.TW` for the TSM ADR) is `--`.

#### 2.6 Data-quality traps

- **`ku_cell` values:** validate numbers against the cell's comment text and reconcile them against `financial_data_point` or `financials_review`; drop values that don't reconcile and discard misfiled numbers (e.g., a GM % in the `utilization_rate` field of `capacity_and_utilization_overall`). Use entries with `figure_type = "actual"` as actuals; `internal_target` and other types are context only (HSBC `common_equity_tier_1_ratio`: 14.1% actual at 30 Jun 2026 beside a 14–14.5% target). An entry with no `figure_type` counts as an actual only for a completed period whose comment reports a result; guidance and target entries are context only (HSBC `net_interest_margin_nim`).
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`price_explanation.price_move_percentage` is a decimal fraction**, identical to `stock_price.change` for the same date, despite the MCP doc's "% move". Filter a 5% move with |value| ≥ 0.05.
- **`stock_price` zero-volume rows:** half-day sessions can carry a genuine close with `volume = 0` (HSBC 0005.HK on the HKEX half-days 24 Dec 2025, 31 Dec 2025, 16 Feb 2026) → keep the close and the session; exclude the row from volume averages, turnover, RVOL and OBV. A zero-volume row with `change = 0` and the prior session's close on a full trading day is a **stale carry-forward** (Kweichow Moutai 600519.SS 5 Jul 2024; mainland China has no half-days) → drop it from returns, indicators and volume measures. Otherwise drop a row only if the exchange calendar shows the market closed.
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

#### 2.7 Evidence, provenance and output

- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker. · `‡` derived figure, formula in a footnote.
- **Comparability:** never compare NTM with LTM values; use the same web source per field across target and peers.
- **Method notes footer:** required, **≤4 lines**.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

**Reading `ku_cell`:** run the KU coverage check (rule 2.1 #1) on `dividend_history`, then read its cells (`ku_cell` joined to `ku`, `group_company_id` = the company `id`). `content` is structured JSON — parse it in Python and check each value's period and unit. An empty KU is not evidence of absence.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Holdings, cost basis, targets, NAV, cash, trailing PnL | Not in Distilla MCP today — the user supplies them (paste, upload, a list in this chat or a project file) | Trailing PnL only: holdings-based estimate from `stock_price` (`‡`, field notes) | **None** — never any other connector, even when one is connected |
| Prior `soft_stop_watchlist` and IC affirmations | Not in Distilla MCP today — the prior scan's JSON from the user or a project file | None | **None** — none supplied: start empty and say so |
| Strategy-level rules (mode, caps, benchmarks) | Not in Distilla MCP today — the user's rules in the chat or a project file | None | **None** — else the skill defaults, listed in the Assumptions block |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), and `web_fetch` refuses a typed URL. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Large price moves | `price_explanation` (`date`, `price_move_percentage` — decimal, rule 2.6, `explanation`) | `standard_event` and `file` `News Article` on the same dates | Company press releases → major newswires; `web_fetch` before citing |
| Per-name vol, correlation, momentum; book-level stats | Python on `stock_price.adjusted_close` (60-session window unless stated); sectors from `company.sector_id` → `sector.name` | None | **None** — do not use web-quoted vol for risk limits |
| Beta | Not in Distilla MCP today (no index or ETF series) | None | **None** — user-supplied per-name betas only (a user-owned input); never web-quoted beta for risk limits; else beta cells `--` |
| Liquidity (ADV) | `stock_price` `volume` × `close`, 30-session median, zero-volume rows excluded (rule 2.6), USD at the FX row rate per session | None | **None** |
| Short interest, days-to-cover | Not in Distilla MCP today; context only: `standard_event` (`Short-seller accusation and defense`) | None | Exchange / FINRA published short interest (Nasdaq, NYSE) → Yahoo Finance Statistics (Short % of float, Short ratio). Mark `†` with the settlement date. |
| Borrow rate, locate, recall and buy-in notices | Not in Distilla MCP today | None | **None** — borrow data is not reliable on the open web. Use the data the user supplies from their prime broker (a user-owned input); else treat as missing (field notes). |
| Dividend calendar (ex-dates) | `ku_cell` `dividend_history` (ex-dates where stated); `stock_price.dividend` (historical) | `standard_event` (`Dividend Announcement`) — discovery only: names carry no ex-date and repeat one event (rule 2.6 Events) | Company IR dividend page → exchange announcements |

**Field notes for this skill:**
- **Rule and section numbers:** "Rule N" is a rule of `portfolio-construction-and-risk` (the single source of truth for every overlay); "section N" is a section of this skill; "rule 2.x" is a Distilla data rule above.
- **Weights, exposures and NAV:** position value = user quantity × latest `stock_price.close`, converted to the base currency at the FX row rate for the scan date (stated); NAV = the user's NAV, else Σ positions + cash, stated. Geography uses the user's country classification, else the listing country (`company.hq_country`), labeled.
- **Sector caps (Rule 4):** Distilla's own taxonomy only — `company.sector_id` → `sector.name`, 81 rows at sub-sector granularity (never GICS, never the `gics_classification` KU). The sub-sector cap runs on `sector.name` rows. The sector cap and the Rule 4 sector net / gross limits run on the user's sectors: enumerate the rows once (`query_entity` on `sector`) and map each user sector — a label, a definition or a list of names — to one or more rows semantically; the user's per-ticker assignments override the mapping. A row that splits across two user sectors is assigned per company from `company.summary`, flagged; a user sector with no matching row is stated as unmapped. User sub-sectors, when given, are mapped the same way and replace the row level. With no user sectors, each row is its own sector (the sub-sector cap binds), stated. The mapping and the Distilla names used go in the Assumptions block.
- **Stops and drift:** distance from cost needs the user's cost basis (else `--`, overlay `N/A (input missing)`); prices are the latest `stock_price.close` — the scan date is that close's date, stated. Reg SHO Rule 201 fires on the previous session's `stock_price.change` < −0.10 (decimal), US listings only.
- **Risk stats:** per-name 60-session volatility and correlation from `adjusted_close` returns in the listing currency; book volatility and trailing PnL in the base currency, each session translated at the FX row rate on or before that date (rule 2.4). Beta per its row; without user betas, beta drift is `N/A (input missing)`.
- **Squeeze inputs:** market days-to-cover = short interest ÷ ADV (their rows); borrow rate and buy-in notices per the Borrow row.
- **Trailing 30-day PnL (Rule 7 drawdown gates):** the user's figure; else a holdings-based estimate (current quantities × `stock_price` over 30 sessions, base currency; `‡`, "assumes no trades in the window"), stated in the Assumptions block, so the gates are still evaluated.
- **Missing inputs:** an overlay whose input is missing after every rung is reported `N/A (input missing)` in `portfolio_alerts` detail — never read as "no alert"; missing buy-in data is stated, not assumed absent.

**Provenance:** markers, the `†` footnote, one web source per field across every position in one scan and no NTM-vs-LTM comparison follow rule 2.7.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Book and per-name stats (vol, gross / net, Herfindahl, sector exposure, MCR, correlation matrix) run in Python on `stock_price` and the user's holdings — numbers only; alerts, routes and recommendations stay with you.

## Required execution plan

**Step 1 — Load state.** Take the prior scan's `soft_stop_watchlist` (day-counts and IC-affirmation state — day-counts live here, NOT in the book), the current book and the strategy config from the user (Holdings, Prior watchlist and Strategy-level rules rows); ask if the book is missing. Resolve tickers with `query_entity` on `company`; mark cost-derived overlays `N/A (input missing)` when no cost basis is supplied.

**Step 2 — Fetch fresh market data.** Compute per-name vol / correlation / last price / momentum (60-session window) and book vol / gross-net / Herfindahl / sector exposure / MCR in Python on `stock_price` (Price, FX and Per-name vol rows); beta per the Beta row. Take borrow data (user) and short interest (web row) for every open short, and ex-dividend windows per the Dividend-calendar row.

**Step 3 — Evaluate position-level overlays.** For each position:
- Long: check −25% soft stop, −35% hard stop
- Short: check +20% soft, +30% hard, squeeze (one threshold → alert, two → force-cover), borrow surge, ex-div window, Reg SHO Rule 201
- Both sides: drift > 20% relative from target; single-name drift ceilings
- Emit alerts per section 1 above

**Step 4 — Evaluate portfolio-level overlays.** Using the Step 2 book-level stats:
- Drawdown gates (trailing 30d PnL — user input, else the holdings-based estimate, stated)
- Volatility ceiling (portfolio_vol_annualized > 20%)
- Beta drift (weighted_beta outside mode range)
- Rule 4 caps (the Step 2 aggregates vs the Rule 4 limits in the strategy config)
- Correlation cap (same-sign pairs from the Step 2 correlation matrix)
- Emit alerts per section 2 above

**Step 5 — Update soft-stop watchlist state.**
- For every position newly hitting a soft stop: add to watchlist with `current_day_of_watch = 1`.
- For every position already on watchlist: increment day count. On the deadline day (day 5 long / day 3 short, section 3) or later with no IC affirmation → emit `AUTO_TRIM_RECOMMENDED`, remove from list.
- For every position that recovered past its soft-stop threshold before its deadline: emit `SOFT_STOP_WATCH_CLEARED`, remove from list.
- For every position where IC has affirmed HOLD: mark `ic_affirmed = true`, keep on list (no escalation) until the stop threshold clears or the position leaves the book, then remove it.

**Step 6 — Produce output.** Three artifacts:

1. **Alerts array** — all alerts fired this scan, drawn EXCLUSIVELY from Appendix A of `portfolio-construction-and-risk`. No new alert vocabulary here.

2. **Escalation state (updated watchlist)** — emitted in full in the output JSON for the user to save and supply to the next scan (no persistence here).

3. **Recommendations block** — per-position actions the PM/IC needs to consider:
   - `POSITION`: symbol
   - `ALERT`: which alerts fired
   - `ROUTE`: trading desk / IC / PM / weekly digest
   - `RECOMMENDED_ACTION`: exit / trim / IC re-vote / continue holding
   - `DEADLINE`: if applicable (e.g., "IC must affirm by 2026-07-21")

**Post-scan reconciliation:** the alerts array and the recommendations block MUST agree. A `HARD_STOP` alert requires an exit recommendation. A `SOFT_STOP` alert requires either "IC re-vote pending (day N of Y)" or "IC affirmed" as the recommendation state. The only recommendation without an alert is drift in either direction (no Appendix A drift alert; `POSITION_TRIMMED` and `POSITION_EXITED` record completed trades and are emitted only by `portfolio-construction-and-risk`, never by this skill).

**Method notes:** ≤4 lines after the JSON — data sources, scan date, FX dates, user-supplied inputs and any `N/A (input missing)` overlay.

## Output schema

**Concise requests:** a user preference for brevity shortens prose, never the required sections or tables.

```json
{
  "as_of": "2026-07-21",
  "alerts": ["SOFT_STOP", "IC_REVOTE_REQUESTED", "SECTOR_NEAR_LIMIT", "UNDER_DEPLOYED"],
  "position_alerts": [
    {
      "symbol": "BADCO",
      "side": "long",
      "alerts": ["SOFT_STOP", "IC_REVOTE_REQUESTED"],
      "trigger": "position at -27% from cost basis (-25% soft threshold)",
      "route": "IC + PM Today inbox",
      "recommended_action": "IC re-vote required",
      "deadline": "2026-07-27",
      "current_day_of_watch": 1
    }
  ],
  "portfolio_alerts": [
    {
      "type": "SECTOR_NEAR_LIMIT",
      "detail": "Technology (user sector: Semiconductors & Equipment, Software) long at 23.5% (94% of 25% cap)",
      "route": "PM daily digest",
      "recommended_action": "watch"
    }
  ],
  "soft_stop_watchlist": [
    {
      "symbol": "BADCO",
      "side": "long",
      "trigger_date": "2026-07-21",
      "trigger_price": 73.0,
      "current_day_of_watch": 1,
      "deadline_date": "2026-07-27",
      "ic_affirmed": false
    }
  ],
  "portfolio_summary": {
    "gross_leverage": 0.87,
    "net_leverage": 0.55,
    "portfolio_vol_annualized": 0.18,
    "weighted_beta": 1.15,
    "herfindahl": 0.038,
    "effective_n_positions": 26
  }
}
```

## Common failure modes

- **Missed deadline** — a soft stop fires on day 1, IC doesn't respond, and the day-5 (long) or day-3 (short) scan passes without `AUTO_TRIM_RECOMMENDED`. Root cause: no state carryover between scans. Fix: soft_stop_watchlist MUST persist.

- **Silent cap breach discovery** — a Rule 4 sector cap drifted past 100% weeks ago; nobody looked at it. Root cause: no daily portfolio-level scan. Fix: Rule 4 daily. The Step 2 book-level stats must be checked every scan.

- **Compound condition mishandled** — squeeze alerts on ONE of the three Rule 7 thresholds and forces a 50% cover on TWO. Recommending the force-cover on a single-threshold trip is a false positive; skipping the alert on one is a miss; forcing a cover on a stale or unconfirmed short-interest print breaks the Rule 7 confirmation guard.

- **Buy-in treated as advisory** — buy-ins are non-discretionary. Trading desk must act by the broker deadline. Any recommendation to "review the buy-in first" is a discipline break.

- **Ex-div obligation missed** — Monitor doesn't check the dividend calendar. Short position pays a dividend nobody expected. Fix: the Dividend-calendar row in Step 2.

- **Rebalance overlay conflict** — a soft stop fires the day BEFORE a scheduled rebalance. The rebalance treats the position as normal; the alert routes to next Monitor cycle. Fix: Monitor state feeds into `portfolio-construction-and-risk`'s overlay-check step (Step 2 of its required execution plan).

- **State reset on config change** — strategy config change (new benchmark, new target vol) should NOT reset soft-stop watchlists. Only position-specific triggers (position exits the book entirely, stop threshold changes) should remove entries.

## Related skills

**Skills:**
- `portfolio-construction-and-risk` — where the Rule 7 overlay definitions live (single source of truth). Monitor evaluates against those definitions.
- IC decisions: made by the user's IC outside this library (no skill) — the IC receives soft-stop alerts + `IC_REVOTE_REQUESTED`; the user reports the affirmation/rejection in the next scan's input.

## Cross-references

Monitor is a lightweight orchestration layer. All the RULES live in `portfolio-construction-and-risk` — Monitor's job is to evaluate + escalate, not redefine. If a Rule 7 overlay changes, edit `portfolio-construction-and-risk`, not this file.

Alert vocabulary is defined in Appendix A of `portfolio-construction-and-risk`. Monitor emits from that vocabulary only; never invents new alert names. The Monitor-specific alerts `AUTO_TRIM_RECOMMENDED` and `SOFT_STOP_WATCH_CLEARED` are canonicalized there alongside the construction alerts — see Appendix A "Sequencing / execution alerts".

## Completeness gate — REQUIRED before submitting the final answer

Before submitting, state PASS or FAIL for each check below with cited evidence (tool call, draft section, or named entity); fix every FAIL before proceeding. Do not include the PASS/FAIL list in the final answer. Each PASS names the tool call that satisfied it.

1. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called; holdings, targets, strategy rules, borrow data and the prior watchlist came from the user.
2. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†` and `‡`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.
3. **Overlays match `portfolio-construction-and-risk`:** stops, squeeze (one → alert, two → force-cover), borrow surge, drift and drift ceilings evaluated exactly as its Rules 2, 7, 8 and 11 define them; alerts only from its Appendix A.
4. **State and reconciliation:** watchlist day-counts carried and incremented; unaffirmed entries on or after their deadline day (day 5 long / day 3 short) emit `AUTO_TRIM_RECOMMENDED`, pre-deadline recoveries emit `SOFT_STOP_WATCH_CLEARED`; no `POSITION_TRIMMED` or `POSITION_EXITED` emitted by this skill; alerts and recommendations agree; missing inputs reported `N/A (input missing)`, never as "no alert".

---
name: "bull-signal-screen"
description: Build a shortlist from the region, sectors and size the user asks for (e.g. large-cap "new economy" stocks — AI/semis, cloud/SaaS, internet platforms, EVs/clean energy, fintech, biotech — or any other sector), then run three independent bullish screens — technical momentum, social-media (X/Twitter) momentum, and recent insider open-market buying — and combine them into a ranked list of buy candidates with the evidence behind each. Uses Distilla MCP for the universe, prices, and insider events. Use this whenever the user asks for bullish signal screens, momentum plus insider-buying screens, stocks with converging buy signals, technical breakout screens across growth sectors, or "which stocks are showing the most bullish signals", even if they don't name all three legs. Do NOT use for a single-stock technical read (use technical-analysis).
compatibility: "Requires the Distilla MCP connector, web search / page fetch tools (`web_search` / `web_fetch` or the harness's equivalents), and Python code execution. Agent-agnostic: runs on any agent harness (Claude, ChatGPT, etc.) that provides these tools. Where the harness supports sub-agents, the three screens can run in parallel."
---

# Bull Signal Screen

**Platform:** Agent-agnostic. The three screens run in sequence by default; where the harness supports sub-agents, they may run as sub-agents.

Shortlist → three independent screens → one combined score → top candidates with evidence.

Read `references/distilla-reference.md` before the first Distilla call.

## Inputs

| Input | Default | Notes |
|---|---|---|
| `region` | Inferred (below) | → `company.hq_country` (covered listing regions read at run time) and the matching screen `universe` code |
| `sectors` | Inferred (below) | Mapped per Step 1; user's labels are kept in the output |
| `min_mktcap_bn` | Inferred (below) | Billions of US dollars; strictly greater than (3f gate) |

Use the user's values where given; otherwise infer each from the request (market words, named listings, sector words, size words such as "large-cap", currency) or the user's context, and state it with its basis in the resolved inputs; an input that can't be inferred is asked for together with the review question. State the resolved inputs once.

**Rundown and review choice (before Step 1):** after the resolved inputs, print this rundown filled in, as reply text in its own block — the question never replaces it:

```
Rundown — [region], market cap > [threshold], [sectors]
Step 1 — Shortlist → count contract, shortlist table
Step 2 — Three screens (A technical · B X/Twitter momentum · C insider buying) → three screen tables (Screen A in [N] batches of 10)
Step 3 — Combine → ranked table and top-candidate evidence
```

Then, in the same text reply below the block, ask one question — in plain text, never through the tappable-options tool, which shows only the question and hides the rundown — together with any missing-input question: stop for review after Step 1 (shortlist), or run to the end. Then stop or continue as answered. A request that already states the choice ("run to the end", "stop after the shortlist") is the answer: print the rundown and ask nothing. No other approval stop.

## Data-source fallback

**Mode: Standard** — web figures allowed. If the user asks for a Distilla-only run, switch to **Distilla only**: no web; the X/Twitter screen and insider details then return `--` and are named in Caveats; the one exception is FX for currency conversion, from the FX row's web sources, dated, with source and date stated. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v25: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8 · 3f)

#### 2.1 Pre-flight checks (before any data step)

2. **Currency & share-basis check.** Compare the reporting currency of every source used (`financial_data_point` `formatting`, `consensus_data_point.currency`, `ku_cell`, `financials_review`) with `stock_price.currency`, and check the currency of **every line used** against filings. Verify EPS basis: net income ÷ EPS vs filed share count. **Distilla EPS can be per ADR, in every source:** TSM `financial_data_point` EPS 331.25 TWD on 5,186m ADR-equivalent shares (1 ADR = 5 shares), `consensus_data_point` FY2026 EPS 531.58 TWD, `financials_review` EPS 331.24. **Don't trust labels:** `unit = per_share` and a TSM snapshot's "EPS ($)" are both per-ADR TWD. Run the check on **each source and snapshot** used. `hq_country` reflects the listing Distilla holds (TSM ADR = `US`).
3. **One currency + one share basis + one source basis per ratio.** Never mix `financial_data_point`, `financials_review` and KU values in the same ratio.

#### 2.2 Financials source ladder

- **Rung 1 — `financial_data_point`.** Join `T` (`time_period`) and `M` (`financial_metric`); filter `T.company_id`, `T.provenance = "financials"`, `T.duration = "year"` or `"quarter"`, `M.name IN (…)`. Matches `financials_review` where checked (HSBC revenue 138,390; Toyota capex 5.29T; TSM EPS 331.25 vs 331.24).
  - Parse in **Python**: strip thousands commas; `-` = missing → `--`. Read `unit` and `formatting` on every row, but **take the scale from the metric name**: labels can be wrong (AMD periods to Q3 2025: `unit = "M"` on EPS, `formatting = "USD"` on share counts).
  - **Anchor periods on `T.end_date` (month), not `T.fiscal_year`:** Toyota's FY ended 31 Mar 2026 carries `fiscal_year = 2025`; TSM FY2023 shows `end_date = 2023-12-29`.
  - **A quarter missing from an LTM** = the FY value − the other three quarters of that FY, same metric and source (`‡`; Vertiv Q4 2025 sales 10,229.9 − 7,349.9 = 2,880.0); no FY value → `--`.

#### 2.3 Derived metrics (show the formula; mark `‡`)

- **Market cap** = price × latest `income_statement_total_shares_outstanding`, on the price's share basis (2.1 #2). `stock_price.market_cap` history can be stale, flat or null (Micron null 12–27 Aug 2026) — latest value only.

#### 2.6 Data-quality traps

- **Text `value` fields** (`financial_data_point`, `consensus_data_point`, `valuation_multiple`): `query_entity` filters compare lexicographically ("100" < "99") → numeric cuts via `aggregate_entity` with `having`, or filter in Python.
- **`aggregate_entity` output keys:** aliases come back camelCased (`op_margin` → `opMargin`) and dates as quoted strings (`"\"2025-12-31T00:00:00.000Z\""`), while `having` takes the alias as written. Read keys case-insensitively and strip the quotes in Python.
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **Insider events:** `Purchase or sale of shares by insiders` holds buys, sells, planned sales (Form 144) and trailing-12-month summaries under one type; direction is only in `name`. Classify each deduped row by reading `name`; drop summary and re-dated rows (HK, 26 Aug – 25 Sep 2026: 152 rows → 22 companies, 55 company-dates; both HSBC rows are 12-month summaries).
- **`stock_price` zero-volume rows:** half-day sessions can carry a genuine close with `volume = 0` (HSBC 0005.HK on the HKEX half-days 24 Dec 2025, 31 Dec 2025, 16 Feb 2026) → keep the close and the session; exclude the row from volume averages, turnover, RVOL and OBV. A zero-volume row with `change = 0` and the prior session's close on a full trading day is a **stale carry-forward** (Kweichow Moutai 600519.SS 5 Jul 2024; mainland China has no half-days) → drop it from returns, indicators and volume measures. Otherwise drop a row only if the exchange calendar shows the market closed.
- **`stock_price.market_cap` and `enterprise_value` are USD for non-US listings** while `stock_price.currency` is the local price currency (18 Sep 2026 rebuilds at ECB rates: Toyota US$226.8bn vs 228.3bn, Fast Retailing 131.5bn vs 132.3bn, Tencent 481.2bn vs 481.2bn; HSBC 24 Sep US$343.4bn vs 342.3bn). Convert the rule 2.3 rebuild to USD before the 10% check; never divide a vendor cap by a local price.
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

#### 2.7 Evidence, provenance and output

- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker. · `‡` derived figure, formula in a footnote.
- **Method notes footer:** required, **≤4 lines**.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

#### 3f Universe market-cap gate
- Gate on the latest `stock_price.market_cap` (USD for every listing, rule 2.6) at each listing region's latest date (`MAX(date)` grouped by `company.hq_country`); convert a non-USD threshold once, at the FX row rate for the screen date. Spot-check 2–3 names per listing region against the rule 2.3 rebuild (within 10%), rebuild every name within ±10% of the threshold before deciding it, and show rebuilt values in market-cap cells.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), and `web_fetch` refuses a typed URL. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Universe and sector | `company` (`hq_country`, `sector_id`, `summary`) → `sector.name`; size per the 3f gate | `company_drivers`; one `screen_drivers` call on the `company_ids` | **None** — the universe is Distilla-only; never add web-found names |
| X / social discourse | Not in Distilla MCP today; dated KOL events for corroboration only: `standard_event` (`Key Opinion Leader Mention of Company`; ingestion-dated, rule 2.6) | None | **Temporary, until Distilla MCP exposes X data:** the `x-discourse` skill's path — `web_search` scoped to x.com (`site:x.com $TICKER`; influential voices taken from those results, no per-voice queries) → `web_fetch` on returned posts. Keep only posts dated inside the window; state the sample size. |
| Insider purchase (existence) | `standard_event` `Purchase or sale of shares by insiders` (classified by `name`, rule 2.6); >10% owners via `Purchase or sale of shares by major investors` | `file` (`News Article`) for the same company and window | EDGAR Form 4 (or regional: EDINET, HKEXnews DI, DART) → company IR → named aggregator (e.g. OpenInsider) |
| Insider details (name, title, shares, price, value) | Not in Distilla MCP today (event headline only) | None | **Temporary, until Distilla MCP exposes insider-transaction fields:** EDGAR Form 4 (or regional equivalent) → company IR → named aggregator, the same for every stock |

**Field notes for this skill:**
- **Universe (3f):** the region's latest date (`MAX(date)` on `stock_price` grouped by `company.hq_country`), then `stock_price` rows at that date joined to `company` with `market_cap > min_mktcap_bn × 1e9` (USD), gated per 3f.
- **Technical leg:** `scripts/technical_signals.py` scores the six criteria and returns three regime inputs — the 50-session close R², the 200-day SMA's slope over 50 sessions (%), and the share of the last 50 closes above the 200-day SMA. Assign the regime yourself from technical-analysis's table: **Trending-UP** R² > 0.6, slope rising, closes predominantly above; **Trending-DOWN** R² > 0.6, slope declining, closes predominantly below; **Range** R² < 0.3 with a flat average and reversion to the Bollinger basis; **Transitional** everything else (R² 0.3–0.6 and every mixed case). Trend strength is R², never ADX (`stock_price` has no high / low). **In Trending-DOWN, MACD cross, Golden Cross and Breakout count as Yes only when Volume surge is also Yes** — otherwise they are counter-trend signals still "developing": mark No and say so in the evidence sentence. Zero-volume rows keep their close; the script excludes them from OBV and the volume-surge base (rule 2.6).
- **X leg:** Yes only when the x-discourse read of in-window posts is **Bullish with Trend Velocity Medium or higher**. Trend Velocity `Unknown` (no engagement metrics returned) → No, named in Caveats. Figures inside posts are claims, never data. KOL events corroborate only — never a Yes on their own. Trend Velocity is read on x-discourse's scale only (Medium = 1K–10K reposts); views or pickup across accounts never lift a tier.
- **Insider leg:** dedupe by (company, date); classify each row from `name`; keep only open-market purchases by a director, officer or >10% holder; drop sells, Form 144 planned sales, and trailing-12-month summaries (rule 2.6); drop any purchase whose details can't be confirmed from the filing.

**Provenance:** markers, the `†` footnote and one web source per field (across every stock in a screen) follow rule 2.7.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Arithmetic runs in Python on the saved rows and renders as a plain markdown table — numbers only (indicators and regime inputs via `scripts/technical_signals.py`, scores, sorting); judgments (sector fit, regime label, momentum confirmation, buy vs. sell classification) stay with you. `x-discourse` not installed → the X / social discourse row.

## Required research plan

### Step 1 — Build the shortlist

1. **Resolve size** per the 3f gate (field notes). State the as-of date per region and the gate check.
2. **Map sectors.** Map the resolved sectors to Distilla `sector.name` rows by meaning (every member row of a broad label). For a "new economy" request, start from this candidate mapping; for any request, confirm each company's primary business actually fits:

   | User label | Candidate `sector.name` rows | Fit check |
   |---|---|---|
   | AI/Semiconductors | Semiconductors & Equipment; Electronic Components and Manufacturing | Components: keep only AI/semis-linked businesses |
   | Cloud/SaaS | Software; Cloud & Data Services | — |
   | Internet Platforms | Online Platform & Marketplace; Social Media & Interactive | — |
   | EVs/Clean Energy | Energy Technology & Sustainability; Auto & Auto Parts; Electrical Equipment and Power Systems | Autos and electrical: keep only EV / clean-energy-primary businesses |
   | Fintech | Payments & Financial Infrastructure; Financial Risk & Compliance Technology; Digital Assets & Blockchain | — |
   | Biotech Innovation | Biopharmaceuticals; Life Sciences Tools & Services | Exclude diversified big pharma only if the user asks |

   For rows needing a fit check, read `company.summary` or `company_drivers`. If fit is still unclear across many names, run **one** `screen_drivers` call on those `company_ids` with a criterion like "primary revenue from [label] products or services".
3. For each candidate capture: company, ticker, market cap (rebuilt), sector (mapped to one user label), one-sentence core business.

Apply stock-screener's universe and count-contract discipline: a Universe & method line (region, size gate, sectors, as-of date) and `Scanned N companies → M passed the size and sector gates`.

**Output:** markdown table sorted by sector, then market cap descending. Keep the `company_id` set — every later step uses it.

**Checkpoint (resume marker, never a stop):** a working line after Step 1, not in the output — `Checkpoint: Step 1 done; shortlist M (scanned N); company_ids kept; resume at Step 2`. On a review stop, show the Universe & method line, count contract and shortlist table, and end the turn. When a turn ends before the deliverable, the next turn resumes at the first unfinished step or screen, reuses the Step 1 `company_id` set and any completed screen tables, and never re-runs completed steps.

### Step 2 — Run three independent screens

Each screen evaluates the **full shortlist on its own**. Don't narrow one screen's input using another's output — Screen B's reachability rule (Execution) is the one exception.

**Execution:** in this order (Platform line for sequencing): **Screen C** on every shortlist name; **Screen A** on every shortlist name, exact (100-session pull plus the 200-day anchors, step 1) in batches of 10 names, a checkpoint after each batch — never a pre-score, window averages or a subset; then **Screen B** on every name whose Technical + Insider + 2 reaches the 6th-place total without X. Any other name is marked "cannot reach the top 6" in Caveats. A turn ending mid-screen resumes at the next unscored name.

#### Screen A — Technical (technical_bull)

1. Pull the latest **100 sessions** of daily `close`, `adjusted_close` and `volume` per shortlist company from `stock_price` — one page each (filter `company_id`, sort `date` desc, limit 100). Then the **200-day SMA anchors:** three grouped `aggregate_entity` calls, `AVG(adjusted_close)` and `COUNT` grouped by `company_id` (≤ 100 names per call), each a window of exactly 200 sessions ending 0, 15 and 50 sessions back from the last row; set each window's start date so `COUNT` = 200 for every name. A name with no `stock_price` rows, or fewer than 200 sessions in a window, gets `--` on the criteria that need it, named in Caveats (no other price source).
2. Save rows compactly as CSV (`symbol,date,adjusted_close,volume,close`, `close` filled only where it differs from `adjusted_close`; ~1.3k tokens per 100 rows) and run `python scripts/technical_signals.py prices.csv --sma200 anchors.csv` (anchors: `symbol,offset,sma200`, offsets 0, 15, 50). The script pins every parameter so results are repeatable; the breakout's 60-session high uses split-adjusted `close` (a dividend back-adjustment fakes new highs on `adjusted_close`), and stale zero-volume carry-forward rows are dropped (rule 2.6).
3. Criteria (Yes/No each):
   1. **RSI 50–70** — 14-day RSI currently between 50 and 70 inclusive.
   2. **OBV rising** — On-Balance Volume trending up over the recent period.
   3. **Volume surge** — a recent session well above the 20-day average volume.
   4. **Golden Cross** — 50-day SMA crosses above 200-day SMA within the last 15 trading days.
   5. **MACD cross** — MACD line crosses above the signal line from below within the last 15 trading days.
   6. **Breakout** — close breaks above a major resistance level or key moving average.
4. Assign each stock's regime from the script's regime inputs and apply the Trending-DOWN rule (field notes).
5. `Total Score` = count of Yes (0–6). Rank highest to lowest and **remove 0-score rows**.

**Output:** table (ticker rows, six Yes/No columns, Total Score last), then one sentence per remaining stock on its strongest technical evidence, naming its regime. `executive_summary` with category `technical_analysis` may be cited as a cross-check, not as the scoring source.

#### Screen B — X/Twitter momentum (twitter_momentum)

X/Twitter data is **not in Distilla MCP today**. Follow the X / social discourse row: the `x-discourse` skill's scoped-search path (temporary), per stock, over the last 14 days.

- Confirm whether each stock shows **fresh** momentum or attention: a strengthening or newly trending narrative in in-window posts — not stale or fading chatter — scored per the X-leg field note.
- Capture concrete evidence: specific trending narratives, notable accounts or posts driving it, engagement data points, and the in-window post count.
- Supporting signal: Distilla `standard_event` type `Key Opinion Leader Mention of Company` in the last 30 days, one grouped call for all names (deduped, rule 2.6). Cite it as "KOL mention (Distilla)", not as X data.
- Every reachable name gets its X search before Step 3, with `web_search` — never a fast or snippet-only search variant (e.g. `web_search_fast`) that ignores `site:`. An unsearched name is never scored 0; a run with an unsearched reachable name is partial: name them and resume, never rank with them open.
- **Keep only confirmed Yes rows.**

**Output:** table — ticker, momentum = Yes, narrative summary, notable accounts/posts, engagement or sentiment evidence (Trend Velocity).

#### Screen C — Insider buying (insider_bull)

Check whether any director, C-suite officer, or >10% beneficial owner made an **open-market purchase** in the last 30 days (US Form 4 / Section 16, or the applicable regime for `region`).

1. **Candidates from Distilla:** `standard_event` type `Purchase or sale of shares by insiders`, `company_id IN [shortlist]`, `date ≥ today − 30`. For >10% owners also check `Purchase or sale of shares by major investors`, keeping only rows that are a >10% holder buying (not routine fund trades).
2. **Classify each row from its `name`** per the insider-leg field note (dedupe; drop sells, Form 144 plans and 12-month summaries).
3. **Get transaction details** (insider name/title, date, shares, price, value) per the Insider details row (Form 4 or regional filing first). Drop any purchase you can't confirm. Every candidate row ends confirmed or dropped with its reason; "not checked" is never a final state.
4. **Combine multiple purchases into one row per company:**
   - List each distinct insider name/title; show dates as a range (earliest–latest).
   - Same currency and security type → sum shares and value; show price as one range (lowest–highest).
   - Different currencies or security types (e.g. local ordinary shares vs. USD ADS) → keep separate labeled entries in the same cell: price `$40-50 & TWD350-400`; value `$4.2M & TWD120M`; shares `100k ADS & 200k common shares`.
5. **Keep only confirmed Yes rows.**

**Output:** table — ticker, insider purchase = Yes, insider/title, date, shares, price, dollar value; one combined row per company.

### Step 3 — Combine and recommend (synthesize_signals)

Build one table with a row for **every ticker appearing in at least one screen**:

| Column | Rule |
|---|---|
| Technical Score | Total Score from Screen A; 0 if absent |
| Twitter Momentum | 2 if in Screen B (Yes); 0 if absent |
| Insider Buy | 2 if in Screen C (Yes); 0 if absent |
| Total Score | Technical + Twitter + Insider (max 10) |

Use the sector from the Step 1 shortlist. Rank highest to lowest Total Score.

For up to the **top 6** names, recap the evidence behind the score: the specific technical signals met and the regime (from Screen A notes), the X/Twitter evidence (narrative, accounts/posts, engagement data), and the insider detail (insider/title, date, shares, price, value). Write **"None"** explicitly for any leg that didn't contribute.

## Completeness gate

Before answering, check each item and state PASS with the tool call that satisfied it; fix any failure before submitting. Don't show the checklist.

1. **Shortlist declared:** N, region, market-cap threshold, and as-of date come from a `company` / `stock_price` query; every sector assignment passed its fit check; the rundown printed before Step 1 and the review choice after Step 1 honored.
2. **Screens independent:** each screen evaluated the full shortlist; no screen's output narrowed another's input (Screen B's reachability rule excepted).
3. **Technical scores reproducible:** from `scripts/technical_signals.py` output; regime assigned from R² (never ADX) and the Trending-DOWN rule applied; 0-score rows removed; short histories shown as `--`.
4. **Only confirmed rows kept** in the X/Twitter and insider screens; X Yes rows are Bullish with Trend Velocity Medium or higher; every insider row is an open-market **purchase** with confirmed details, combined one row per company.
5. **Scores recomputed:** Total = Technical + Twitter (2/0) + Insider (2/0); top-6 recap writes "None" for any missing leg.
6. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called.
7. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†` and `‡`; every step run in full — none shortened or skipped for speed; Method notes ≤4 lines; each PASS names its tool call.

## Output

**Concise requests:** a user preference for brevity shortens prose, never the required sections or tables.

1. Resolved inputs and shortlist size (N as of date).
2. **Combined ranked table:** ticker, sector, Technical Score, Twitter Momentum, Insider Buy, Total Score.
3. **Top Candidates:** up to 6 names, each with its technical, X/Twitter, and insider evidence.
4. **Caveats:** short price histories, counter-trend signals held as "developing", X rows with Unknown velocity, insider rows dropped as unconfirmed, names marked "cannot reach the top 6", and any missing-tool replacements used.
5. **Source footnotes:** every `†` footnote (`† {source}, as of {date}; not Distilla data — methodology may differ.`).
6. **Method notes (≤4 lines):** as-of dates and market-cap gate check, price window and regime basis (R²), X search scope and in-window post counts, insider sources.

Include the Step 1 shortlist and the three screen tables in an appendix after the main output if the user wants the full audit trail; otherwise offer them.

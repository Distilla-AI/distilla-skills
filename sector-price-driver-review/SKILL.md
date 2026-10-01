---
name: "sector-price-driver-review"
description: 'Explain what drove stock prices across a sector, theme, or value chain over a recent period, find the pattern separating winners from losers, and turn it into today''s setup: layer verdicts, catalysts within the user''s trading horizon, and up to 3 long and 3 avoid/short ideas. Distilla MCP first; web search only for macro and breaking news. Use ONLY when the user asks for the forward-looking part for a sector or theme: "today''s setup", "trade ideas", "setups", "what''s the trade now", "how to position", "where''s the opportunity" after its recent moves (e.g. AI infrastructure, GLP-1, defense, uranium, EV supply chain, China internet) — including a question that asks both why it moved and what to do now. Do NOT use when the user only asks why a sector or value chain moved, what drove it, or which layer led or lagged, with no setup or ideas requested (use sector-price-driver-patterns); for a single-stock question; or for general market commentary with no sector focus.'
compatibility: "Target platform: Claude.ai. Requires the Distilla MCP connector, web_search / web_fetch, and Python code execution. Claude Code note: the same file runs there unchanged."
---

# Sector Price-Driver Review

Goal: turn "what moved this group and why" into **tested patterns** and **actionable setups for today**. The workflow is built around what Distilla does better than the open web: systematic universe discovery, consistent price data, dated attribution for every large move, and cross-company earnings commentary.

**Setup required.** A question that only asks why the group moved, what drove it or which layer led or lagged belongs to `sector-price-driver-patterns`, which runs Steps 0–5 and a layer read; this skill runs the same analysis and adds the Step 6 setup and ideas.

## Step 0: Clarify the scope before any research

Check the user's request for these parameters. Only ask about the ones that are missing or ambiguous; never re-ask something the user already stated or that is clear from the conversation.

| Parameter | Required? | Default if user says "you choose" |
|---|---|---|
| **Sector / theme / value chain** | Required, no default | — |
| **Lookback window** (what period to explain) | Required | 3 months |
| **Trading horizon** (how long they hold) | Required | Weeks (2–8 weeks) |
| **Region** | Optional | Global, US-listed emphasis |
| **Their holdings / watchlist** | Optional | None |

How to ask:
- Use the `ask_user_input_v0` tool (tappable options) when available. Put at most 3 questions in one call, each with 2–4 short options. Prioritize: sector/theme first, then lookback window, then trading horizon.
- If only the sector/theme is missing and it's open-ended, ask in one short prose question instead, since options can't cover every sector. You can offer 3–4 example themes as options plus let them type their own.
- Add a brief line before the tool call, e.g. "A few quick choices so the review fits how you trade:".
- End the turn after asking. Start research only after the user answers.
- If everything required is already stated, skip Step 0 entirely and say nothing about it.
- **Holdings / watchlist:** never assume a source. If the user mentions holdings or "my names" without listing them, ask for the tickers or where to find them (paste, upload, a list in this chat), then resolve them with `query_entity` on `company`.

Before starting research, restate the scope in one line, e.g. "**Scope:** AI infrastructure · last 3 months · weeks horizon · global."

## Data-source fallback

**Mode: Standard** — web figures allowed. If the user asks for a Distilla-only run, switch to **Distilla only**: every claim traces to a Distilla document or entity, no web, and missing = `--` or drop the item; the one exception is FX for currency conversion, from the FX row's web sources, dated, with source and date stated. Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v25: 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.8 · 3b)

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

#### 2.4 Prices, FX and valuation

- `stock_price.sell_side_target_price` is back-filled → **latest value only**, never a history.

#### 2.6 Data-quality traps

- **Text `value` fields** (`financial_data_point`, `consensus_data_point`, `valuation_multiple`): `query_entity` filters compare lexicographically ("100" < "99") → numeric cuts via `aggregate_entity` with `having`, or filter in Python.
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`earnings_calendar`:** filter and sort on `earnings_date` (there is no `date` field); rows from different `source`s (YFINANCE, FMP) can disagree for one company (AVGO: 9 vs 10 Dec 2026) — show both dates, each with its source, never pick one.
- **`price_explanation.price_move_percentage` is a decimal fraction**, identical to `stock_price.change` for the same date, despite the MCP doc's "% move". Filter a 5% move with |value| ≥ 0.05.
- **`stock_price` zero-volume rows:** half-day sessions can carry a genuine close with `volume = 0` (HSBC 0005.HK on the HKEX half-days 24 Dec 2025, 31 Dec 2025, 16 Feb 2026) → keep the close and the session; exclude the row from volume averages, turnover, RVOL and OBV. A zero-volume row with `change = 0` and the prior session's close on a full trading day is a **stale carry-forward** (Kweichow Moutai 600519.SS 5 Jul 2024; mainland China has no half-days) → drop it from returns, indicators and volume measures. Otherwise drop a row only if the exchange calendar shows the market closed.
- **`stock_price.market_cap` and `enterprise_value` are USD for non-US listings** while `stock_price.currency` is the local price currency (18 Sep 2026 rebuilds at ECB rates: Toyota US$226.8bn vs 228.3bn, Fast Retailing 131.5bn vs 132.3bn, Tencent 481.2bn vs 481.2bn; HSBC 24 Sep US$343.4bn vs 342.3bn). Convert the rule 2.3 rebuild to USD before the 10% check; never divide a vendor cap by a local price.
- **Implausible figures** (standard mode): a value far outside the company's own history, its peers or a cross-source check (a KU capex several times the `financial_data_point` line; a single-digit P/E on a large cap) → web-search the company's filing or results release to resolve it and cite the source (`†` in tables); unresolved → `--`, named in Method notes.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

#### 2.7 Evidence, provenance and output

- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker. · `‡` derived figure, formula in a footnote.
- **Comparability:** never compare NTM with LTM values; use the same web source per field across target and peers.
- **Public Library numbers** must trace to a named broker + title + date (from the summary); otherwise use **qualitatively only**.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

#### 3b Peer scope
- Peers **segment-matched**. `financial_data_point` and `financials_review` are company-wide → use `by_segment_financials` for conglomerates if available; otherwise **exclude or flag** (e.g., Samsung for foundry) and keep out of medians. Compare **growth rates / intensity**, not summed amounts. "Vs sector" only if the peer set matches the sub-industry (**temporary** until Distilla exposes sub-industry medians).

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Market cap, EV | Rebuild per rule 2.3 | `stock_price.market_cap` / `enterprise_value` only if within 10% of the rebuild | **None** — rebuild or `--` |
| FX rates | Not in Distilla MCP today | None (vendor `market_cap` ÷ local cap, rule 2.6, is a cross-check only, never an input) | **Latest date — Google Finance, tried first, before any other source or `--`:** `web_search` for `google.com/finance/quote/USD-{CCY}` (e.g. `USD-JPY`, `USD-KRW`, `USD-HKD`, `USD-CNY`, `USD-TWD`), then `web_fetch` the returned URL and read the rate and timestamp from the page — never the search snippet (it can be a stale crawl), and `web_fetch` refuses a typed URL. **Past date or month-end history:** Federal Reserve H.10 / FRED daily USD series (covers TWD, HKD, JPY, KRW, CNY) → ECB euro reference rates, crossed via EUR (no TWD); H.10 publishes weekly with a lag — check each series' latest observation; for dates after it, use ECB for that date. **Pair check:** `USD / JPY 157.2750` = JPY per USD → divide the local amount by it; a USD-per-local quote (`1 KRW = 0.00073785 USD`) is inverted first (1,355.3 KRW per USD). A rate that feeds a compared, ranked, valued or threshold-tested number is stated with pair, rate, source and timestamp (or date); only an illustrative conversion (a USD equivalent in prose, a floor cleared ≥2×) may use an approximate rate, written `≈ {rate}, as of {date}`. |
| Large price moves | `price_explanation` (`date`, `price_move_percentage` — decimal, rule 2.6, `explanation`) | `standard_event` and `file` `News Article` on the same dates | Company press releases → major newswires; `web_fetch` before citing |
| Ratings, target price | Broker notes: `get_library_document` `summary` (rating, TP, change old → new, date) of a note found by `search_public_library` `list`; consensus TP = **latest** `stock_price.sell_side_target_price` only | None — drop the item. `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) is discovery only: it names brokers and dates to list again with `brokers=[…]` (at most five per call), never a rating, TP or TP trajectory; an event no note matches is left out, and a note it conflicts with wins | **None** |
| Value-chain universe | `screen_drivers` (one full-scope call, `universe` = the screen code for the user's region — covered regions are the `company.hq_country` values at run time — or `["all"]`) → `get_screen_job` | `company_drivers`; `product`; product categories via `ku_cell` `groupProductCategory` (the `product` entity has no category field); `company.sector_id` → `sector` | **None** — the universe is Distilla-only; never add web-found or recalled names |
| Earnings-period fundamentals | `screen_earnings` (Step 1 `company_ids`, last 2 periods) → `get_screen_job` | `standard_event` (`Earnings announcement`) `earnings_summary`, period checked (rule 2.6 Events); `file` `Transcript` | Official filings — SEC EDGAR (US), HKEXnews (HK), EDINET / TDnet (JP), DART (KR), CNINFO (CN) → company IR |
| Beat / miss (paradox reactions) | `standard_event` `Earnings beat or miss` whose `name` names the reported period, dated on or after the confirmed print; pre-print "anticipated" and re-dated rows dropped | `price_explanation` `explanation` naming the result, corroborated by that event | Company press release (results vs the company's own guidance only; no web consensus) |
| Broker research | `search_public_library` (`doc_types = ["Research", "Podcast"]`, `tickers` or `brokers`, `mode = "synthesize"` for the layer read, `mode = "list"` to confirm a named broker action, `date_range` = the smallest bucket covering the lookback; Research field note); `get_library_document` for summary + tags (Research never returns full text) | `standard_event` (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side coverage initiation`) — discovery only: brokers to list again, never a rating or TP | **None** — broker reports are not reliably on the open web; a layer with no library note rests on its price and event evidence. |
| Earnings and event dates | `earnings_calendar.earnings_date`; `standard_event` (`Announcement of the next earnings release`) — confirmed from the event name or source (rule 2.6 Events) | None | Company IR events calendar |
| Macro triggers and calendar | `standard_event` (`Change in macroeconomic environment`) on the synchronized dates | `file` `News Article` on the same dates | Central-bank and statistics-agency releases and calendars (Federal Reserve, ECB, BoJ, PBoC, BoK; BLS and national statistics bureaus) → major newswires (Reuters, Bloomberg, Nikkei Asia); `web_fetch` before citing |
| Breaking news (last ~24 hours) | `file` `News Article` (`published_at` in the last day); `price_explanation` | `standard_event` by `date` | Company press releases → major newswires; `web_fetch` before citing |

**Field notes for this skill:**
- **Returns:** lookback-window, 1-month and year-to-date returns from `stock_price.adjusted_close` on the nearest trading day on or before each endpoint, in the listing currency (stated; no FX-translated returns). Distance from the period high uses the **closing** high — `stock_price` has no high / low. Half-day rows keep their close (rule 2.6).
- **Benchmarks:** layer and universe medians from per-company `stock_price` only. Distilla MCP has no index or ETF series, so vs-index and vs-ETF cells are `--`; never source a benchmark history from the web.
- **Peer scope (3b):** a one-segment conglomerate (e.g. Samsung Electronics in memory) is flagged and kept out of layer medians unless `by_segment_financials` shows the segment; layers compare returns and move counts.
- **Market cap:** per the Market cap row, used only to rank liquidity within a layer. The USD vendor `stock_price.market_cap` (rule 2.6), latest value only (rule 2.3), is usable for that ranking only after 2–3 names per listing region pass the rule 2.3 rebuild within 10%.
- **Target-price upside:** latest `sell_side_target_price` (rule 2.4) ÷ latest close − 1, both from the same listing (an ADR target on the ADR close).
- **Large moves:** `price_explanation` with |`price_move_percentage`| ≥ 0.05 (0.03–0.04 for low-volatility sectors), paged by date, deduped, each claim checked to fall in the window (rule 2.6 Events). Analyst-action tags need a broker note (a Research list row from that broker, report type `Estimates, Rating, Price Target Changes`) dated on or just before the move date; a `Sell-side Rating Action` event alone is a lead, never the tag.
- **Paradox reactions:** a beat or miss counts only from the Beat / miss row (period named, dated on or after the confirmed print); never recomputed from consensus here.
- **Research (layer level):** one `search_public_library` call per layer, `mode = "synthesize"`, `doc_types = ["Research"]`, `tickers` = the layer's names, `date_range` = the smallest bucket that covers the lookback (`30d` for one month; `180d` or `1y` beyond 90 days, stated) — about 3k tokens with dated sources. The answer is a sample, not a sweep: use it for the layer's narrative, and trace any figure or broker view to its source with `get_library_document` (title, broker, date). `mode = "list"` only to confirm a named broker action (per ticker and broker, smallest bucket). Library evidence supports or challenges the layer thesis; price, events and drivers stay the primary evidence.

**Provenance:** markers, the `†` footnote and one web source per field across the universe follow rule 2.7. The template's **(Distilla)** / **(Web)** tags stay for prose; a web figure in the layer table also carries `†`. No Method notes footer: the template's one-line caveat carries data gaps (output contract kept).

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Returns, medians and move counts run in Python on the retrieved rows — numbers only; patterns, verdicts and ideas stay with you.

## Step 1: Build the universe from Distilla, not memory

Read `references/distilla-notes.md` before the first Distilla call. It lists the entities, field quirks, and limits that cause the most common mistakes.

1. Run `screen_drivers` once at full universe scope (`universe: ["all"]`, or the user's region) with a criterion describing dependence on the theme, e.g. "revenue growth depends materially on [theme] as a primary driver". Raise `top_n` for breadth (up to 100 — a higher value errors) instead of splitting into parallel sector calls. Poll `get_screen_job` until done. **Retry coverage:** a `universe` call scores only part of the scope — re-run the same criterion on `result.coverage.not_evaluated_company_ids` as `company_ids`, in chunks of up to 448 IDs (full coverage live; coverage is not scoring accuracy — see False-negative re-score), and merge the new matches into `ranked` before grouping; a residual that stays unscored is counted in the caveat line. **Sector sweep:** a `universe` call can under-match even when `not_evaluated_company_ids` is empty. For every Distilla `sector_id` with ≥ 3 matches in `ranked`, take that sector's non-delisted companies (`query_entity` on `company`), filtered to the user's region by `company.hq_country` where one was given, drop those already matched, and re-run the same criterion on the rest as `company_ids` (≤ 448 per call); merge only matches scoring ≥ 2 into `ranked` before grouping, and count the added names in the caveat line ("N names added by sector sweep"). Distilla-only: no recalled or web names. **False-negative re-score:** a batched screen can score a clear match 0 while coverage reports it scored (TSM: 0 in `["all"]` and in a 297-ID sweep, 3 alone; NVDA and AVGO: 0 in a 25-ID chunk; 10-ID chunks held in 6 of 6 runs, 3 fully dense; 27 Sep 2026). A batched 0 is not proof of a non-match. After the sweep, for every `sector_id` with ≥ 3 matches, take that sector's 3 largest unmatched names (vendor `stock_price.market_cap` on each listing region's latest date, `MAX(date)` grouped by `company.hq_country` — ordering only), pool them across sectors and re-run the same criterion on them in chunks of ≤ 10 IDs (`top_n` 10); launch every re-score job before polling any. Smaller unmatched names are not re-scored — layers keep the most liquid names. Merge scores ≥ 2 into `ranked` before grouping and count them in the caveat line ("N names added by re-score"). Distilla-only.
2. Group the ranked companies into **value-chain layers** based on their driver profiles and product categories (query `company_drivers`, `product`, `sector`, or product categories via `ku_cell` `groupProductCategory` as needed). Choose layers that fit the theme; e.g. for a supply chain: end demand/spenders → core product → components/inputs → equipment/tools → enablers. Segment-match each layer (3b).
3. Keep the 3–6 most relevant, liquid companies per layer. Include non-US names when relevant. State the grouping logic in one line. Aim for roughly 15–30 companies total.
4. If the user supplied holdings, make sure they're in the universe and flag them throughout.
5. **Checkpoint:** state one working line before Step 2 (not part of the final output) — `Universe: N names in M layers; retry +a, sweep +b, re-score +c`. If the turn ends before the output, the next turn resumes at the first unfinished step and reuses this universe; never re-run Step 1.

## Step 2: Quantify performance

From `stock_price` (see distilla-notes for the decimal scale and trading-day handling, and the field notes above):
- Lookback-window return and a 1-month return for every company.
- Distance from the period closing high, market cap (Market cap row), and upside to the latest `sell_side_target_price`.
- Layer medians and the universe median (no index or ETF series; vs-index `--`).

Build this as **working data for your own analysis, not for the output**. You'll use it to test patterns and support ideas; the reader sees only the conclusions it supports. Sanity-check outliers: a return that contradicts the daily moves (e.g. a big decline despite many large up days) may indicate a split or data issue. Check it against `stock_price.split` and `dividend` on the window's dates and the compounded daily `change` values; if it stays unresolved, flag it (price history has no web rung).

## Step 3: Attribute the moves

Pull `price_explanation` for the universe over the window and filter to large moves (Large moves note; lower the threshold for low-volatility sectors such as utilities or staples).

Classify every large move into one bucket:
- **Macro / sector** (includes "no company-specific driver")
- **Earnings / guidance**
- **Deal / partnership / product**
- **Analyst action**
- **Dilution / insider / legal / regulatory**

Compute per layer (working data; the output uses only what supports a finding):
- **(a) Beta share:** the percentage of large moves tagged macro/sector. A high share means the layer trades as a group; stock-picking matters less than the factor.
- **(b) Synchronized days:** dates when most of the universe moved in the same direction, with the trigger. Use the Macro triggers row (Distilla first; the web for triggers Distilla doesn't name).
- **(c) Paradox reactions:** stocks that fell on beats or rose on misses (Beat / miss row). These reveal what's priced in.

Treat individual explanations with care: they're machine-generated and sometimes mislabel periods or repeat one event on several dates. Rely on patterns across many explanations more than on any single one.

## Step 4: Check the fundamentals against price

1. Run `screen_earnings` on the universe's company IDs (last 2 reporting periods) for the fundamentals most relevant to the theme. Default criteria: supply constraints and pricing power; guidance raised versus cut; capex or investment plans; competitive, regulatory, or geopolitical risk. Adjust wording to the sector. A batched 0 can be a false negative at any batch size (29 Sep 2026): no layer tone or divergence read rests on missing matches alone, and where screen results feed a read, the caveat line states "batched `screen_earnings` 0s may be false negatives".
2. Compare management tone with price action. Flag **divergences**: fundamentals improving while the stock fell (possible opportunity), or fundamentals softening while the stock rose (possible risk).
3. Use `search_public_library` (Broker research row; Research field note) for recent research reports and podcasts that support or challenge each layer's thesis; Research documents return summaries only, and numbers follow rule 2.7 (Public Library).

## Step 5: Identify and test the pattern

- State 2–3 patterns that explain the gap between winners and losers.
- **Test each against the Step 2 table.** List exceptions explicitly. Drop any pattern the returns don't support, even if it's a compelling narrative. This step is what separates this review from a story.
- Distinguish lookback-window behavior from year-to-date behavior; they often differ.

## Step 6: Today's setup

1. From the Earnings and event dates row, list catalysts for the universe within the trading horizon (Step 0; default 2–8 weeks); `earnings_calendar` dates are confirmed by event names (rule 2.6 Events). Add macro events (central bank meetings, key data releases) from the Macro triggers row.
2. Label each layer with the template's verdict — **Oversold**, **Crowded**, **Mixed**, **Avoid** or **Neutral** — and a one-line reason.
3. Give up to **3 long ideas and 3 avoid/short ideas**, sized to the user's horizon. For each: thesis, catalyst and date, main risk, and what would invalidate it. If the evidence doesn't support 3 of each, give fewer and say why.
4. If holdings were supplied, note which patterns each holding is exposed to.

## Completeness gate

Before answering, check each item and state PASS with the tool call that satisfied it; fix any failure before submitting. Don't show the checklist.

1. **Universe from Distilla:** one full-scope `screen_drivers` call, its `not_evaluated_company_ids` retried as `company_ids`, and the sector sweep run (sectors with ≥ 3 matches, region-filtered, score ≥ 2 merged) (Step 1) — the PASS names the retry call and the sweep call; the false-negative re-score run (each qualifying sector's 3 largest unmatched names, pooled in ≤ 10-ID chunks) and named; no qualifying sector's 3 largest unmatched names left unscored; no web-found or recalled names; layers segment-matched, conglomerates excluded from medians or flagged (3b).
2. **Patterns tested:** every finding was checked against the Step 2 returns, with exceptions named; unsupported patterns dropped.
3. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called; no index or ETF series (per-company `stock_price` only).
4. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; no markers beyond `†` and `‡`; every step run in full — none shortened or skipped for speed; each PASS names its tool call.
5. **Research:** one synthesize read per layer on the smallest bucket covering the lookback; library figures and broker views traced to broker / title / date with `get_library_document`; a named broker action confirmed by a `list` row.
6. **Output contract:** the template's hard rules — 350–500 words, one layer verdict table, no per-stock tables or chronology.

## Output

Follow `references/output-template.md` exactly, including its example and its hard rules (length, the single layer verdict table, no chronology or methodology narration, the closing watch item, caveat and data offer). The core principle: **synthesize, don't report** — patterns, verdicts and ideas, each backed by the one or two data points that make the case, not reworded raw data. **Concise requests:** a user preference for brevity shortens prose, never the required sections, tables or verdict line. Beyond the template:
- Concise language; **bold** keywords and conclusions.
- Tag claims **(Distilla)** or **(Web)** sparingly, at the end of a finding rather than on every number; cite web claims with the platform's citation format.

Before sending, check every number in the draft: does it support a specific finding or idea? If not, delete it.

## Sourcing rules

- Distilla first for all company-level data and narrative (Data-source fallback ladder); the web only for macro (rates, central banks, commodities, geopolitics), news from the last ~24 hours (Distilla's news can lag a few hours) and gaps Distilla leaves, in the field table's source order.
- Don't fill numbers from memory. If data is missing, say so.

---
name: "daily-brief"
description: Per-watchlist-company summary of important not-yet-priced events from yesterday or today. Use when the user asks for a "morning note", "daily brief", "what's moving today", or any watchlist-scoped catalyst/news check for today or this morning. Watchlist-only; companies with no qualifying event are excluded entirely. Do NOT use for sector-wide or universe-wide price movement queries ("which stocks in X moved yesterday") — those should go to `stock-screener`.
---

**Runtime requirements:** Requires Distilla MCP tools, web search / page fetching (`web_search` / `web_fetch` or equivalent host tools), and Python code execution. Map the tool names in these instructions to the host's equivalent capabilities while preserving source restrictions and required checks. If tool loading is deferred, use the host's discovery mechanism; MCP tool prefixes may vary.

**Common failure** — failure modes to guard against before output:
1. Using the article's published date as the event date. The article is *about* an event that may have happened earlier; the event date is inside the body.
2. Adding placeholders, excluded-names lists, or narrative intros — both sections show only qualifying companies.
3. Including high-salience events (earnings, M&A, big regulatory) announced during or before yesterday's regular session on the rationale that "the full reaction is expected today" — the stock has already traded on them. Drop. A catalyst that broke after yesterday's close (e.g. last night's post-close earnings print) with no full session since is in, subject to the direct-evidence test (Gate 1).
4. **Including events whose price reaction has already occurred** — if the article OR your own framing describes the stock as having "surged / plunged / popped / jumped / rallied / sold off / hit record high / hit all-time low / +X% / −X%" *in response to the catalyst*, that price action IS the market pricing it. Gate 1 fails by definition. Drop, regardless of when the catalyst broke.
5. **Summary written as price-action narration** — Summary that reads like a market wrap ("Shares surged 40% on earnings beat") instead of a forward-looking event/implication. Reframe to event-language or drop.

## System Prompt

You are a buy-side analyst running a morning filter to surface only not-yet-priced material events from a watchlist. Two principles govern every output:

1. **Assume pricing efficiency** — markets absorb high-salience events in pre-market and after-hours; by today's open, anything from yesterday's regular session is already in the price. A >5% pre-market or after-hours move directly attributed to the catalyst means the stock has *already traded through it*, even if the regular session has not yet opened. When in doubt, drop rather than include.
2. **Direct-evidence test beats time test** — if there is any evidence that the stock has already reacted to the catalyst (price-move language in the article body, your own Summary describing the move, news framed as a market recap), Gate 1 fails regardless of when the event broke.

## Window

Events from yesterday or today only. Older items don't qualify, even if referenced in fresh articles.

## Two gates

Include an event only if **both** hold:

1. **Not yet reflected in price** — include only if **all** hold:
   - **Time test** — event is scheduled or breaking **today** (intraday or upcoming session today), OR catalyst broke **after yesterday's regular close** (post-market / overnight) and the stock has had no full session of post-catalyst trading.
   - **Direct-evidence test** — no evidence the stock has already reacted: article body must NOT describe the stock as having *surged / plunged / popped / jumped / rallied / sold off / hit record high or low / moved +X% or −X%* in response to the catalyst. Pre-market or after-hours move >5% attributed to the catalyst = priced; drop.
   - **Self-framing test** — your own Summary or 1-line event must NOT narrate past price action. If the most natural way to describe it starts with "Shares surged…" or "Stock dropped…", the event is priced; drop or reframe.

   Anything announced during or before yesterday's regular session → **drop**, even if you believe the market underreacted. Forward-rationalization phrases (*"expected during today's session"*, *"will be digested today"*, *"market will price in today"*) → drop it.
2. **Materially impactful** — moves the stock once digested (earnings results, M&A, regulatory, guidance change, major product/clinical milestone, large contract, leadership). **Drop all analyst rating output** (consensus ratings, broker upgrades/downgrades, target price changes), routine PR, and generic price commentary.

Companies without a qualifying event: **exclude entirely** — no placeholder.

## Data-source fallback

**Mode: Standard** — web sources allowed, on the ladder below.

**User inputs first.** The watchlist comes **from the user**: ask for the tickers or where to find them (paste, upload, a list in this chat, or a project file). Distilla MCP exposes no watchlist (`watchlist_data` is not an entity); never assume a source.

Take each input from the first rung that returns usable data; move down **only after the higher rung was queried and came back empty** — never to save a call:

1. **Distilla MCP** — the tool or entity the step names.
2. **Other Distilla data** for the same field (table below).
3. **Open web** — `web_search`, then `web_fetch` on a returned URL, in the table's source order.

Never call any other connector, even when one is connected.

### Distilla data rules (shared block v25: 2.6, 2.7, 2.8)

#### 2.6 Data-quality traps
- **Events:** dedupe `standard_event`, across types by meaning too (one broker action can appear as Rating, Target Price and Estimates rows in varied wording); drop stale re-dated re-reports and pre-print "anticipated" beat/miss rows; `standard_event.date` = **ingestion date** except `Earnings announcement` — treat it as "no earlier than" and confirm the real date from the event name or source; `Dividend Announcement` rows repeat and carry no ex-date (discovery only); `earnings_summary` can leak other-period content; verify each `price_explanation` claim falls in the window. Query filters have **no "not in"** — filter in Python.
- **Event attribution:** a `standard_event` row filed under one `company_id` can describe another company (Intel rating actions by Northland and BofA under NVDA's `company_id`, 8–11 Sep 2026) — keep a row only when its `name` names the company queried or no other company; drop rows that name another company, then dedupe.
- **`earnings_calendar`:** filter and sort on `earnings_date` (there is no `date` field); rows from different `source`s (YFINANCE, FMP) can disagree for one company (AVGO: 9 vs 10 Dec 2026) — show both dates, each with its source, never pick one.
- **`price_explanation.price_move_percentage` is a decimal fraction**, identical to `stock_price.change` for the same date, despite the MCP doc's "% move". Filter a 5% move with |value| ≥ 0.05.
- **Web rung:** `web_fetch` the page before writing `--`; snippets rarely contain figures.

#### 2.7 Evidence, provenance and output
- **Markers** (no others; flags such as conglomerate-blended or not covered are written in words): `†` web figure in a table cell — `† {source}, as of {date}; not Distilla data — methodology may differ.`; in narrative, the inline citation with its date serves as the marker.
- **Full workflow:** run every step the skill defines; never shorten, skip or summarize a step for speed. A step blocked by a missing tool or empty data is a gap stated in Method notes.
- **Gate:** stays internal, but **each PASS names the tool call** that satisfied it.

| Field | Distilla (use first) | Next fallback | Web fallback, in order |
|---|---|---|---|
| Watchlist / "my names" | Tickers the user gives (paste, upload, list in this chat, a project file), resolved with `query_entity` on `company` | None | **None** — ask the user; never assume a source |
| News and corporate events | `file` (`source_type = "News Article"`: `title`, `summary`, `url`); `standard_event` filtered by `company_id`, `type`, `date` | `price_explanation` on the same dates | Company press releases → major newswires; `web_fetch` the article before citing it |
| Large price moves | `price_explanation` (`date`, `price_move_percentage` — decimal, rule 2.6, `explanation`) | `standard_event` and `file` `News Article` on the same dates | Company press releases → major newswires; `web_fetch` before citing |
| Price, returns, volume | `stock_price` (`adjusted_close`, `volume`, `currency`; `change` is a decimal fraction) | None | Current quote only: Yahoo Finance. History: **None** — leave `--`. |
| Earnings and event dates | `earnings_calendar.earnings_date`; `standard_event` (`Announcement of the next earnings release`) | `standard_event` (`Shareholder meetings`, `Specialized Presentation or Report`) | Company IR events calendar |

**Field notes for this skill:**
- **Watchlist (Step 1):** resolve each user ticker with one `query_entity` on `company` (`symbol` exact, or `name` with `ilike`; `hq_country` `HK` and `CN` are distinct). Ask the user to confirm a ticker that does not resolve before the scan; never guess one.
- **Window and session:** "yesterday", "today" and "regular session" are judged on each listing's own exchange calendar and local time (`company.hq_country`).
- **Candidate pull (Step 2):** `file` (`source_type = "News Article"`, `published_at` in the window) and `standard_event` (`date` in the window) with `company_id` IN the resolved IDs, paged until `truncated = false`. `standard_event.date` is the ingestion date (rule 2.6 Events), so an in-window row is a lead, not an in-window event — Step 3 dates it from the body or `name`. Drop the four sell-side types (`Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side Estimates Action`, `Sell-side coverage initiation`) in Python (Gate 2; filters have no "not in").
- **Web:** `web_fetch` on a `file.url` reads a Distilla document — no `†`. `web_search` runs only when the user names breaking news (Step 2); an item found that way carries `†`.
- **Already-priced check (Gate 1):** pre-market and after-hours prices are not in Distilla MCP today (`stock_price` holds one close per session) → the article body, else the Yahoo Finance current quote (`†`, as-of time). A listing that has traded a full session since the catalyst (Asia listings often have, by the US morning) fails the time test; its `stock_price.change` (decimal) and any same-date `price_explanation` confirm the reaction. Latest rows lag by region (KR 23 Sep on 25 Sep 2026): a missing row does not prove no session was held — check the exchange calendar.
- **Scheduled events today:** `earnings_calendar` dates confirmed by event names (rule 2.6 Events); a vendor date alone is "no earlier than".
- **No Method notes footer:** the output pattern has no intro or outro.

**Provenance:** markers and the `†` footnote follow rule 2.7, on every web-sourced line; the footnote is required although the output has no intro or outro. Inline citations are suppressed, so a web-sourced line in narrative also takes `†`.

**Missing tools:** this skill names no legacy tools; never stall on a missing one. Date filtering and dedupe run in Python on the retrieved rows — facts only; the gates and the wording stay with you.

## Required research plan

**Step 1 — Pull watchlist:** ask the user for the watchlist tickers (Watchlist row); if none are given, stop. Resolve them with one `query_entity` on `company`.

**Step 2 — Per-name news scan:** pull candidates for every watchlist company over [yesterday, today] per the Candidate pull note (`file` `News Article` and `standard_event` by `company_id`). Skip web search unless the user names breaking news.

**Step 3 — Extract event date:** from each candidate's article body. Drop if no body anchoring, or date outside yesterday/today. *Article body:* `file.summary` first; `web_fetch` the `file.url` when the summary lacks the event date.

## Self-review (per candidate, before output)

- Ticker + 1-line event + quote the article body sentence anchoring the date + event timestamp (today / yesterday post-close / yesterday in-session).
- **Gate 1 — time test**: event happened during or before yesterday's regular session? Yes → drop.
- **Gate 1 — direct-evidence test**: does the article describe the stock as already moved (surged / plunged / popped / jumped / rallied / sold off / record high / record low / +X% / −X%) in response to the catalyst? Or is there a >5% pre-market / after-hours move attributed to it? Yes → drop.
- **Gate 1 — self-framing test**: does your Summary or 1-line event narrate past price action ("Shares surged…", "Stock dropped…", "Closed at record")? Yes → reframe to forward event-language or drop.
- **Gate 2**: analyst rating output, target-price change, or routine PR? Yes → drop. An earnings release is judged by Gate 1 alone: last night's post-close print passes the time test; one from yesterday's regular session or earlier fails it.

Output kept rows only; never invent items. If nothing survives, use the empty-output line in Output.

## Output

Do NOT output any commentary or note about excluded companies or events. **Concise requests:** a user preference for brevity shortens prose, never the required sections or tables.

Follow below pattern exactly, with no narrative intro or outro.

If no companies qualify, ignore the section headers and acknowledge the empty output with a final line: "No high impact events for watchlist companies today."

# Watchlist Brief — {date}

## Summary
**{Ticker}** — key forward-looking takeaway (the *event* or its forward implication; never a description of past price action).

## Company Updates
**{Ticker}** — {1-2 sentence event} *(event date)*.

## Completeness gate — REQUIRED before submitting the final answer

Before submitting:

- For each check below, state PASS or FAIL with cited evidence — the tool call and its filters, a specific section in your draft, or a named entity. A PASS without specific cited evidence counts as FAIL.
- For every FAIL, execute the implied recovery — run the missing tool, build the missing section or table, fill the missing cell, or write the missing component — before proceeding.
- Do not include the PASS/FAIL list in the submitted final answer.

1. **Watchlist from the user:** tickers obtained from the user and resolved with `query_entity` on `company` before any news search; if none, output stops.
2. **News searched per company:** candidates pulled for every watchlist company over [yesterday, today] (Candidate pull note, paged until `truncated = false`).
3. **Both gates applied:** Each included event passed Gate 1 (time test + direct-evidence test + self-framing test — no past price-action language anywhere) and Gate 2 (materially impactful); analyst rating output dropped.
4. **No placeholders:** Excluded companies produce no output row; if nothing qualifies, the output is only the line "No high impact events for watchlist companies today."
5. **No price-action narration:** Summary and Company Update lines describe the event or its forward implication, never past price moves. Banned vocabulary in output: "surged / plunged / popped / jumped / rallied / sold off / hit record high / hit all-time low / +X% / −X%".
6. **Data rules:** every input came from the highest rung with data, under the Data-source fallback ladder and the pasted Distilla data rules as written; no connector called.
7. **Visible lines and workflow:** every caption, stated rate, label and footnote the steps and output format require is present; every web figure, in a table or in narrative, carries `†` (no inline citations); no markers beyond `†`; every step run in full — none shortened or skipped for speed; each PASS names its tool call.

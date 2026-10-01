# Distilla MCP working notes

Read before the first Distilla call. These are the quirks that caused errors in earlier runs.

## Setup
- Distilla tools may be deferred. Load them with `tool_search` (e.g. query "Distilla queryable entities price move") before calling.
- Call `list_queryable_entities`, then `describe_queryable_entities` for any entity whose fields you haven't confirmed in this conversation. Don't guess field names. `describe` accepts a comma-separated list, so describe several at once.
- Entities useful for this skill: `company`, `company_drivers`, `sector`, `product`, `product_category`, `ticker`, `stock_price`, `price_explanation`, `earnings_calendar`, `standard_event`, `ku_cell`, `executive_summary`.

## Scale and units (most common mistake)
- `stock_price.change` and `price_explanation.price_move_percentage` are **decimal fractions** (-0.132 = -13.2%; rule 2.6): filter a 5% move with |value| ≥ 0.05, not `> 5`.
- Use `adjusted_close` for returns so splits and dividends don't distort them. Market cap, closing highs and benchmarks: SKILL.md field notes.

## Limits and pagination
- `price_explanation` max 300 rows per call; `stock_price` max 100; `ticker` max 100. A full page returns `truncated: true`.
- For price explanations over a multi-month window, sort by date ascending, then re-query starting the day after the last returned date until `truncated` is false.
- Large results may be written to a file instead of returned inline. Parse the file with a short Python script (the JSON may be wrapped as a list whose first element has a `text` field containing the JSON string).
- To get period returns efficiently, query `stock_price` with `date IN [start, end]` for all symbols in one call. Use actual trading days; if a date returns no rows (weekend/holiday), move to the nearest prior trading day.

## Screens
- `screen_drivers` and `screen_earnings` are **asynchronous**: they return a `job_id`. Poll `get_screen_job` until status is `done` or `error`.
- Issue **one** call at full scope rather than several sector-narrowed calls; raise `top_n` for breadth and group from the `ranked` list.
- Pass exactly one of `company_ids` or `universe`. For Step 4, pass the company IDs from Step 1.
- Batched `screen_drivers` can return silent false negatives with clean coverage fields (TSM 0 in `["all"]`, 3 alone; NVDA and AVGO 0 in a 25-ID chunk; 27 Sep 2026). Before treating a batched 0 as a non-match, re-score each qualifying sector's 3 largest unmatched names in ≤ 10-ID chunks — launch every job, then poll (SKILL.md Step 1).
- `screen_drivers` = durable thesis-level drivers. `screen_earnings` = what management said in recent filings and calls. Neither is for dated price events; use `price_explanation` for those.

## Data-quality caveats
- Price explanations are LLM-generated. Known issues: wrong fiscal-period labels, muddled EPS figures, and the same event (e.g. an investment announcement) attributed to several different dates.
- "No company-specific driver" is frequent and meaningful: count it as a macro/sector move.
- Cross-check any single explanation that a conclusion depends on: a second Distilla entity first, then the web (Large price moves row).
- Event dates: rule 2.6 Events (`standard_event.date` is the ingestion date).

## Library
- `search_public_library` finds research reports and podcasts (news is `file` `News Article`); `get_library_document` reads one. Research documents omit full text by provider terms; use the summary.

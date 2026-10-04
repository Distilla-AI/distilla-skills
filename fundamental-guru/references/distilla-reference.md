# Distilla MCP reference

Verified against the live Distilla MCP schema (25 Sep 2026). Read this before the first Distilla call. Re-run `describe_queryable_entities` if a field here errors — the schema is the authority. The skill's own Distilla data rules (the shared block in `SKILL.md`) win where this file is less specific. Call only Distilla MCP, web search / page fetch (`web_search` / `web_fetch` or the harness's equivalents) and Python — never any other connector, even when one is connected.

## Contents
1. Setup and tools
2. Entities and key fields
3. Units, scale, and dates (most common mistakes)
4. Query syntax and limits
5. `standard_event` types
6. Knowledge units (KUs)
7. Sector taxonomy
8. Other enumerated values
9. Known gaps and data-quality caveats

---

## 1. Setup and tools

Distilla tools may be deferred. If the harness defers tool loading, load them with its tool-search mechanism (e.g. query "Distilla queryable entities") before the first call. Some harnesses prefix MCP tool names (e.g. `mcp__Distilla__<tool>`).

Call `list_queryable_entities`, then `describe_queryable_entities` (comma-separated, e.g. `company,stock_price,standard_event`) once per conversation before querying. Don't guess field names.

| Tool | Use for | Notes |
|---|---|---|
| `query_entity` | Row reads with filters, joins, sort | Returns one page; `truncated: true` + `next_hint` when more exist |
| `aggregate_entity` | GROUP BY with COUNT/SUM/AVG/MIN/MAX | `filters` = WHERE, `having` = HAVING |
| `screen_drivers` | Durable, thesis-level exposure ("what drives this company") across a universe | Async. Backed by `company_drivers` |
| `screen_earnings` | What management said in recent filings/calls (`periods`, default 4) | Async. Backed by `ku_cell` from earnings documents |
| `get_screen_job` | Poll a screen job until `status` is `done` or `error` | Result has `summary`, `matches` (top_n), `ranked` (full list), `coverage` |
| `search_public_library` | Broker research and podcasts; `mode` = `synthesize` (default) or `list` | Returns `answer` + `sources[]` with `document_id` |
| `get_library_document` | Metadata, summary, tags for one `document_id` | Research docs never include full text |

**Screen rules** (`screen_drivers`, `screen_earnings`):
- Pass exactly one of `company_ids` (integer IDs from `company`) or `universe` (region codes: `all`, `us`, `cn`, `jp`, `hk`, `kr`). `company_ids` wins if both are set.
- Issue **one call per distinct criterion** at full scope. Do not split one question into parallel sector-narrowed calls; raise `top_n` for breadth and group from `ranked`.
- Pick one screener per information need. Use `screen_drivers` for structural exposure, `screen_earnings` for recent disclosed commentary. Run the second only as a fallback if the first returns nothing.
- Neither screener is for dated events or price moves — use `standard_event` and `price_explanation` for those.

## 2. Entities and key fields

| Entity | Key fields | Use |
|---|---|---|
| `company` | `id`, `name`, `symbol`, `hq_country`, `sector_id`, `summary`, `is_delisted` | Universe definition (max 1000 rows/page) |
| `sector` | `id`, `name` | Taxonomy (see section 7) |
| `ticker` | `symbol`, `company_id` | Symbol → company mapping |
| `stock_price` | `symbol`, `company_id`, `date`, `close`, `adjusted_close`, `volume`, `change`, `market_cap`, `enterprise_value`, `sell_side_target_price`, `currency` | Prices, returns, size filter |
| `price_explanation` | `symbol`, `company_id`, `date`, `price_move_percentage`, `explanation` | Why a stock moved on a date (max 300 rows/page) |
| `standard_event` | `type`, `name`, `date`, `company_id`, `file_id`, `earnings_summary` | Dated corporate events (see section 5) |
| `earnings_calendar` | `company_id`, `earnings_date`, `timezone`, `source` | Upcoming/past earnings dates |
| `company_drivers` | `company_id`, `symbol`, `content`, `updated_at` | Synthesized driver profile (Type / Topic / Causal Relationship / Support / Current vs. Past) |
| `executive_summary` | `company_id`, `name`, `category`, `content` (HTML) | Pre-built company summaries (see section 8) |
| `knowledge_unit` | `id`, `name`, `cell_type`, `group_type`, `description` | KU definitions (see section 6) |
| `ku_cell` | `ku_id`, `group_company_id`, `cell_time_period_id`, `cell_standard_event_id`, `cell_as_of_date`, `content` (JSON), `published_at` | KU values per company/period |
| `product` | `company_id`, `name`, `description` | Named products — evidence for "does this company sell X" |
| `product_category` | `id`, `name`, `sector_id` | Companies sharing a category are competitive peers |
| `time_period` | `company_id`, `start_date`, `end_date`, `duration`, `fiscal_year`, `fiscal_quarter`, `provenance` | Fiscal periods for actuals (`provenance = "financials"`) and consensus (`"consensus"`). Anchor on the `end_date` month; `fiscal_year` labels and `provenance = "filing"` dates can be wrong |
| `file` | `source_type`, `published_at`, `company_id`, `title`, `summary`, `url` | Filings, transcripts, news (see section 8) |
| `financial_data_point` | `time_period_id`, `financial_metric_id`, `value` (text), `unit`, `formatting` | Financial actuals, one row per metric per period (max 300 rows/page). Joins only `time_period` (alias `T`) and `financial_metric` (alias `M`) — filter `T.company_id`; no `company` join |
| `financial_metric` | `id`, `name`, `display_name`, `category` | 219 line-item and ratio definitions, e.g. `income_statement_sales`, `cash_flow_capital_expenditures`; no growth-rate or total-debt lines |
| `consensus_data_point` | `time_period_id`, `consensus_metric_id`, `value` (text), `consensus_date`, `currency` | Consensus estimates, weekly vintages (max 300 rows/page). Joins `time_period` (`T`) and `consensus_metric` (`C`); period from `T.end_date` and `T.duration` (annual and Q4 rows share `end_date`), never `consensus_date` |
| `consensus_metric` | `id`, `name`, `category`, `statistics` | `<category>_<statistic>`, e.g. `eps_gaap_mean`, `sales_nest` (12 categories × 6 statistics) |
| `valuation_multiple` | `company_id`, `type`, `valuation_date` (text `YYYY-MM-DD`), `value` (text) | Weekly LTM / NTM multiples, e.g. `NTM_Pe_Med_W`, `LTM_Ev_Ebitda_Med_W` (22 types; banks carry no EV types) |

## 3. Units, scale, and dates

- **`stock_price.change` is a decimal fraction**: `0.05` = +5%. Filter a >10% drop with `change < -0.10`, not `< -10`.
- **`price_explanation.price_move_percentage` is also decimal-scaled** (e.g. `0.0325` = +3.25%) despite its name.
- **`stock_price.market_cap` and `enterprise_value` are USD for every listing**, while `currency` describes `close` only (rebuilds within 0.6% for Toyota, Fast Retailing, Tencent and HSBC, 18–24 Sep 2026). Never divide a vendor cap by a local price. Apply a universe size threshold through the skill's market-cap gate (sub-block 3f).
- `close` / `adjusted_close` are in the listing `currency`. Use `adjusted_close` for returns and indicators.
- **Latest trading date differs by region** (holidays). Get `MAX(date)` per `company.hq_country` with `aggregate_entity` before building a size-filtered universe; don't assume one date fits all.
- **Text `value` fields** (`financial_data_point`, `consensus_data_point`, `valuation_multiple`) compare lexicographically in `query_entity` filters — use `aggregate_entity` with `having`, or filter in Python. `financial_data_point` values carry thousands commas; consensus amounts are in millions with no unit field.
- Present percentages to the reader as percent-scale (`3.40%`), never raw decimals.
- Symbol formats: US `AAPL`; Japan `7203.T`; Hong Kong `0700.HK`; Korea `005930.KS`.

## 4. Query syntax and limits

- **Joins:** `joins: [{"relation": "company"}]`, then select or filter joined fields with dot notation, e.g. `company.symbol`, `company.hq_country`. Works on any entity with a `company_id` join target.
- **Operators (observed working):** `=`, `!=`, `>`, `>=`, `<`, `<=`, `in` (list on `value`), `like` (with `%` wildcards).
- **`filter_logic`** (`AND` / `OR`) applies to the whole filter list — no nesting. For "type IN (...) AND date ≥ X" use `in` plus `AND`. For keyword OR-searches, use `like` filters with `OR` in a separate query.
- **Page limits:** `company` 1000; `price_explanation`, `financial_data_point`, `consensus_data_point`, `valuation_multiple` 300; most others 100. Paginate with `next_hint` (e.g. `id > last_id`) or by date until `truncated` is false. Event queries saturate fast (Japan `Merger or Acquisition`: 100 rows cover ~15 days) — page by date sub-windows.
- **`aggregate_entity` output keys** come back camelCased (`op_margin` → `opMargin`) and dates as quoted strings; `having` takes the alias as written.
- **`ku_cell` is heavy:** always filter by both `ku_id` and `group_company_id` (or `cell_standard_event_id`). Unfiltered or broad sorts time out.
- **`hq_country` codes:** `US`, `JP`, `HK` (HKEX), `CN` (mainland A-shares), `KR` today. `HK` and `CN` are distinct — never conflate them. Never hardcode the covered set: read it at run time as the non-delisted `company.hq_country` values.

Example — market-cap-filtered Japan universe:
```
aggregate_entity(entity="stock_price", aggregates=[{"function":"MAX","field":"date","alias":"latest"}],
  group_by=["company.hq_country"], joins=[{"relation":"company"}],
  filters=[{"field":"company.hq_country","op":"=","value":"JP"}, {"field":"date","op":">=","value":"<today-10d>"}])
query_entity(entity="stock_price", select=["company_id","symbol","market_cap","close","currency","company.name","company.sector_id"],
  joins=[{"relation":"company"}],
  filters=[{"field":"date","op":"=","value":"<latest>"}, {"field":"company.hq_country","op":"=","value":"JP"},
           {"field":"market_cap","op":">","value":2000000000}], limit=100)   # paginate
```

Example — events for a universe in a window:
```
query_entity(entity="standard_event", select=["id","type","name","date","company_id","company.symbol"],
  joins=[{"relation":"company"}],
  filters=[{"field":"type","op":"in","value":["Merger or Acquisition","Spin-offs"]},
           {"field":"company.hq_country","op":"=","value":"JP"}, {"field":"date","op":">=","value":"<start>"}],
  sort=[{"field":"date","direction":"desc"}], limit=100)
```

## 5. `standard_event` types

Use these exact strings in `type` filters. `name` is a short headline — read it, don't infer from `type` alone.

**Deals and structure:** `Merger or Acquisition`, `Spin-offs`, `Divestment`, `Joint venture creation`, `Equity investment`, `Discontinuation of a business or region`, `Development of a significant subsidiary or portfolio company`, `IPO`, `Other public listing`, `Secondary listing`, `Delisting`, `Name change`, `Ticker change`

**Governance and activism:** `Shareholder Activism`, `Change in Board of Directors`, `Management change`, `Change of management incentive plan`, `Amendment to Articles or other key governance documents`, `Shareholder meetings`, `Strategy change`, `Corporate restructuring and reorganization`, `Layoffs or hiring plan`, `Short-seller accusation and defense`

**Ownership and capital return:** `Purchase or sale of shares by insiders`, `Purchase or sale of shares by major investors`, `Buyback program change`, `Treasury Share / Treasury Stock Cancellation or Disposal`, `Dividend Announcement`, `Dividend policy change`, `Dividend outlook change`, `Shareholder Benefit Program`, `Stock split / reverse split`, `Lockup expiry`, `Index inclusion or exclusion`

**Financing and distress:** `Financial Distress or Solvency Concern`, `Credit rating change`, `Liquidity outlook change`, `Debt default`, `Debt Restructuring`, `Insolvency filing`, `Auditor going concern`, `Auditor change`, `Delayed filing`, `Restatement of Financials`, `Material Accounting Disclosure`, `Significant accounting policy change`, `Issuance of follow-ons`, `Issuance of bonds or non-convertible debt`, `Issuance of Convertible Debt`, `Convertible Debt conversion`, `Early debt buyback / retirement`, `Net working capital profile change`, `Cash flow reaching inflection point`

**Earnings and guidance:** `Earnings announcement`, `Earnings beat or miss`, `Topline beat or miss`, `Management guidance`, `Announcement of the next earnings release`, `Company profitability inflection point`, `Operational KPI announcement`, `Operational KPI Redefinition`, `Change of reporting segments`, `Change of fiscal year end`, `Analyst tone expressed during Q&A`, `Non-deal roadshow, or other ad-hoc management presentations`, `Specialized Presentation or Report`

**Sell-side:** `Sell-side Rating Action`, `Sell-side Target Price Action`, `Sell-side Estimates Action`, `Sell-side coverage initiation`

**Business and industry:** `Customer win or loss`, `Partnerships and Alliances`, `Product Launch Action`, `Product or Service Enhancement`, `Market Entry or Expansion Action`, `Adjustment of Production Facilities or Capacity`, `Progress of new initiatives`, `Competitive dynamics change`, `Demand Supply Dynamics Change`, `Industry outlook change`, `Technology trend affecting the industry`, `Input cost fluctuation`, `Supply chain disruption`, `Supply chain restructuring`, `Outsourcing or Insourcing`, `Operation disruption`, `Subsidy awards`, `Industry awards and recognitions`, `Key Opinion Leader Mention of Company`

**Legal, regulatory, macro, other:** `Lawsuits`, `Class Action Investigation Announcement`, `Regulatory investigations`, `Regulatory approvals or denials`, `Intellectual Property Disputes`, `Addition or removal from government lists`, `Product Recalls or Defects`, `Cybersecurity Incidents`, `PR Crisis`, `Workplace scandal`, `ESG Update`, `Change in macroeconomic environment`, `Significant political event`, `Headquarters change`, `Founder's life event`

## 6. Knowledge units (KUs)

~1,000 KUs exist. Most are `cell_type = time_period`, `group_type = company` (one JSON cell per company per fiscal period, with `sources[].file_id` page citations). A KU counts as covered only if its `content` is non-empty — run the skill's KU coverage check (rule 2.1 #1) before relying on a unit. Find a KU id by name, then read cells:

```
query_entity(entity="knowledge_unit", select=["id","name","description"],
  filters=[{"field":"name","op":"like","value":"%backlog%"}])
query_entity(entity="ku_cell", select=["cell_time_period_id","cell_as_of_date","content"],
  filters=[{"field":"ku_id","op":"=","value":<id>}, {"field":"group_company_id","op":"=","value":<company_id>}],
  sort=[{"field":"cell_time_period_id","direction":"desc"}], limit=2)
```

Verified KU names by domain (not exhaustive — search `knowledge_unit.name` with `like` for others):

- **Corporate actions and ownership:** `mergers_and_acquisitions`, `restructuring`, `major_shareholders`, `share_buybacks`, `share_buyback_program`, `board_directors`, `management_info`, `related_party_transactions`, `amendments_to_articles_and_bylaws`
- **Balance sheet and credit:** `cash_and_debt`, `debt_details`, `debt_refinancing_risk`, `debt_issuance`, `balance_sheet_details`, `cash_flow_details`, `credit_risk`, `auditor`, `auditor_opinion`
- **Growth and guidance:** `growth_drivers`, `growth_strategies`, `organic_sales_growth`, `price_growth`, `guidances`, `guidances_numbers_to_narratives`, `addressable_market_tam`, `by_segment_financials`, `by_segment_performances`, `reporting_segments`, `geographical_segments`, `business_initiatives`
- **Orders and customers:** `order_backlog`, `order_intake`, `book_to_bill_ratio`, `bookings`, `key_customer_wins`, `key_customer_losses`, `notable_customers`, `customer_concentration_disclosure`, `revenue_stream_by_customer`, `customer_bargaining_power`, `customer_capex_cycle`
- **Brand and pricing:** `brand_equity`, `brand_positioning`, `brand_awareness`, `brand_differentiation`, `brand_portfolio`, `brand_ranking`, `pricing_power`, `pricing_strategy`, `market_shares`, `loyalty_program`, `advertising_and_promotion_and_marketing_and_branding`
- **Channels:** `distribution_model`, `channel_mix`, `channel_shifts`, `channel_inventory`, `distributors`, `distributor_dealer_network`, `distributor_dealer_profitability`, `direct_to_consumer_dtc`, `digital_sales_e_commerce`
- **Cost structure:** `cogs_fixed_components`, `opex_fixed_components`, `raw_material_input_costs`, `cost_pass_through`, `gross_margin_trends`, `operating_margin_trends`, `operating_leverage`, `cost_per_unit`, `commodity_exposure_mix`
- **Supply chain:** `top_suppliers`, `notable_suppliers`, `supplier_concentration_disclosure`, `supplier_bargaining_power`, `supplier_tiers`, `supply_chain_resilience`, `supply_chain_interdependencies`, `supply_chain_availability`
- **Technology and IP:** `research_and_development_intensity`, `research_and_development_pipeline`, `patent_portfolio`, `ip_intellectual_property`, `proprietary_exclusive_technology`, `disruptive_technologies`, `innovation_cycle`, `product_innovation`, `automation`, `robotics`
- **Capex and capacity:** `capital_expenditure`, `maintenance_capex`, `expansion_capex`, `capacity_and_utilization_overall`, `capacity_and_utilization_outlook`
- **Competition:** `competitions`, `competitive_outlook`, `competitive_strategy`, `regulatory_moat`, `commoditization_risk`
- **Never use:** `financial_statement_data`, `capital_expenditure_maintenance_expansion` (no cells anywhere) — financials come from `financial_data_point` (rule 2.2).

Non-time-period KUs (singleton / comparison / event-scoped):
- Company singletons: `fundamental_drivers`, `company_drivers_extensive`, `relative_weighting`, `products_details_enriched`, `upstream_categories_enriched`, `downstream_categories_enriched`, `product_mappings`, `gics_classification` (never for sector classification — use `sector.name`, section 7), `trading_currencies`, `ipo_dates`
- Product-category level: `category_definition_enriched`, `category_size_and_growth_enriched`, `category_trends`, `category_trends_enriched` (singleton); `business_breakdown`, `business_breakdown_enriched`, `product_competitiveness_enriched`, `general_comparison` (comparison — filter by `group_product_category_id`)
- Event-scoped: `standard_event_summary`, `meaningful_standard_event_summary` (filter by `cell_standard_event_id`; coverage is sparse)

## 7. Sector taxonomy (`sector.name`)

Aerospace & Defense · Agriculture · Airlines · Apparel & Footwear · Asset & Wealth Management · Auto & Auto Parts · Auto Retail · Beverages Production · Biopharmaceuticals · Building & Construction Materials · Business Services · Capital Markets & Investment Banking · Cargo Transportation & Infrastructure Services · Chemicals · Cloud & Data Services · Commercial & Industrial Distribution · Commercial Services & Supplies · Conglomerates & Trading Houses · Construction & Engineering · Delivery and Logistics Services · Digital Assets & Blockchain · Diversified Financial Services · Educational Services · Electrical Equipment and Power Systems · Electronic Components and Manufacturing · Energy Minerals · Energy Technology & Sustainability · Energy Trading & Commodities · Energy Transportation & Storage · Entertainment & Leisure · Financial Risk & Compliance Technology · Food and Staples Retail · Food Production · Healthcare Services · Home Builders · Home Improvement Retail · Hospitality Services · Household Appliances · Household & Personal Care · Household Products · Insurance · Investment Services · IT Distribution · IT Services & Consulting · Leisure Products · Lending & Specialty Finance · Life Sciences Tools & Services · Luxury Goods · Machinery Manufacturing · Manufactured Products · Marine Engineering & Shipbuilding · Media & Publishing · Medical Devices & Equipment · Metals & Smelting · Mining & Mineral Processing · Nutrition & Wellness · Oilfield Equipment & Services · Oil & Gas Exploration & Production · Online Platform & Marketplace · Payments & Financial Infrastructure · Personal Services · Professional & Consulting Services · Professional Data and Services · Public Transport · Real Estate · Real Estate Finance · Real Estate Investment & REITs · Recycling & Circular Materials · Refining & Petrochemicals · Restaurants · Retail & Commercial Banking · Semiconductors & Equipment · Skin Care Products · Social Media & Interactive · Software · Specialty Retail · Telecommunications · Tobacco · Transportation Equipment Manufacturing · Utilities · Waste Management

These are sub-sector-grained (81 rows) and are the only sector classification skills use. Map a broad label (e.g. "Industrials") semantically to the full set of member rows — never by keyword match — confirm 2–3 canonical names land in the chosen set, and state the Distilla names used. Never map to GICS or classify from the `gics_classification` KU.

## 8. Other enumerated values

- `executive_summary.category` (= `name`): `business_review`, `recent_performance`, `mgmt_analysis`, `financials_review`, `technical_analysis`, `industry_analysis`
- `file.source_type`: `Filing`, `Transcript`, `Composite Filing`, `News Article` (only these four)
- `time_period.duration`: `year`, `half`, `quarter`, `nine_months`; `provenance`: `financials`, `consensus`, `filing`
- `search_public_library`: `doc_types` = `Research`, `Podcast`; `date_range` = `7d`, `30d`, `60d`, `90d`, `180d`, `200d`, `1y`; `mode` = `synthesize` or `list`; `sole_company=true` needs exactly one ticker
- `valuation_multiple.type`: `LTM_` and `NTM_` versions of `Pe`, `Ev_Ebitda`, `Ev_Ebit`, `Ev_free_cash_flow`, `price_sales_per_share`, `price_book_value_per_share`, `price_tangible_book_value_per_share`, `price_free_cash_flow_per_share`, `Peg_ratio`, `Fcf_yield`, `dividend_yield`, each suffixed `_Med_W` (suffix undocumented)
- `consensus_metric.category`: `SALES`, `GROSS_INC`, `EBIT`, `EBITDA`, `NET_INC`, `NET_INC_ADJ`, `EPS_GAAP`, `EPS_EX_XORD`, `DPS`, `CAPEX`, `FCF`, `UFCF`; `statistics`: `MEAN`, `MEDIAN`, `HIGH`, `LOW`, `STDDEV`, `NEST`
- `financial_metric.category`: `income_statement`, `balance_sheet`, `cash_flow`, `ratio_analysis_*` (names carry the category prefix, e.g. `income_statement_sales`)

## 9. Known gaps and data-quality caveats

**Not in Distilla MCP today** — follow the skill's Data-source fallback ladder (other Distilla data → open web) and mark every web-sourced cell `†` with a source + date footnote:
- Social-media / X data (mention volume, sentiment, accounts)
- Structured insider-trade details (insider name, title, shares, price). `standard_event` gives only a headline
- Credit-rating levels as a field (only `Credit rating change` event headlines)
- Deal terms (offer price, consideration) as structured fields — read event headlines, `mergers_and_acquisitions` KU, filings, or news
- FX rates (use the skill's FX row: Google Finance for the latest rate, tried first; Fed H.10 / FRED, then ECB, for past dates)

Financial actuals, consensus estimates and valuation multiples **are** in Distilla (`financial_data_point`, `consensus_data_point`, `valuation_multiple`) — never state otherwise.

**Data-quality caveats:**
- `standard_event.date` is the record/news date, not necessarily when the event happened. Headlines can describe old history (observed: a 1965 stock decline tagged `Financial Distress or Solvency Concern` with a 2026 date). Verify the underlying event date before applying any recency rule.
- Events are often duplicated (same action, several rows or dates). Dedupe by (company, type, underlying event) before counting.
- `Purchase or sale of shares by insiders` mixes buys, sells, planned sales (Form 144) and 12-month summaries; direction is only in `name`. Dedupe by (company, date), classify each row from its `name`, drop summaries, then verify.
- Event rows attach to the reporting company — for `Merger or Acquisition` usually the acquirer. Read the target from `name`, and check that the headline concerns this entity (off-entity rows occur).
- `price_explanation` and `earnings_summary` are LLM-generated: fiscal-period labels and figures can be wrong. "No company-specific driver" is common and means a macro/sector move.
- `time_period.fiscal_year` and filing-derived period dates can be wrong; anchor on the `end_date` month of `provenance = "financials"` periods, or on `cell_as_of_date` / `published_at` for KU cells.
- Cross-check any single data point a conclusion depends on against a second entity or source.

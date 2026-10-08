# Distilla data pull — query recipes and gotchas

Read this before querying. Every step below was tested against live Distilla data
(Apple, Samsung Electronics). Follow the order; each step feeds `raw.json`.

## Contents
1. Resolve the company and its sector
2. Annual actuals (one query)
3. Latest quarterly balance sheet (equity bridge)
4. Consensus estimates
5. Share price and target
5b. Finance arm (captive finance)
5c. Segments (Drivers tab)
6. Sanity checks before writing raw.json
7. raw.json schema
8. Gotchas (read this)

---

## 1. Resolve the company and its sector

```
query_entity(entity="company",
  filters=[{"field":"symbol","op":"in","value":["AAPL"]}],
  select=["id","name","symbol","hq_country","sector_id"])
```
Symbol formats: US plain (`AAPL`), Korea `005930.KS` / `.KQ`, Hong Kong `0700.HK`, Japan and
China per Distilla's ticker registry — if a lookup misses, query `ticker` by symbol or `company`
by `name`. Then look up the sector name:
```
query_entity(entity="sector", filters=[{"field":"id","op":"eq","value":<sector_id>}])
```
**Stop here for financials** — see SKILL.md "When not to build a DCF".
Financial sector ids: 292 Retail & Commercial Banking, 279 Insurance, 271 Capital Markets &
Investment Banking, 281 Lending & Specialty Finance, 274 Diversified Financial Services,
288 Real Estate Finance. Caution (build, but warn): 289 REITs, 269 Asset & Wealth Management,
280 Investment Services.

## 2. Annual actuals — one query, ~280 rows

```
query_entity(entity="financial_data_point",
  joins=[{"relation":"time_period","alias":"T"},{"relation":"financial_metric","alias":"M"}],
  filters=[
    {"field":"T.company_id","op":"eq","value":<id>},
    {"field":"T.provenance","op":"eq","value":"financials"},
    {"field":"T.duration","op":"eq","value":"year"},
    {"field":"T.end_date","op":"gte","value":"<5 fiscal years back, e.g. 2021-06-01>"},
    {"field":"M.name","op":"in","value":[ ...METRICS... ]}],
  select=["M.name","value","T.end_date"],
  sort=[{"field":"M.name","direction":"asc"},{"field":"T.end_date","direction":"asc"}],
  limit=300)
```
METRICS (57 — every line the Model tab itemises; tested on Apple, Samsung, BYD, Fast Retailing, Caterpillar).
Every Distilla subtotal is a clean sum of these lines, which is what lets the model reconcile history
line by line instead of plugging:

Income statement (12): `income_statement_sales, income_statement_cost_of_goods_sold_cogs_incl_d_and_a,
income_statement_ebit_operating_income, income_statement_nonoperating_interest_income,
income_statement_interest_expense, income_statement_gross_interest_expense, income_statement_pretax_income, income_statement_income_taxes,
income_statement_minority_interest, income_statement_net_income,
income_statement_diluted_shares_outstanding, income_statement_dividends_per_share`

Balance sheet (24): `balance_sheet_cash_and_short_term_investments, balance_sheet_short_term_receivables,
balance_sheet_inventories, balance_sheet_other_current_assets, balance_sheet_total_current_assets,
balance_sheet_net_property_plant_and_equipment, balance_sheet_total_long_term_investments,
balance_sheet_intangible_assets, balance_sheet_deferred_tax_assets, balance_sheet_other_assets,
balance_sheet_total_assets, balance_sheet_short_term_debt_and_curr_portion_long_term_debt,
balance_sheet_accounts_payable, balance_sheet_income_tax_payable, balance_sheet_other_current_liabilities,
balance_sheet_total_current_liabilities, balance_sheet_long_term_debt_excl_lease_obligations,
balance_sheet_capital_and_operating_lease_obligations, balance_sheet_provision_for_risks_and_charges,
balance_sheet_deferred_tax_liabilities, balance_sheet_other_liabilities, balance_sheet_total_liabilities,
balance_sheet_total_shareholders_equity, balance_sheet_accumulated_minority_interest`

Cash flow (21): `cash_flow_depreciation_depletion_and_amortization, cash_flow_deferred_taxes,
cash_flow_funds_from_operations, cash_flow_changes_in_working_capital, cash_flow_net_operating_cash_flow,
cash_flow_capital_expenditures, cash_flow_capital_expenditures_fixed_assets,
cash_flow_net_assets_from_acquisitions, cash_flow_sale_of_fixed_assets_and_businesses,
cash_flow_purchase_or_sale_of_investments, cash_flow_other_investing_funds,
cash_flow_net_investing_cash_flow, cash_flow_cash_dividends_paid,
cash_flow_repurchase_of_common_and_preferred_stock, cash_flow_sale_of_common_and_preferred_stock,
cash_flow_issuance_or_reduction_of_debt_net, cash_flow_repayments_of_operating_lease_liabilities,
cash_flow_other_financing_funds, cash_flow_net_financing_cash_flow, cash_flow_exchange_rate_effect,
cash_flow_net_change_in_cash`
(`cash_flow_capital_expenditures_fixed_assets` only feeds the Distilla-definition FCF memo line.)

57 metrics × 5 years = 285 rows, which fits under the 300-row limit.
`income_statement_gross_interest_expense` (before capitalized interest) is the cost-of-debt input; the
net `income_statement_interest_expense` is the fallback when the gross line is `-`. If it comes back truncated, split
into two queries (IS + BS, then CF).

Optional fallbacks if a core line comes back "-": `balance_sheet_long_term_debt` (total incl. leases),
`balance_sheet_goodwill`, `balance_sheet_other_intangible_assets`,
`income_statement_depreciation_and_amortization_expense`. Do **not** add
`balance_sheet_long_term_note_receivable`: it is already inside other lines (adding it double-counts —
seen on Samsung).

## 3. Latest quarterly balance sheet (for the equity bridge)

Same query shape with `T.duration` IN `["quarter", "half"]` (Hong Kong and many Asian companies
report half-yearly), `T.end_date >= <~6 months ago>`, sorted by `T.end_date desc`, metrics: cash,
total LT investments, ST debt, LT debt excl. leases, lease obligations, accumulated minority
interest, diluted shares, `income_statement_total_shares_outstanding` (basic, for the share-count
check). Use the most recent period-end.
If the latest quarter is the fiscal year-end, the annual figures are the bridge.

## 4. Consensus estimates

Consensus metric ids: sales_mean 1, sales_high 5, sales_low 6, gross_inc_mean 7, ebitda_mean 13,
ebit_mean 19, ebit_high 23, ebit_low 24, capex_mean 61 (verify with `consensus_metric` if a query looks
off). gross_inc_mean drives opex %, and ebitda_mean − ebit_mean gives consensus D&A; both matter.
```
query_entity(entity="consensus_data_point",
  joins=[{"relation":"time_period","alias":"T"},{"relation":"consensus_metric","alias":"C"}],
  filters=[
    {"field":"T.company_id","op":"eq","value":<id>},
    {"field":"T.duration","op":"eq","value":"year"},
    {"field":"T.end_date","op":"gte","value":"<day after last actual FYE>"},
    {"field":"consensus_metric_id","op":"in","value":[1,5,6,7,13,19,23,24,61]},
    {"field":"consensus_date","op":"gte","value":"<~10 days ago>"}],
  select=["C.name","value","consensus_date","T.end_date"],
  sort=[{"field":"consensus_date","direction":"desc"}], limit=60)
```
Keep only the latest `consensus_date` per (metric, period) — prepare_inputs.py does this if you
pass rows. `consensus_date` is the snapshot vintage, never the fiscal period.

## 5. Share price and target

```
query_entity(entity="stock_price",
  filters=[{"field":"company_id","op":"eq","value":<id>},{"field":"date","op":"gte","value":"<~7 days ago>"}],
  select=["symbol","date","close","sell_side_target_price","currency","market_cap"],
  sort=[{"field":"date","direction":"desc"}], limit=1)
```
**Stock splits.** The same entity carries `split` (ratio on the effective date). Query `stock_price` from the
bridge balance-sheet date to today, `select=["date","split"]`, filter `split` `gt` 0 (days without a split
show 0), and record every ratio other than 1 in
`market.splits_after_bridge` (e.g. `[{"date":"2026-09-29","ratio":5}]`) with share counts left as Distilla
delivers them: the script scales them once. The market-cap cross-check catches a missed split.

`market_cap` is in USD for every listing (rule 2.6): it is the cross-check for the rebuilt market cap,
never an input.

## 5b. Finance arm (captive finance)

```
query_entity(entity="ku_cell",
  joins=[{"relation":"ku","alias":"K"},{"relation":"cellTimePeriod","alias":"P"}],
  filters=[{"field":"group_company_id","op":"eq","value":<id>},
           {"field":"K.name","op":"in","value":["by_segment_financials","cash_and_debt"]}],
  select=["id","K.name","cell_as_of_date","P.end_date","P.duration","content"],
  sort=[{"field":"cell_as_of_date","direction":"desc"}], limit=6)
```
Look for a finance segment (Financial Products, Financial Services, GM Financial, Ford Credit,
Toyota Financial Services). If its assets are 10% or more of total assets, fill `finance_arm`:
- **From Distilla** (`by_segment_financials`, the fiscal year matching the last actual year): segment
  revenue, pre-tax segment profit, segment assets (from the filing when the cell has none). Parse the content in Python. Periods are
  year-to-date and sometimes mislabelled (a 9-month cell tagged `quarter`), labels vary by filing, and
  labels with commas shift the columns ("Selling, general and administrative" splits) — check each
  value against the cell's period and unit before using it.
- **From the latest filing that shows the finance arm separately** (the 10-Q nearest the bridge date,
  else the annual report; official filings, `†` with the as-of date): the supplemental
  consolidating data or the finance segment's balance sheet. Finance receivables, current and
  long-term: the consolidated balance sheet lines. Debt, equity and cash: the finance arm's own column
  after intercompany eliminations. Assets leased to customers (equipment on operating leases, leased
  vehicles): the PP&E line or note. One search for the filing, then fetch it with the host's fetch
  tool; if it is too long, fetch EDGAR's `R2.htm` / `R4.htm` pages or the XBRL company-facts page.
  Never download with code or send user details.
- **Fallback:** `cash_and_debt` comment text may give the finance arm's leverage (Cat Financial
  covenant leverage 7.96x, Jun 2026) — record it as `leverage`; the script then estimates equity and
  debt and flags them. Anything not found stays `null`.

## 5c. Segments (Drivers tab)

```
query_entity(entity="ku_cell",
  joins=[{"relation":"ku","alias":"K"},{"relation":"cellTimePeriod","alias":"P"}],
  filters=[{"field":"group_company_id","op":"eq","value":<id>},
           {"field":"K.name","op":"eq","value":"by_segment_financials"},
           {"field":"P.duration","op":"eq","value":"year"}],
  select=["id","P.end_date","cell_as_of_date","content"],
  sort=[{"field":"cell_as_of_date","direction":"desc"}], limit=1)
```
Then, if that cell carries fewer than two years, add the previous annual cells that use the same segment
names (Anta: FY2023 and FY2024 cells). If its year ends before the last actual fiscal year, the same query with
`P.duration` IN `["quarter", "half", "nine_months"]` and `P.end_date` inside that year (the year-to-date and
last-quarter cells). Leave out cells with a different segment structure (Micron's 2020 cell: CNBU / MBU /
SBU / EBU). When one field holds several breakdowns at once (Anta "Revenue": brand, product and channel),
the listing warns that they overlap: keep one breakdown with `--keep` (repeat it per segment).
The latest annual cell usually carries three years (Caterpillar FY2025: 2023–25). Save the rows to a file
and run `python <skill_dir>/scripts/segments.py cells.json` to list the fields and segments, then
`--revenue "<field>"` (plus `--units "<field>"` for a structured unit series) `--out segments.json`.
Totals, consolidated and elimination rows are dropped; the model shows the gap to Distilla's revenue as
"Other / eliminations" (intersegment sales). If the latest annual cell is older than the last actual
year, add the cell for that year (or the full-year columns of the fourth-quarter cell) to the file.

## 6. Sanity checks before writing raw.json

- **Consensus units vs actuals.** Compare FY1 consensus sales with the last actual year and with
  the sum of reported quarters in the current fiscal year. A 1000x gap means a units mismatch;
  a large but real jump (e.g. a memory up-cycle) will be visible in the quarterly actuals too.
- **Market cap cross-check.** Rebuilt market cap (price × FX × diluted shares) converted to USD
  against `stock_price.market_cap`: record both in `market` (`vendor_market_cap_usd`,
  `usd_per_price_currency`, 1.0 for USD listings); the script flags a gap over 10%.
- **Price currency vs reporting currency.** If they differ (ADRs, dual listings, HK-listed
  companies reporting in CNY such as BYD), find an FX rate by web search and set
  `fx_reporting_per_price` = reporting-currency units per 1 unit of price currency (BYD: 0.867 CNY
  per HKD). The risk-free rate must be the one for the **reporting currency** (BYD: China 10y, not HK).
- **Accounting standard.** Set `company.accounting_standard` when known (`US_GAAP`, `IFRS`, `J_GAAP`,
  `CAS`). Japan mixes J-GAAP and IFRS; Hong Kong listings report under HKFRS (= IFRS) or, for
  mainland companies, sometimes CAS. For JP, HK and CN companies confirm it from the latest results
  announcement or annual report (one search) and state the source; never set it from memory.
- **Share classes.** Distilla diluted shares can include preferred / non-voting classes (Samsung:
  ~6.7bn incl. preferred). Value per share is then per combined share; say so in the summary.

## 7. raw.json schema

```json
{
 "company": {"name":"...","ticker":"...","distilla_company_id":0,"hq_country":"US|KR|JP|CN|HK",
             "sector":"<Distilla sector name>","reporting_currency":"USD","units":"m"},
 "valuation_date": "YYYY-MM-DD",
 "annual":    {"<metric>": {"<end_date>": "<value as delivered>"}},   // or the raw row list
 "consensus": {"sales_mean": {"<end_date>": "<value>"}, ...},          // or the raw row list
 "market": {"price":0,"price_date":"","price_currency":"","fx_reporting_per_price":1.0,
            "fx_source":"","target_price":0,"vendor_market_cap_usd":null /* USD m, as Distilla delivers */,"usd_per_price_currency":1.0,
            "splits_after_bridge":[]},
 "bridge": {"as_of":"YYYY-MM-DD","source":"","cash":0,"lt_investments":0,"st_debt":0,
            "lt_debt":0,"leases":0,"leases_source":"","minority_interest":0,"diluted_shares":0,
            "pension_deficit":null,"pension_source":"","basic_shares":null,
            "shares_source":""},   // say which count diluted_shares holds when you replace it (e.g. basic after the share-count flag)
 "include_lt_investments": 1,
 "wacc": {"rf":0.0,"rf_source":"","beta":null,"beta_source":"","erp":null,"erp_source":"",
          "crp":null,"crp_source":"","kd_pretax":null,"terminal_growth":null,
          "beta_published":[1.09,0.92],"beta_published_sources":"Yahoo 5Y monthly 1.09; GuruFocus 0.92"},
 "long_history": {"income_statement_sales": {...}, "income_statement_ebit_operating_income": {...}},
 "basis_gap": {"adjusted_by_year": {"2025": 0, "2024": 0, "2023": 0}, "source": ""},   // company's own operating profit; or {"none": true, "reason": ""}
 "continuing_history": {"income_statement_sales": {}, "income_statement_ebit_operating_income": {}, "source": ""},   // after a divestiture; omit otherwise
 "segments": {"field":"","unit":"","revenue":{"<segment>":{"YYYY-MM-DD":0}},"units":{},"units_unit":"","source":"",
              "basis_type":"business segments | product / service | market x share | geography | kpi",
              "line_sources":{"<line>":"<where each year's history came from>"},   // lines you wrote yourself
              "hold":["<finance segment>"],   // keep their own trend, out of the calibration
              "drivers":{"<segment>":{"base":{"volume":{"2027":0.05},"price":{"2027":0.02}},"bull":{},"bear":{},  // or "market" + "share" instead of "volume"
                                      "basis":"<guidance / broker view (broker, title, date) / history>"}}},   // segments.py output + anchors
 "broker_discount_rates": [{"broker": "", "date": "YYYY-MM-DD", "rate": 0.0, "basis": "WACC | cost of equity"}],
 "multiple_history": {"type":"NTM_Ev_Ebitda_Med_W","from":"YYYY-MM-DD","avg":0,"min":0,"max":0,"n":0,
                      "basis":"<vendor EV with or without a finance arm's debt, from the spot-check>"},
 "finance_arm": {"name":"","period":"YYYY-MM-DD","segment_source":"","revenue":0,"profit_pretax":0,"assets":0,
                 "st_receivables":null,"lt_receivables":null,"debt":null,"equity":null,"cash":null,
                 "leased_assets":null,"bs_source":"",
                 "leverage":null,"leverage_source":"","pb_override":null},   // omit when there is no finance arm
 "anchors": {...}, "evidence": [...], "returns": {...}   // from the evidence step; see evidence_guide.md
}
```
Paste Distilla values exactly as delivered ("1,234.00", "-"); the script parses them. `annual`
and `consensus` accept either the pivoted form above (compact — preferred) or the raw row lists.
Leave any WACC field `null` that you could not source live; the script fills a flagged default.

## 8. Gotchas

| Issue | What to do |
|---|---|
| Values are text with commas; `"-"` = not reported | Paste as-is; the script parses |
| Units: `m` = millions of the reporting currency (Samsung revenue `333,605,938` = ₩333.6tn) | Keep the model in reporting-currency millions; per-share values are full currency units |
| Shares are in millions (`15,004.70` = 15.0bn) | Same unit everywhere, so value/share works out |
| Capex, dividends, buybacks, lease repayments are negative in cash flow | Paste as-is |
| `fiscal_year` labels unreliable | Always identify periods by `T.end_date` |
| `provenance = "filing"` periods are LLM-derived | Use only `provenance = "financials"` for actuals |
| `stock_price.market_cap` is in USD for every listing (Samsung looks ~1000x off in KRW terms) | Cross-check only, after converting the rebuild to USD; the model computes price × FX × diluted shares |
| SG&A already includes R&D | Model derives opex = gross profit − EBIT, so EBIT ties exactly |
| Interest expense/income often blank in recent years | Model uses pretax − EBIT for historical non-operating |
| Quarterly lease obligations often 0 / missing | Use the latest annual lease figure; note it in `leases_source` |
| Lease principal repayments are a separate financing line for IFRS lessees (Fast Retailing ¥140bn/yr) | Include `cash_flow_repayments_of_operating_lease_liabilities`, or cash from financing will not tie |
| Consensus EBITDA can be "adjusted" (excludes SBC) while consensus EBIT is GAAP (Duolingo) | prepare_inputs.py detects it and ignores consensus EBITDA for D&A and exit multiples |
| Research library / KUs can be empty for a company (Duolingo) | Fall back to company_drivers and the company's own filings (web search for targets); record that the library had nothing |
| Distilla FCF = CFO − **fixed-asset** capex only | Model FCF deducts all capex incl. intangibles (Samsung: ₩2–5tn/yr difference); memo line shows Distilla's |
| Tax lines can be benefits (negative) | Script ignores benefit years when setting the rate |
| Minority interest (IS) is positive = deduction | Paste as-is; residual goes to "other after-tax items" |
| Distilla's own balance sheet can fail to balance (BYD FY2021: ¥4.5bn, 1.5% of assets) | Shown on the "Unreconciled (equity / other instruments)" line and flagged; mention it to the user |
| Small rounding in Distilla subtotals (Fast Retailing: ¥2–5m on ¥ trillions) | Tie checks use a 0.01%-of-revenue tolerance |
| Large 52/53-week FYE dates (Sep 29, Dec 30, Aug 29) | Fine — forecast dates snap to month-end |
| First forecast year already ended but not yet reported (Fast Retailing, Aug FYE) | Handled: only cash flows after the bridge balance-sheet date are counted |

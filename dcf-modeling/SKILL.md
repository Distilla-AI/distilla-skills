---
name: dcf-modeling
description: Build a full 3-statement financial model (income statement, balance sheet, cash flow) and a DCF valuation in Excel with live formulas, using Distilla MCP data (actuals, consensus estimates, prices) for US, Korean, Japanese, Chinese and Hong Kong listed companies. Use this skill whenever the user asks to value a company, build a DCF, do a discounted cash flow, build a 3-statement or three-statement model, estimate intrinsic or fair value, work out what a stock is worth, or asks for a financial model or valuation model of a listed company, even if they don't say "DCF" or "Distilla". Also use it for bull/bear/base scenario valuations, WACC-and-terminal-growth sensitivity tables, or updating a model built earlier with this skill.
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
- `scripts/recalc.py` — recalculates the workbook in Python (`formulas` package) when the host has
  no spreadsheet recalculation tool.
- `scripts/check_model.py` — independent post-recalc verification.
- `references/distilla_queries.md` — **read before querying**: exact query recipes, the 56
  metrics, the raw.json schema, data gotchas.
- `references/assumptions_guide.md` — read before the checkpoint: how the draft is built, the
  judgment calls to raise, WACC sourcing order, the checkpoint table format.
- `references/evidence_guide.md` — read for step 4: which Distilla qualitative sources to use
  (company_drivers, research library, knowledge units), query recipes, and rules.

## When not to build a DCF

Check the Distilla sector first (ids in distilla_queries.md §1), and also the business itself:
sector tags are coarse (HSBC is tagged "Diversified Financial Services", not banking), so read
the company name and `company.summary` too.

- **Not in Distilla:** if the company lookup returns nothing (Distilla coverage is not
  universal; for example, few US banks), say so and ask for another ticker. Don't substitute
  web-scraped financials into this workflow, because the model's integrity checks assume
  Distilla's standardized statements.

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
latest quarterly balance sheet → consensus → price. Run the §6 sanity checks, especially
consensus units against quarterly actuals, price vs reporting currency, and the accounting
standard (it decides how leases are treated).

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
- **Equity risk premium:** Damodaran's latest mature-market implied ERP.
- **FX:** if the price currency differs from the reporting currency.
Don't compute beta from Distilla prices: Distilla has no index series and only one year of
(patchy) market caps, and home-made proxies gave clearly biased betas in testing. Record a short source string for each. Leave anything you cannot find as
`null`; the script fills a flagged default. Don't spend more than one search per input.

### 3. Prepare and draft
Write `raw.json` (schema in distilla_queries.md §7) in a working folder, then:
```bash
python <skill_dir>/scripts/prepare_inputs.py raw.json model_inputs.json
```
The printout is the draft. Read `references/assumptions_guide.md` now.

### 4. Evidence first, then anchor the numbers
The mechanical draft only covers the consensus years honestly. After that it is formula, and a
formula dressed up with reasons found afterwards is retrofitting. So for the drivers that decide
the value (post-consensus EBIT margin and growth, sometimes capex), follow
`references/evidence_guide.md`:
1. **Gather evidence before deciding**: one `company_drivers` query, then 2–3 *neutral*
   `search_public_library` questions ("when does the shortage end?", not "confirm the margin").
2. **Anchor each number to something real**: a historical reference point (the script prints the
   long-run average, peak and trough; pass `long_history` for a full cycle), a company target, or
   a specific research view. Put these in `raw.json["anchors"]` with a basis text.
3. **Where sources disagree, make that the scenarios** (Samsung: shortage ends 2028 vs 2031 vs
   oversupply 2029 → base / bull / bear), instead of consensus high/low alone.
4. **Leave it as formula when nothing supports a change**, and let the label say "formula, no
   evidence". Record in each evidence entry what it changed, including "no change".
Rerun prepare_inputs.py; evidence, anchors and return policy live in raw.json, so nothing is lost.

### 5. Checkpoint — stop and get confirmation
Present, compactly, in chat:
- The Base case table (growth, EBIT margin, capex %) by forecast year, noting which years are
  consensus-anchored.
- WACC and terminal growth, each input tagged *live* or *default*.
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

If the host has its own spreadsheet recalculation tool (for example an xlsx skill's `recalc.py`),
it may replace the second line. `recalc.py` needs the Python `formulas` package; install it if it
is missing. If no recalculation is possible, deliver the workbook marked "not recalculated or
verified here; values compute when opened in Excel or Google Sheets", give no value per share in
chat, and say why.

### 8. Deliver
Save the workbook where the host delivers files and share it with the user (attach, link or
present it through the host's file mechanism). Then a short summary in prose:
value per share (all three scenarios) against the current price and consensus target, **what the
price implies** (reverse DCF: perpetual growth or margin needed), the two or three inputs that
drive the answer and the evidence behind them, the terminal-multiple cross-check, any warnings, and how to use the
workbook (blue cells are inputs; scenario switch at the top of Assumptions; sensitivity tab).
Present the value as the output of stated assumptions, not a recommendation. The assistant isn't
a financial advisor, and the user makes the call.

## The workbook

| Tab | Contents |
|---|---|
| Summary | Value per share, upside, EV, WACC, checks status, forecast snapshot, key-assumption basis table (formula-only items in red), evidence table (finding, stance, source, date, effect), model notes, flags |
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
- Market cap is computed as price × FX × diluted shares, never Distilla's `market_cap` field.
- The valuation uses perpetuity growth only. Today's market multiple is shown as a reference but
  never used as the terminal assumption: it prices today's growth, not a mature terminal year
  (Duolingo: 38.9x today would need 7% growth forever). An exit multiple is used only when the user
  supplies one with a basis (`raw.json["dcf"] = {"exit_multiple": x, "exit_multiple_basis": "...", "tv_method": 2}`).

## Follow-ups

For "what if WACC is 9%" or other single-input questions, the user can type into the blue cell
and the model recalculates. Offer that. If they want you to change it, edit model_inputs.json,
rebuild, recalc, check, and re-present the file. Report what changed in value per share.

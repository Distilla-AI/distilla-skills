# Assumptions guide — drafting, judgment calls, WACC sourcing

prepare_inputs.py drafts every assumption mechanically. Your job at the checkpoint is to apply
judgment the script cannot: spot where the mechanical draft is wrong for *this* company, say so
plainly, and let the user decide.

## How the draft is built

| Driver | Consensus years | After consensus | Source when no consensus |
|---|---|---|---|
| Revenue growth | consensus mean path (Base), high (Bull), low (Bear) | linear fade to terminal growth | 3-yr historical average, clipped to −10%..+25% |
| Segment drivers (Drivers tab) | the scenario total plus each line's lead over it (year-to-date for year 1 when the interim cell is in, then trailing CAGR averaged with it), or its anchor, plus one common volume shift so the segments sum to the scenario total | the lead fades to zero over five years (or consensus years + 2), price to zero, unless anchored; held lines keep their own trend | — (no Drivers tab without segment data) |
| EBIT margin | consensus EBIT / consensus sales | hold last consensus margin, or fade to mid-cycle (peak guard) | 3-yr historical average |
| Segment margins (Drivers tab, with segment profit) | last actual margin (or its anchor) plus one common shift, so EBIT = consensus EBIT; corporate / unallocated held at its median % of revenue (up to 3 years) | the line's anchor, else in proportion to the company-level path; held lines flat; company margin = mix | — |
| Opex % revenue (SG&A, R&D, other) | (consensus gross profit − EBIT) / sales | held at last consensus year | last actual year |
| Gross margin | not an input: EBIT margin + opex %, so it follows the scenario and opex can never go negative | | |
| D&A | consensus EBITDA − EBIT, as % of sales | depreciation rate × beginning net PP&E (median of recent years) | depreciation rate |
| Capex % revenue | consensus capex / sales | level that keeps PP&E/revenue stable: k·(d+g)/(1+g), less new leases | 3-yr historical |
| New leases (IFRS 16 only) | historical lease principal repaid / revenue | same | 0 under US GAAP / J-GAAP |
| Working-capital days, other CA/CL % | last fiscal year | held flat | same |
| Tax rate | median of recent normal-rate (0–50%) years | same | statutory default |
| Payout, buybacks | 3-yr average % of net income | same | 0 |
| Debt | flat (net issuance 0) | same | same |

Why D&A follows the asset base: revenue can jump on price alone (Samsung's memory up-cycle roughly
doubled revenue) without the depreciation charge doubling. Tying D&A to revenue overstated Samsung's
FCF by tens of trillions of won a year before this rule.

Why leases are modelled as asset additions under IFRS 16: D&A includes right-of-use depreciation, but
consensus capex excludes new leases. Without the lease line, the model would never pay for new stores
(Fast Retailing ~4.6% of revenue a year). New leases are added to PP&E and the lease liability and
deducted in FCF like capex. Existing leases are covered by subtracting the lease liability in the
bridge. Under US GAAP, operating-lease cost already sits in EBIT, so neither applies.

Discount-rate, tax and growth defaults follow the **reporting currency**, not the listing (BYD:
HK-listed, CNY cash flows → China defaults).

Thresholds for the guards and checks (peak-margin multiple, PP&E drift band, cash build-up, TV share,
max gross margin) are named settings at the top of prepare_inputs.py and are carried into
model_inputs.json. They are heuristics, first calibrated on four companies; change them there, not in
code.

Horizon is 5 years, or 10 when consensus revenue CAGR exceeds 15% **or** growth in the last
consensus year is still more than 6 points above terminal growth. Otherwise the fade to terminal
growth becomes a cliff (Duolingo: 13.5% in year 3). The horizon is itself a formula choice with a
real effect: moving BYD and Fast Retailing from 5 to 10 years raised value by 17–23%, so mention it
when growth is still high at the end of consensus.

**Adjusted-EBITDA guard.** Consensus EBITDA is often "adjusted" (adds back stock-based comp), so
EBITDA − EBIT overstates D&A and would inflate FCF (Duolingo: implied D&A 15.8% of revenue vs
1.4% actual). If implied D&A exceeds 2× the actual D&A ratio or actual + 3 points, it is not used
(flagged), and the exit-multiple cross-check does not use consensus EBITDA either. Company margin
targets are often adjusted too: convert them to GAAP EBIT by subtracting the latest gap between
adjusted EBITDA and GAAP EBIT (SBC, D&A, other add-backs) before using them as anchors.

Bull and bear use the high and low analyst estimates. They are the edges of the analyst range,
not a coherent alternative story. A bull margin can come out *below* base because the most
optimistic revenue analyst is not the most optimistic margin analyst. Say this if the user asks
why.

## Terminal value, cross-checks and the reverse DCF

- **One valuation method**: perpetuity growth. Two "values" (perpetuity vs exit multiple) invite
  picking the one you like; the standard practice (Koller et al.) is one method plus checks.
- **Terminal multiple cross-check**: compare the EV/EBITDA the perpetuity value implies with
  reference multiples (mature peers, the company's own history). Today's market multiple is shown
  for reference only; the model also shows the perpetual growth it would imply if held forever.
- **Reverse DCF**: the perpetual growth, or the EBIT-margin scale (all forecast years), needed to
  justify today's price with everything else unchanged. Use it at delivery: "the price needs X% growth
  forever or a Y% margin; do you believe that?" is easier to judge than a value gap. If the price is
  below the value of the forecast years alone, no growth rate solves it and the model says so.
  Accuracy: the margin scale was tested by re-running the model at the implied scale - within
  1.5% of the price for four companies. The growth figure holds terminal cash flow fixed (no extra
  reinvestment for extra growth), so the true growth requirement is somewhat higher. Both return
  "n/a" with a reason when they cannot be solved (loss-making terminal year, answer above WACC).
- **Reinvestment check**: terminal growth needs reinvestment. Return on new capital (g ÷
  reinvestment rate) below WACC means growth destroys value; no net reinvestment (typical with
  prepaid subscriptions or negative working capital) means growth is assumed free forever. It is
  a warning only when material (cash flow >10% above NOPAT forever) or when RONIC < WACC.

## Judgment calls to raise at the checkpoint

Raise only the ones that apply. Lead with the one that moves value most.

00. **Discount rate vs brokers.** When the broker notes state a discount rate more than 3 points
   from the model's (WACC to WACC, cost of equity to cost of equity), lead with it: show both and the
   value per share at each, name what drives the difference (risk-free rate of the currency, beta,
   ERP), and ask which rate to use. Never switch rates without the user's answer.
0. **Beta quality.** If the beta was blended with the sector (published betas far from the sector,
   typical for foreign listings with low R²), or several sources disagree, say so: a 0.2 change in
   beta moved value by 20–25% for BYD and Fast Retailing in testing.
1. **Cyclical peak.** If the peak guard fired (last consensus margin above 1.5× the historical
   average — the long-run average when `long_history` gives 8+ years, else the last 5), explain that the draft fades margins to a mid-cycle level and ask whether the user
   believes the margin is structural. This was the single biggest value driver in testing
   (Samsung: holding a 56% memory-cycle margin vs fading to 34% moved value by about 25%).
2. **Tax far below statutory.** Credits, incentives and loss carryforwards run out. A large
   deferred-tax benefit (valuation-allowance release, Duolingo FY2025) signals normal taxes ahead.
   Offer a normalised rate; the user's choice goes in `raw.json["assumption_overrides"]`.
3. **Terminal value share of EV above ~75%.** The answer mostly rests on g and WACC; point the
   user to the sensitivity tab.
4. **Market-implied gap.** If the draft value per share (built before the checkpoint) is more than
   ±40% from the price, check the exit
   multiple cross-check and the implied exit multiple. A big gap usually traces to one input
   (WACC, terminal margin, terminal growth). Name it rather than presenting the number as a
   verdict.
5. **Negative forecast cash or capped buybacks.** Buybacks are capped at the cash available, so
   negative cash now means dividends alone exceed it; capped years (Checks tab) mean the historical
   buyback rate is not affordable. Propose a lower payout or buyback %, or debt issuance.
6. **Capex below D&A.** For a growing company this shrinks the asset base. After consensus the
   draft sizes capex to keep PP&E/revenue stable; if consensus capex itself is far below D&A, say so.
7. **PP&E / revenue drift (Checks tab).** Usually means revenue moved on price rather than volume,
   or an IFRS 16 lessee's leases are not modelled. Say which it is.
8. **Cash build-up (Checks tab).** Valuation is unaffected, but interest income and EPS are inflated.
   Offer to raise payout or buybacks.
9. **Distilla data gaps.** A non-zero "Unreconciled vs Distilla" line means Distilla's own statements
   don't add up for that year (BYD FY2021). Mention the amount and that the model shows it rather than
   hiding it.
10. **Non-operating assets.** Long-term investments are added to equity value by default. Ask if
   they look operating (strategic stakes the business depends on) or if the company is a holding
   company.
11. **Share classes / FX.** Mention when diluted shares combine classes, or when a converted price
   is used, and when the market-cap cross-check is more than 10% off.
12. **Finance arm.** When one is valued separately, show its book equity and how it was sourced
   (annual report, or estimated from leverage), its ROE and the justified P/B. Say that WACC rises:
   the industrial business carries little of the group's debt once the finance arm's borrowing is
   taken out. Name any input that fell back to a default (1.0× book, 7× leverage).
13. **Basis gap and pensions.** Say how much the basis gap moves the consensus margin, which way,
   what it is (recurring charges, or other income Distilla books below EBIT — which may carry value of
   its own) and where it came from, and the after-tax pension deficit in the bridge; if the CONSENSUS
   BASIS flag fired and the move is real, say so.
14. **History break.** After a divestiture, say whether the reference points use restated
   continuing-operations history, and if not, that the long-run average mixes perimeters.
15. **Segment drivers.** Say which drivers carry evidence and which are only calibrated: the common
   volume shift is a mechanical allocation, not a view (Caterpillar FY26: every segment +12–24% to reach
   consensus). Name the segment that moves value most and its basis; flag other / eliminations above 10%
   of revenue. Show how the mix moves from the last actual year to the last forecast year; a line whose
   share doubles needs evidence. Say which segments are held at their own trend (a finance segment), and point out a
   calibrated volume that swings against an anchored year (GM International: +12.9% anchored, then −9.5%).
   When every line is anchored in a consensus year, the total leaves consensus that year (shown as a
   variance) and an unanchored line can absorb a catch-up the next year (Tokyo Electron test: Field
   Solutions +48.5%) — say which it is, or leave a sizeable line unanchored.
16. **Segment margins.** The common margin shift in consensus years is calibration, not a view: say
   which line margins carry evidence. When the mix-built company margin parts from the company-level
   path (mix toward a higher-margin segment), say which segment drives it and whether the peak guard
   still holds for the total. Always say what the corporate / unallocated line holds — corporate costs,
   restructuring (guided lower?), the basis gap (other income below Distilla's EBIT) — and whether holding
   it at that share is right; say when the median rests on fewer than 3 years. When the history holds
   a cost that has stopped (GM: Cruise losses in 2023–24), set `segments.corporate_pct` with
   `corporate_basis` and cite it. Size it from what continues: the company's reported corporate /
   unallocated line for the last year (corporate costs, without the stopped item and one-off charges) as a
   % of revenue, plus the basis gap (GM: −0.6% corporate + the 1.8% gap = −2.4%).

## WACC sourcing order (user choice: web search, then defaults)

For each input, search once. If nothing reliable comes back, leave it `null` in raw.json and let
the script fill a flagged default. Record the source text for every live value.

| Input | Search for | Fallback |
|---|---|---|
| Risk-free rate | "<country> 10-year government bond yield" (today's date) | country table in prepare_inputs.py (US, KR verified Sep 2026; others rough) |
| Beta | full web search: "<ticker> beta 5Y monthly"; record all 5Y figures in `beta_published` | median → Blume-adjusted (⅔·raw + ⅓) → if >40% from relevered sector beta, 50/50 blend + flag; none found → sector beta |
| ERP | "Damodaran implied equity risk premium <month year>"; record the as-of month | 4.23% mature market (Damodaran, start of 2026) |
| Country risk premium | only for non-US; "<country> country risk premium" | table in prepare_inputs.py |
| Cost of debt | credit rating or bond yields if easy to find | gross interest ÷ average debt if above rf (with a finance arm: interest ÷ industrial debt), else rf + 150bp, labelled a default |
| Terminal growth | not searched | country default, capped at rf |

The WACC tax rate is the historical effective rate. Forecast interest expense uses the *historical*
cost of debt (existing coupons); WACC uses the *marginal* cost. The two differ on purpose.

## Checkpoint table format

Present in chat, compact, one row per driver, forecast years as columns. Then list flags, then
ask one question: confirm or tell me what to change. For example:

```
Samsung Electronics — Base case draft, KRW tn
                   FY26E  FY27E  FY28E  FY29E … FY35E
Revenue growth      119%    35%     8%     7% …   2%   ← consensus mean FY26-28, then fade
EBIT margin          52%    57%    56%    53% …   34%  ← consensus; then fade to mid-cycle (peak guard)
Capex % revenue      10%     8%     8%     7% …    6%  ← consensus; then keeps PP&E/revenue stable
WACC 10.9% (rf 4.54% live · beta 1.36 = published 1.54, Blume-adjusted · ERP 4.23% Damodaran) · g 2.0%

Evidence
• Margin hold to 2028 — supports: ~2/3 of output on minimum-price LTAs; shortage seen through 2028
  (company_drivers, Sep 28) · challenges: Q3 price growth slowing, China supply rising (same)
• Returns — Aug-26 plan ≈ 50% of FCF → suggest return basis = FCF, 50% (valuation-neutral)
Flags: cyclical-peak guard · cash build-up · tax 8.6% vs 26.4% statutory
Confirm, or tell me what to change?
```

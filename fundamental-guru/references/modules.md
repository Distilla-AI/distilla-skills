# Module call contracts

Each module: call the named skill (all twelve are converted Distilla skills); if it isn't installed, follow the fallback spec below. Every module receives the Step 1 findings and the **valuation context** as context — a module carrying 3a also the Step 2 broker notes (`SKILL.md` Step 2) — and returns its own report with its own section names — keep them.

**Inputs to pass (so no module stops to ask):** the company (ticker + `company_id`), the **sub-sector** from the module's own list (row below, mapped from `sector.name`; if nothing fits, `other` plus the `sector.name`), and the module's **default time horizon**. Pass no focus unless the user named one. Modules default to single-company deep dives; don't add peers — each module builds its own segment-matched peer set (3b).

**Carry back per `SKILL.md` Step 2** — the closing verdict line and `Investor Action:` line verbatim in the summary; the module's own section keeps (a)–(c) where the callee produces them; per-module line formats are in the rows below. The modules' "investable at current valuation?" lens takes its valuation from the guru's valuation context — never from a recalled multiple — and a module that states valuation was not assessed is corrected to cite the context.

**Fallback specs** (module skill not installed): run the KU coverage check (rule 2.1 #1) on the KU list, then read the units per the `ku_cell` note in `SKILL.md`; financials from `financial_data_point` (rule 2.2). Cells carry `sources[].file_id` — cite them. Skip empty units and note material gaps. **Peers:** from the Peer / rival set row, segment-matched (3b); the product-category route and its comparison KUs held no cells when checked (27 Sep 2026), so peers come from `company.sector_id` and the `competitions` / `category_rivalry` KUs.

## Contents
- brand · channel · growth · cost · supply_chain · technology · profit_pool · capex_cycle · cycle · utilization · roe · moat

---

## brand
**Skill:** `consumer-brand-equity`
- **Sub-sector (its list):** apparel & footwear / food & beverage / beauty & personal care / luxury / restaurants / household & CPG / other. Map: Apparel & Footwear → apparel & footwear; Beverages Production, Food Production → food & beverage; Household & Personal Care, Skin Care Products → beauty & personal care; Luxury Goods → luxury; Restaurants → restaurants; Household Products → household & CPG.
- **Horizon:** its default (5–10 year durability view).
- **Carry back:** `Brand Equity: [Strong & Durable / Stable / Eroding / Weak] — …` and `Investor Action: [Worth deep research / Monitor / Pass]`. Its market-action reconciliation uses an **LTM** multiple vs its 3-year average — report it as the module's, never compare it with an NTM valuation context.

**Fallback spec:** evaluate brand strength, positioning and loyalty; compare recognition against key competitors; assess how brand value contributes to pricing power. KUs `brand_equity`, `brand_positioning`, `brand_awareness`, `brand_differentiation`, `brand_portfolio`, `brand_ranking`, `pricing_power`, `market_shares`, `loyalty_program`, `advertising_and_promotion_and_marketing_and_branding`.

## channel
**Skill:** `distribution-channels`
- **Sub-sector (its list):** apparel & footwear / beauty / food & beverage / restaurants / household & CPG / consumer electronics / B2B industrial / pharma / software & SaaS / healthcare devices / tech hardware / other.
- **Horizon:** its default (5-year backward + 3-year forward).
- **Carry back:** `Channel Position: [Direct-led / Balanced / Channel-dependent / Channel-concentrated] — …` and `Investor Action: …`.

**Fallback spec:** channel structure (online vs. offline, DTC vs. wholesale); main distribution partners and dependency; contract terms and channel margins (undisclosed spread = `--`). KUs `distribution_model`, `channel_mix`, `channel_shifts`, `channel_inventory`, `distributors`, `distributor_dealer_network`, `distributor_dealer_profitability`, `direct_to_consumer_dtc`, `digital_sales_e_commerce`, `customer_concentration_disclosure`; singleton KU `downstream_categories_enriched`. Channel KUs are sparse — run the coverage check first.

## growth
**Skill:** `growth-profile`
- **Sub-sector (its list):** tech & SaaS / consumer / healthcare & pharma / industrials / financials / energy & commodities / telecom & utilities / retail / real estate & REITs / other. Consumer Discretionary → consumer, or retail for Specialty Retail, Auto Retail and Food and Staples Retail; Tech Software → tech & SaaS; Healthcare → healthcare & pharma; Utilities, Telecom → telecom & utilities; Real Estate → real estate & REITs; Insurance, Other Financials → financials.
- **Horizon:** its default (5 FY backward + latest 4–8 quarters + 3-year forward).
- **Carry back:** `Quality of Growth: [Compounder / Accelerating / Cyclical-growth / Decelerating / Mature / Stalling] — …` and `Investor Action: …`.

**Fallback spec:** what drives revenue growth (volume, price/mix, new categories, geographies, products); durability vs. what the valuation context prices in; deceleration or reacceleration risk. Growth computed per the growth-rate guard (base ≤ 0 → `--`; beyond ±1,000% excluded and named). KUs `growth_drivers`, `growth_strategies`, `organic_sales_growth`, `price_growth`, `by_segment_performances`, `geographical_segments`, `addressable_market_tam`, `guidances`; `company_drivers`; `standard_event` types `Management guidance`, `Topline beat or miss`, `Market Entry or Expansion Action`, `Product Launch Action`.

## cost
**Skill:** `manufacturing-cost-structure`
- **Sub-sector (its list):** heavy industrial / auto OEM / industrial machinery / electronics & semis / aerospace & defense / consumer durables / process industries / other. Tech Hardware → electronics & semis (Household Appliances → consumer durables); Industrials → by `sector.name` (Machinery Manufacturing → industrial machinery; Auto & Auto Parts → auto OEM; Aerospace & Defense → aerospace & defense; Chemicals, Metals & Smelting → process industries); Materials → process industries.
- **Horizon:** its default (5-year backward + 3-year forward).
- **Carry back:** `Cost Competitiveness: [Best-in-class & durable / Competitive / Cost-challenged / At-risk] — …` and `Investor Action: …`. Its gross margin is after D&A (Distilla definition) — keep that label.

**Fallback spec:** cost components (fixed vs. variable); cost drivers and commodity sensitivity; cost structure vs. segment-matched peers; pass-through ability. KUs `cogs_fixed_components`, `opex_fixed_components`, `raw_material_input_costs`, `commodity_exposure_mix`, `cost_pass_through`, `gross_margin_trends`, `operating_margin_trends`, `operating_leverage`, `cost_per_unit`; `standard_event` type `Input cost fluctuation`.

## supply_chain
**Skill:** `supply-chain-resilience`
- **Sub-sector (its list):** tech & semis / auto & EV / pharma & biotech / consumer & apparel / industrial & capital goods / aerospace & defense / food & agriculture / energy & commodities / healthcare devices / other. Healthcare → pharma & biotech (healthcare devices for device makers).
- **Horizon:** its default (5-year backward + 3-year forward).
- **Carry back:** `Supply Chain Resilience: [Resilient / Balanced / Vulnerable / At-risk] — …` and `Investor Action: …`.

**Fallback spec:** primary suppliers and dependency risk; sourcing and logistics stability; geographic and geopolitical risk (an empty supplier or sanctions KU is not evidence of low exposure). KUs `top_suppliers`, `notable_suppliers`, `supplier_concentration_disclosure`, `supplier_bargaining_power`, `supplier_tiers`, `supply_chain_resilience`, `supply_chain_interdependencies`, `supply_chain_availability`; singleton KU `upstream_categories_enriched`; `standard_event` types `Supply chain disruption`, `Supply chain restructuring`, `Addition or removal from government lists`.

## technology
**Skill:** `technology-position`
- **Sub-sector (its list):** software & SaaS / semiconductors / pharma & biotech / internet & platforms / industrial tech / consumer tech & hardware / energy & clean tech / healthcare devices / financial services tech / telecom / other (state tech-native or tech-adopting). Tech Hardware → semiconductors (Semiconductors & Equipment) or consumer tech & hardware; Tech Software → software & SaaS or internet & platforms; Healthcare → pharma & biotech (healthcare devices for device makers).
- **Horizon:** its default (5 FY backward + 3-year forward).
- **Carry back:** `Technology Position: [Tech-leader / Competitive / Vulnerable / Behind] — …` and `Investor Action: …`.

**Fallback spec:** core technologies and R&D differentiation (R&D intensity per its definition); sustainability of the tech advantage and IP protection; industry tech trends and disruption risk. KUs `research_and_development_intensity`, `research_and_development_pipeline`, `patent_portfolio`, `ip_intellectual_property`, `proprietary_exclusive_technology`, `disruptive_technologies`, `innovation_cycle`, `product_innovation`; `standard_event` types `Technology trend affecting the industry`, `Intellectual Property Disputes`.

## profit_pool
**Skill:** `profit-pool-analysis`
- **Inputs (its list):** target company (ticker) **and** its sub-industry (`sector.name`), so it maps the company's position in the chain; focus tier = the company's own tier; horizon = its default (1–3 years).
- **Carry back:** it has no tier verdict or Investor Action line — carry its opening `Supply Chain Verdict` paragraph (the callee's section name; it is the profit-pool verdict) and its Profit Pool Migration conclusion. Its Tier Cycle Sensitivity cells without evidence stay `--`.

**Fallback spec:** which layer of the software stack (infrastructure, platform, application) holds pricing power; whether the company is gaining or losing profit-pool share; vendor/customer concentration risk. KUs `market_shares`, `pricing_power`, `customer_bargaining_power`, `supplier_bargaining_power`, `customer_concentration_disclosure`, `competitive_outlook`; singleton KUs `upstream_categories_enriched`, `downstream_categories_enriched`. Tier margins from `financial_data_point`, LTM from quarters when year-end months differ (rule 2.4).

## capex_cycle
**Skill:** `capex-cycle`
- **Sub-sector (its list):** heavy industrial / semis / telecom & utilities / oil & gas / aerospace & defense / auto & EV / REITs & real estate / industrial machinery / other. Energy → oil & gas; Utilities, Telecom → telecom & utilities; Real Estate → REITs & real estate.
- **Horizon:** its default (last 5 FYs from `financial_data_point` + 3-year forward; ≥ 1 full cycle).
- **Carry back:** `Capex Cycle Stance: [Disciplined / Balanced / Stretched / Overinvesting / Underinvesting] — …` and `Investor Action: …`. It builds no valuation itself; with the guru's valuation context supplied, its lens cites that context instead of "not assessed".

**Fallback spec:** whether the company invests at the right point in the cycle; historical and expected returns on capex (ROIIC ≥ 2 windows, from `financial_data_point`); position vs. peers in ramping or pulling back capex (capex/OCF, not capex/FCF). KUs `capital_expenditure`, `maintenance_capex`, `expansion_capex`, `capacity_and_utilization_overall`, `capacity_and_utilization_outlook`, `customer_capex_cycle`, `order_backlog`; `standard_event` type `Adjustment of Production Facilities or Capacity`.

## cycle
**Skill:** `cycle-positioning`
- **Sub-sector:** none passed — it infers the sector from `sector.name`.
- **Horizon:** its default.
- **Carry back:** `Revision Phase: [Early / Mid / Late] — …` and `Pricing Gap: [Ahead of cycle / In-line / Behind cycle] — …` (no Investor Action block — none built). Its Market Pricing section uses NTM types (banks / insurers: LTM P/B) — report them as the module's, never compared with a valuation context on another horizon.

**Fallback spec:** where the sector and the company sit in their cycles, anchored to a driver-matched trough and comparable cycle; revision phase; what the current multiple prices in vs. the fundamental cycle. KUs `leading_indicators`, `cycle_sensitivity`, `inflection_point`, `inventory_cycle`, `industry_supply_outlook`, `capacity_and_utilization_outlook`, `customer_capex_cycle`, `commodity_prices`, `order_backlog`, `order_intake`, `guidances_numbers_to_narratives`; revisions per rule 2.5; `standard_event` types `Earnings beat or miss`, `Change in macroeconomic environment`.

## utilization
**Skill:** `capacity-utilization`
- **Sub-sector:** none passed — it identifies the capacity type itself.
- **Horizon:** its default.
- **Carry back:** `Utilization Trend: [Tightening / Stable / Loosening] — …`, `Pricing Power: [Strong / Moderate / Weak / Diminishing] — …` and `Cycle Signal: […] — …` (no Investor Action block — none built).

**Fallback spec:** current utilization vs. own range and segment-matched peers (derived loading ratios `‡` for non-disclosers); sector supply/demand balance; the pricing power and cycle signal it implies. KUs `capacity_and_utilization_overall`, `capacity_and_utilization_by_node`, `capacity_and_utilization_outlook`, `new_capacity_timeline_and_progress`, `industry_supply_outlook`, `supply_outlook`, `pricing_power`, `pricing_mechanism`, `product_spread_margin`, `rig_utilization`, `compute_utilization`; `standard_event` type `Adjustment of Production Facilities or Capacity`.

## roe
**Skill:** `roe-decomposition`
- **Sub-sector (its list):** industrial / consumer / tech & SaaS / healthcare / energy & commodities / retail / utilities / banks / insurance / asset managers / other. Banks → banks; Insurance → insurance; Other Financials → asset managers; Utilities → utilities.
- **Depth:** 3-step. **Horizon:** 5 FY + latest 4 quarters.
- **Carry back:** `Quality of ROE: [Operating-excellence / Capital-efficient / Leverage-amplified / Distorted / Mixed] — …` (no Investor Action block — none built).

**Fallback spec:** ROE = NPM × asset turnover × equity multiplier from `financial_data_point` (NI, sales, total assets, equity; opening + closing averages), so the product reconciles; banks / insurers ROE = ROA × leverage, drivers and capital from KUs with `figure_type = "actual"`. KUs `net_interest_margin_nim`, `fee_income_mix`, `bank_efficiency_ratio`, `provision_for_credit_losses`, `non_performing_loan_ratio`, `common_equity_tier_1_ratio`, `insurance_combined_ratio`, `risk_based_capital_ratio`, `asset_under_management_aum`, `return_on_assets`, `return_on_equity` (cross-check only), `share_buybacks`, `dividend_payout_ratios`.

## moat
**Skill:** `competitive-position`
- **Rivals:** none passed — it picks 4–6. **Focus:** none. **Horizon:** medium-term (1–3 years).
- **Carry back:** `Moat: [Wide / Narrow / None] — …` (no Investor Action block — none built).

**Fallback spec:** moat sources and durability; rival dynamics and share trend; Five Forces; the most important competitive threat. KUs `competitions`, `category_rivalry` (rival names resolved via `company` `name ilike`), `market_shares`, `competitive_strategy`, `competitive_outlook`, `regulatory_moat`, `pricing_power`, `customer_churn`, `customer_bargaining_power`, `supplier_bargaining_power`, `addressable_market_tam`, `market_consolidation`; margins and `ROIC‡` per rule 2.3, cross-peer period basis per rule 2.4.

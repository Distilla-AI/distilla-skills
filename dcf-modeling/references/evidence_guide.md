# Evidence step: qualitative sources behind the assumptions

The draft from prepare_inputs.py is purely numerical. This step finds the business reasons for,
or against, the few assumptions that drive value, so the checkpoint can say *why* a margin
fades or a payout changes. Tested on Samsung Electronics (Sep 2026).

## Contents
1. Which sources to use (and which not)
2. Query recipes
3. What to ask, driven by the draft's flags
4. Rules
5. From evidence to numbers
6. Recording evidence

---

## 1. Which sources to use

| Source | What it is | Use it for | Verdict |
|---|---|---|---|
| `company_drivers` | One table per company: driver, causal link, evidence with numbers, current vs past. Updated every few days | The backbone: cycle position, pricing, competition, capital allocation, risks | **Always** — one query |
| `search_public_library` `list` + `get_library_document` | Catalog of broker notes (90 days), then a note's summary: rating, target price, date | Rule 3a coverage: which brokers cover the company, their latest view and target | **Always** — one list, every broker's note read |
| `search_public_library` `synthesize` | Synthesised answer over recent sell-side research, with document titles and dates | Targeted questions about specific assumptions | **Always** — 2 to 3 questions |
| `ku_cell` (knowledge units) | Per-topic qualitative cells (pricing power, operating leverage, catalysts ...), about 13 quarters, cited to filing pages | Supporting quotes with page-level sourcing, when a relevant KU exists | Optional |
| `file` | Metadata only (type, date, period); no text | Freshness: date of the latest results and transcript | Metadata only |
| `file` news articles | Company tag is loose (Samsung's includes unrelated articles) | — | **Don't use** |

## 2. Query recipes

**company_drivers** (content is a markdown table, often long):
```
query_entity(entity="company_drivers",
  filters=[{"field":"company_id","op":"eq","value":<id>}],
  select=["symbol","updated_at","content"], limit=1)
```

**Broker coverage (rule 3a)** — list first, group the documents by their `broker` field, then read
each broker's most relevant recent note (else its latest) — one read per broker, not per document:
```
search_public_library(query="<company>", mode="list", date_range="90d", doc_types=["Research"],
  tickers=["<ticker>"])
get_library_document(document_id=<id>)   # summary: rating, target price, change old -> new, date
```
Fewer than 3 brokers → the same list once at `date_range="180d"`. The `Brokers:` line in the
delivery reports the counts and the notes read.

**search_public_library** `mode="synthesize"`: write one specific question per call, naming the company, the year and
the assumption. For example: "Samsung Electronics 2026 memory capex outlook HBM pricing guidance".
The answer is synthesised and lists sources (title, type, publication_date). Prefer sources from
the last ~60 days.

**Which KUs exist for this company** (coverage differs by company and sector):
```
aggregate_entity(entity="ku_cell",
  filters=[{"field":"group_company_id","op":"eq","value":<id>}],
  group_by=["ku_id"], aggregates=[{"alias":"n","field":"id","function":"COUNT"}])
```
KU ids most relevant to DCF assumptions:
643 cycle_sensitivity, 630 incremental_margins, 1256 operating_leverage, 765 pricing_power,
621 catalysts, 644 inflection_point, 614 capital_deployment, 871 working_capital, 627 tail_risks.
Then read the latest cell:
```
query_entity(entity="ku_cell",
  filters=[{"field":"group_company_id","op":"eq","value":<id>},{"field":"ku_id","op":"in","value":[...]}],
  joins=[{"relation":"ku","alias":"K"}], select=["id","K.name","published_at"],
  sort=[{"field":"published_at","direction":"desc"}], limit=10)
query_entity(entity="ku_cell", filters=[{"field":"id","op":"in","value":[<latest ids>]}],
  joins=[{"relation":"ku","alias":"K"}], select=["K.name","published_at","content"])
```

**Latest results date** (freshness):
```
query_entity(entity="file",
  filters=[{"field":"company_id","op":"eq","value":<id>},
           {"field":"source_type","op":"in","value":["Transcript","Filing","Composite Filing"]}],
  select=["source_type","published_at","time_period_id"],
  sort=[{"field":"published_at","direction":"desc"}], limit=3)
```

## 3. What to ask, driven by the draft

Spend the questions where value is sensitive or a flag fired:

| Draft signal | Question for the library / what to look for in drivers |
|---|---|
| Cyclical-peak guard fired | Where are we in the cycle? Pricing outlook for the next 2–3 years; contract structures (long-term agreements, minimum prices); new supply coming |
| Terminal EBIT margin (always) | Structural vs temporary margin drivers: mix, pricing power, competition, cost pressure |
| Cash build-up warning | Shareholder-return policy: dividend policy, buyback programme, % of FCF commitments |
| PP&E drift / capex | Capex guidance and multi-year investment plans; new capacity timing |
| High growth years | Management revenue targets; TAM and share projections |
| Tax far below statutory | Tax incentives and when they expire |

## 4. Rules

- **Evidence first.** Gather it before deciding post-consensus numbers, and ask neutral questions.
  Finding reasons for numbers already chosen is retrofitting.
- **The user still decides.** Anchored numbers are a proposal shown at the checkpoint with their
  basis; the user confirms or changes them.
- **Show both sides.** When sources conflict (Samsung: long-term contracts support the margin, but
  price growth is decelerating and Chinese supply is rising), show both. Don't pick the one that
  fits the draft.
- **Paraphrase and keep it short.** Research and filings are copyrighted: summarise in your own
  words, one or two sentences per finding, and no long quotes.
- **Cite.** Record source (company_drivers / library document title / KU name and filing page) and
  date for every finding.
- **Some evidence is valuation-neutral.** Shareholder-return policy changes the balance sheet and
  EPS but not the DCF value, so say so when you propose it.
- **Stay quick.** One drivers query, the broker list with every broker's note, plus 2–3 library
  questions is usually enough. Skip KUs unless
  a relevant one exists.
- **When Distilla runs dry**, use the company's own disclosures (web search: "<company> long-term
  margin target", shareholder letters, 8-K / annual report). A stated company target is a valid
  anchor; convert adjusted targets to GAAP first (see assumptions_guide.md). Duolingo: library and
  KUs empty; the 30–35% adjusted-EBITDA target came from its SEC-filed shareholder letter.

## 5. From evidence to numbers (not the other way round)

The mechanical draft is formula after the consensus years. Evidence must be able to change it;
otherwise it is decoration. For each value-driving assumption:

| Step | What to do | Samsung example |
|---|---|---|
| Ask neutrally | Question the uncertainty, not the draft | "When does the shortage end? Oversupply risk 2028–29? Normalised margins?" |
| Find reference points | Long-run history (pass `long_history`), company targets, peers | EBIT margin 2014–25: average 14.4%, previous peak 24.2% (FY2018), trough 2.5% (FY2023) |
| Pick the anchor | Terminal level = a reference point, with the evidence explaining why that one | Base terminal 24.2% (previous peak, not average: LTAs cover >70% of wafers, HBM mix rising) |
| Timing from evidence | When the fade starts / ends | Base: hold to FY2028 (most research: balanced by 2028) |
| Disagreement → scenarios | Each credible view becomes a case | Bull: shortage to 2031 (Citi). Bear: oversupply 2029 (extreme-bear research case), margin to 14.4%, revenue −14% (FY2023 precedent) then back to trend |
| Nothing found → say so | Keep the formula; label stays "formula, no evidence" (red on the Summary tab) | Base/bull post-consensus revenue growth |

Anchors go in `raw.json`:
```json
"anchors": {
  "ebit_margin": {"base": {"hold_until": "2028-12-31", "reach_by": "2031-12-31", "terminal": 0.242,
                           "basis_type": "history + evidence", "basis": "<why this level and timing, with sources>"}},
  "revenue_growth": {"bear": {"overrides": {"2029-12-31": -0.14, "2030-12-31": 0.02},
                              "basis_type": "history + evidence", "basis": "<...>"}}}
```
`hold_until`: last year the consensus (or last consensus) margin is kept. `reach_by`: year the
terminal level is reached (linear in between). Growth `overrides` pin specific years; later years
interpolate to terminal growth, so pin the recovery year too if the evidence says revenue recovers.

Sanity check before the checkpoint: could you defend each anchor if the user asked "why this
number?" If the only answer is "the formula gave it", the label must say so.

## 6. Recording evidence

Evidence, anchors and the return policy all live in `raw.json` (`evidence`, `anchors`, `returns`),
so re-running prepare_inputs.py never loses them. Each evidence entry:
```json
{"assumption": "EBIT margin (base, post-FY2028)", "stance": "supports|challenges|informs",
 "finding": "<one or two sentences, paraphrased>", "source": "Distilla library: <title>", "date": "YYYY-MM-DD",
 "effect": "<what it changed in the numbers, or 'no change'>"}
```
Return policy stated as a share of FCF: `"returns": {"basis": 2, "payout": 0.5, "buyback": 0.0}`.

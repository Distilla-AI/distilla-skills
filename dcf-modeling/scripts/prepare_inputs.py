#!/usr/bin/env python3
"""
prepare_inputs.py - turn raw Distilla pulls into a clean model_inputs.json.

Usage:
    python prepare_inputs.py raw.json model_inputs.json [--years N]

raw.json is written by the assistant from Distilla MCP results (see references/distilla_queries.md
for the exact schema). This script:
  1. parses Distilla's text numbers ("333,605,938.00", "-" = missing)
  2. aligns annual actuals by fiscal-year end date
  3. takes the latest consensus snapshot for each forecast period
  4. computes historical ratios
  5. drafts Base / Bull / Bear assumptions (consensus-anchored, fading to steady state)
  6. fills WACC inputs, using defaults (and flagging them) where live values are missing
It prints a human-readable assumptions summary for the assistant to present to the user.
Nothing here is final: the user confirms or edits model_inputs.json before build_model.py runs.
"""
import json
import sys
import datetime as dt
from collections import defaultdict

# ---------------------------------------------------------------- defaults
# Fallbacks only. Always prefer live values found by web search and record the source.
# Values are approximate and dated; the model flags every default it uses.
DEFAULTS_AS_OF = "2026-09"
COUNTRY_DEFAULTS = {
    # rf: 10y local government yield (fallback only - search first)
    # crp: approx. country risk premium on top of mature-market ERP
    # tax: approx. statutory corporate rate incl. typical local surcharges
    # g: default terminal growth (nominal, local currency)
    "US": {"rf": 0.052, "crp": 0.000, "tax": 0.25,  "g": 0.025},   # rf verified Sep 2026
    "KR": {"rf": 0.045, "crp": 0.007, "tax": 0.264, "g": 0.020},   # rf verified Sep 2026
    "JP": {"rf": 0.030, "crp": 0.008, "tax": 0.306, "g": 0.015},   # rf verified Sep 2026 (JGB ~3.0%)
    "CN": {"rf": 0.017, "crp": 0.010, "tax": 0.25,  "g": 0.025},   # rf verified Sep 2026 (CGB ~1.67%)
    # HK rf below is a rough, unverified placeholder - always search first
    "HK": {"rf": 0.035, "crp": 0.007, "tax": 0.165, "g": 0.025},
}
MATURE_ERP = 0.0423  # Damodaran mature-market ERP, start of 2026 (fallback only - search first)
SECTOR_UNLEVERED_BETA = {  # approximate global industry averages; keyword-matched against Distilla sector names
    "semiconductor": 1.25, "software": 1.10, "cloud": 1.10, "online platform": 1.05, "social media": 1.10,
    "it services": 0.95, "electronic": 1.05, "telecom": 0.60, "media": 0.85, "entertainment": 0.90,
    "auto": 0.85, "retail": 0.85, "apparel": 0.85, "luxury": 0.90, "restaurant": 0.75, "hospitality": 0.90,
    "household": 0.65, "food": 0.60, "beverage": 0.60, "tobacco": 0.60, "skin care": 0.75,
    "pharma": 0.90, "biotech": 1.15, "medical": 0.85, "health": 0.80, "life sciences": 0.95,
    "aerospace": 0.95, "machinery": 0.95, "electrical equipment": 1.00, "shipbuilding": 1.00,
    "construction": 0.90, "home builder": 0.95, "conglomerate": 0.80, "business services": 0.85,
    "chemical": 0.90, "metal": 1.00, "mining": 1.00, "energy minerals": 1.00, "oil": 0.90,
    "refining": 0.90, "energy": 0.85, "utilit": 0.45, "real estate": 0.60, "logistics": 0.85,
    "transport": 0.85, "airline": 1.00, "agriculture": 0.75, "waste": 0.65, "education": 0.85,
}
DEFAULT_UNLEVERED_BETA = 0.95

# Judgment thresholds. They are heuristics (first calibrated on Apple / Samsung), kept here so
# they are visible and adjustable rather than buried in code. build_model.py reads the same
# values from model_inputs.json["thresholds"].
THRESHOLDS = {
    "peak_margin_multiple": 1.5,   # consensus margin > 1.5x history avg -> fade to mid-cycle
    "max_gross_margin": 0.95,      # EBIT margin + opex % may not imply GM above this
    "tv_share_warn": 0.85,         # terminal value share of EV that triggers a warning
    "ppe_drift_low": 0.5,          # terminal PP&E/revenue below 0.5x last actual -> review
    "ppe_drift_high": 2.0,         # ... or above 2x
    "cash_build_multiple": 3.0,    # terminal cash/revenue above 3x last actual (and >50%) -> review
    "beta_sector_band": 0.40,      # adjusted published beta >40% away from sector beta -> blend 50/50 + flag
}
# Lease treatment: under US GAAP (and J-GAAP) operating-lease cost sits inside EBIT, so the
# lease liability must NOT also be subtracted in the equity bridge. Under IFRS 16 / CAS it is debt.
DEFAULT_STANDARD = {"US": "US_GAAP", "KR": "IFRS", "HK": "IFRS", "CN": "CAS", "JP": None}

TERMINAL_FADE_NOTE = ("Years after the last consensus year fade revenue growth linearly to terminal "
                      "growth; EBIT margin holds the last consensus margin, or fades to a mid-cycle "
                      "margin when consensus looks like a cyclical peak.")


# ---------------------------------------------------------------- helpers
def num(v):
    """Distilla values are strings like '1,234.00' or '-'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "NA", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pivot(block, name_key, date_key="T.end_date"):
    """Accept either a list of Distilla rows or an already-pivoted {metric: {date: value}}."""
    out = defaultdict(dict)
    if isinstance(block, dict):
        for m, series in block.items():
            for d, v in series.items():
                out[m][str(d)[:10]] = num(v)
        return out
    for r in block or []:
        m = r.get(name_key) or r.get("name") or r.get("metric")
        d = str(r.get(date_key) or r.get("end_date"))[:10]
        out[m][d] = num(r.get("value"))
    return out


def pick_latest_consensus(block):
    """Rows: {C.name, value, consensus_date, T.end_date}. Keep the latest snapshot per (metric, period)."""
    if isinstance(block, dict):
        return pivot(block, "C.name")
    best = {}
    for r in block or []:
        m = r.get("C.name") or r.get("name")
        d = str(r.get("T.end_date"))[:10]
        cd = str(r.get("consensus_date"))[:10]
        k = (m, d)
        if k not in best or cd > best[k][0]:
            best[k] = (cd, num(r.get("value")))
    out = defaultdict(dict)
    for (m, d), (_, v) in best.items():
        out[m][d] = v
    return out


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def clamp(x, lo, hi):
    return None if x is None else max(lo, min(hi, x))


def add_years(date_str, n):
    d = dt.date.fromisoformat(date_str)
    y = d.year + n
    # keep month-end semantics (e.g. Sep 29/30 -> Sep 30, Feb 28/29 -> month end)
    if d.month == 12:
        nxt = dt.date(y + 1, 1, 1)
    else:
        nxt = dt.date(y, d.month + 1, 1)
    last_day = (nxt - dt.timedelta(days=1)).day
    day = last_day if d.day >= 28 else d.day  # 52/53-week year ends snap to month end
    return dt.date(y, d.month, day).isoformat()


# ---------------------------------------------------------------- revenue drivers
def build_drivers(SEG, periods, rev, fc_periods, N, ncons, scen, g_term, rev_anchors, idx_of, flags, ebit=None):
    """Segment revenue drivers for the Drivers tab, or None (single growth rate) with the reason flagged.

    SEG = raw.json["segments"]: {"revenue": {line: {end_date: value}}, "units": {line: {...}} (optional),
    "units_unit", "source", "basis_type" (business segments | product / service | market x share | geography | kpi),
    "line_sources": {line: text}, "hold": [...],
    "drivers": {line: {scenario: {"volume" | "market" + "share" | "price" | "margin": {year: v}}, "basis": text}},
    "profit": {line: {end_date: value}} (optional: segment operating profit -> EBIT from segment margins)}.
    A line need not be a reported segment: a product / service split (new equipment vs services), market x
    share, a region or a KPI line works the same way when its history is sourced. Where a line has "market"
    (market growth) and optionally "share" (share change) for a year, volume = (1 + market)(1 + share) - 1.
    """
    if not SEG.get("revenue"):
        return None

    def match(series):
        """{end_date: value} -> values aligned to Distilla's fiscal periods (end dates within 20 days)."""
        out = []
        for p in periods:
            pd_ = dt.date.fromisoformat(p)
            hit = [num(v) for d, v in series.items()
                   if abs((dt.date.fromisoformat(str(d)[:10]) - pd_).days) <= 20]
            out.append(hit[0] if hit else None)
        return out

    names = list(SEG["revenue"])
    hist = {s: match(SEG["revenue"][s]) for s in names}
    # A small segment with no value for the last actual year (an "All Other" line a later cell omits) moves
    # into other / eliminations rather than blocking the tab; a material one still blocks it.
    for s in list(names):
        if hist[s][-1] is None:
            last = next((v for v in reversed(hist[s]) if v is not None), None)
            i_last = max((i for i, v in enumerate(hist[s]) if v is not None), default=None)
            if last is not None and rev[i_last] and abs(last) / rev[i_last] < 0.02:
                names.remove(s)
                flags.append(f"SEGMENTS: '{s}' has no {periods[-1][:4]} value and is small ({abs(last) / rev[i_last]:.1%} of "
                             "revenue in its last year) - moved into other / eliminations.")
    hist = {s: hist[s] for s in names}
    if len(names) < 2:
        flags.append("SEGMENTS not used: fewer than 2 revenue lines - revenue stays on the single growth rate. A "
                     "single-segment company can use a product / service split, market x share, geography or KPI "
                     "lines instead (SKILL.md, Segments).")
        return None
    usable = [i for i in range(len(periods)) if all(hist[s][i] is not None for s in names)]
    if not usable or usable[-1] != len(periods) - 1 or len(usable) < 2:
        flags.append("SEGMENTS not used: segment revenue does not cover the last actual year and the one before "
                     f"(years found: {[periods[i][:4] for i in usable]}) - revenue stays on the single growth rate.")
        return None
    seg_sum = [sum(hist[s][i] for s in names) if i in usable else None for i in range(len(periods))]
    other = [rev[i] - seg_sum[i] if i in usable else None for i in range(len(periods))]
    o_share = other[-1] / rev[-1] if rev[-1] else 0
    if abs(o_share) > 0.25:
        flags.append(f"SEGMENTS not used: segments sum to {seg_sum[-1]:,.0f} against Distilla revenue {rev[-1]:,.0f} "
                     f"({o_share:+.0%} other / eliminations) - check the field and the segment list.")
        return None
    if abs(o_share) > 0.10:
        flags.append(f"SEGMENTS: other / eliminations is {o_share:+.0%} of revenue (intersegment sales or unallocated "
                     "revenue); it grows with the segment sum.")

    units = {}
    for s, ser in (SEG.get("units") or {}).items():
        if s in hist:
            u = match(ser)
            if u[-1] and u[-2]:
                units[s] = u
    # own trailing growth per segment (CAGR over the usable years, clipped) = default volume driver
    i0, i1 = usable[0], usable[-1]
    own = {}
    for s in names:
        a, b = hist[s][i0], hist[s][i1]
        own[s] = clamp(((b / a) ** (1 / (i1 - i0)) - 1) if (a and b and a > 0 and b > 0) else 0.0, -0.15, 0.30)

    seg_anchor = SEG.get("drivers") or {}
    # "hold": segments that keep their own trend and stay out of the calibration shift (a finance segment,
    # a segment with its own guidance path) - the shift then falls on the others
    hold = [s for s in (SEG.get("hold") or []) if s in hist]

    def anchor(s, sc, kind, i):
        if kind == "volume":
            v_ = raw_anchor(s, sc, "volume", i)
            if v_ is None:
                m_ = raw_anchor(s, sc, "market", i)
                if m_ is not None:
                    sh_ = raw_anchor(s, sc, "share", i)
                    v_ = (1 + m_) * (1 + (sh_ or 0.0)) - 1
            return v_
        return raw_anchor(s, sc, kind, i)

    def raw_anchor(s, sc, kind, i):
        d = ((seg_anchor.get(s) or {}).get(sc) or {}).get(kind) or {}
        for y, v in d.items():  # keyed by fiscal-year label ("2029") or end date: matched on the label year
            if fc_periods[i][:4] == str(y)[:4]:
                return float(v)
        return None

    # Segment margins (option A): when every line has profit history for the last actual year, EBIT is built
    # from segment margins plus a corporate / unallocated line (Distilla EBIT - segment profit: corporate costs,
    # restructuring, the basis gap), held as a % of revenue.
    phist = {s: match((SEG.get("profit") or {}).get(s, {})) for s in names}
    margins_on = bool(SEG.get("profit")) and ebit is not None and all(phist[s][-1] is not None for s in names) \
        and all(hist[s][-1] for s in names)
    if SEG.get("profit") and not margins_on:
        flags.append("SEGMENT MARGINS not used: profit history does not cover every line in the last actual year - "
                     "EBIT stays on the company-level margin.")
    corp_hist, corp_pct = None, None
    if margins_on:
        corp_hist = [(ebit[i] - sum(phist[s][i] for s in names)) if all(phist[s][i] is not None for s in names)
                     and ebit[i] is not None else None for i in range(len(periods))]
        corp_pct = corp_hist[-1] / rev[-1] if rev[-1] else 0.0
        if abs(corp_pct) > 0.05:
            flags.append(f"SEGMENT MARGINS: corporate / unallocated is {corp_pct:+.1%} of revenue (Distilla EBIT less "
                         "segment profit: corporate costs, restructuring, basis gap); held at that share.")
    out = {"segments": names, "hist": hist, "other_hist": other, "units": units,
           "margins_on": margins_on, "profit_hist": phist, "corp_hist": corp_hist,
           "corp_pct": [round(corp_pct, 6)] * N if margins_on else None, "margin": {}, "company_margin": {},
           "basis_type": SEG.get("basis_type", "business segments"),
           "line_sources": {s: (SEG.get("line_sources") or {}).get(s, "") for s in names},
           "market": {sc: {s: [raw_anchor(s, sc, "market", i) for i in range(N)] for s in names} for sc in scen},
           "share": {sc: {s: [raw_anchor(s, sc, "share", i) for i in range(N)] for s in names} for sc in scen},
           "units_unit": SEG.get("units_unit", ""), "source": SEG.get("source", "Distilla by_segment_financials"),
           "field": SEG.get("field", ""), "scen": {}, "total_growth": {}, "pinned": {}, "basis_summary": {},
           "basis": {s: (seg_anchor.get(s) or {}).get("basis", "") for s in names}}
    for sc in scen:
        target_g = scen[sc]["revenue_growth"]
        over = {idx_of(d) for d in ((rev_anchors.get(sc) or {}).get("overrides") or {})}
        pinned = [i < ncons or i in over for i in range(N)]
        R = {s: hist[s][-1] for s in names}
        O, S_prev, T_prev = other[-1], seg_sum[-1], rev[-1]
        vol = {s: [] for s in names}
        pr = {s: [] for s in names}
        tot_g = []
        Rpath, Tpath = {s: [] for s in names}, []
        level, L = [], rev[-1]  # the scenario's revenue level each year: pinned years aim at the level, so a year
        for g_ in target_g:     # left off-consensus (every line anchored) does not carry its gap forward
            L *= 1 + g_
            level.append(L)
        for i in range(N):
            p_i = {s: anchor(s, sc, "price", i) for s in names}
            v_a = {s: anchor(s, sc, "volume", i) for s in names}
            if pinned[i]:
                T = level[i]
                S_target = T / (1 + O / S_prev) if S_prev else T
                base_v = {s: (v_a[s] if v_a[s] is not None else own[s]) for s in names}
                p_use = {s: (p_i[s] if p_i[s] is not None else 0.0) for s in names}
                free = [s for s in names if v_a[s] is None and s not in hold]
                fixed = sum(R[s] * (1 + base_v[s]) * (1 + p_use[s]) for s in names)
                denom = sum(R[s] * (1 + p_use[s]) for s in free)
                delta = (S_target - fixed) / denom if denom else 0.0
                v_use = {s: base_v[s] + (delta if s in free else 0.0) for s in names}
                if not free:
                    flags.append(f"Drivers ({sc}, {fc_periods[i][:4]}): every segment has a volume anchor, so the total "
                                 "is not calibrated to the scenario path that year.")
            else:
                # fade from the last value to terminal growth (volume) and zero (price), unless anchored
                k_left = N - i
                v_use, p_use = {}, {}
                for s in names:
                    lv, lp = (vol[s][-1] if vol[s] else own[s]), (pr[s][-1] if pr[s] else 0.0)
                    v_use[s] = v_a[s] if v_a[s] is not None else lv + (g_term - lv) / k_left
                    p_use[s] = p_i[s] if p_i[s] is not None else lp - lp / k_left
            S = 0.0
            for s in names:
                vol[s].append(round(v_use[s], 6))
                pr[s].append(round(p_use[s], 6))
                R[s] = R[s] * (1 + v_use[s]) * (1 + p_use[s])
                Rpath[s].append(R[s])
                S += R[s]
            O = O * (S / S_prev) if S_prev else O
            T = S + O
            Tpath.append(T)
            tot_g.append(T / T_prev - 1 if T_prev else 0.0)
            S_prev, T_prev = S, T
        out["scen"][sc] = {s: {"volume": vol[s], "price": pr[s]} for s in names}
        if margins_on:
            path = scen[sc]["ebit_margin"]  # company-level path: consensus (Distilla basis), anchors, peak guard
            last_act = ebit[-1] / rev[-1] if rev[-1] else 0.0
            m_prev = {s: phist[s][-1] / hist[s][-1] for s in names}
            m_ref, ref_c = dict(m_prev), last_act
            mg, comp, pin_m = {s: [] for s in names}, [], -1
            for i in range(N):
                T_ = Tpath[i]
                m_a = {s: anchor(s, sc, "margin", i) for s in names}
                if i < ncons:  # consensus years: segment margins calibrated so total EBIT = consensus EBIT
                    base_m = {s: (m_a[s] if m_a[s] is not None else m_prev[s]) for s in names}
                    free = [s for s in names if m_a[s] is None and s not in hold]
                    fixed = sum(Rpath[s][i] * base_m[s] for s in names) + corp_pct * T_
                    den = sum(Rpath[s][i] for s in free)
                    d_ = (path[i] * T_ - fixed) / den if den else 0.0
                    m_use = {s: base_m[s] + (d_ if s in free else 0.0) for s in names}
                    pin_m = i
                    m_ref, ref_c = dict(m_use), path[i]
                else:  # after consensus: the line's own anchor, else in proportion to the company-level path
                    sc_ = path[i] / ref_c if ref_c else 1.0
                    m_use = {s: (m_a[s] if m_a[s] is not None else m_ref[s] if s in hold else m_ref[s] * sc_)
                             for s in names}
                for s in names:
                    mg[s].append(round(m_use[s], 6))
                m_prev = m_use
                comp.append((sum(Rpath[s][i] * m_use[s] for s in names) + corp_pct * T_) / T_ if T_ else 0.0)
            out["margin"][sc] = mg
            out.setdefault("company_path", {})[sc] = [round(x, 6) for x in path]
            out["margin_pinned"] = [i <= pin_m for i in range(N)]
            out["company_margin"][sc] = comp
            if abs(comp[-1] - path[-1]) > 0.02:
                flags.append(f"SEGMENT MARGINS ({sc}): the mix gives a terminal EBIT margin of {comp[-1]:.1%} against the "
                             f"company-level path's {path[-1]:.1%} - say which segment drives the difference.")
        out["total_growth"][sc] = tot_g
        out["pinned"][sc] = pinned
        anchored = [s for s in names if (seg_anchor.get(s) or {}).get(sc)]
        if hold:
            out["basis"].update({s: (out["basis"].get(s) or "") + " [held at its own trend: out of the calibration]" for s in hold})
        out["basis_summary"][sc] = ("calibrated to the scenario total in pinned years; segment anchors for "
                                    + ", ".join(anchored) if anchored else
                                    "calibrated to the scenario total in pinned years; trailing segment growth, "
                                    "faded to terminal growth after (formula, no evidence)")
    flags.append(f"Revenue built from {len(names)} {out['basis_type']} lines ({', '.join(names)}) on the Drivers tab"
                 + (f"; units x price for {', '.join(units)}" if units else "") + ".")
    return out


# ---------------------------------------------------------------- main
def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    raw = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    forced_years = None
    if "--years" in sys.argv:
        forced_years = int(sys.argv[sys.argv.index("--years") + 1])

    flags = []
    co = raw["company"]
    country = co.get("hq_country", "US")
    # Discount-rate, tax and growth defaults follow the currency of the CASH FLOWS, not the
    # listing: BYD is HK-listed but earns and reports in CNY, so it gets China's defaults.
    CURRENCY_COUNTRY = {"USD": "US", "KRW": "KR", "JPY": "JP", "CNY": "CN", "HKD": "HK"}
    rate_country = CURRENCY_COUNTRY.get(co.get("reporting_currency"), country)
    cdef = COUNTRY_DEFAULTS.get(rate_country, COUNTRY_DEFAULTS["US"])

    # ---------- annual actuals
    A = pivot(raw["annual"], "M.name")
    periods = sorted({d for s in A.values() for d in s})
    # keep the most recent N_HIST periods that have revenue
    periods = [p for p in periods if A.get("income_statement_sales", {}).get(p) is not None]
    n_hist = int(raw.get("n_hist", 5))
    periods = periods[-n_hist:]
    _rv = [A.get("income_statement_sales", {}).get(q) for q in periods]
    if len(_rv) >= 2 and _rv[-2] and _rv[-1] is not None and abs(_rv[-1] / _rv[-2] - 1) > 0.25 \
            and not raw.get("continuing_history"):
        flags.append(f"HISTORY BREAK?: revenue moved {_rv[-1] / _rv[-2] - 1:+.0%} in the last actual year. If a business was "
                     "sold or reclassified as discontinued, record the continuing-operations revenue and EBIT for earlier "
                     "years in raw.json['continuing_history'] (from the restated comparatives in the latest filing) and re-run; "
                     "otherwise say why the move is real.")
    if len(periods) < 3:
        flags.append(f"THIN HISTORY: only {len(periods)} annual periods with revenue. Ask the user before proceeding.")

    def s(metric):
        return [A.get(metric, {}).get(p) for p in periods]

    def s0(metric):
        return [x if x is not None else 0.0 for x in s(metric)]

    # Derive LT debt excl leases where Distilla leaves it blank
    ltd_x = s("balance_sheet_long_term_debt_excl_lease_obligations")
    ltd = s("balance_sheet_long_term_debt")
    lease = s0("balance_sheet_capital_and_operating_lease_obligations")
    for i, v in enumerate(ltd_x):
        if v is None and ltd[i] is not None:
            A["balance_sheet_long_term_debt_excl_lease_obligations"][periods[i]] = ltd[i] - lease[i]
    # Intangibles: prefer total intangibles; else goodwill + other intangibles
    for p in periods:
        if A.get("balance_sheet_intangible_assets", {}).get(p) is None:
            gw = A.get("balance_sheet_goodwill", {}).get(p) or 0.0
            oi = A.get("balance_sheet_other_intangible_assets", {}).get(p) or 0.0
            A["balance_sheet_intangible_assets"][p] = gw + oi
    # D&A: prefer cash-flow D&A (always the full non-cash charge), else IS D&A
    for p in periods:
        if A.get("cash_flow_depreciation_depletion_and_amortization", {}).get(p) is None:
            A["cash_flow_depreciation_depletion_and_amortization"][p] = \
                A.get("income_statement_depreciation_and_amortization_expense", {}).get(p)

    required = ["income_statement_sales", "income_statement_ebit_operating_income",
                "income_statement_pretax_income", "income_statement_income_taxes",
                "income_statement_net_income", "balance_sheet_total_assets",
                "balance_sheet_total_liabilities", "balance_sheet_total_shareholders_equity",
                "balance_sheet_cash_and_short_term_investments", "balance_sheet_total_current_assets",
                "balance_sheet_total_current_liabilities", "cash_flow_net_operating_cash_flow",
                "cash_flow_capital_expenditures", "income_statement_cost_of_goods_sold_cogs_incl_d_and_a"]
    itemised = ["balance_sheet_other_current_assets", "balance_sheet_other_current_liabilities",
                "balance_sheet_other_assets", "balance_sheet_other_liabilities",
                "cash_flow_funds_from_operations", "cash_flow_changes_in_working_capital",
                "cash_flow_net_investing_cash_flow", "cash_flow_net_financing_cash_flow"]
    absent = [m for m in itemised if m not in A]
    if absent:
        flags.append(f"NOT PULLED from Distilla: {absent}. History will not reconcile line by line - "
                     "re-query with the full metric list in distilla_queries.md.")
    for m in required:
        miss = [p for p in periods if A.get(m, {}).get(p) is None]
        if miss:
            flags.append(f"MISSING {m} for {miss} (treated as 0 in the model - review).")

    # historical balance check (as reported)
    for i, p in enumerate(periods):
        ta = s0("balance_sheet_total_assets")[i]
        rhs = (s0("balance_sheet_total_liabilities")[i] + s0("balance_sheet_total_shareholders_equity")[i]
               + s0("balance_sheet_accumulated_minority_interest")[i])
        if ta and abs(ta - rhs) / ta > 0.005:
            flags.append(f"HISTORICAL BS DOES NOT TIE in {p}: assets {ta:,.0f} vs L+E {rhs:,.0f}.")

    rev = s0("income_statement_sales")
    cogs = s0("income_statement_cost_of_goods_sold_cogs_incl_d_and_a")
    ebit = s0("income_statement_ebit_operating_income")
    da = s0("cash_flow_depreciation_depletion_and_amortization")
    pretax = s0("income_statement_pretax_income")
    tax = s0("income_statement_income_taxes")
    ni = s0("income_statement_net_income")
    mi = s0("income_statement_minority_interest")
    rec = s0("balance_sheet_short_term_receivables")
    inv = s0("balance_sheet_inventories")
    ap = s0("balance_sheet_accounts_payable")
    cash = s0("balance_sheet_cash_and_short_term_investments")
    tca = s0("balance_sheet_total_current_assets")
    tcl = s0("balance_sheet_total_current_liabilities")
    std = s0("balance_sheet_short_term_debt_and_curr_portion_long_term_debt")
    ltdx = [A["balance_sheet_long_term_debt_excl_lease_obligations"].get(p) or 0.0 for p in periods]
    capex = [abs(x) for x in s0("cash_flow_capital_expenditures")]
    div = [abs(x) for x in s0("cash_flow_cash_dividends_paid")]
    bb = [abs(x) for x in s0("cash_flow_repurchase_of_common_and_preferred_stock")]
    int_inc = s("income_statement_nonoperating_interest_income")
    # Cost of debt uses gross interest (before capitalized interest); the net line is the fallback
    int_exp = [g if g is not None else n_ for g, n_ in zip(s("income_statement_gross_interest_expense"),
                                                        s("income_statement_interest_expense"))]

    def safe(a, b):
        return a / b if b else None

    oca = [tca[i] - cash[i] - rec[i] - inv[i] for i in range(len(periods))]
    ocl = [tcl[i] - std[i] - ap[i] for i in range(len(periods))]
    L = len(periods)
    last3 = slice(max(0, L - 3), L)
    hist_ratios = {
        "revenue_growth": [None] + [safe(rev[i], rev[i - 1]) - 1 if rev[i - 1] else None for i in range(1, L)],
        "gross_margin": [safe(rev[i] - cogs[i], rev[i]) for i in range(L)],
        "ebit_margin": [safe(ebit[i], rev[i]) for i in range(L)],
        "da_pct_rev": [safe(da[i], rev[i]) for i in range(L)],
        "capex_pct_rev": [safe(capex[i], rev[i]) for i in range(L)],
        "dso": [safe(rec[i] * 365, rev[i]) for i in range(L)],
        "dio": [safe(inv[i] * 365, cogs[i]) for i in range(L)],
        "dpo": [safe(ap[i] * 365, cogs[i]) for i in range(L)],
        "oca_pct_rev": [safe(oca[i], rev[i]) for i in range(L)],
        "ocl_pct_rev": [safe(ocl[i], rev[i]) for i in range(L)],
        "tax_rate": [safe(tax[i], pretax[i]) if pretax[i] > 0 else None for i in range(L)],
        "payout": [safe(div[i], ni[i]) if ni[i] > 0 else None for i in range(L)],
        "buyback_pct_ni": [safe(bb[i], ni[i]) if ni[i] > 0 else None for i in range(L)],
        "mi_pct": [safe(mi[i], ni[i] + mi[i]) if (ni[i] + mi[i]) else None for i in range(L)],
    }
    for i in range(1, L):
        if rev[i - 1] == 0:
            hist_ratios["revenue_growth"][i] = None

    # cash yield / cost of debt from history when interest lines exist
    cy_hist, kd_hist = [], []
    for i in range(1, L):
        if int_inc[i] not in (None, 0) and (cash[i] + cash[i - 1]):
            cy_hist.append(int_inc[i] / ((cash[i] + cash[i - 1]) / 2))
        d_avg = (std[i] + ltdx[i] + std[i - 1] + ltdx[i - 1]) / 2
        if int_exp[i] not in (None, 0) and d_avg:
            kd_hist.append(int_exp[i] / d_avg)

    # ---------- consensus
    C = pick_latest_consensus(raw.get("consensus"))
    last_fye = periods[-1]
    cons_periods = sorted(p for p in C.get("sales_mean", {}) if p > last_fye and C["sales_mean"][p])
    ncons = len(cons_periods)
    if ncons == 0:
        flags.append("NO CONSENSUS: forecast drafted from historical trends only.")

    # ---------- WACC inputs (live values from raw['wacc'] if the assistant found them)
    W = raw.get("wacc", {})
    mkt = raw["market"]
    bridge = raw["bridge"]
    wacc = {}

    def take(key, default, label):
        v = W.get(key)
        src = W.get(key + "_source")
        if v is None:
            wacc[key] = default
            wacc[key + "_source"] = f"DEFAULT ({label}, as of {DEFAULTS_AS_OF}) - verify"
            flags.append(f"WACC input '{key}' uses a default ({default:.2%}). Replace with a live source if possible.")
        else:
            wacc[key] = v
            wacc[key + "_source"] = src or "user/web (source not recorded)"

    take("rf", cdef["rf"], f"{rate_country} 10y govt yield")
    take("erp", MATURE_ERP, "mature-market ERP")
    if W.get("crp") is None and rate_country == "US":
        wacc["crp"], wacc["crp_source"] = 0.0, "US cash flows: no country risk premium"
    else:
        take("crp", cdef["crp"], f"{rate_country} country risk premium")

    fx = mkt.get("fx_reporting_per_price", 1.0)
    # Stock splits after the bridge date: Distilla's share counts are pre-split while the price is post-split
    # (Tokyo Electron 5-for-1, 29 Sep 2026). Record them as found; the script scales the shares once.
    splits = [s_ for s_ in (mkt.get("splits_after_bridge") or []) if s_.get("ratio") not in (None, 1, 1.0)]
    if splits:
        f_ = 1.0
        for s_ in splits:
            f_ *= float(s_["ratio"])
        for k_ in ("diluted_shares", "basic_shares"):
            if bridge.get(k_):
                bridge[k_] = bridge[k_] * f_
        bridge["shares_source"] = ((bridge.get("shares_source") or f"Distilla diluted shares, {bridge.get('as_of')}")
                                  + f" x {f_:g} for split(s) after the bridge date ("
                                  + ", ".join(f"{s_['ratio']:g}-for-1 {s_.get('date', '')}" for s_ in splits) + ")")
        flags.append(f"STOCK SPLIT: share counts scaled x{f_:g} for split(s) after the bridge date - per-share history "
                     "(EPS, DPS) in the Model tab stays pre-split; check broker targets are on the same basis.")
    mcap = mkt["price"] * fx * bridge["diluted_shares"]
    debt_total = bridge.get("st_debt", 0) + bridge.get("lt_debt", 0) + bridge.get("leases", 0)
    vm = mkt.get("vendor_market_cap_usd")
    if vm:
        rebuilt_usd = mkt["price"] * bridge["diluted_shares"] * mkt.get("usd_per_price_currency", 1.0)
        gap = rebuilt_usd / vm - 1
        mkt["mcap_check"] = f"rebuilt {rebuilt_usd:,.0f} vs Distilla market_cap {vm:,.0f} (USD m): {gap:+.1%}"
        if abs(gap) > 0.10:
            flags.append(f"MARKET CAP CHECK: rebuilt market cap is {gap:+.1%} from Distilla's - check the share "
                         "count basis (classes, ADR ratio) and the FX rate before trusting value per share.")
    bs_ = bridge.get("basic_shares")
    if bs_ and bridge.get("diluted_shares") and bridge["diluted_shares"] > 1.03 * bs_:
        flags.append(f"SHARE COUNT: diluted shares {bridge['diluted_shares']:,.1f}m are {bridge['diluted_shares'] / bs_ - 1:.1%} above "
                     f"basic {bs_:,.1f}m. If the difference is convertible-bond conversion while the bonds also sit in "
                     "debt, keep one: basic shares, or remove the convertible from debt.")
    # ---------- finance arm (captive finance) valued separately: see SKILL.md field notes
    fa_raw = raw.get("finance_arm") or {}
    fa = None
    ta_last = s0("balance_sheet_total_assets")[-1]
    if fa_raw.get("assets") and ta_last:
        share = fa_raw["assets"] / ta_last
        if share < 0.10:
            flags.append(f"Finance segment '{fa_raw.get('name')}' is {share:.0%} of total assets (<10%): not separated.")
        else:
            fa = {"on": 1, "name": fa_raw.get("name", "Finance arm"), "assets": fa_raw["assets"],
                  "asset_share": round(share, 4), "period": fa_raw.get("period"),
                  "segment_source": fa_raw.get("segment_source", "Distilla by_segment_financials"),
                  "profit": fa_raw.get("profit_pretax") or 0.0, "revenue": fa_raw.get("revenue"),
                  "pb_override": fa_raw.get("pb_override")}
            if fa_raw.get("period") and fa_raw["period"][:7] != periods[-1][:7]:
                flags.append(f"Finance segment figures are for {fa_raw['period']}, not the last actual year "
                             f"{periods[-1]} - the profit share of revenue may be off.")
            bs_src = fa_raw.get("bs_source") or "annual report"
            if fa_raw.get("equity") is not None:
                fa["equity"], fa["equity_basis"] = fa_raw["equity"], f"{bs_src} (live)"
            else:
                lev, lsrc = fa_raw.get("leverage"), fa_raw.get("leverage_source")
                if lev is None:
                    lev, lsrc = 7.0, "DEFAULT 7x debt/equity (typical captive finance) - verify"
                    flags.append("Finance arm: no equity or leverage found - equity estimated at a DEFAULT 7x leverage.")
                fa["equity"] = fa["assets"] / (1 + lev)
                fa["equity_basis"] = f"estimate: assets / (1 + leverage {lev:.2f}x; {lsrc})"
            if fa_raw.get("debt") is not None:
                fa["debt"], fa["debt_basis"] = fa_raw["debt"], f"{bs_src} (live)"
            else:
                fa["debt"] = fa["assets"] - fa["equity"]
                fa["debt_basis"] = "estimate: assets - estimated equity"
            fa["debt"] = min(fa["debt"], bridge.get("st_debt", 0) + bridge.get("lt_debt", 0))
            if fa_raw.get("lt_receivables") is not None:
                fa["lt_rec"] = min(fa_raw["lt_receivables"], bridge.get("lt_investments", 0))
                fa["lt_rec_basis"] = fa_raw.get("lt_receivables_source") or bs_src
            else:
                fa["lt_rec"], fa["lt_rec_basis"] = 0.0, "not found - long-term investments kept whole"
                flags.append("Finance arm: long-term finance receivables not found - they may sit in long-term "
                             "investments AND in the finance arm's equity value (double count). Source them.")
            if fa_raw.get("st_receivables") is not None and rec[-1]:
                fa["rec_share"] = clamp(fa_raw["st_receivables"] / rec[-1], 0.0, 1.0)
                fa["rec_share_basis"] = f"current finance receivables {fa_raw['st_receivables']:,.0f} / receivables {rec[-1]:,.0f}"
            else:
                fa["rec_share"], fa["rec_share_basis"] = 0.0, "not found - finance receivables growth stays in the cash flow (conservative)"
            fa["profit_pct"] = fa["profit"] / rev[-1] if rev[-1] else 0.0
            ppe_last = s0("balance_sheet_net_property_plant_and_equipment")[-1]
            if fa_raw.get("leased_assets") is not None and ppe_last:
                fa["leased"] = min(fa_raw["leased_assets"], ppe_last)
                fa["leased_basis"] = (f"assets leased to customers inside net PP&E {ppe_last:,.0f} ({bs_src}); held flat - "
                                      "post-consensus capex and D&A run on the rest")
            else:
                fa["leased"], fa["leased_basis"] = 0.0, "no leased assets found in PP&E"
            if fa_raw.get("cash") is not None:
                fa["cash"] = min(fa_raw["cash"], bridge.get("cash", 0))
                fa["cash_basis"] = fa_raw.get("cash_source") or bs_src
            else:
                fa["cash"], fa["cash_basis"] = 0.0, "not found - bridge cash kept whole (finance-arm cash may count twice)"
                flags.append("Finance arm: its own cash not found - it may sit in bridge cash AND in its equity value.")
    # Effective tax: median of recent years with a normal (0-50%) rate; tax-benefit years are ignored
    valid_tax = sorted(t for t in hist_ratios["tax_rate"][last3] if t is not None and 0 <= t <= 0.5)
    if valid_tax:
        tax_eff = valid_tax[len(valid_tax) // 2]
        if tax_eff < 0.5 * cdef["tax"]:
            flags.append(f"Effective tax rate {tax_eff:.1%} is under half the statutory rate "
                         f"({cdef['tax']:.1%}) - credits, incentives or one-off charges. The draft fades it to "
                         f"statutory by the last forecast year (WACC and finance-arm ROE use statutory). Ask the "
                         f"user; their rate goes in assumption_overrides.")
    else:
        tax_eff = cdef["tax"]
        flags.append(f"Tax rate: no usable history, using statutory default {cdef['tax']:.1%}.")
    # Beta. Order: explicit override -> published betas (median, Blume-adjusted, sanity-checked
    # against the relevered sector beta) -> sector beta. Published betas for non-US listings are
    # often low-R2 (weak link to the benchmark), which is why the adjustment and band exist.
    sector = (co.get("sector") or "").lower()
    bu = next((b for k, b in SECTOR_UNLEVERED_BETA.items() if k in sector), DEFAULT_UNLEVERED_BETA)
    # Published betas are measured on the whole company's shares (finance arm included), so the
    # sector check relevers at consolidated leverage even when a finance arm is valued separately.
    de = debt_total / mcap if mcap else 0
    b_sector = bu * (1 + (1 - tax_eff) * de)
    raws = [float(x) for x in (W.get("beta_published") or []) if x is not None]
    if W.get("beta") is not None:
        wacc["beta"] = W["beta"]
        wacc["beta_source"] = W.get("beta_source", "user")
    elif raws:
        med = sorted(raws)[len(raws) // 2] if len(raws) % 2 else sum(sorted(raws)[len(raws) // 2 - 1:len(raws) // 2 + 1]) / 2
        adj = 2 / 3 * med + 1 / 3
        band = THRESHOLDS["beta_sector_band"]
        src = W.get("beta_published_sources", "published")
        if fa:
            # A finance arm's debt funds low-risk receivables, so relevering a sector beta at group
            # leverage overstates it (GM: 2.17). The published beta is the market's own measure: use it.
            wacc["beta"] = round(adj, 3)
            wacc["beta_source"] = (f"Published 5Y betas {raws} ({src}); median {med:.2f}, Blume-adjusted {adj:.2f}; "
                                   "sector check skipped - finance arm valued separately")
        elif (1 - band) * b_sector <= adj <= (1 + band) * b_sector:
            wacc["beta"] = round(adj, 3)
            wacc["beta_source"] = (f"Published 5Y betas {raws} ({src}); median {med:.2f}, Blume-adjusted {adj:.2f}; "
                                   f"within {band:.0%} of sector beta {b_sector:.2f}")
        else:
            wacc["beta"] = round((adj + b_sector) / 2, 3)
            wacc["beta_source"] = (f"Published 5Y betas {raws} ({src}); median {med:.2f}, Blume-adjusted {adj:.2f}; "
                                   f"more than {band:.0%} from sector beta {b_sector:.2f} -> 50/50 blend {wacc['beta']:.2f}")
            flags.append(f"Beta: published betas ({med:.2f} raw, {adj:.2f} adjusted) differ a lot from the sector "
                         f"beta {b_sector:.2f}; blended to {wacc['beta']:.2f}. Often a weak link to the benchmark "
                         f"(foreign listing, low R-squared). Confirm with the user.")
    else:
        wacc["beta"] = round(b_sector, 3)
        wacc["beta_source"] = (f"DEFAULT: sector unlevered beta {bu:.2f} ('{co.get('sector')}') relevered at "
                               f"D/E {de:.1%} - verify")
        flags.append(f"Beta not found live; relevered sector beta {b_sector:.2f} used.")
    wacc["beta_sector"] = round(b_sector, 3)

    rf = wacc["rf"]
    # Two different debt costs:
    #  - kd_book: historical interest / average debt -> drives forecast interest expense on existing debt
    #  - kd (WACC): marginal cost of new debt today -> never below rf + a spread
    kd_h = clamp(avg(kd_hist), 0.0, 0.20)
    kd_ind = None
    if fa and int_exp[-1] not in (None, 0):
        d_ind = std[-1] + ltdx[-1] - fa["debt"]
        if d_ind > 0:
            kd_ind = clamp(int_exp[-1] / d_ind, 0.0, 0.20)
    kd_book = kd_h if (kd_h and kd_h > 0.005) else rf + 0.015
    kd = W.get("kd_pretax")
    if kd is None:
        spread = W.get("credit_spread", 0.015)
        if kd_ind and kd_ind > rf + 0.002:
            kd = kd_ind
            wacc["kd_pretax_source"] = ("Interest expense / industrial debt (consolidated debt less finance-arm "
                                        "debt; Distilla + finance-arm balance sheet)")
        elif kd_h and kd_h > rf + 0.002 and not fa:
            kd = kd_h
            wacc["kd_pretax_source"] = "Historical gross interest expense / average debt (Distilla)"
        else:
            kd = rf + spread
            why = ("finance-arm interest sits in cost of sales" if fa else f"historical book rate {(kd_h or 0):.2%} is below today's rf")
            wacc["kd_pretax_source"] = f"DEFAULT rf + {spread*1e4:.0f}bp spread ({why}) - verify"
    else:
        wacc["kd_pretax_source"] = W.get("kd_pretax_source", "user/web")
    wacc["kd_pretax"] = round(kd, 4)
    # A rate under half statutory (credits, one-off charges) is not a long-run rate: the forecast fades it
    # to statutory, and the long-run uses (WACC, finance-arm ROE, pension after tax) take statutory.
    tax_low = tax_eff < 0.5 * cdef["tax"]
    wacc["tax_rate"] = round(cdef["tax"] if tax_low else tax_eff, 4)
    wacc["target_debt_weight"] = W.get("target_debt_weight")  # None = use current market weights
    # B: discount rates the brokers' notes state, beside the model's. The user picks; nothing changes here.
    bdr = [b for b in (raw.get("broker_discount_rates") or []) if b.get("rate") is not None]
    ke_model = wacc["rf"] + wacc["beta"] * wacc["erp"] + wacc["crp"]
    if bdr:
        def _med(xs):
            xs = sorted(xs)
            return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
        bw = [float(b["rate"]) for b in bdr if str(b.get("basis", "WACC")).upper() == "WACC"]
        bk = [float(b["rate"]) for b in bdr if str(b.get("basis", "")).lower().startswith("cost")]
        wacc["broker_rates"] = "; ".join(f"{b.get('broker')} {float(b['rate']):.1%} {b.get('basis', 'WACC')} ({b.get('date', '')})" for b in bdr)
        wacc["broker_wacc_median"] = round(_med(bw), 4) if bw else None
        if bk and not bw:  # a cost of equity only: compare like with like, and price it at today's weights
            wacc["broker_ke_median"] = round(_med(bk), 4)
        wacc["broker_basis"] = "cost of equity" if wacc.get("broker_ke_median") else "WACC"
        flags.insert(0, f"DISCOUNT RATE vs BROKERS: brokers' notes state {wacc['broker_rates']}. The model's cost of equity is "
                        f"{ke_model:.1%}; the workbook prices the value at the brokers' median rate beside the model's. "
                        "If they differ by more than 3 points, this is the first judgment call: ask which rate to use.")

    # ---------- forecast horizon & dates
    g_term = W.get("terminal_growth")
    if g_term is None:  # absent or null in raw.json -> country default
        g_term = cdef["g"]
    g_term = min(g_term, rf)  # terminal growth above the risk-free rate is rarely defensible
    base_rev_path = [C["sales_mean"][p] for p in cons_periods]
    cagr = None
    if ncons:
        cagr = (base_rev_path[-1] / rev[-1]) ** (1 / ncons) - 1
    # 10 years when growth is still far above terminal at the end of consensus; otherwise the fade
    # to terminal growth would be an unrealistic cliff (Duolingo: 13.5% in year 3).
    last_cons_g = None
    if ncons >= 2:
        last_cons_g = base_rev_path[-1] / base_rev_path[-2] - 1
    elif ncons == 1:
        last_cons_g = base_rev_path[0] / rev[-1] - 1
    steep = last_cons_g is not None and last_cons_g - g_term > 0.06
    N = forced_years or (10 if ((cagr is not None and cagr > 0.15) or steep) else 5)
    N = max(N, ncons)
    fc_periods = list(cons_periods[:N])
    while len(fc_periods) < N:
        fc_periods.append(add_years(fc_periods[-1] if fc_periods else last_fye, 1))

    # ---------- drafting helper
    def fade(first_vals, n_total, end_val):
        vals = list(first_vals)
        k0 = len(vals)
        start = vals[-1] if vals else end_val
        for k in range(k0 + 1, n_total + 1):
            frac = (k - k0) / (n_total - k0) if n_total > k0 else 1
            vals.append(start + (end_val - start) * frac)
        return vals

    def path_from(sales_key, ebit_key):
        sp = [C.get(sales_key, {}).get(p) for p in cons_periods]
        ep = [C.get(ebit_key, {}).get(p) for p in cons_periods]
        if not ncons or any(v is None for v in sp):
            return None
        g, m = [], []
        prev = rev[-1]
        for i in range(ncons):
            g.append(sp[i] / prev - 1)
            prev = sp[i]
            m.append(ep[i] / sp[i] - charges_pct if ep[i] is not None else None)
        return g, m

    # historical reference points for anchoring and the peak guard (uses long_history if provided)
    LH = pivot(raw.get("long_history") or {}, "M.name")
    ref_rev = {**{p: v for p, v in LH.get("income_statement_sales", {}).items()}, **dict(zip(periods, rev))}
    ref_ebit = {**{p: v for p, v in LH.get("income_statement_ebit_operating_income", {}).items()}, **dict(zip(periods, ebit))}
    ref_m = {p: ref_ebit[p] / ref_rev[p] for p in sorted(ref_rev) if ref_rev.get(p) and ref_ebit.get(p) is not None}
    # G1: continuing-operations history (after a divestiture) replaces the reference points and peak-guard
    # averages and is the basis the basis gap is measured against (consensus covers the continuing
    # business); the Model tab still shows Distilla as delivered.
    _ch = {k: v for k, v in (raw.get("continuing_history") or {}).items() if isinstance(v, dict)}
    CH = pivot(_ch, "M.name")  # the 'source' text sits beside the series, not in them
    if CH:
        for q, v in CH.get("income_statement_sales", {}).items():
            ref_rev[q] = v
        for q, v in CH.get("income_statement_ebit_operating_income", {}).items():
            ref_ebit[q] = v
        ref_m = {q: ref_ebit[q] / ref_rev[q] for q in sorted(ref_rev) if ref_rev.get(q) and ref_ebit.get(q) is not None}
        flags.append("Continuing-operations history used for reference points and the peak guard "
                     f"({', '.join(sorted(q[:4] for q in CH.get('income_statement_sales', {})))}; "
                     f"{(raw.get('continuing_history') or {}).get('source', 'source not recorded')}).")
    # Recurring charges: consensus EBIT is often the company's ADJUSTED measure (it leaves out
    # restructuring and other special charges that recur). The gap is measured against Distilla's own
    # EBIT for the same year - the basis the model's history uses, which can already be close to the
    # adjusted figure (Caterpillar) - and the MEDIAN of up to 3 years is deducted from every
    # consensus-derived margin, so one exceptional year (GM 2025 EV charges) does not set it.
    rc = raw.get("basis_gap") or raw.get("recurring_charges") or {}
    charges_pct = 0.0
    if rc.get("pct_rev") is not None:
        charges_pct = float(rc["pct_rev"])
    elif rc.get("adjusted_by_year"):
        pcts, gaps = [], []
        for y, adj_ebit in rc["adjusted_by_year"].items():
            p_ = next((q for q in ref_rev if q[:4] == str(y)[:4] and ref_rev[q]), None)
            if p_ and num(adj_ebit) is not None and ref_ebit.get(p_) is not None:
                gap = num(adj_ebit) - ref_ebit[p_]
                gaps.append(f"{str(y)[:4]}: {num(adj_ebit):,.0f} - {ref_ebit[p_]:,.0f} = {gap:,.0f}")
                pcts.append(gap / ref_rev[p_])
        if pcts:
            srt = sorted(pcts)
            charges_pct = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
            if abs(charges_pct) < 0.0025:  # under 0.25% of revenue: the two bases agree
                charges_pct = 0.0
            rc["source"] = (rc.get("source") or "source not recorded") + "; adjusted - Distilla EBIT " + "; ".join(gaps)
    if charges_pct:
        flags.append(f"BASIS GAP: consensus follows the company's own operating profit, which runs {charges_pct:+.1%} of revenue "
                     f"against Distilla's EBIT (median; {rc.get('source', 'source not recorded')}); that gap comes off every "
                     "consensus-derived margin so the forecast is on Distilla's basis. Anchors must be on that basis. Say what "
                     "the gap is (recurring charges, other income) - it may carry value of its own.")
    hist_g = avg(hist_ratios["revenue_growth"][last3]) or 0.03
    hist_m = avg(hist_ratios["ebit_margin"][last3]) or 0.10
    scen = {}
    base = path_from("sales_mean", "ebit_mean")
    if base:
        bg, bm = base
        bm = [x if x is not None else hist_m for x in bm]
    else:
        bg, bm = [clamp(hist_g, -0.10, 0.25)], [hist_m]
    # Steady-state margin for years after consensus. Default: hold the last consensus margin.
    # Cyclical-peak guard: if that margin is > 1.5x the full-history average, fade to the midpoint
    # (a mid-cycle margin) instead of capitalising peak earnings forever.
    # Peak guard tests against the long-run average when 8+ years are available (a 5-year window can
    # sit inside one cycle: Caterpillar FY21-25 averaged 17.5% vs 13.5% over 2010-25).
    long_run = len(ref_m) >= 8
    hist_all_m = avg(list(ref_m.values())) if long_run else avg(hist_ratios["ebit_margin"])
    hist_span = f"{sorted(ref_m)[0][:4]}-{sorted(ref_m)[-1][:4]}" if long_run else f"{L}-yr"
    def steady(m_last):
        if hist_all_m and hist_all_m > 0 and m_last > 1.5 * hist_all_m and N > ncons:
            return (m_last + hist_all_m) / 2, True
        return m_last, False
    ss_base, peak = steady(bm[-1])
    if peak:
        flags.append(f"CYCLICAL PEAK GUARD: last consensus EBIT margin {bm[-1]:.1%} is >1.5x the "
                     f"{hist_span} average ({hist_all_m:.1%}); beyond-consensus margins fade to a mid-cycle "
                     f"{ss_base:.1%}. Confirm with the user - this is the biggest value driver.")
    if not rc and ncons and C.get("ebit_mean", {}).get(cons_periods[0]) and hist_ratios["ebit_margin"][-1] is not None:
        # cleared by raw.json basis_gap = {"none": true, "reason": ...} (rc is then non-empty)
        m1 = C["ebit_mean"][cons_periods[0]] / C["sales_mean"][cons_periods[0]]
        if m1 > hist_ratios["ebit_margin"][-1] + 0.03:
            flags.append(f"CONSENSUS BASIS: FY1 consensus EBIT margin {m1:.1%} is well above the last reported "
                         f"{hist_ratios['ebit_margin'][-1]:.1%}. If consensus follows the company's own (adjusted) "
                         "operating profit, record it by year in raw.json['basis_gap']['adjusted_by_year']; if you checked "
                         "and the move is real (an upcycle), record basis_gap = {'none': true, 'reason': ...}.")
    if rc.get("none"):
        flags.append(f"Basis gap checked: none - {rc.get('reason', 'reason not recorded')}.")
    scen["base"] = {"revenue_growth": fade(bg, N, g_term), "ebit_margin": fade(bm, N, ss_base)}
    for name, sk, ek, dg, dm in (("bull", "sales_high", "ebit_high", 0.02, 0.01),
                                 ("bear", "sales_low", "ebit_low", -0.02, -0.01)):
        p = path_from(sk, ek)
        if p and all(x is not None for x in p[1]):
            g_, m_ = p
        else:
            g_ = [x + dg for x in bg]
            m_ = [x + dm for x in bm]
        scen[name] = {"revenue_growth": fade(g_, N, g_term), "ebit_margin": fade(m_, N, steady(m_[-1])[0])}


    # ---------- Evidence-based anchors (set by the assistant AFTER the evidence step; see
    # references/evidence_guide.md). An anchor replaces a mechanical path only where the user or
    # the evidence gives a reason. Every key number gets a basis label so nothing is dressed up.
    anchors = raw.get("anchors") or {}
    basis = {"revenue_growth": {}, "ebit_margin": {}}
    for sc in ("base", "bull", "bear"):
        src = {"base": "consensus mean", "bull": "consensus high", "bear": "consensus low"}[sc]
        basis["revenue_growth"][sc] = {"type": "consensus + formula",
                                       "text": f"{src} for {ncons} yrs, then linear fade to terminal growth (formula, no evidence)"}
        basis["ebit_margin"][sc] = {"type": "consensus + formula",
                                    "text": f"{src} for {ncons} yrs, then " + ("hold (formula, no evidence)" if not peak
                                            else "fade to midpoint of last consensus and history average (peak guard formula, no evidence)")}

    def piecewise(points, n):
        """points: {index: value}; linear interpolation between known points, flat beyond the last."""
        ks = sorted(points)
        out = []
        for i in range(n):
            if i in points:
                out.append(points[i]); continue
            lo = max([k for k in ks if k < i], default=None)
            hi = min([k for k in ks if k > i], default=None)
            if lo is None:
                out.append(points[hi])
            elif hi is None:
                out.append(points[lo])
            else:
                out.append(points[lo] + (points[hi] - points[lo]) * (i - lo) / (hi - lo))
        return out

    def idx_of(date_str):
        """Forecast index of the fiscal year ending on/after date_str (or the last one)."""
        for i, p in enumerate(fc_periods):
            if p >= date_str[:10]:
                return i
        return N - 1

    for sc, a in (anchors.get("ebit_margin") or {}).items():
        cur = scen[sc]["ebit_margin"]
        h = idx_of(a["hold_until"]) if a.get("hold_until") else ncons - 1
        r = idx_of(a["reach_by"]) if a.get("reach_by") else N - 1
        pts = {i: cur[i] for i in range(min(h, ncons - 1) + 1)}
        hold_val = cur[min(h, ncons - 1)] if ncons else cur[0]
        for i in range(ncons, h + 1):
            pts[i] = hold_val
        pts[max(r, h + 1)] = a["terminal"]
        scen[sc]["ebit_margin"] = piecewise(pts, N)
        basis["ebit_margin"][sc] = {"type": a.get("basis_type", "evidence"), "text": a["basis"]}
    for sc, a in (anchors.get("revenue_growth") or {}).items():
        cur = scen[sc]["revenue_growth"]
        pts = {i: cur[i] for i in range(ncons)}
        for d, v in (a.get("overrides") or {}).items():
            pts[idx_of(d)] = v
        pts[N - 1] = g_term
        scen[sc]["revenue_growth"] = piecewise(pts, N)
        basis["revenue_growth"][sc] = {"type": a.get("basis_type", "evidence"), "text": a["basis"]}
    if peak and (anchors.get("ebit_margin") or {}).get("base"):
        flags[:] = [f + " REPLACED in base by the evidence anchor (see the basis table)."
                    if f.startswith("CYCLICAL PEAK GUARD") else f for f in flags]
    if not anchors:
        flags.append("No evidence anchors yet: post-consensus growth and margins are FORMULA values with no "
                     "evidence behind them. Run the evidence step before the checkpoint.")

    # ---------- Revenue drivers (Drivers tab): segment revenue = last year x (1 + volume) x (1 + price), or
    # units x price per unit where Distilla has a unit series. Years the scenario total is pinned (consensus
    # years, and years a revenue anchor overrides) are calibrated: a common volume shift on the segments
    # without their own volume anchor makes the total match exactly. Other years run on the segment drivers,
    # fading to terminal growth (volume) and zero (price). "Other / eliminations" grows with the segment sum.
    drivers = build_drivers(raw.get("segments") or {}, periods, rev, fc_periods, N, ncons, scen, g_term,
                            (anchors.get("revenue_growth") or {}), idx_of, flags, ebit=ebit)
    if drivers:
        for sc in scen:
            scen[sc]["revenue_growth"] = drivers["total_growth"][sc]
            if drivers.get("margins_on"):
                scen[sc]["ebit_margin"] = drivers["company_margin"][sc]
                basis["ebit_margin"][sc] = {"type": "segment margins",
                                            "text": "segment margins on the Drivers tab: calibrated to consensus EBIT in "
                                                    "consensus years, then each line's anchor or the company-level path "
                                                    "(" + basis["ebit_margin"][sc]["text"] + "); total = mix"}
            if drivers["pinned"][sc] != [True] * N:
                basis["revenue_growth"][sc] = {
                    "type": "drivers",
                    "text": basis["revenue_growth"][sc]["text"].split(", then")[0]
                    + "; segment drivers after that (Drivers tab: " + drivers["basis_summary"][sc] + ")"}

    reference_points = {"ebit_margin_by_year": {p[:4]: round(v, 4) for p, v in ref_m.items()},
                        "ebit_margin_avg": round(sum(ref_m.values()) / len(ref_m), 4) if ref_m else None,
                        "ebit_margin_max": max(ref_m.values()) if ref_m else None,
                        "ebit_margin_min": min(ref_m.values()) if ref_m else None}

    # ---------- accounting standard -> lease treatment in the equity bridge
    standard = co.get("accounting_standard") or DEFAULT_STANDARD.get(country)
    if standard is None:
        standard = "IFRS"
        flags.append("Accounting standard unknown (Japan uses both J-GAAP and IFRS): assumed IFRS, so "
                     "lease liabilities are subtracted in the bridge. Confirm with the user.")
    if raw.get("subtract_leases") is not None:
        subtract_leases = int(raw["subtract_leases"])
    else:
        subtract_leases = 0 if standard in ("US_GAAP", "J_GAAP") else 1

    # ---------- IFRS 16 leases: new leases are modelled as debt-financed asset additions.
    # Right-of-use additions (% revenue) go into PP&E and the lease liability and are deducted in
    # FCF like capex; principal is repaid at a rate on the beginning liability. Existing leases are
    # covered by subtracting the lease liability in the equity bridge. US GAAP / J-GAAP: none.
    lease_bal = s0("balance_sheet_capital_and_operating_lease_obligations")
    lease_rep = [abs(x) for x in s0("cash_flow_repayments_of_operating_lease_liabilities")]
    if subtract_leases:
        lease_add_pct = avg([lease_rep[i] / rev[i] for i in range(max(0, L - 3), L) if rev[i]]) or 0.0
        rates = [lease_rep[i] / lease_bal[i - 1] for i in range(1, L) if lease_bal[i - 1] > 0 and lease_rep[i] > 0]
        lease_rate = sorted(rates[-3:])[len(rates[-3:]) // 2] if rates else 0.0
        if lease_add_pct == 0 and lease_bal[-1] > 0.05 * rev[-1]:
            flags.append("Material lease liability but no lease repayments reported: new leases not modelled - check.")
    else:
        lease_add_pct, lease_rate = 0.0, 0.0

    # ---------- D&A: consensus-implied (EBITDA - EBIT) where available, else a depreciation
    # rate on beginning net PP&E. D&A must follow the asset base, not revenue: a price-driven
    # revenue jump (e.g. a memory up-cycle) does not double the depreciation charge.
    ppe = s0("balance_sheet_net_property_plant_and_equipment")
    dep_hist = [da[i] / ppe[i - 1] for i in range(1, L) if ppe[i - 1] > 0 and da[i] > 0]
    dep_rate = sorted(dep_hist[-3:])[len(dep_hist[-3:]) // 2] if dep_hist else 0.15
    da_override = []
    hist_da_pct = hist_ratios["da_pct_rev"][-1] or 0.0
    adjusted_seen = False
    for p in cons_periods[:N]:
        e, b, sm = (C.get("ebitda_mean", {}).get(p), C.get("ebit_mean", {}).get(p), C["sales_mean"].get(p))
        v = (e - b) / sm if (e is not None and b is not None and sm and e > b) else None
        # Guard: consensus EBITDA is often "adjusted" (adds back stock-based comp), so EBITDA - EBIT
        # would overstate D&A and inflate FCF. Reject implied D&A far above the company's actual D&A.
        if v is not None and v > max(2 * hist_da_pct, hist_da_pct + 0.03):
            v, adjusted_seen = None, True
        da_override.append(v)
    if adjusted_seen:
        flags.append(f"Consensus EBITDA looks ADJUSTED (implied D&A far above actual {hist_da_pct:.1%} of revenue - "
                     "probably excludes stock-based comp). Not used for D&A; the depreciation rate is used instead. "
                     "Also do not use it for exit multiples.")
    da_override += [None] * (N - len(da_override))

    # ---------- Operating expenses (SG&A, R&D, other) as % revenue. Gross margin is then
    # EBIT margin + opex %, so it moves with the scenario and opex can never turn negative.
    last_opex = (rev[-1] - cogs[-1] - ebit[-1]) / rev[-1] if rev[-1] else 0.2
    opex_path = []
    for i, p in enumerate(cons_periods[:N]):
        gi, sm, eb = (C.get("gross_inc_mean", {}).get(p), C["sales_mean"].get(p), C.get("ebit_mean", {}).get(p))
        opex_path.append((gi - eb) / sm if (gi is not None and eb is not None and sm and gi >= eb) else None)
    if not any(x is not None for x in opex_path) and ncons:
        flags.append("No consensus gross profit: opex % revenue held at last actual year.")
    filled, lastv = [], max(last_opex, 0.0)
    for x in opex_path + [None] * (N - len(opex_path)):
        lastv = x if x is not None else lastv
        filled.append(lastv)
    opex_path = filled
    for i in range(N):
        mmax = max(scen[k]["ebit_margin"][i] for k in scen)
        if mmax + opex_path[i] > THRESHOLDS["max_gross_margin"]:
            opex_path[i] = max(0.0, THRESHOLDS["max_gross_margin"] - mmax)
            flags.append(f"Opex % capped in year {i + 1} so implied gross margin stays <= "
                         f"{THRESHOLDS['max_gross_margin']:.0%}.")

    # ---------- Capex: consensus capex / sales where available. Afterwards, the capex that keeps
    # PP&E / revenue stable given the depreciation rate and growth: capex/rev = k*(d+g)/(1+g).
    capex_cons = []
    for p in cons_periods[:N]:
        cx, sm = C.get("capex_mean", {}).get(p), C["sales_mean"].get(p)
        capex_cons.append(abs(cx) / sm if (cx is not None and sm) else None)
    hist_capex = avg(hist_ratios["capex_pct_rev"][last3]) or 0.05
    capex_cons = [x if x is not None else hist_capex for x in capex_cons]
    # simulate the base-case PP&E path through the consensus years
    # A finance arm's assets leased to customers are held flat inside PP&E: they are the finance arm's
    # business (valued separately), and consensus capex / D&A usually leave them out. Post-consensus capex
    # and D&A then run on industrial PP&E, at the depreciation rate the last consensus year implies.
    leased = min(fa["leased"], ppe[-1]) if fa else 0.0
    r_, p_ = rev[-1], ppe[-1] - leased
    g_base = scen["base"]["revenue_growth"]
    d_last = p_beg_last = None
    for i in range(len(capex_cons)):
        r_ *= 1 + g_base[i]
        d_ = da_override[i] * r_ if da_override[i] is not None else dep_rate * p_
        d_last, p_beg_last = (d_ if da_override[i] is not None else None), p_
        p_ = p_ + (capex_cons[i] + lease_add_pct) * r_ - d_
    if leased and d_last and p_beg_last and p_beg_last > 0:
        dep_rate = d_last / p_beg_last
    k_ratio = p_ / r_ if r_ else 0
    capex_path = list(capex_cons)
    for i in range(len(capex_cons), N):
        g_ = g_base[i]
        capex_path.append(max(0.0, k_ratio * (dep_rate + g_) / (1 + g_) - lease_add_pct))
    da_pct = avg(hist_ratios["da_pct_rev"][last3]) or 0.03

    def last_or_avg(key, lo, hi, default):
        v = hist_ratios[key][-1]
        if v is None:
            v = avg(hist_ratios[key][last3])
        return clamp(v, lo, hi) if v is not None else default

    cash_yield = clamp(avg(cy_hist), 0, 0.10)
    if cash_yield is None:
        cash_yield = max(0.0, rf - 0.01)

    assumptions = {
        "scenario": 1,
        "scenario_names": ["Base", "Bull", "Bear"],
        "base": scen["base"], "bull": scen["bull"], "bear": scen["bear"],
        "opex_pct_rev": opex_path,
        "da_override_pct_rev": da_override,
        "dep_rate": [round(dep_rate, 4)] * N,
        "lease_add_pct_rev": [round(lease_add_pct, 4)] * N,
        "lease_repay_rate": [round(lease_rate, 4)] * N,
        "capex_pct_rev": capex_path,
        "dso": [last_or_avg("dso", 0, 365, 45)] * N,
        "dio": [last_or_avg("dio", 0, 365, 45)] * N,
        "dpo": [last_or_avg("dpo", 0, 365, 45)] * N,
        "oca_pct_rev": [last_or_avg("oca_pct_rev", -1, 1, 0.02)] * N,
        "ocl_pct_rev": [last_or_avg("ocl_pct_rev", -1, 1, 0.05)] * N,
        "tax_rate": ([tax_eff + (cdef["tax"] - tax_eff) * i / max(1, N - 1) for i in range(N)] if tax_low
                     else [tax_eff] * N),
        "cash_yield": [round(cash_yield, 4)] * N,
        "cost_of_debt": [round(kd_book, 4)] * N,
        "payout": [clamp(avg(hist_ratios["payout"][last3]), 0, 1.5) or 0.0] * N,
        "buyback_pct_ni": [clamp(avg(hist_ratios["buyback_pct_ni"][last3]), 0, 2.0) or 0.0] * N,
        "net_debt_issuance": [0.0] * N,
        "return_basis": 1,  # 1 = % of net income (default, from history); 2 = % of FCF (use when policy says so)
        "mi_pct": [clamp(avg(hist_ratios["mi_pct"][last3]), -0.5, 0.9) or 0.0] * N,
    }

    # ---------- exit multiple default: current EV / FY1 EBITDA
    ebitda1 = C.get("ebitda_mean", {}).get(cons_periods[0]) if (ncons and not adjusted_seen) else None
    if ebitda1 is None:
        ebitda1 = rev[-1] * (1 + scen["base"]["revenue_growth"][0]) * (scen["base"]["ebit_margin"][0] + da_pct)
    ev_now = (mcap + debt_total - (1 - subtract_leases) * bridge.get("leases", 0) - bridge.get("cash", 0)
              - bridge.get("lt_investments", 0) * raw.get("include_lt_investments", 1)
              + bridge.get("minority_interest", 0) + max(0.0, bridge.get("pension_deficit") or 0) * (1 - tax_eff))
    if fa:  # industrial EV: finance debt, finance receivables and the finance arm (at book) come out
        ev_now += -fa["debt"] + fa["lt_rec"] * raw.get("include_lt_investments", 1) - fa["equity"] + fa["cash"]
        ebitda1 -= fa["profit"] * (1 + scen["base"]["revenue_growth"][0])
    exit_mult = round(ev_now / ebitda1, 1) if ebitda1 and ebitda1 > 0 else 10.0

    model = {
        "company": co,
        "valuation_date": raw.get("valuation_date", dt.date.today().isoformat()),
        "units": co.get("units", "m"),
        "historical": {
            "periods": periods,
            "raw": {m: [A.get(m, {}).get(p) for p in periods] for m in sorted(A)},
        },
        "hist_ratios": hist_ratios,
        "consensus": {"periods": cons_periods,
                      "series": {m: [C.get(m, {}).get(p) for p in cons_periods] for m in sorted(C)}},
        "forecast_periods": fc_periods,
        "assumptions": assumptions,
        "market": mkt,
        "bridge": bridge,
        "include_lt_investments": raw.get("include_lt_investments", 1),
        "accounting_standard": standard,
        "subtract_leases": subtract_leases,
        "thresholds": THRESHOLDS,
        "wacc": wacc,
        # Exit multiple is user-supplied only (with a basis); today's market multiple is a reference, never
        # the terminal assumption - it prices today's growth, not a mature terminal year.
        "dcf": {"terminal_growth": round(g_term, 4),
                "exit_multiple": (raw.get("dcf") or {}).get("exit_multiple"),
                "exit_multiple_basis": (raw.get("dcf") or {}).get("exit_multiple_basis"),
                "market_multiple_ref": exit_mult, "tv_method": (raw.get("dcf") or {}).get("tv_method", 1),
                "mid_year": 1},
        "notes": [TERMINAL_FADE_NOTE],
        "basis": basis,
        "reference_points": reference_points,
        "finance_arm": fa or {},
        "drivers": drivers or {},
        "recurring_charges": {"pct_rev": round(charges_pct, 4), "source": rc.get("source", "")} if charges_pct else {},
        "multiple_history": raw.get("multiple_history") or {},
        "basis_gap": {"none": True, "reason": rc.get("reason", "")} if rc.get("none") else {},
        "evidence": [],  # filled by the assistant in the evidence step (see references/evidence_guide.md)
        "flags": flags,
    }
    # evidence and user-confirmed policies live in raw.json so re-drafting never loses them
    if raw.get("evidence"):
        model["evidence"] = raw["evidence"]
    rp_ = raw.get("returns") or {}
    if rp_:
        model["assumptions"]["return_basis"] = rp_.get("basis", 1)
        if "payout" in rp_:
            model["assumptions"]["payout"] = [rp_["payout"]] * N
        if "buyback" in rp_:
            model["assumptions"]["buyback_pct_ni"] = [rp_["buyback"]] * N
    # user-confirmed overrides (e.g. {"tax_rate": 0.24}) - constant across the forecast
    if "tax_rate" in (raw.get("assumption_overrides") or {}):
        flags[:] = [f for f in flags if not f.startswith("Effective tax rate")]
        flags.append(f"Tax rate set by the user: {raw['assumption_overrides']['tax_rate']:.1%}.")
    for k, v in (raw.get("assumption_overrides") or {}).items():
        cur_ = model["assumptions"].get(k)
        if isinstance(cur_, list):
            if isinstance(v, dict):  # per year: {"2027": 0.20} keyed by fiscal-year label
                for y, x in v.items():
                    for i_, q in enumerate(fc_periods):
                        if q[:4] == str(y)[:4]:
                            cur_[i_] = x
            elif isinstance(v, list):
                model["assumptions"][k] = (list(v) + [v[-1]] * N)[:N]
            else:
                model["assumptions"][k] = [v] * N
        if k == "tax_rate":
            model["wacc"]["tax_rate"] = v if not isinstance(v, (dict, list)) else model["wacc"]["tax_rate"]
    json.dump(model, open(out_path, "w"), indent=1, default=str)
    tax_eff = model["wacc"]["tax_rate"]  # the printout shows the values after user overrides

    # ---------- summary for the confirmation checkpoint
    cur = co.get("reporting_currency", "")
    print(f"\n{co.get('name')} ({co.get('ticker')}) - reporting currency {cur}, units {model['units']}")
    print(f"History: {periods[0]} .. {periods[-1]}   Forecast: {fc_periods[0]} .. {fc_periods[-1]} "
          f"({N} yrs, {ncons} consensus-anchored)")
    hdr = "".join(f"{p[:4]:>9}" for p in fc_periods)
    print(f"{'':28}{hdr}")

    def row(lbl, vals, pct=True):
        cells = "".join(f"{(v * 100 if pct else v):9.1f}" if v is not None else f"{'-':>9}" for v in vals)
        print(f"{lbl:28}{cells}")
    for sc in ("base", "bull", "bear"):
        row(f"{sc.title()} revenue growth %", scen[sc]["revenue_growth"])
        row(f"{sc.title()} EBIT margin %", scen[sc]["ebit_margin"])
    if drivers:
        print("Drivers (base): segment volume / price growth %, last actual revenue")
        for s_ in drivers["segments"]:
            d_ = drivers["scen"]["base"][s_]
            row(f"  {s_[:20]} vol", d_["volume"])
            if any(abs(x) > 1e-9 for x in d_["price"]):
                row(f"  {s_[:20]} price", d_["price"])
        if drivers.get("margins_on"):
            for s_ in drivers["segments"]:
                row(f"  {s_[:20]} margin", drivers["margin"]["base"][s_])
            print(f"  corporate / unallocated {drivers['corp_pct'][0]:+.1%} of revenue (held)")
        print(f"  other / eliminations last actual {drivers['other_hist'][-1]:,.0f} "
              f"({drivers['other_hist'][-1] / rev[-1]:+.1%} of revenue); pinned years: "
              f"{sum(drivers['pinned']['base'])} of {N}")
    row("Capex % revenue", capex_path)
    row("Opex % revenue", opex_path)
    row("D&A % rev (consensus)", da_override)
    print(f"Depreciation rate on beginning PP&E (after consensus): {dep_rate:.1%}")
    print(f"Accounting standard {standard}: lease liabilities {'subtracted' if subtract_leases else 'NOT subtracted'} in bridge; "
          f"new leases {lease_add_pct:.1%} of revenue, repaid at {lease_rate:.0%} of opening liability")
    print(f"\nHistorical (last FY): GM {hist_ratios['gross_margin'][-1]:.1%}, EBIT margin "
          f"{hist_ratios['ebit_margin'][-1]:.1%}, DSO {assumptions['dso'][0]:.0f}, DIO "
          f"{assumptions['dio'][0]:.0f}, DPO {assumptions['dpo'][0]:.0f}")
    rb = "FCF" if model["assumptions"]["return_basis"] == 2 else "NI"
    tx = model["assumptions"]["tax_rate"]
    print(f"Tax {tx[0]:.1%}" + (f" -> {tx[-1]:.1%}" if abs(tx[-1] - tx[0]) > 1e-4 else "")
          + f" | payout {model['assumptions']['payout'][0]:.0%} of {rb} | buybacks "
          f"{model['assumptions']['buyback_pct_ni'][0]:.0%} of {rb}")
    print(f"WACC inputs: rf {wacc['rf']:.2%} ({wacc['rf_source']}); beta {wacc['beta']:.2f} ({wacc['beta_source']});")
    print(f"  ERP {wacc['erp']:.2%}; CRP {wacc['crp']:.2%}; Kd {wacc['kd_pretax']:.2%} ({wacc['kd_pretax_source']})")
    print(f"Terminal growth {g_term:.2%} | today's market EV/EBITDA {exit_mult:.1f}x (reference only; not a terminal assumption)")
    mh = raw.get("multiple_history") or {}
    if mh.get("avg") is not None:
        print(f"Own-history {mh.get('type')} since {mh.get('from')}: avg {float(mh['avg']):.1f}x, "
              f"low {float(mh['min']):.1f}x, high {float(mh['max']):.1f}x (n={mh.get('n')})")
    if charges_pct:
        print(f"Basis gap taken off consensus margins: {charges_pct:+.1%} of revenue ({rc.get('source', '')})")
    if wacc.get("broker_rates"):
        print(f"Discount rates in broker notes: {wacc['broker_rates']} | model cost of equity "
              f"{wacc['rf'] + wacc['beta'] * wacc['erp'] + wacc['crp']:.2%}")
    pdf = bridge.get("pension_deficit")
    print(f"Pension & retiree-benefit deficit in the bridge: " + (f"{pdf:,.0f} pre-tax, {max(0.0, pdf) * (1 - tax_eff):,.0f} "
          f"after tax ({bridge.get('pension_source', 'source not recorded')})" if pdf is not None else "not sourced (0)"))
    if mkt.get("mcap_check"):
        print("Market cap check: " + mkt["mcap_check"])
    if fa:
        roe = fa["profit"] * (1 - tax_eff) / fa["equity"] if fa["equity"] else None
        print(f"Finance arm valued separately - {fa['name']}: assets {fa['assets']:,.0f} ({fa['asset_share']:.0%} of total), "
              f"pre-tax profit {fa['profit']:,.0f} ({fa['profit_pct']:.1%} of revenue)")
        print(f"  equity {fa['equity']:,.0f} [{fa['equity_basis']}]; debt {fa['debt']:,.0f} [{fa['debt_basis']}]")
        print(f"  own cash {fa['cash']:,.0f} [{fa['cash_basis']}]; leased assets held flat {fa['leased']:,.0f} "
              f"[{fa['leased_basis']}]")
        print(f"  LT finance receivables {fa['lt_rec']:,.0f} [{fa['lt_rec_basis']}]; current share of receivables "
              f"{fa['rec_share']:.0%} [{fa['rec_share_basis']}]")
        if roe is not None:
            print(f"  after-tax ROE {roe:.1%}; justified P/B = (ROE - g) / (cost of equity - g) is computed in the workbook")
    rp = reference_points
    if rp["ebit_margin_by_year"]:
        yrs = sorted(rp["ebit_margin_by_year"])
        print(f"\nReference points for anchoring - EBIT margin {yrs[0]}-{yrs[-1]}: avg {rp['ebit_margin_avg']:.1%}, "
              f"max {rp['ebit_margin_max']:.1%}, min {rp['ebit_margin_min']:.1%}")
    print("Basis of key assumptions:")
    for drv in ("revenue_growth", "ebit_margin"):
        for sc in ("base", "bull", "bear"):
            b = basis[drv][sc]
            print(f"  {drv:15} {sc:5} [{b['type']}] {b['text']}")
    if flags:
        print("\nFLAGS:")
        for f in flags:
            print("  - " + f)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
segments.py - turn Distilla `by_segment_financials` cells into a clean annual segment table.

Usage:
    python segments.py cells.json                      # list the fields, segments and years found
    python segments.py cells.json --revenue "Sales and revenues" [--revenue "Total sales and revenues"]
                       [--units "Wholesale vehicle sales"] [--profit "Segment profit"] [--exclude "Cruise"]
                       [--rename "CMBU=Cloud Memory"]
                       [--out segments.json]

cells.json is the `query_entity` result on `ku_cell` for `by_segment_financials` (the rows, or the whole
result with "rows"); each row's `content` is a list of {segment, field_name, value, unit, time_period}.

Only full-year periods are kept ("YYYY-MM-DD to YYYY-MM-DD" spanning about a year): the cells mix
year-to-date quarters and halves, and some are mislabelled. Where a year has no full-year row, a
year-to-date row plus the quarter that completes it (back to back, together about a year) is joined into
one (Micron FY2026 = 9M YTD + Q4); the output says which years were joined. A field given more than once
(--revenue A --revenue B) merges label variants across filings, the first label winning per segment-year;
--rename maps segment names that differ between cells. Total / consolidated / elimination rows are
dropped (the model rebuilds the total and shows the gap to Distilla's revenue as "Other / eliminations").
When two cells give the same segment-year, the cell published later wins.

The output goes into raw.json["segments"] as {"field", "unit", "revenue": {segment: {end_date: value}},
"units": {...}, "units_field", "profit": {...}, "profit_field", "source"}; prepare_inputs.py checks it against
consolidated revenue. --profit takes the segment operating profit field (segment profit, operating income,
segment EBIT); with it the Drivers tab builds EBIT from segment margins.
"""
import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict

TOTAL_LIKE = re.compile(r"\b(total|overall|consolidated|reportable segments|elimination|reconcil|corporate|intersegment|"
                        r"inter-segment|adjustment|headquarters|unallocated)\b|^\s*(null|none|n/?a|-)?\s*$", re.I)
REVENUE_LIKE = re.compile(r"^(?!.*\bcost of\b)(?!.*/cost\b).*(sales|revenue)", re.I)
PROFIT_LIKE = re.compile(r"^(?!.*non-?operating)(?!.*\b(gross|net income|tax|interest (income|expense))\b).*"
                         r"(segment (profit|result)|operating (profit|income)|profit from operations|\bebita?\b|"
                         r"earnings.*before interest|profit \(loss\))", re.I)


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s.lower() in ("", "-", "null", "none", "n/a", "na"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def span(tp):
    """'2025-01-01 to 2025-12-31' -> (start, end) dates, else None."""
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s*$", str(tp or ""))
    return tuple(dt.date.fromisoformat(x) for x in m.groups()) if m else None


def full_year_end(tp):
    """'2025-01-01 to 2025-12-31' -> '2025-12-31' when the span is a year (330-380 days), else None."""
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s*$", str(tp or ""))
    if not m:
        return None
    a, b = (dt.date.fromisoformat(x) for x in m.groups())
    return b.isoformat() if 330 <= (b - a).days <= 380 else None


def load(path):
    data = json.load(open(path))
    rows = data.get("rows", data) if isinstance(data, dict) else data
    cells = []
    for r in rows:
        content = r.get("content", r if isinstance(r, list) else None)
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                content = None
        if isinstance(content, list):
            cells.append((str(r.get("cell_as_of_date") or r.get("published_at") or ""), content))
        elif isinstance(r, dict) and "field_name" in r:  # a flat list of content rows
            cells.append(("", [r]))
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cells")
    ap.add_argument("--revenue", action="append")
    ap.add_argument("--units", action="append")
    ap.add_argument("--profit", action="append")
    ap.add_argument("--hold", action="append", default=[],
                    help="segment kept at its own trend and margin, out of the calibration (a finance segment)")
    ap.add_argument("--rename", action="append", default=[], help="OLD=NEW segment name")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--keep", action="append", default=[],
                    help="keep only these segments (when one field holds several breakdowns: brand, product, channel)")
    ap.add_argument("--out")
    a = ap.parse_args()

    cells = load(a.cells)
    if not cells:
        sys.exit("No by_segment_financials content found in " + a.cells)
    ren = dict(r.split("=", 1) for r in a.rename if "=" in r)
    # (field, segment, end) -> (as_of, value, unit); later cells win. Partial spans kept for joining.
    best, part = {}, {}
    fields = defaultdict(set)
    for as_of, content in cells:
        for row in content:
            if not isinstance(row, dict):
                continue
            seg, field = str(row.get("segment") or "").strip(), str(row.get("field_name") or "").strip()
            seg = ren.get(seg, seg)
            v = num(row.get("value"))
            sp = span(row.get("time_period"))
            if not sp or not seg or not field or v is None:
                continue
            end = full_year_end(row.get("time_period"))
            if end:
                fields[field].add(seg)
                k = (field, seg, end)
                if k not in best or as_of >= best[k][0]:
                    best[k] = (as_of, v, str(row.get("unit") or ""))
            else:
                k = (field, seg, sp)
                if k not in part or as_of >= part[k][0]:
                    part[k] = (as_of, v, str(row.get("unit") or ""))
    # join a year-to-date span and the quarter that completes it into one full year (if none exists)
    joined = set()
    for (f, s, (a1, b1)), (as1, v1, u1) in list(part.items()):
        for (f2, s2, (a2, b2)), (as2, v2, u2) in part.items():
            if f2 != f or s2 != s or a2 != b1 + dt.timedelta(days=1):
                continue
            if 330 <= (b2 - a1).days <= 380 and (f, s, b2.isoformat()) not in best:
                best[(f, s, b2.isoformat())] = (max(as1, as2), v1 + v2, u1 or u2)
                fields[f].add(s)
                joined.add(b2.isoformat()[:4])

    if not a.revenue:
        print("Fields with full-year values (segments in each):")
        for f, segs in sorted(fields.items(), key=lambda x: -len(x[1])):
            years = sorted({k[2][:4] for k in best if k[0] == f})
            mark = ("  <- revenue candidate" if REVENUE_LIKE.search(f) else
                    "  <- profit candidate" if PROFIT_LIKE.search(f) and not TOTAL_LIKE.search(f) else "")
            print(f"  {f!r}: {len(segs)} segments, years {years}{mark}")
            for s in sorted(segs):
                print(f"      {'(dropped: total-like) ' if TOTAL_LIKE.search(s) else ''}{s}")
            if REVENUE_LIKE.search(f):  # several breakdowns in one field double-count
                for y in years:
                    parts = [v for (f_, s_, e_), (_, v, _) in best.items() if f_ == f and e_[:4] == y and not TOTAL_LIKE.search(s_)]
                    # a total from this field, or from any revenue-like field labelled total / overall
                    tots = [v for (f_, s_, e_), (_, v, _) in best.items() if e_[:4] == y and REVENUE_LIKE.search(f_)
                            and ((f_ == f and TOTAL_LIKE.search(s_)) or re.search(r"\b(total|overall)\b", f_, re.I))]
                    if tots and parts and sum(parts) > 1.5 * max(tots):
                        print(f"      ! {y}: segments sum to {sum(parts):,.0f}, {sum(parts) / max(tots):.1f}x the total "
                              f"{max(tots):,.0f} - several breakdowns overlap; pick one with --keep")
        print("\nRe-run with --revenue \"<field>\" (and --units \"<field>\" where a unit series exists, --profit \"<field>\" "
              "where segment operating profit exists).")
        return

    def table(field_list):
        out, unit = defaultdict(dict), ""
        for field in field_list:  # first label wins per segment-year
            for (f, seg, end), (_, v, u) in best.items():
                if f != field or TOTAL_LIKE.search(seg) or seg in a.exclude or (a.keep and seg not in a.keep) \
                        or end in out.get(seg, {}):
                    continue
                out[seg][end] = v
                unit = unit or u
        return {s: dict(sorted(d.items())) for s, d in sorted(out.items()) if d}, unit

    rev, unit = table(a.revenue)
    if not rev:
        sys.exit(f"No segment rows for field(s) {a.revenue!r}")
    res = {"field": " | ".join(a.revenue), "unit": unit, "revenue": rev,
           "source": "Distilla ku_cell by_segment_financials (full-year periods"
                     + (f"; {', '.join(sorted(joined))} joined from year-to-date + quarter" if joined else "") + ")"}
    if a.units:
        units, uunit = table(a.units)
        res.update({"units_field": " | ".join(a.units), "units_unit": uunit, "units": units})
    if a.profit:
        profit, _ = table(a.profit)
        res.update({"profit_field": " | ".join(a.profit), "profit": {s: d for s, d in profit.items() if s in rev}})
        # the reported segment-profit total, from the field's own total row or a "Total / Overall <field>" field
        for y in sorted({e for d in res["profit"].values() for e in d}):
            tots = [v for (f_, s_, e_), (_, v, _) in best.items() if e_ == y and (
                (f_ in a.profit and TOTAL_LIKE.search(s_) and not re.search(r"corporate|unallocated|headquarters|elimination", s_, re.I))
                or any(re.fullmatch(r"(total|overall)\s+" + re.escape(pf), f_, re.I) for pf in a.profit))]
            ssum = sum(d.get(y, 0) for d in res["profit"].values())
            if tots and abs(ssum - tots[0]) > 0.01 * abs(tots[0]):
                print(f"  ! {y[:4]}: segment profit sums to {ssum:,.0f} against the reported total {tots[0]:,.0f} "
                      f"({ssum / tots[0] - 1:+.1%}): headquarters / unallocated items, or a missing or extra line - the corporate "
                      "line takes the difference; check the segment list if no headquarters line explains it")
    if a.hold:
        res["hold"] = [s for s in a.hold if s in rev]
    # Year-to-date growth: the latest interim span after the last full year that has the same span a year
    # earlier, for every line on one span. Spans are tried latest first; a latest cell with no prior-year
    # columns falls back to an earlier span that has them (Caterpillar H1 2026 -> Q1 2026 with restated
    # comparatives). Never pair cells across a segment restructure: give only cells on one structure.
    last_full = max(e for d in rev.values() for e in d)

    def prior_of(s, a1, b1):
        pv = [v for (f_, s_, (a2, b2)), (_, v, _) in part.items() if f_ in a.revenue and s_ == s
              and abs((a1 - a2).days - 365) <= 20 and abs((b1 - b2).days - 365) <= 20 and v]
        return pv[0] if pv else None
    cands = sorted({sp for (f_, s_, sp) in part if f_ in a.revenue and s_ in rev and sp[1].isoformat() > last_full},
                   key=lambda sp: (sp[1], (sp[1] - sp[0]).days), reverse=True)
    ytd, skipped = {}, []
    for a1, b1 in cands:
        got = {}
        for s in rev:
            v1 = next((v for (f_, s_, sp), (_, v, _) in part.items() if f_ in a.revenue and s_ == s and sp == (a1, b1)), None)
            pv = prior_of(s, a1, b1) if v1 is not None else None
            if pv:
                got[s] = {"growth": round(v1 / pv - 1, 6), "end": b1.isoformat(),
                          "period": f"{a1.isoformat()} to {b1.isoformat()} vs a year earlier"}
        if len(got) == len(rev):
            ytd = got
            break
        skipped.append(f"{a1.isoformat()} to {b1.isoformat()} ({len(got)} of {len(rev)} lines have a prior-year value)")
    if ytd:
        res["ytd_growth"] = ytd
    if skipped:
        print("  year-to-date: skipped " + "; ".join(skipped) + (" - used the next span" if ytd else " - none used"))
    years = sorted({e for d in rev.values() for e in d})
    print(f"Segments ({len(rev)}): {', '.join(rev)}")
    print(f"Years: {', '.join(y[:4] for y in years)}   unit: {unit}")
    for y in years:
        tot = sum(d.get(y, 0) for d in rev.values())
        print(f"  {y[:4]}: segment sum {tot:,.0f}" + ("" if all(y in d for d in rev.values()) else "  (some segments missing)"))
    if a.units:
        for s, d in res["units"].items():
            per = "; ".join(f"{y[:4]}: {d[y]:,.1f} units, {rev[s][y] / d[y]:,.2f} revenue/unit" for y in d if rev.get(s, {}).get(y) and d[y])
            print(f"  units {s}: {per}")
    if a.profit:
        for s in rev:
            d = res["profit"].get(s, {})
            per = "; ".join(f"{y[:4]}: {d[y] / rev[s][y]:.1%}" for y in sorted(d) if rev[s].get(y))
            print(f"  margin {s}: {per or 'no profit rows - check the label or --rename'}")
    for s, d in (res.get("ytd_growth") or {}).items():
        print(f"  year-to-date {s}: {d['growth']:+.1%} ({d['period']})")
    if joined:
        print(f"Joined from year-to-date + quarter: {', '.join(sorted(joined))}")
    if a.exclude:
        print(f"Excluded: {', '.join(a.exclude)}")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
        print(f"Wrote {a.out} - put it in raw.json['segments']")
    else:
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

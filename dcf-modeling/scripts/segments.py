#!/usr/bin/env python3
"""
segments.py - turn Distilla `by_segment_financials` cells into a clean annual segment table.

Usage:
    python segments.py cells.json                      # list the fields, segments and years found
    python segments.py cells.json --revenue "Sales and revenues" [--units "Wholesale vehicle sales"]
                       [--exclude "Financial Products Segment"] [--out segments.json]

cells.json is the `query_entity` result on `ku_cell` for `by_segment_financials` (the rows, or the whole
result with "rows"); each row's `content` is a list of {segment, field_name, value, unit, time_period}.

Only full-year periods are kept ("YYYY-MM-DD to YYYY-MM-DD" spanning about a year): the cells mix
year-to-date quarters and halves, and some are mislabelled. Total / consolidated / elimination rows are
dropped (the model rebuilds the total and shows the gap to Distilla's revenue as "Other / eliminations").
When two cells give the same segment-year, the cell published later wins.

The output goes into raw.json["segments"] as {"field", "unit", "revenue": {segment: {end_date: value}},
"units": {...}, "units_field", "source"}; prepare_inputs.py checks it against consolidated revenue.
"""
import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict

TOTAL_LIKE = re.compile(r"\b(total|consolidated|reportable segments|elimination|reconcil|corporate|intersegment|"
                        r"inter-segment|adjustment)\b", re.I)
REVENUE_LIKE = re.compile(r"(sales|revenue)", re.I)


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
    ap.add_argument("--revenue")
    ap.add_argument("--units")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()

    cells = load(a.cells)
    if not cells:
        sys.exit("No by_segment_financials content found in " + a.cells)
    # (field, segment, end) -> (as_of, value, unit); later cells win
    best = {}
    fields = defaultdict(set)
    for as_of, content in cells:
        for row in content:
            if not isinstance(row, dict):
                continue
            end = full_year_end(row.get("time_period"))
            seg, field = str(row.get("segment") or "").strip(), str(row.get("field_name") or "").strip()
            v = num(row.get("value"))
            if not end or not seg or not field or v is None:
                continue
            fields[field].add(seg)
            k = (field, seg, end)
            if k not in best or as_of >= best[k][0]:
                best[k] = (as_of, v, str(row.get("unit") or ""))

    if not a.revenue:
        print("Fields with full-year values (segments in each):")
        for f, segs in sorted(fields.items(), key=lambda x: -len(x[1])):
            years = sorted({k[2][:4] for k in best if k[0] == f})
            mark = "  <- revenue candidate" if REVENUE_LIKE.search(f) else ""
            print(f"  {f!r}: {len(segs)} segments, years {years}{mark}")
            for s in sorted(segs):
                print(f"      {'(dropped: total-like) ' if TOTAL_LIKE.search(s) else ''}{s}")
        print("\nRe-run with --revenue \"<field>\" (and --units \"<field>\" where a unit series exists).")
        return

    def table(field):
        out, unit = defaultdict(dict), ""
        for (f, seg, end), (_, v, u) in best.items():
            if f != field or TOTAL_LIKE.search(seg) or seg in a.exclude:
                continue
            out[seg][end] = v
            unit = unit or u
        return {s: dict(sorted(d.items())) for s, d in sorted(out.items())}, unit

    rev, unit = table(a.revenue)
    if not rev:
        sys.exit(f"No segment rows for field {a.revenue!r}")
    res = {"field": a.revenue, "unit": unit, "revenue": rev,
           "source": "Distilla ku_cell by_segment_financials (full-year periods)"}
    if a.units:
        units, uunit = table(a.units)
        res.update({"units_field": a.units, "units_unit": uunit, "units": units})
    years = sorted({e for d in rev.values() for e in d})
    print(f"Segments ({len(rev)}): {', '.join(rev)}")
    print(f"Years: {', '.join(y[:4] for y in years)}   unit: {unit}")
    for y in years:
        tot = sum(d.get(y, 0) for d in rev.values())
        print(f"  {y[:4]}: segment sum {tot:,.0f}" + ("" if all(y in d for d in rev.values()) else "  (some segments missing)"))
    if a.exclude:
        print(f"Excluded: {', '.join(a.exclude)}")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
        print(f"Wrote {a.out} - put it in raw.json['segments']")
    else:
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

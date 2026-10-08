#!/usr/bin/env python3
"""
recalc.py - recalculate a workbook written by build_model.py, in Python.

Usage:
    python recalc.py model.xlsx

openpyxl writes formulas without values, so check_model.py (and any viewer that does not
recalculate) sees empty cells. This script evaluates every formula with the pure-Python
`formulas` package and stores each result as the cell's cached value. Formulas are kept, and
the workbook still recalculates in full when opened in Excel or Google Sheets.

Use it when the host has no spreadsheet recalculation tool of its own. If `formulas` is not
installed, install it (`pip install formulas`) where the host allows.

Prints JSON: engine, status, total_formulas, total_errors, error_summary (error -> up to 20
cell locations). Exit code 0 = recalculated with no errors, 1 = formula errors found,
2 = could not recalculate (package missing or evaluation failed).
"""
import json
import re
import shutil
import sys
import tempfile
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET

ERRORS = ("#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def report(payload, code):
    print(json.dumps(payload, indent=2))
    sys.exit(code)


def scalar(v):
    """One Python value from a `formulas` result (ranges come back as arrays)."""
    v = getattr(v, "value", v)
    try:
        v = v[0, 0]
    except (TypeError, IndexError, KeyError):
        pass
    if hasattr(v, "item"):
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    return v


def evaluate(path):
    import formulas  # noqa: imported here so a missing package is reported, not raised

    sol = formulas.ExcelModel().loads(path).finish().calculate()
    values = {}
    for key, v in sol.items():
        if "!" not in key:
            continue
        sheet, addr = key.rsplit("!", 1)
        if ":" in addr:
            continue
        sheet = sheet.strip("'")
        sheet = sheet.split("]", 1)[1] if "]" in sheet else sheet
        values[(sheet.upper(), addr.replace("$", "").upper())] = scalar(v)
    return values


def sheet_files(z):
    """Sheet name -> worksheet XML path inside the package."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels.findall("rel:Relationship", NS)}
    out = {}
    for s in wb.findall("m:sheets/m:sheet", NS):
        t = target[s.get("{%s}id" % NS["r"])].lstrip("/")
        out[s.get("name")] = t if t.startswith("xl/") else "xl/" + t
    return out


def cached(v):
    """(type attribute, <v> text) for a computed value."""
    if isinstance(v, bool):
        return ' t="b"', "1" if v else "0"
    if isinstance(v, (int, float)):
        return "", repr(float(v)) if isinstance(v, float) else str(v)
    s = "" if v is None else str(v)
    if s in ERRORS:
        return ' t="e"', s
    if s == "empty":  # `formulas` marks a reference to a blank cell this way
        return "", "0"
    return ' t="str"', s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CELL = re.compile(r'<c r="([A-Z]+[0-9]+)"([^>]*?)>(<f>.*?</f>)(?:<v>.*?</v>|<v\s*/>)?</c>', re.S)


def main():
    if len(sys.argv) < 2:
        report({"status": "usage", "message": "python recalc.py model.xlsx"}, 2)
    path = sys.argv[1]
    try:
        values = evaluate(path)
    except ImportError:
        report({"engine": "formulas", "status": "unavailable",
                "message": "Python package `formulas` is not installed; install it (pip install formulas) "
                           "or use the host's spreadsheet recalculation tool."}, 2)
    except Exception as exc:  # evaluation failure: report, never ship silently
        report({"engine": "formulas", "status": "unavailable", "message": f"evaluation failed: {exc}"}, 2)

    errors = defaultdict(list)
    n_formulas = 0
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        files = {v: k for k, v in sheet_files(zin).items()}
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in files:
                sheet = files[item.filename]

                def fill(m):
                    nonlocal n_formulas
                    addr, attrs, f = m.groups()
                    attrs = re.sub(r'\s+t="[^"]*"', "", attrs)
                    n_formulas += 1
                    key = (sheet.upper(), addr)
                    if key not in values:
                        errors["not evaluated"].append(f"{sheet}!{addr}")
                        return f'<c r="{addr}"{attrs}>{f}</c>'
                    t, text = cached(values[key])
                    if t == ' t="e"':
                        errors[text].append(f"{sheet}!{addr}")
                    return f'<c r="{addr}"{attrs}{t}>{f}<v>{text}</v></c>'

                data = CELL.sub(fill, data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)

    total = sum(len(v) for v in errors.values())
    report({"engine": "formulas", "status": "errors_found" if total else "success",
            "total_formulas": n_formulas, "total_errors": total,
            "error_summary": {k: {"count": len(v), "locations": v[:20]} for k, v in errors.items()}},
           1 if total else 0)


if __name__ == "__main__":
    main()

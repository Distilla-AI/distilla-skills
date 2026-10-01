#!/usr/bin/env python3
"""Score the six bull-signal technical criteria from daily adjusted close + volume.

Also returns the three numeric regime inputs the technical-analysis skill uses
(numbers only -- the regime label is assigned by Claude, never by this script).

Input: a CSV or JSON file of rows with columns symbol, date, adjusted_close, volume and,
optionally, close, split and change (Distilla stock_price rows). Needs >= 250 sessions per symbol for full scoring
(200-day SMA plus its 50-session slope).

Short-history mode: pass --sma200 anchors.csv (columns symbol, offset, sma200) with the
200-day SMA of adjusted_close at offsets 0, 15 and 50 sessions back from each symbol's last
row (grouped aggregate_entity AVG windows of exactly 200 sessions). With >= 80 sessions of
rows (100 pulled), the 200-day SMA is interpolated linearly between the anchors for Golden cross, the
200-day part of Breakout and the share-above input; the 50-session slope is exact.

Usage:
    python technical_signals.py prices.csv            # markdown table to stdout
    python technical_signals.py prices.json --json    # JSON output
    python technical_signals.py prices.csv --sma200 anchors.csv

Pinned parameters (do not vary between runs):
    RSI: 14-day, Wilder smoothing. Pass if 50 <= RSI <= 70.
    OBV: pass if OBV's 20-session linear-regression slope > 0 AND OBV > its 20-session SMA.
    Volume surge: pass if any of the last 10 sessions has volume >= 2.0x the average
                  of the 20 sessions before it.
    Golden cross: 50-day SMA crosses above 200-day SMA within the last 15 sessions.
    MACD: (12, 26, 9) EMA. MACD line crosses above signal from below within last 15 sessions.
    Breakout: within the last 15 sessions, close exceeds the highest close of the prior
              60 sessions, OR close crosses above the 50- or 200-day SMA from below. The
              60-session high uses split-adjusted `close` when the column is present
              (dividend back-adjustment lowers pre-ex-date closes and fakes new highs);
              otherwise adjusted_close. Indicators stay on adjusted_close.
    Zero-volume rows (e.g. exchange half-days): close and session kept; the row is
              excluded from OBV, the volume-surge ratio and its 20-session base. A stale
              carry-forward row (volume 0, change 0, close equal to the prior close) is
              dropped when close and change are present.
    Regime inputs: r2_50 = R^2 of an OLS fit of close on time over the last 50 sessions;
              sma200_slope50_pct = % change of the 200-day SMA over the last 50 sessions;
              pct_above_sma200_50 = share of the last 50 closes above the 200-day SMA.
"""
import json
import sys

import numpy as np
import pandas as pd

LOOKBACK = 15


def load(path):
    if path.endswith(".json"):
        data = json.load(open(path))
        if isinstance(data, dict) and "rows" in data:
            data = data["rows"]
        df = pd.DataFrame(data)
    else:
        df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.dropna(subset=["adjusted_close"]).sort_values(["symbol", "date"])
    return df.drop_duplicates(["symbol", "date"], keep="last")


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def crossed_above(a, b, window):
    """True if series a crossed from <= b to > b within the last `window` bars."""
    above = a > b
    prev_below = (a.shift(1) <= b.shift(1))
    cross = above & prev_below
    return bool(cross.iloc[-window:].any())


def r2(x):
    t = np.arange(len(x))
    return float(np.corrcoef(t, x)[0, 1] ** 2)


def split_adjusted_close(g):
    """Raw close divided by the product of every later split ratio (missing/<=0 -> 1)."""
    if "close" not in g:
        return None
    sp = pd.to_numeric(g["split"], errors="coerce") if "split" in g else pd.Series(1.0, index=g.index)
    sp = sp.where(sp > 0, 1.0).fillna(1.0)
    later = sp[::-1].cumprod()[::-1].shift(-1).fillna(1.0)  # product of splits after each row
    raw = pd.to_numeric(g["close"], errors="coerce").fillna(g["adjusted_close"])  # blank close = no split/dividend gap
    return (raw / later).reset_index(drop=True)


def drop_stale(g):
    close = pd.to_numeric(g["close"], errors="coerce").fillna(g["adjusted_close"]) if "close" in g \
        else g["adjusted_close"]
    flat = (pd.to_numeric(g["change"], errors="coerce") == 0) if "change" in g else pd.Series(True, index=g.index)
    stale = (g["volume"].astype(float) <= 0) & flat & (close == close.shift(1))
    return g[~stale]


def anchor_series(n, a):
    """200-day SMA over the last 51 rows, piecewise linear between offsets 50, 15 and 0."""
    s = pd.Series(np.nan, index=range(n))
    offs = sorted(a)  # 0, 15, 50
    for i in range(51):
        off = 50 - i
        lo = max(o for o in offs if o <= off); hi = min(o for o in offs if o >= off)
        val = a[lo] if lo == hi else a[hi] + (a[lo] - a[hi]) * (hi - off) / (hi - lo)
        s.iloc[n - 51 + i] = val
    return s


def score(g, anchors=None):
    g = drop_stale(g)
    c = g["adjusted_close"].reset_index(drop=True)
    lvl = split_adjusted_close(g)
    lvl = c if lvl is None else lvl
    v = g["volume"].astype(float).reset_index(drop=True)
    vol = v.where(v > 0)  # zero-volume sessions: close kept, volume excluded
    n = len(c)
    out = {"symbol": g["symbol"].iloc[0], "as_of": g["date"].iloc[-1].date().isoformat(),
           "sessions": n, "zero_volume_rows": int((v <= 0).sum())}
    notes = []

    r = rsi(c)
    out["rsi_50_70"] = bool(50 <= r.iloc[-1] <= 70) if n >= 30 else None
    notes.append(f"RSI14 {r.iloc[-1]:.1f}" if n >= 30 else "RSI n/a")

    direction = c.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (direction * vol.fillna(0)).cumsum()
    if n >= 40:
        tail = obv.iloc[-20:]
        slope = pd.Series(range(20)).cov(tail.reset_index(drop=True)) / pd.Series(range(20)).var()
        out["obv_rising"] = bool(slope > 0 and obv.iloc[-1] > obv.rolling(20).mean().iloc[-1])
    else:
        out["obv_rising"] = None

    if n >= 31:
        base = vol.shift(1).rolling(20, min_periods=15).mean()
        ratio = (vol / base).iloc[-10:]
        out["volume_surge"] = bool((ratio >= 2.0).any())
        notes.append(f"max vol/20d avg {ratio.max():.1f}x")
    else:
        out["volume_surge"] = None

    sma50, sma200 = c.rolling(50).mean(), c.rolling(200).mean()
    anchored = n < 200 + LOOKBACK and anchors is not None and {0, 15, 50} <= set(anchors) and n >= 80
    if anchored:
        sma200 = anchor_series(n, anchors)
        notes.append("200d SMA from anchors")
    full200 = n >= 200 + LOOKBACK or anchored
    out["golden_cross"] = crossed_above(sma50, sma200, LOOKBACK) if full200 else None

    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    out["macd_cross"] = crossed_above(macd, signal, LOOKBACK) if n >= 60 else None

    if full200:
        prior_high = lvl.shift(1).rolling(60).max()
        new_high = bool((lvl > prior_high).iloc[-LOOKBACK:].any())
        ma_break = crossed_above(c, sma50, LOOKBACK) or crossed_above(c, sma200, LOOKBACK)
        out["breakout"] = new_high or ma_break
        if new_high:
            notes.append("new 60-session closing high")
        elif ma_break:
            notes.append("reclaimed 50/200-day SMA")
    else:
        out["breakout"] = None

    out["r2_50"] = round(r2(c.iloc[-50:].values), 3) if n >= 50 else None
    out["sma200_slope50_pct"] = (round(float((sma200.iloc[-1] / sma200.iloc[-51] - 1) * 100), 1)
                                 if n >= 250 or anchored else None)
    out["pct_above_sma200_50"] = (round(float((c.iloc[-50:] > sma200.iloc[-50:]).mean()), 2)
                                  if n >= 249 or anchored else None)

    keys = ["rsi_50_70", "obv_rising", "volume_surge", "golden_cross", "macd_cross", "breakout"]
    out["total_score"] = sum(1 for k in keys if out[k] is True)
    out["notes"] = "; ".join(notes)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    df = load(sys.argv[1])
    anchors = {}
    if "--sma200" in sys.argv:
        a = pd.read_csv(sys.argv[sys.argv.index("--sma200") + 1])
        for r in a.itertuples():
            anchors.setdefault(str(r.symbol), {})[int(r.offset)] = float(r.sma200)
    rows = [score(g, anchors.get(str(s))) for s, g in df.groupby("symbol")]
    rows.sort(key=lambda r: -r["total_score"])
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return
    fmt = lambda x: "Yes" if x is True else ("No" if x is False else "--")
    print("| Ticker | RSI 50-70 | OBV rising | Volume surge | Golden cross | MACD cross | Breakout | Total Score |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["total_score"] == 0:
            continue
        print(f"| {r['symbol']} | {fmt(r['rsi_50_70'])} | {fmt(r['obv_rising'])} | {fmt(r['volume_surge'])} | "
              f"{fmt(r['golden_cross'])} | {fmt(r['macd_cross'])} | {fmt(r['breakout'])} | {r['total_score']} |")
    print("\nRegime inputs (label assigned by Claude per the technical-analysis regime table):")
    for r in rows:
        print(f"- {r['symbol']}: R2(50) {r['r2_50']}; 200d SMA 50-session slope {r['sma200_slope50_pct']}%; "
              f"share of last 50 closes above 200d SMA {r['pct_above_sma200_50']}; "
              f"zero-volume rows {r['zero_volume_rows']}")
    short = [r["symbol"] for r in rows if r["sessions"] < 250 and "200d SMA from anchors" not in r["notes"]]
    if short:
        print(f"\nShort history (<250 sessions, some criteria or regime inputs '--'): {', '.join(short)}")


if __name__ == "__main__":
    main()

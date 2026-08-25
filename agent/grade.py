#!/usr/bin/env python3
"""grade.py — IR-001 and IR-002 in one place.

TWO COLUMNS, BOTH DECIDED AT CALL TIME, NEITHER A FILTER.

IR-001 `grade` — cluster size and price stratum
    core  : cluster >= $100,000 AND price_at_call >= $5
    noise : anything else

    Measured 2026-08-24 on the 97 open calls, split by these thresholds:

        stratum  n   up    mean    excess vs SPY   median
        core     52  62%  +2.51%      +2.91%       +1.23%
        noise    45  47%  +0.12%      +0.67%        0.00%

    The noise stratum contributes essentially nothing and owns the whole left
    tail: HCWB -32%, XAIR -21%, SAGT -14%, FOCL -13%, all sub-$5, several with
    theses this lab itself wrote as "noise-scale cluster" and "$300 total".

    THE THRESHOLDS WERE CHOSEN AFTER SEEING THAT TABLE. That is exactly the
    post-hoc slicing backtest-overfitting exists to catch, so this column
    PROVES NOTHING TODAY. It is pre-registered here, dated, and its verdict
    comes only from rows logged from 2026-08-24 forward. The backfill on older
    rows is for reporting both strata side by side, never for claiming an edge.

    Like `stale_quote`, this is a DISCLOSURE column: it drops no row, excludes
    nothing, and changes no `outcome`. Every cluster is still logged without
    discretion — the agent scores the signal, not its own taste.

IR-002 `spy_at_call` / `spy_at_check` / `outcome_excess` — the benchmark leg
    AGENT.md already says: "The long-only design means a bull market inflates
    the hit rate." It does, and the reverse is worse — over the current open
    book SPY averaged -0.48%, so four names that BEAT the index are still
    booked `wrong` by a raw-direction test. `outcome_excess` records whether
    the call beat SPY over the same holding window. `outcome` is untouched:
    the original unit keeps its record, and the two are reported together.

Usage:
    py agent/grade.py --check TICKER --price 12.34 --thesis "[insider] ..."
    py agent/grade.py --backfill        # add the columns to existing rows
"""
import argparse, csv, json, os, re, sys, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
MIN_USD, MIN_PX = 100_000.0, 5.00
UA = {"User-Agent": "Mozilla/5.0"}
NEW_COLS = ["grade", "spy_at_call", "spy_at_check", "outcome_excess"]


def cluster_usd(thesis):
    """Dollar size stated in the thesis. None when the thesis states no size —
    which is NOT the same as zero and must not be graded as `noise` silently."""
    m = re.search(r"\$([\d.]+)\s*([MK])?", thesis or "")
    if not m:
        return None
    v = float(m.group(1))
    return v * {"M": 1e6, "K": 1e3}.get(m.group(2), 1.0)


def grade(thesis, price):
    usd = cluster_usd(thesis)
    if usd is None or price is None:
        return ""                       # unknown is honest; guessed is not
    return "core" if (usd >= MIN_USD and price >= MIN_PX) else "noise"


def spy_close(day):
    """SPY close on `day`, or the last close before it. Objective and fixed at
    the call date — backfilling it looks at no information the row did not have."""
    u = ("https://query1.finance.yahoo.com/v8/finance/chart/SPY"
         "?range=2y&interval=1d")
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
    r = d["chart"]["result"][0]
    hist = {datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"): c
            for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}
    ks = [k for k in hist if k <= day]
    return hist[max(ks)] if ks else None


def backfill():
    rows = list(csv.DictReader(open(LEDGER)))
    hdr = list(rows[0].keys()) if rows else []
    for c in NEW_COLS:
        if c not in hdr:
            hdr.append(c)
    u = ("https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=2y&interval=1d")
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
    r = d["chart"]["result"][0]
    hist = {datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"): c
            for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}

    def at(day):
        ks = [k for k in hist if k <= day]
        return hist[max(ks)] if ks else None

    n_g = n_s = 0
    for row in rows:
        for c in NEW_COLS:
            row.setdefault(c, "")
        if not row.get("grade"):
            try:
                px = float(row["price_at_call"])
            except (TypeError, ValueError):
                px = None
            row["grade"] = grade(row.get("thesis"), px)
            n_g += 1 if row["grade"] else 0
        if not row.get("spy_at_call"):
            v = at(row["date"])
            if v:
                row["spy_at_call"] = f"{v:.2f}"
                n_s += 1
        # only rows already scored can have their benchmark leg completed
        if (row.get("outcome") in ("right", "wrong")
                and row.get("price_at_check") and not row.get("outcome_excess")):
            v = at(row["check_date"])
            if v and row.get("spy_at_call"):
                row["spy_at_check"] = f"{v:.2f}"
                s0, s1 = float(row["spy_at_call"]), v
                p0, p1 = float(row["price_at_call"]), float(row["price_at_check"])
                row["outcome_excess"] = "right" if (p1/p0 - 1) > (s1/s0 - 1) else "wrong"
    with open(LEDGER, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows)
    done = [r for r in rows if r.get("outcome") in ("right", "wrong")]
    void = [r for r in rows if r.get("outcome") == "void"]
    ex = [r for r in rows if r.get("outcome_excess")]
    print(f"backfilled: grade on {n_g} rows, spy_at_call on {n_s} rows "
          f"({len(void)} rows are void — unpriceable, never a loss)")
    for g in ("core", "noise", ""):
        sub = [r for r in rows if r.get("grade") == g]
        sd = [r for r in sub if r.get("outcome") in ("right", "wrong")]
        lab = g or "(size not stated)"
        nv = sum(1 for r in sub if r.get("outcome") == "void")
        line = f"  {lab:<18} n={len(sub):3}  scored={len(sd):2}  void={nv:2}"
        if sd:
            line += f"  raw {sum(1 for r in sd if r['outcome']=='right')}/{len(sd)}"
        print(line)
    if ex:
        print(f"  benchmark leg: raw {sum(1 for r in done if r['outcome']=='right')}/{len(done)}"
              f" vs excess {sum(1 for r in ex if r['outcome_excess']=='right')}/{len(ex)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check")
    ap.add_argument("--price", type=float)
    ap.add_argument("--thesis", default="")
    ap.add_argument("--backfill", action="store_true")
    a = ap.parse_args()
    if a.backfill:
        return backfill()
    if not a.check:
        ap.error("give --check TICKER --price P --thesis '...' or --backfill")
    print(grade(a.thesis, a.price))


if __name__ == "__main__":
    main()

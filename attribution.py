#!/usr/bin/env python3
"""attribution.py — join every insider call to the information that produced it.

Anupam, 2026-08-17: "connect it to the trades, so we know which insider
information was useful and which was not, and the agents can learn accordingly."

He is pointing at a real hole. The lab has a FEED (docs/data/insiders.json:
purchases, clusters) and a BOOK (agent/ledger.csv, agent/forecasts.csv), and
nothing machine-readable joins them — the cluster's features live in prose
("2 insiders bought $22.0M cluster") that no learner can compute over. When the
first cohort scores, the lab could say WHETHER it was right but not WHICH KIND
of information was worth acting on.

VINTAGE-CORRECT BY CONSTRUCTION. The live feed is a rolling ~11-day window, so
July's clusters have scrolled out of it. This file reads the feed AS OF EACH
CALL'S DATE from git history (the collector commits many times a day), so every
row's features are exactly the information that existed when the call was made
— no lookahead, and no dependence on today's window. A call whose vintage feed
cannot be recovered is written with empty features and counted, never dropped.

FEATURES PER CALL (the learnable surface):
    n_insiders, total_usd, max_single_usd    cluster size and concentration
    ceo, cfo, director_only                  who was buying
    pct_placement                            open-market vs placement dollars
    avg_purchase_px, runup_at_call_pct       what price they paid vs the call
    days_filed_to_call                       how stale the information was

OUTPUT: agent/attribution.csv — one row per ledger call and per forecast,
joined to outcome and return once scored. The strata report prints per-feature
hit rates WITH n, and n here counts CALL DATES, not rows: 47 of the first 53
calls were entered on one day, so this table's honest denominator is dates.

This file NEVER writes lessons. AGENT.md's lesson step now cites this table —
the agent learns from computed splits, not from vibes about prose.

Run:  /opt/anaconda3/bin/python attribution.py           # rebuild + report
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(BASE, "agent", "ledger.csv")
FORECASTS = os.path.join(BASE, "agent", "forecasts.csv")
OUT = os.path.join(BASE, "agent", "attribution.csv")
FEED_PATH = "docs/data/insiders.json"

COLS = ["book", "date", "ticker", "call", "outcome", "ret_pct",
        "n_insiders", "total_usd", "max_single_usd", "ceo", "cfo",
        "director_only", "pct_placement", "avg_purchase_px",
        "runup_at_call_pct", "days_filed_to_call", "vintage_commit", "note"]


def feed_as_of(date):
    """The feed exactly as the collector had committed it by end of `date`."""
    try:
        c = subprocess.run(
            ["git", "-C", BASE, "rev-list", "-1",
             f"--before={date} 23:59", "HEAD", "--", FEED_PATH],
            capture_output=True, text=True, timeout=20).stdout.strip()
        if not c:
            return None, ""
        raw = subprocess.run(["git", "-C", BASE, "show", f"{c}:{FEED_PATH}"],
                             capture_output=True, text=True, timeout=20).stdout
        return json.loads(raw), c[:8]
    except Exception:
        return None, ""


def features(feed, ticker, call_date, price_at_call):
    P = [p for p in feed.get("purchases", []) if p.get("ticker") == ticker]
    if not P:
        return None
    names = {p.get("insider") for p in P}
    vals = [p.get("value") or 0 for p in P]
    roles = " ".join((p.get("role") or "").lower() for p in P)
    placement = sum(p.get("value") or 0 for p in P if p.get("placement"))
    tot = sum(vals)
    pxs = [(p.get("price"), p.get("shares")) for p in P if p.get("price") and p.get("shares")]
    avg_px = (sum(a * b for a, b in pxs) / sum(b for _, b in pxs)) if pxs else None
    filed = [p.get("filed") for p in P if p.get("filed")]
    days = ((dt.date.fromisoformat(call_date)
             - min(dt.date.fromisoformat(f) for f in filed)).days if filed else "")
    runup = ""
    try:
        if avg_px and price_at_call:
            runup = round(100 * (float(price_at_call) / avg_px - 1), 1)
    except (ValueError, ZeroDivisionError):
        pass
    is_exec = ("chief executive" in roles or "ceo" in roles,
               "chief financial" in roles or "cfo" in roles)
    return {"n_insiders": len(names), "total_usd": round(tot),
            "max_single_usd": round(max(vals)) if vals else "",
            "ceo": int(is_exec[0]), "cfo": int(is_exec[1]),
            "director_only": int("chief" not in roles and "officer" not in roles),
            "pct_placement": round(100 * placement / tot, 1) if tot else "",
            "avg_purchase_px": round(avg_px, 2) if avg_px else "",
            "runup_at_call_pct": runup, "days_filed_to_call": days}


def ret_pct(r):
    try:
        a, b = float(r["price_at_call"]), float(r["price_at_check"])
        return round(100 * (b / a - 1), 2)
    except (ValueError, KeyError, ZeroDivisionError):
        return ""


def main():
    rows, cache = [], {}
    for r in csv.DictReader(open(LEDGER)):
        if "VOIDED" in (r.get("thesis") or ""):
            continue
        d = r["date"]
        if d not in cache:
            cache[d] = feed_as_of(d)
        feed, commit = cache[d]
        f = features(feed, r["ticker"], d, r.get("price_at_call")) if feed else None
        rows.append({"book": "ledger", "date": d, "ticker": r["ticker"],
                     "call": r.get("call", ""), "outcome": (r.get("outcome") or "").strip(),
                     "ret_pct": ret_pct(r), "vintage_commit": commit,
                     "note": "" if f else "vintage feed lacks this ticker — counted, not dropped",
                     **(f or {k: "" for k in ["n_insiders", "total_usd", "max_single_usd",
                                              "ceo", "cfo", "director_only", "pct_placement",
                                              "avg_purchase_px", "runup_at_call_pct",
                                              "days_filed_to_call"]})})
    if os.path.exists(FORECASTS):
        for r in csv.DictReader(open(FORECASTS)):
            d = r["date"]
            if d not in cache:
                cache[d] = feed_as_of(d)
            feed, commit = cache[d]
            f = features(feed, r["instrument"], d, None) if feed else None
            out = (r.get("outcome") or "").strip()
            rows.append({"book": "forecast", "date": d, "ticker": r["instrument"],
                         "call": f"p={r.get('p','')}", "outcome": out, "ret_pct": "",
                         "vintage_commit": commit,
                         "note": "" if f else "vintage feed lacks this ticker — counted, not dropped",
                         **(f or {k: "" for k in ["n_insiders", "total_usd", "max_single_usd",
                                                  "ceo", "cfo", "director_only", "pct_placement",
                                                  "avg_purchase_px", "runup_at_call_pct",
                                                  "days_filed_to_call"]})})
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    have = [r for r in rows if r["n_insiders"] != ""]
    scored = [r for r in rows if r["outcome"] not in ("", None) and r["ret_pct"] != ""]
    print(f"attribution: {len(rows)} calls joined ({len(have)} with vintage features, "
          f"{len(rows)-len(have)} disclosed as unrecoverable), {len(scored)} scored")

    if scored:
        def split(name, pred):
            g = [r for r in scored if r["n_insiders"] != "" and pred(r)]
            if not g:
                return
            wins = sum(1 for r in g if float(r["ret_pct"]) > 0)
            avg = sum(float(r["ret_pct"]) for r in g) / len(g)
            dates = len({r["date"] for r in g})
            print(f"    {name:<28} n={len(g):<3} dates={dates:<3} "
                  f"hit {100*wins/len(g):3.0f}%  avg {avg:+.1f}%")
        print("  strata (n counts rows, dates is the honest denominator; "
              "n<30 proves nothing):")
        split("big cluster (>= $5M)", lambda r: float(r["total_usd"]) >= 5e6)
        split("small cluster (< $5M)", lambda r: float(r["total_usd"]) < 5e6)
        split("CEO buying", lambda r: r["ceo"] == 1 or r["ceo"] == "1")
        split("directors only", lambda r: r["director_only"] in (1, "1"))
        split("3+ insiders", lambda r: int(r["n_insiders"]) >= 3)
        split("bought the run-up (>10%)", lambda r: r["runup_at_call_pct"] != "" and float(r["runup_at_call_pct"]) > 10)


if __name__ == "__main__":
    main()

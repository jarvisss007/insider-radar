#!/usr/bin/env python3
"""strata.py — score the insider ledger in its two size strata, never blended.

INS-002, ruled by Anupam 2026-08-12: a $100,000 STRATUM, not an exclusion.

Every cluster keeps being logged — a row not logged is gone forever — but the
HEADLINE hit rate is computed on clusters >= $100k, and sub-$100k rows are
reported separately and NEVER blended into it.

Why the floor exists at all: the book spans $22.0M (NTSK) down to $5,446 (CZNC),
three orders of magnitude. The signal hypothesis is that insiders with
information buy meaningfully; a $300 purchase (RGCO, 08-06) cannot express that,
and neither can BHRB $0.08M or NWPP $0.027M. Blending them measures two different
phenomena and reports one number.

Why $100k specifically: chosen on that principle — large enough to read as a
considered investment decision rather than an administrative one — and NOT on any
outcome. It was ruled on 2026-08-12, four days before the first seven rows score
on 2026-08-16, precisely so that it could not be. A floor picked after outcomes
are visible is threshold-tuning on realised results, which is the failure this
account's own overfitting toolkit exists to convict.

This file REPORTS. It writes nothing to the ledger and changes no outcome.

Run:  /opt/anaconda3/bin/python agent/strata.py
      /opt/anaconda3/bin/python agent/strata.py --floor 250000   # sensitivity only
"""
from __future__ import annotations

import argparse
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
FLOOR = 100_000          # INS-002, ruled 2026-08-12. A rule change, not a tweak.

# "[insider] 2 insiders bought $22.0M cluster" / "$0.027M" / "$5,446"
_AMT = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*([MKB])?", re.I)
_MULT = {"k": 1e3, "m": 1e6, "b": 1e9}


def cluster_usd(thesis: str):
    """Dollar size of the cluster from the thesis the lab wrote, or None.

    The ledger has no cluster_usd column, so this parses the sentence the agent
    already writes. None is returned rather than 0 when nothing parses — an
    unparseable row is UNKNOWN, and an unknown must never be silently sorted into
    the sub-floor stratum where it would look like a deliberate small cluster.
    """
    m = _AMT.search(thesis or "")
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return v * _MULT.get((m.group(2) or "").lower(), 1.0)


def score(rows, floor):
    """Split into headline / sub-floor / unknown and score each separately."""
    out = {"headline": [], "sub": [], "unknown": []}
    for r in rows:
        usd = cluster_usd(r.get("thesis", ""))
        key = "unknown" if usd is None else ("headline" if usd >= floor else "sub")
        out[key].append((r, usd))
    return out


def line(label, bucket):
    n = len(bucket)
    scored = [(r, u) for r, u in bucket if (r.get("outcome") or "").strip() in ("right", "wrong")]
    right = sum(1 for r, _ in scored if r["outcome"] == "right")
    days = len({r["date"] for r, _ in scored})
    hit = f"{100*right/len(scored):.0f}%" if scored else "—"
    verdict = ("nothing scored yet" if not scored
               else f"proves nothing yet · n={len(scored)} on {days} entry day(s)"
               if len(scored) < 30 else f"n={len(scored)} on {days} entry day(s)")
    return f"  {label:<28}{n:>5} logged{len(scored):>7} scored{hit:>7}   {verdict}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=float, default=FLOOR,
                    help="sensitivity check ONLY — the ruled floor is $100,000 and "
                         "changing it for a report does not change the ruling")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(LEDGER)))
    b = score(rows, args.floor)

    print(f"\nInsider ledger — two strata, never blended  (floor ${args.floor:,.0f})\n")
    print(line(f"HEADLINE  >= ${args.floor/1000:,.0f}k", b["headline"]))
    print(line(f"sub-floor  < ${args.floor/1000:,.0f}k", b["sub"]))
    if b["unknown"]:
        print(line("unknown (unparseable)", b["unknown"]))
    print()
    if args.floor != FLOOR:
        print(f"  ⚠ floor overridden to ${args.floor:,.0f} for this run only. The RULED "
              f"floor is ${FLOOR:,.0f}.\n")

    sub = sorted([(u, r["ticker"], r["date"]) for r, u in b["sub"]])
    if sub:
        print("  below the floor — reported, never folded into the headline:")
        for u, t, d in sub:
            print(f"    {d}  {t:<6} ${u:,.0f}")
    print("\n  There is deliberately NO combined hit rate in this output. If asked for "
          "\"the\"\n  insider hit rate, give both strata with their n.")


if __name__ == "__main__":
    main()

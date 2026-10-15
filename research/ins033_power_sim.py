#!/usr/bin/env python3
"""INS-033: what the frozen decision rule would say, by simulation. Prior only; reads and writes no book.

Question: with about 8 entry weeks per bucket (the cohort window 2026-10-15..2026-12-01 spans ISO weeks 42-49), how often does the
rule in ins033_floor_test.decide() return PASS / FAIL / CONTINUE if the true weekly gap D were 0, 3, 6.9 (the in-sample size), 10, 15 pp?
Entry-week values are drawn Normal around the true gap with the in-sample spread (INS-033_cuts_looked_at.txt, the line "At $5, entry-week
values of excess"), min n assumed met. The real weekly values are fat-tailed and autocorrelated through the market, so this flatters the
test: read it as an upper bound on power.

Run:  /opt/anaconda3/bin/python research/ins033_power_sim.py
"""
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ins033_floor_test as F  # noqa: E402

SD_GE5, SD_LT5 = 9.14, 6.80            # in-sample entry-week sd of excess, GE5 and LT5 (INS-033_cuts_looked_at.txt)
WEEKS = 8
TRIALS = 40000
SEED = 11
MET = dict(rows=40, entry_days=20, entry_weeks=WEEKS)


def run(true_d):
    rnd = random.Random(SEED)
    out = {"PASS": 0, "FAIL": 0, "CONTINUE": 0}
    for _ in range(TRIALS):
        hi = [rnd.gauss(true_d, SD_GE5) for _ in range(WEEKS)]
        lo = [rnd.gauss(0.0, SD_LT5) for _ in range(WEEKS)]
        out[F.decide(hi, lo, MET, MET, 0)["decision"]] += 1
    return {k: v / TRIALS for k, v in out.items()}


if __name__ == "__main__":
    print(f"INS-033 rule by simulation: {WEEKS} entry weeks a bucket, sd {SD_GE5}/{SD_LT5} pp, {TRIALS} trials, seed {SEED}, bar t >= {F.PASS_T}, min n assumed met")
    print(f"{'true D (pp)':>12}{'PASS':>8}{'FAIL':>8}{'CONTINUE':>10}")
    for d in (0.0, 3.0, 6.9, 10.0, 15.0):
        r = run(d)
        print(f"{d:>12.1f}{r['PASS']:>8.1%}{r['FAIL']:>8.1%}{r['CONTINUE']:>10.1%}")

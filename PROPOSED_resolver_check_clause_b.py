#!/usr/bin/env python3
"""PROPOSED - NOT APPLIED. A resolver check for insider-radar's REGISTRY Clause B (applied 2026-10-17).

A patch proposal for ~/command-center/council/resolver.py, deliberately NOT applied (resolver.py and
council/issues.json are owned by another session). To adopt, paste the function into resolver.py and register it, e.g.
    CHECKS.update({"ins_clause_b_applied": check_ins_clause_b_applied})

Clause B (REGISTRY.md, pre-registered 2026-09-04): at n=40, skill <= 0 -> the discretionary p is retired and every
later row is filed at the running climatological base rate. It tripped on 2026-10-05 and nobody recorded it.
The check holds the two halves: (1) the LATEST forecasts row's p is the base rate, +/-0.005; (2) REGISTRY.md carries
the verdict entry. The base rate drifts by up to ~0.015 each time a row resolves, so (1) is read against the base the
writer filed at - the `base=` in the row's own [CLAUSE-B ...] stamp - and that stamp must itself sit within 0.05 of
today's running base, so a forged stamp cannot launder a discretionary p. A row with no stamp is read against today's
base. This is RED until the first row is filed after 2026-10-17 (the next session run), by design.

Returns (ok: bool, evidence: str). Standalone run prints the current result, read-only:
    /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_check_clause_b.py
"""
import csv
import os
import re

_ROOT = os.path.expanduser("~/insider-radar")


def check_ins_clause_b_applied(root=_ROOT):
    """INS Clause B: latest forecasts row filed at the running base rate (+/-0.005) AND the verdict is in REGISTRY.md."""
    try:
        rows = list(csv.DictReader(open(f"{root}/agent/forecasts.csv")))
        reg = open(f"{root}/REGISTRY.md").read()
    except OSError as e:
        return False, f"cannot verify - {e}"
    res = [r for r in rows if (r.get("outcome") or "").strip() in ("0", "1")]
    if not rows or not res:
        return False, "forecasts.csv has no rows / no resolved rows - cannot compute the base rate"
    now = sum(int(r["outcome"]) for r in res) / len(res)
    last = rows[-1]
    m = re.search(r"\[CLAUSE-B[^\]]*\bbase=([0-9.]+) k=\d+ n=\d+", last.get("notes") or "")
    ref = float(m.group(1)) if m else now
    bad = []
    if abs(float(last["p"]) - ref) > 0.005:
        bad.append(f"latest row {last['date']} {last['instrument']} p={last['p']} is not the base rate {ref:.4f}")
    if m and abs(ref - now) > 0.05:
        bad.append(f"its stamped base {ref:.4f} is far from today's running base {now:.4f}")
    if "Clause B tripped at n=40" not in reg:
        bad.append("REGISTRY.md lacks the 'Clause B tripped at n=40' verdict entry")
    if bad:
        return False, "; ".join(bad)
    return True, (f"latest row {last['date']} {last['instrument']} p={last['p']} = base rate {ref:.4f} "
                  f"(running now {now:.4f}, n={len(res)}); REGISTRY carries the Clause B verdict")


if __name__ == "__main__":
    print(check_ins_clause_b_applied())

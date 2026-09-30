#!/usr/bin/env python3
"""PROPOSED — NOT APPLIED. The prereg-reviewer's check extension for INS-022 (2026-09-29).

A patch proposal for ~/command-center/council/resolver.py, deliberately NOT applied: resolver.py and
council/issues.json are owned by another session. To adopt, replace the body of resolver.py's
check_no_unadjusted_splits (DATA-003, ~line 3768) with the function below (same name, same registration —
nothing new to register). It keeps every clause of the current check and adds:

  SOURCE HALF (INS-022)
    - no bare `except ...: pass` inside any SPLIT GUARD block of ~/bin/grade_all_due.py, nor inside the
      split helpers _split_events / _split_factor (an unknown split history must never read as "no split");
    - the stall token 'SPLIT-UNKNOWN' is present, the helper asks for raise_errors=True, and no code line
      reads yfinance's `.splits` property (which calls history(period="max") with raise_errors=False, so a
      failed fetch returns an EMPTY Series);
    - LiveFetch.bars reads splits through _split_events (the insider path shares the helper).
  DATA HALF (INS-022)
    - the >10x-without-disclosure scan now covers the stock-radar and india-radar ledgers as well as the
      insider ledger.

Returns (ok: bool, evidence: str) like every resolver check. Standalone run prints the current result,
read-only:  /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_check_INS-022.py
"""
import os
import re

HOME = os.path.expanduser("~")


def _blocks_after(src, marker, n_lines=30):
    """Each SPLIT GUARD block: from the marker line to the next blank-line-free run of n_lines."""
    lines = src.splitlines()
    out = []
    for i, l in enumerate(lines):
        if marker in l:
            out.append("\n".join(lines[i:i + n_lines]))
    return out


def _func_body(src, name):
    m = re.search(rf"^def {name}\(.*?(?=^\S)", src, re.S | re.M)
    return m.group(0) if m else None


_EXCEPT_PASS = re.compile(r"except\b[^\n]*:\s*(?:#[^\n]*)?\n?\s*pass\b")


def check_no_unadjusted_splits():
    """DATA-003 + INS-022: a split between a row's call date and its grading must adjust the basis, disclosed;
    a split history that cannot be established stalls the row (SPLIT-UNKNOWN) — it never reads as "no split".

    GRML's 1-for-50 reverse split (2026-08-24) turned a -4% insider row into "+4436%" on the page for a
    morning. Source half: the daily grader carries the split guard and the never-twice token check, and
    (INS-022) no split guard or split helper swallows a failed lookup. Data half: the GRML row carries its
    disclosure, and no scored row on any of the three graded ledgers implies a >10x move without one.
    """
    import csv as _csv
    src_p = f"{HOME}/bin/grade_all_due.py"
    if not os.path.exists(src_p):
        return False, "grade_all_due.py missing"
    s = open(src_p).read()
    if "SPLIT GUARD" not in s or "never adjust twice" not in s:
        return False, "grade_all_due.py lacks the split guard or the double-adjust token check"
    # ---- INS-022 source half
    if "SPLIT-UNKNOWN" not in s:
        return False, "grade_all_due.py lacks the SPLIT-UNKNOWN stall (INS-022)"
    regions = _blocks_after(s, "SPLIT GUARD")
    for fn in ("_split_events", "_split_factor"):
        body = _func_body(s, fn)
        if body is None:
            return False, f"grade_all_due.py has no {fn}() — the INS-022 split helper is gone"
        regions.append(body)
    for reg in regions:
        if _EXCEPT_PASS.search(reg):
            return False, "a split guard / split helper in grade_all_due.py swallows a failure with a bare `except ...: pass` (INS-022)"
    if "raise_errors=True" not in (_func_body(s, "_split_events") or ""):
        return False, "_split_events() does not request raise_errors=True — a failed fetch could read as 'no split' (INS-022)"
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    if re.search(r"[A-Za-z_)\]]\.splits\b", code):
        return False, "grade_all_due.py reads yfinance's `.splits` (raise_errors=False: a failed fetch is an empty Series) (INS-022)"
    m = re.search(r"    def bars\(self.*?(?=\n    def )", s, re.S)
    if not m or "_split_events(" not in m.group(0):
        return False, "LiveFetch.bars does not read splits through _split_events — the insider path has its own reader (INS-022)"
    # ---- data half (insider as before, plus stock-radar and india-radar — INS-022)
    ledgers = [f"{HOME}/insider-radar/agent/ledger.csv", f"{HOME}/stock-radar/agent/ledger.csv",
               f"{HOME}/india-radar/agent/ledger.csv"]
    grml_ok, bad, scanned = False, [], 0
    for led in ledgers:
        if not os.path.exists(led):
            return False, f"{os.path.relpath(led, HOME)} missing — cannot scan it"
        lab = os.path.relpath(led, HOME).split("/")[0]
        for r in _csv.DictReader(open(led)):
            if lab == "insider-radar" and r.get("ticker") == "GRML" and r.get("date") == "2026-07-25":
                grml_ok = "[SPLIT ADJUSTED" in (r.get("thesis") or "")
            if (r.get("outcome") or "").strip() in ("right", "wrong"):
                scanned += 1
                try:
                    p0, p1 = float(r["price_at_call"]), float(r["price_at_check"])
                    if p0 > 0 and (p1 / p0 > 10 or p1 / p0 < 0.1) and "[SPLIT ADJUSTED" not in (r.get("thesis") or ""):
                        bad.append(f"{lab} {r['ticker']} {r['date']} ({p0} -> {p1})")
                except (ValueError, KeyError):
                    continue
    if not grml_ok:
        return False, "the GRML 2026-07-25 row does not carry its [SPLIT ADJUSTED] disclosure"
    if bad:
        return False, f"scored row(s) imply >10x without a split disclosure: {', '.join(bad[:4])}"
    return True, (f"split guard present, no swallowed split lookup, SPLIT-UNKNOWN stalls on both paths (INS-022); "
                  f"GRML disclosed; 0 of {scanned} scored rows across insider/stock/india imply an undisclosed >10x basis jump")


if __name__ == "__main__":
    print(check_no_unadjusted_splits())

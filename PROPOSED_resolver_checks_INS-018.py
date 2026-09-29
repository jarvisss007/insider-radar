#!/usr/bin/env python3
"""PROPOSED — NOT APPLIED. Three resolver checks for INS-018, as the prereg-reviewer specified (2026-09-29).

This file is a patch proposal for ~/command-center/council/resolver.py. It was deliberately NOT applied:
resolver.py and council/issues.json are owned by another session. To adopt, paste the three functions into
resolver.py and register them, e.g.

    CHECKS.update({
        "insider_single_grader": check_insider_single_grader,
        "insider_grader_clauses_tested": check_insider_grader_clauses_tested,
        "insider_due_rows_accounted": check_insider_due_rows_accounted,
    })

Each returns (ok: bool, evidence: str) like every resolver check. Running this file standalone prints each
check's current result, read-only:  /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_checks_INS-018.py

RELATED, ALSO NOT APPLIED — check_insider_substituted_bar_is_stamped (resolver.py ~line 3647) accepts only the
stamps "RESOLVED OFF" / "resolved off" / "SUBSTITUTED BAR" / "bar used" / "BAR USED" on a SPLIT ADJUSTED row. The
INS-018 grader's reviewer-prescribed roll-forward stamp is "[INS-012: no bar on {cd}; scored on the {bd} close, the
next session with a traded bar]". Today no scored row carries it, so the check passes; the first split-day
roll-forward (a GRML-shaped row) would FAIL it although the row names its bar. Proposed one-line amendment: add
"[INS-012: no bar on" to that tuple of accepted stamps.
"""
import csv
import datetime as dt
import os
import re
import subprocess

HOME = os.path.expanduser("~")
_AGENT = f"{HOME}/insider-radar/agent/AGENT.md"
_LEDGER = f"{HOME}/insider-radar/agent/ledger.csv"
_TESTS = f"{HOME}/insider-radar/tests/test_ins018_grader.py"
_LOG = f"{HOME}/bin/logs/grade-all-due.log"
_SURVIVORSHIP = "A delisted or unfetchable ticker is scored `wrong`"


def _step2(text):
    i = text.find("2. **Score due calls")
    j = text.find("3. **Update lessons**", i)
    return text[i:j] if i >= 0 and j > i else None


def check_insider_single_grader():
    """INS-018. One grader, one code path: insider AGENT.md step 2 names ~/bin/grade_all_due.py as the only writer
    of price_at_check/outcome, carries NO independent Yahoo fetch, and keeps the survivorship clause verbatim
    (dropping it is a rule change the reviewer escalated on 2026-09-29)."""
    if not os.path.exists(_AGENT):
        return False, "insider-radar/agent/AGENT.md missing"
    s2 = _step2(open(_AGENT).read())
    if s2 is None:
        return False, "AGENT.md step 2 ('2. **Score due calls' .. '3. **Update lessons**') not found — cannot verify"
    bad = []
    if "query1.finance.yahoo.com" in s2:
        bad.append("step 2 still carries an independent query1.finance.yahoo.com fetch")
    if "grade_all_due.py" not in s2:
        bad.append("step 2 does not name grade_all_due.py")
    if _SURVIVORSHIP not in s2:
        bad.append(f"step 2 lost the survivorship clause (verbatim '{_SURVIVORSHIP}')")
    if bad:
        return False, "; ".join(bad)
    return True, "step 2 names grade_all_due.py as the only grader, has no independent fetch, and keeps the survivorship clause verbatim"


def check_insider_grader_clauses_tested():
    """INS-018. Every clause of step 2 has an offline test and the suite is green."""
    if not os.path.exists(_TESTS):
        return False, "insider-radar/tests/test_ins018_grader.py missing"
    src = open(_TESTS).read()
    missing = [f"test_{n:02d}" for n in range(1, 13) if f"def test_{n:02d}_" not in src]
    if missing:
        return False, f"the reviewer's numbered tests are missing: {', '.join(missing)}"
    try:
        r = subprocess.run(["/opt/anaconda3/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", _TESTS],
                           capture_output=True, text=True, timeout=600)
    except Exception as e:
        return False, f"could not run the INS-018 suite: {type(e).__name__}: {e}"
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        return False, f"INS-018 grader suite is RED (rc {r.returncode}): {tail}"
    return True, f"INS-018 grader suite green: {tail}"


def _sessions():
    import importlib.util as iu
    sp = iu.spec_from_file_location("_sess_ins018", f"{HOME}/stock-radar/sessions.py")
    m = iu.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _latest_insider_block(log_text):
    """(run_date, {(ticker, check_date): reason}, graded_count) from the newest grade_all_due run in the log."""
    lines = log_text.splitlines()
    ends = [i for i, l in enumerate(lines) if re.match(r"grade_all_due \d{4}-\d{2}-\d{2}:", l)]
    if not ends:
        return None, {}, 0
    end = ends[-1]
    run_date = dt.date.fromisoformat(lines[end].split()[1].rstrip(":"))
    start = max((i for i in range(end) if lines[i].startswith("insider-radar/agent/ledger.csv:")), default=None)
    if start is None or (len(ends) > 1 and start < ends[-2]):
        return run_date, None, 0
    stalls, graded = {}, 0
    for l in lines[start + 1:end]:
        if not l.startswith("   "):
            break
        m = re.match(r"\s+!! (\S+) due (\d{4}-\d{2}-\d{2}) — (.+)", l)
        if m:
            stalls[(m.group(1), m.group(2))] = m.group(3)
        else:
            graded += 1
    return run_date, stalls, graded


def check_insider_due_rows_accounted():
    """INS-018. Nothing due sits silently: every due, blank-outcome insider row appears in the newest grader run's
    log block with a stall reason. A row due since the grader last ran fails loud (the grader stopped), except a
    row due today before the 13:40 PT slot has come."""
    try:
        S = _sessions()
        settled = S.settled_session()
    except Exception as e:
        return False, f"sessions calendar unavailable ({type(e).__name__}) — cannot decide what is due"
    if not os.path.exists(_LOG):
        return False, "~/bin/logs/grade-all-due.log missing"
    run_date, stalls, graded = _latest_insider_block(open(_LOG, errors="ignore").read())
    if run_date is None:
        return False, "no grade_all_due run found in the log"
    if stalls is None:
        return False, f"the {run_date} grader run has no insider-radar block in the log"
    now = dt.datetime.now()
    due, missing, not_run = 0, [], []
    for r in csv.DictReader(open(_LEDGER)):
        if (r.get("outcome") or "").strip() or not r.get("check_date"):
            continue
        try:
            cd = dt.date.fromisoformat(r["check_date"][:10])
        except ValueError:
            missing.append(f"{r.get('ticker')} (unparseable check_date {r['check_date']!r})")
            continue
        cd_eff = cd if S.is_session(cd) else S.next_session(cd)
        if cd_eff > settled:
            continue
        due += 1
        tk = (r.get("ticker") or "").strip()
        if cd_eff > run_date:
            if not (cd_eff == now.date() and (now.hour, now.minute) < (13, 55)):
                not_run.append(f"{tk} due {cd_eff}")
            continue
        if (tk, cd_eff.isoformat()) not in stalls and (tk, cd.isoformat()) not in stalls:
            missing.append(f"{tk} due {cd_eff}")
    if not_run:
        return False, (f"{len(not_run)} insider row(s) due since the grader last ran ({run_date}): "
                       f"{', '.join(not_run[:6])}")
    if missing:
        return False, (f"{len(missing)} due blank-outcome insider row(s) are absent from the {run_date} grader log "
                       f"with no stall reason: {', '.join(missing[:6])}")
    return True, (f"{due} due blank-outcome insider row(s); every one is named with a stall reason in the "
                  f"{run_date} grader log ({len(stalls)} stall line(s), {graded} graded line(s))")


if __name__ == "__main__":
    for fn in (check_insider_single_grader, check_insider_grader_clauses_tested, check_insider_due_rows_accounted):
        ok, ev = fn()
        print(("PASS" if ok else "FAIL"), fn.__name__, "—", ev)

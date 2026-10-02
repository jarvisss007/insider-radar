#!/usr/bin/env python3
"""PROPOSED - NOT APPLIED. Resolver checks for the three rulings executed 2026-10-01 (INS-025, INS-026, FCST-007), for
~/command-center/council/resolver.py.

A patch proposal, deliberately not applied: resolver.py and council/issues.json are not this lab's to edit. To adopt, paste the
functions (and their prefixed helpers) into resolver.py and register them, e.g.

    CHECKS.update({
        "insider_prose_rows_resolved":        _ins025b_prose_rows_resolved,
        "insider_resolver_reads_prose_form":  _ins025b_resolver_reads_prose_form,
        "insider_prose_tests_green":          _ins025b_tests_green,
        "insider_ref_clean_and_restated":     _ins026b_ref_clean_and_restated,
        "forecast_resolver_refuses_zero_volume_on_production": _fcst007_production_path_refuses_zero_volume,
        "forecast_resolver_fcst007_tests_green": _fcst007_tests_green,
    })

Every module-level name carries the _ins025b_ / _ins026b_ / _fcst007_ prefix, so pasting into resolver.py cannot collide. Each check
returns (ok: bool, msg: str) and fails LOUD when it cannot look - a monitor never reports a clean zero it did not measure.
Read-only: nothing here writes a book (price_audit.py refreshes only its own gitignored bar cache; the probe runs in a throwaway HOME).
Standalone run:

    /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_checks_ruled_1001.py

These supersede the staged ~/bin/proposals/INS-025/PROPOSED_resolver_checks_INS-025_INS-026.py now that INS-025 and INS-026 are ruled and executed
(its check_ins026_every_ref_mismatch_disclosed was written for the state "gap disclosed, ruling pending"; after the restatement the
right claim is "no gap at all, and the restatement is on the rows").

INS-025 (ruled (a) OK, executed 2026-10-01) - the estate forecast resolver reads the insider desk's prose question
          "Absolute <T> <N>-session move from ... exceeds <X>% on <D>".
  _ins025b_prose_rows_resolved        no prose-form insider row sits unresolved past its check date plus one settled session; a row due and
                                      still blank inside that one-session grace is NAMED with the stall the resolver prints for it today
                                      (a live --dry run, only when such a row exists); one past the grace FAILS
  _ins025b_resolver_reads_prose_form  the resolver carries the prose parse, scoped to the insider ledger, and its pattern reads every
                                      prose-looking row in the ledger (a new variant fails here the day it is filed)
  _ins025b_tests_green                the INS-025 offline suite (11 tests) is green
INS-026 (ruled (a) FIX, executed 2026-10-01) - DFDV 5.83 -> 5.84 and ATCH 0.1926 -> 0.193, the settled official opens.
  _ins026b_ref_clean_and_restated     price_audit.py --open-only reports REF_MISMATCH 0 and FAIL 0, and both rows carry the restatement note,
                                      the restated price, and the recorded old value
FCST-007 (class (d) defect, fixed 2026-10-01) - the resolver's production price path read the close alone.
  _fcst007_production_path_refuses_zero_volume  the live resolver, run in a throwaway HOME whose production reader returns the close alone,
                                      refuses a zero-volume carry-forward bar with the fallback's own wording and resolves a bar that traded
  _fcst007_tests_green                the FCST-007 offline suite (11 tests) is green
"""
import os as _ins025b_os
import re as _ins025b_re

_ins025b_HOME = _ins025b_os.path.expanduser("~")
_ins025b_PY = "/opt/anaconda3/bin/python"
_ins025b_FORECASTS = f"{_ins025b_HOME}/insider-radar/agent/forecasts.csv"
_ins025b_RESOLVER = f"{_ins025b_HOME}/bin/resolve_forecasts.py"
_ins025b_SESSIONS = f"{_ins025b_HOME}/stock-radar/sessions.py"
_ins025b_TESTS = f"{_ins025b_HOME}/insider-radar/tests/test_ins025_prose_forecast.py"
_ins025b_LEDGER_REL = "insider-radar/agent/forecasts.csv"


def _ins025b_sessions():
    import importlib.util as iu
    sp = iu.spec_from_file_location("_ins025b_sess", _ins025b_SESSIONS)
    m = iu.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _ins025b_parser_pattern():
    """The resolver's OWN prose pattern, read out of its source (never re-typed here), or None."""
    import ast
    try:
        tree = ast.parse(open(_ins025b_RESOLVER).read())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "P" and isinstance(node.value, ast.Call) and node.value.args):
            try:
                return _ins025b_re.compile(ast.literal_eval(node.value.args[0]), _ins025b_re.I)
            except (ValueError, _ins025b_re.error):
                return None
    return None


def _ins025b_live_stalls():
    """({instrument: what the resolver prints for it today}, error) from a live `resolve_forecasts.py --dry` - the insider ledger's block.
    --dry writes nothing. Called only when a due-and-blank prose row exists, so the usual run of this check is a pure file read."""
    import subprocess
    try:
        r = subprocess.run([_ins025b_PY, _ins025b_RESOLVER, "--dry"], capture_output=True, text=True, timeout=900)
    except Exception as e:
        return {}, f"could not run resolve_forecasts.py --dry ({type(e).__name__}: {e})"
    if r.returncode != 0:
        return {}, f"resolve_forecasts.py --dry exited {r.returncode}: {(r.stderr or r.stdout).strip().splitlines()[-1:]}"
    lines = r.stdout.splitlines()
    heads = [i for i, l in enumerate(lines) if l.strip() == _ins025b_LEDGER_REL]
    out = {}
    if heads:
        for l in lines[heads[0] + 1:]:
            if not l.startswith("  "):
                break
            m = _ins025b_re.match(r"\s+SKIP \(([^)]*)\): (\S+) — (.*)", l)
            if m:
                out[m.group(2)] = f"SKIP ({m.group(1)}): {m.group(3).strip()}"
                continue
            m = _ins025b_re.match(r"\s+(\S+) p=\S+ → (YES|no) ", l)
            if m:
                out[m.group(1)] = f"the resolver would score it {m.group(2)} at its next write run"
    return out, ""


def _ins025b_prose_rows_resolved():
    """INS-025. No prose-form insider forecast sits unresolved past its check date plus one settled session. A row due but still inside
    that one-session grace is named with the stall the resolver prints for it today; one past the grace FAILS (a forecast that can never
    be scored is the silent abstention FCST-001 exists to catch)."""
    import csv
    import datetime as dt
    pat = _ins025b_parser_pattern()
    prose_like = _ins025b_re.compile(r"^\s*absolute\s", _ins025b_re.I)
    try:
        S = _ins025b_sessions()
        settled = S.settled_session()
    except Exception as e:
        return False, f"sessions calendar unavailable ({type(e).__name__}) - cannot decide what is due"
    if not _ins025b_os.path.exists(_ins025b_FORECASTS):
        return False, "insider-radar/agent/forecasts.csv missing"
    total = resolved = future = 0
    due_blank = []
    for r in csv.DictReader(open(_ins025b_FORECASTS)):
        q = (r.get("question") or "").replace("radar.json ", "")
        if not prose_like.search(q):
            continue
        total += 1
        ins = (r.get("instrument") or "").strip()
        if (r.get("outcome") or "").strip():
            resolved += 1
            continue
        try:
            cd = dt.date.fromisoformat((r.get("check_date") or "")[:10])
        except ValueError:
            return False, f"{ins}: unparseable check_date {r.get('check_date')!r} on a prose-form row"
        cd_eff = S.roll_to_session(cd)
        if cd_eff > settled:
            future += 1
            continue
        due_blank.append((ins, cd_eff, q))
    if not total:
        return False, "no prose-form row in the insider ledger - the check has nothing to read (a monitor never reports a zero it did not measure)"
    grace, overdue, unreadable = [], [], []
    if due_blank:
        stalls, err = _ins025b_live_stalls()
        for ins, cd_eff, q in due_blank:
            stall = stalls.get(ins) or (f"no line for it in a live resolver run ({err})" if err else "the live resolver run printed no line for it")
            if pat is None or not pat.search(q):
                unreadable.append(f"{ins}: the resolver's prose pattern does not read this question ({stall})")
            elif settled > S.next_session(cd_eff):
                overdue.append(f"{ins} due {cd_eff}, still blank at settled {settled} - {stall}")
            else:
                grace.append(f"{ins} due {cd_eff}: {stall}")
    if unreadable or overdue:
        return False, ("; ".join(unreadable + overdue) + f" [{total} prose-form row(s): {resolved} resolved, "
                       f"{len(grace)} within grace, {future} not yet due]")
    return True, (f"{total} prose-form insider row(s): {resolved} resolved, {future} not yet due, {len(grace)} due and inside the "
                  f"one-session grace" + (" - named: " + "; ".join(grace) if grace else ""))


def _ins025b_resolver_reads_prose_form():
    """INS-025. The estate resolver carries the prose parse, scoped to the insider ledger, and its pattern reads every
    prose-looking question in the ledger (so a NEW variant fails here the day it is filed, not when it comes due)."""
    import ast
    import csv
    if not _ins025b_os.path.exists(_ins025b_RESOLVER):
        return False, "~/bin/resolve_forecasts.py missing"
    src = open(_ins025b_RESOLVER).read()
    pat = _ins025b_parser_pattern()
    if pat is None:
        return False, "resolve_forecasts.py has no prose pattern P - the INS-025 parse is absent (rows will SKIP (unparsed))"
    tree = ast.parse(src)
    scope = [ast.get_source_segment(src, n) for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "PROSE_LEDGERS" for t in n.targets)]
    if not scope or "insider-radar/agent/forecasts.csv" not in scope[0] or scope[0].count("forecasts.csv") != 1:
        return False, "resolve_forecasts.py does not scope the prose parse to the insider ledger alone (PROSE_LEDGERS)"
    if not _ins025b_re.search(r"^\s*elif\s+mp\s*:", src, _ins025b_re.M):
        return False, "resolve_forecasts.py defines the prose pattern but has no branch that scores it"
    bad = [f"{r.get('instrument')} {r.get('date')}" for r in csv.DictReader(open(_ins025b_FORECASTS))
           if _ins025b_re.match(r"^\s*absolute\s", (r.get("question") or "").replace("radar.json ", ""), _ins025b_re.I)
           and not pat.search((r.get("question") or "").replace("radar.json ", ""))]
    if bad:
        return False, f"{len(bad)} prose-looking row(s) the resolver's pattern cannot read: {', '.join(bad[:6])}"
    return True, "resolve_forecasts.py scores the prose form (insider ledger only) and its pattern reads every prose-looking row filed"


def _ins025b_tests_green():
    """INS-025. The offline suite (formula, strictness, guards, scope, old-vs-new replay) is green."""
    import subprocess
    if not _ins025b_os.path.exists(_ins025b_TESTS):
        return False, "insider-radar/tests/test_ins025_prose_forecast.py missing"
    try:
        r = subprocess.run([_ins025b_PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", _ins025b_TESTS],
                           capture_output=True, text=True, timeout=900)
    except Exception as e:
        return False, f"could not run the INS-025 suite: {type(e).__name__}: {e}"
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return (r.returncode == 0), (f"INS-025 suite {'green' if r.returncode == 0 else 'RED (rc %d)' % r.returncode}: {tail}")


# ---------------------------------------------------------------- INS-026
import os as _ins026b_os   # noqa: E402

_ins026b_ROOT = f"{_ins026b_os.path.expanduser('~')}/insider-radar"
_ins026b_AUDIT = f"{_ins026b_ROOT}/price_audit.py"
_ins026b_LEDGER = f"{_ins026b_ROOT}/agent/ledger.csv"
_ins026b_PY = "/opt/anaconda3/bin/python"
# (call date, ticker, the first print the writer recorded, the settled official open it was restated to)
_ins026b_ROWS = [("2026-09-28", "DFDV", "5.83", "5.84"), ("2026-09-29", "ATCH", "0.1926", "0.193")]


def _ins026b_ref_clean_and_restated():
    """INS-026. price_audit.py (read-only apart from its own gitignored bar cache) reports REF_MISMATCH 0 and FAIL 0 and exits 0, AND
    both restated rows carry (a) the restatement note, word for word, (b) the restated price in price_at_call, (c) the recorded old
    value inside that note and the earlier [REF-GAP INS-026 ...] disclosure, left in place. Fails loud if the audit cannot be read."""
    import csv
    import json
    import subprocess
    if not _ins026b_os.path.exists(_ins026b_AUDIT):
        return False, "insider-radar/price_audit.py missing"
    try:
        r = subprocess.run([_ins026b_PY, _ins026b_AUDIT, "--open-only", "--json"], capture_output=True, text=True, timeout=600)
        b = json.loads(r.stdout)
    except Exception as e:
        return False, f"price_audit.py --open-only --json could not be read ({type(e).__name__}) - cannot say the audit is clean"
    mism, fail = b.get("REF_MISMATCH", []), b.get("FAIL", [])
    if mism or fail or r.returncode != 0:
        return False, (f"price audit not clean (exit {r.returncode}): REF_MISMATCH {len(mism)} "
                       + ", ".join(f"{x['ticker']} {x['date']} recorded {x['price_at_call']} vs owed {x.get('owed')}" for x in mism)
                       + f"; FAIL {len(fail)} " + ", ".join(f"{x['ticker']} {x['date']}" for x in fail))
    if not _ins026b_os.path.exists(_ins026b_LEDGER):
        return False, "insider-radar/agent/ledger.csv missing"
    rows = list(csv.DictReader(open(_ins026b_LEDGER, newline="")))
    problems = []
    for d, tk, was, now in _ins026b_ROWS:
        hit = [x for x in rows if x["date"] == d and x["ticker"] == tk]
        if len(hit) != 1:
            problems.append(f"{tk} {d}: {len(hit)} ledger rows (expected 1)")
            continue
        x = hit[0]
        note = (f"RESTATED 2026-10-01 per Anupam's INS-026 ruling: was {was} (first print of a forming bar) -> {now} settled official open")
        if note not in x["thesis"]:
            problems.append(f"{tk} {d}: the restatement note is missing from the thesis cell")
        if x["price_at_call"] != now:
            problems.append(f"{tk} {d}: price_at_call is {x['price_at_call']!r}, not the restated {now!r}")
        if f"[REF-GAP INS-026: recorded {was} " not in x["thesis"]:
            problems.append(f"{tk} {d}: the earlier [REF-GAP INS-026 ...] disclosure (the old value {was}) is gone")
    if problems:
        return False, "; ".join(problems)
    return True, (f"price audit clean: REF_MISMATCH 0, FAIL 0, exit 0 (REF_OK {len(b.get('REF_OK', []))}); "
                  + ", ".join(f"{tk} {was} -> {now}" for _d, tk, was, now in _ins026b_ROWS)
                  + " restated, each row carries the note, the restated price and the recorded old value")


# ---------------------------------------------------------------- FCST-007
import os as _fcst007_os   # noqa: E402

_fcst007_HOME = _fcst007_os.path.expanduser("~")
_fcst007_PY = "/opt/anaconda3/bin/python"
_fcst007_RESOLVER = f"{_fcst007_HOME}/bin/resolve_forecasts.py"
_fcst007_TESTS = f"{_fcst007_HOME}/insider-radar/tests/test_fcst007_production_zero_volume.py"
_fcst007_FAKE_YF = f"{_fcst007_HOME}/insider-radar/tests/fixtures/fake_yf"
_fcst007_SESSIONS = '''
import datetime as dt
SETTLED = dt.date(2026, 9, 30)
def _d(x): return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])
def is_session(d): d = _d(d); return d.weekday() < 5
def settled_session(now=None, cutoff=None): return SETTLED
'''
# The PRODUCTION reader as it is: close_on returns the close alone, with no volume (stock-radar/options_settle.py).
_fcst007_SETTLE = '''
import json, os
class NotSettled(ValueError): pass
def close_on(tk, day):
    for b in json.load(open(os.environ["FAKE_YF_FIXTURE"])).get(tk, {}).get("bars") or []:
        if b[0] == str(day)[:10] and b[4] is not None:
            return float(b[4])
    return None
'''


def _fcst007_production_path_refuses_zero_volume():
    """FCST-007. The resolver's production price path (options_settle.close_on reads the close alone) must not let a zero-volume
    carry-forward bar resolve a forecast. PROBE: the LIVE resolver runs in a throwaway HOME (stub calendar, a production reader that
    returns the close alone, the offline yfinance stand-in) over two insider rows: one whose check-date bar is a carry-forward (volume 0
    on a tape that trades) and one that traded. The first must stay blank with the fallback's own stall wording, the second must resolve.
    A static read first: the source must still define the veto and consult it. Fails loud if the probe cannot run."""
    import ast
    import csv
    import json
    import subprocess
    import tempfile
    if not _fcst007_os.path.exists(_fcst007_RESOLVER):
        return False, "~/bin/resolve_forecasts.py missing"
    if not _fcst007_os.path.isdir(_fcst007_FAKE_YF):
        return False, "insider-radar/tests/fixtures/fake_yf missing - the probe cannot run"
    src = open(_fcst007_RESOLVER).read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return False, f"resolve_forecasts.py does not parse: {e}"
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if not {"_carry_forward", "_production_veto", "close_on"} <= set(fns):
        return False, "resolve_forecasts.py has no production-path zero-volume veto (_carry_forward/_production_veto) - the FCST-007 fix is absent"
    if not any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_production_veto" for c in ast.walk(fns["close_on"])):
        return False, "resolve_forecasts.close_on never consults _production_veto - a close options_settle returns is not tested for volume"
    week = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24",
            "2026-09-25", "2026-09-28"]

    def tape(cf):   # every bar traded at 100; the last is either a carry-forward (the price carried, volume 0) or a traded 105
        out = [[d, 100.0, 100.0, 100.0, 100.0, 1000.0] for d in week[:-1]]
        out.append([week[-1], 100.0, 100.0, 100.0, 100.0, 0.0] if cf else [week[-1], 100.0, 105.0, 100.0, 105.0, 1000.0])
        return out
    cols = ["date", "instrument", "horizon_days", "question", "p", "check_date", "outcome", "notes"]
    rows = [dict(date="2026-09-21", instrument=t, horizon_days="5", question=f"{t} closes above 100 on 2026-09-28", p="0.3",
                 check_date="2026-09-28", outcome="", notes="[probe]") for t in ("PROBECF", "PROBEOK")]
    try:
        with tempfile.TemporaryDirectory() as h:
            _fcst007_os.makedirs(f"{h}/stock-radar")
            _fcst007_os.makedirs(f"{h}/insider-radar/agent")
            open(f"{h}/stock-radar/sessions.py", "w").write(_fcst007_SESSIONS)
            open(f"{h}/stock-radar/options_settle.py", "w").write(_fcst007_SETTLE)
            with open(f"{h}/insider-radar/agent/forecasts.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
            # BOOK-001 does not apply: a scratch fixture inside a temp directory, never a shared book
            json.dump({"PROBECF": {"bars": tape(True), "splits": []}, "PROBEOK": {"bars": tape(False), "splits": []}}, open(f"{h}/yf.json", "w"))
            env = dict(_fcst007_os.environ, HOME=h, FAKE_YF_FIXTURE=f"{h}/yf.json", PYTHONPATH=_fcst007_FAKE_YF)
            r = subprocess.run([_fcst007_PY, _fcst007_RESOLVER], capture_output=True, text=True, env=env, timeout=300)
            got = {x["instrument"]: x for x in csv.DictReader(open(f"{h}/insider-radar/agent/forecasts.csv"))}
    except Exception as e:
        return False, f"the probe could not run ({type(e).__name__}: {e})"
    if r.returncode != 0:
        return False, f"the probe's resolver run exited {r.returncode}: {r.stderr.strip()[-300:]}"
    if got["PROBEOK"]["outcome"] != "1":
        return False, f"probe control: a bar that traded did not resolve (outcome {got['PROBEOK']['outcome']!r}) - the probe or the veto is broken: {r.stdout.strip()[-300:]}"
    if got["PROBECF"]["outcome"] != "":
        return False, (f"the production path RESOLVED a forecast off a zero-volume carry-forward bar (outcome {got['PROBECF']['outcome']!r}) "
                       "- FCST-007 is live again")
    if "SKIP (no close): PROBECF" not in r.stdout or "the 2026-09-28 bar is a zero-volume carry-forward" not in r.stdout:
        return False, f"the carry-forward row stayed blank but the stall was not named in the fallback's wording: {r.stdout.strip()[-300:]}"
    return True, ("the production path refused a zero-volume carry-forward bar ('the 2026-09-28 bar is a zero-volume carry-forward', row left "
                  "blank) and resolved a bar that traded; the veto is wired into close_on")


def _fcst007_tests_green():
    """FCST-007. The offline suite (every form, wording, fuzz old-vs-new, fail-closed, same-day, .NS, real-ledger replay) is green."""
    import subprocess
    if not _fcst007_os.path.exists(_fcst007_TESTS):
        return False, "insider-radar/tests/test_fcst007_production_zero_volume.py missing"
    try:
        r = subprocess.run([_fcst007_PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", _fcst007_TESTS],
                           capture_output=True, text=True, timeout=900)
    except Exception as e:
        return False, f"could not run the FCST-007 suite: {type(e).__name__}: {e}"
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return (r.returncode == 0), (f"FCST-007 suite {'green' if r.returncode == 0 else 'RED (rc %d)' % r.returncode}: {tail}")


def _fcst007_main():
    bad = 0
    for fn in (_ins025b_prose_rows_resolved, _ins025b_resolver_reads_prose_form, _ins025b_tests_green,
               _ins026b_ref_clean_and_restated,
               _fcst007_production_path_refuses_zero_volume, _fcst007_tests_green):
        ok, msg = fn()
        bad += not ok
        print(("PASS" if ok else "FAIL"), fn.__name__, "-", msg)
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    _fcst007_main()

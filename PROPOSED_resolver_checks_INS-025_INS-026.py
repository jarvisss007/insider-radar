#!/usr/bin/env python3
"""PROPOSED - NOT APPLIED. Resolver checks for INS-025 and INS-026 (insider-radar), for ~/command-center/council/resolver.py.

A patch proposal, deliberately not applied: resolver.py and council/issues.json are not this lab's to edit. To adopt, paste the
functions (and their prefixed helpers) into resolver.py and register them, e.g.

    CHECKS.update({
        "insider_prose_forecasts_resolved": check_ins025_prose_rows_resolved,
        "insider_resolver_reads_prose_form": check_ins025_resolver_reads_prose_form,
        "insider_prose_tests_green": check_ins025_tests_green,
        "insider_ref_mismatches_disclosed": check_ins026_every_ref_mismatch_disclosed,
        "insider_fill_reads_settled_bars": check_ins026_writer_fix_holds,
    })

Every module-level name carries the _ins025_ / _ins026_ prefix (or is a check_ins025_* / check_ins026_* function) so pasting
into resolver.py cannot collide. Each check returns (ok: bool, msg: str) and fails LOUD when it cannot look - a monitor never
reports a clean zero it did not measure. Read-only: nothing here writes a book (price_audit.py refreshes only its own gitignored bar cache). Standalone run:

    /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_checks_INS-025_INS-026.py

STATUS 2026-09-30. INS-025's fix is class (c) (prereg-reviewer: ESCALATE) and is NOT applied: it awaits an explicit ruling, so the
three check_ins025_* checks are RED today - which is the truth, and they go green when the ruling is executed. INS-026's writer fix
(class (d)) and the note on the two rows (class (a)) are applied; the audit waiver (class (c)) is NOT, so the two gaps stay
REF_MISMATCH (audit exit 1) until a ruling, tagged as disclosed.

INS-025 - the estate forecast resolver (~/bin/resolve_forecasts.py) could not read the insider desk's prose question
          "Absolute <T> <N>-session move from ... exceeds <X>% on <D>", so rows sat due-and-blank behind "SKIP (unparsed)".
  check_ins025_prose_rows_resolved        no prose-form row is unresolved past its check date plus one settled session; every
                                          due-but-blank prose row is NAMED with the stall the latest resolver run printed for it
  check_ins025_resolver_reads_prose_form  the resolver carries the prose parse, scoped to the insider ledger, and the parse reads
                                          every prose-looking row in the ledger (a new variant fails here, not silently later)
  check_ins025_tests_green                the INS-025 offline suite is green
INS-026 - fill_queued() recorded a mid-session first print as the "official open"; price_audit.py tests the settled open.
  check_ins026_every_ref_mismatch_disclosed  every REF_MISMATCH the audit reports carries a matching [REF-GAP INS-026] note on its own
                                             row (the audit's `disclosed` tag) - an UNDISCLOSED mismatch fails; zero mismatches
                                             (after a restate ruling) also passes. It does not require the audit to exit 0.
  check_ins026_writer_fix_holds              the writer's fix, run for real on a scratch ledger: an in-session bar is NOT filled, the
                                             settled open is, and with no calendar NOTHING is filled (fail closed); and the INS-026
                                             offline suite is green
"""
import os as _ins025_os
import re as _ins025_re

_ins025_HOME = _ins025_os.path.expanduser("~")
_ins025_FORECASTS = f"{_ins025_HOME}/insider-radar/agent/forecasts.csv"
_ins025_RESOLVER = f"{_ins025_HOME}/bin/resolve_forecasts.py"
_ins025_SESSIONS = f"{_ins025_HOME}/stock-radar/sessions.py"
_ins025_LOG = f"{_ins025_HOME}/bin/logs/grade-all-due.log"
_ins025_TESTS = f"{_ins025_HOME}/insider-radar/tests/test_ins025_prose_forecast.py"
_ins025_LEDGER_REL = "insider-radar/agent/forecasts.csv"


def _ins025_sessions():
    import importlib.util as iu
    sp = iu.spec_from_file_location("_ins025_sess", _ins025_SESSIONS)
    m = iu.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _ins025_parser_pattern():
    """The resolver's OWN prose pattern, read out of its source (never re-typed here), or None."""
    import ast
    try:
        tree = ast.parse(open(_ins025_RESOLVER).read())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "P" and isinstance(node.value, ast.Call) and node.value.args):
            try:
                return _ins025_re.compile(ast.literal_eval(node.value.args[0]), _ins025_re.I)
            except (ValueError, _ins025_re.error):
                return None
    return None


def _ins025_stalls_in_latest_run():
    """{instrument: the stall line} for the insider ledger in the NEWEST resolve_forecasts block of the grader log."""
    try:
        lines = open(_ins025_LOG, errors="ignore").read().splitlines()
    except OSError:
        return None, {}
    ends = [i for i, l in enumerate(lines) if _ins025_re.match(r"resolve_forecasts \d{4}-\d{2}-\d{2}:", l)]
    if not ends:
        return None, {}
    end = ends[-1]
    start = max((i for i in range(end) if lines[i].strip() == _ins025_LEDGER_REL), default=None)
    run_date = lines[end].split()[1].rstrip(":")
    stalls = {}
    if start is not None and (len(ends) < 2 or start > ends[-2]):
        for l in lines[start + 1:end]:
            if not l.startswith("  "):
                break
            m = _ins025_re.match(r"\s+SKIP \(([^)]*)\): (\S+) — (.*)", l)
            if m:
                stalls[m.group(2)] = f"SKIP ({m.group(1)}): {m.group(3).strip()}"
    return run_date, stalls


def check_ins025_prose_rows_resolved():
    """INS-025. No prose-form insider forecast sits unresolved past its check date plus one settled session. A row due but
    still inside that one-session grace is named with the stall the latest resolver run printed for it; one past it FAILS."""
    import csv
    import datetime as dt
    pat = _ins025_parser_pattern()
    prose_like = _ins025_re.compile(r"^\s*absolute\s", _ins025_re.I)
    try:
        S = _ins025_sessions()
        settled = S.settled_session()
    except Exception as e:
        return False, f"sessions calendar unavailable ({type(e).__name__}) - cannot decide what is due"
    if not _ins025_os.path.exists(_ins025_FORECASTS):
        return False, "insider-radar/agent/forecasts.csv missing"
    run_date, stalls = _ins025_stalls_in_latest_run()
    total = resolved = future = 0
    grace, overdue, unreadable = [], [], []
    for r in csv.DictReader(open(_ins025_FORECASTS)):
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
            overdue.append(f"{ins} (unparseable check_date {r.get('check_date')!r})")
            continue
        cd_eff = cd if S.is_session(cd) else S.next_session(cd)
        if cd_eff > settled:
            future += 1
            continue
        stall = stalls.get(ins) or (f"no stall line in the {run_date} run" if run_date else "no resolver run found in the log")
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


def check_ins025_resolver_reads_prose_form():
    """INS-025. The estate resolver carries the prose parse, scoped to the insider ledger, and its pattern reads every
    prose-looking question in the ledger (so a NEW variant fails here the day it is filed, not when it comes due)."""
    import csv
    if not _ins025_os.path.exists(_ins025_RESOLVER):
        return False, "~/bin/resolve_forecasts.py missing"
    src = open(_ins025_RESOLVER).read()
    pat = _ins025_parser_pattern()
    if pat is None:
        return False, "resolve_forecasts.py has no prose pattern P - the INS-025 parse is absent (rows will SKIP (unparsed))"
    import ast
    tree = ast.parse(src)
    scope = [ast.get_source_segment(src, n) for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "PROSE_LEDGERS" for t in n.targets)]
    if not scope or "insider-radar/agent/forecasts.csv" not in scope[0] or scope[0].count("forecasts.csv") != 1:
        return False, "resolve_forecasts.py does not scope the prose parse to the insider ledger alone (PROSE_LEDGERS)"
    if not _ins025_re.search(r"^\s*elif\s+mp\s*:", src, _ins025_re.M):
        return False, "resolve_forecasts.py defines the prose pattern but has no branch that scores it"
    bad = [f"{r.get('instrument')} {r.get('date')}" for r in csv.DictReader(open(_ins025_FORECASTS))
           if _ins025_re.match(r"^\s*absolute\s", (r.get("question") or "").replace("radar.json ", ""), _ins025_re.I)
           and not pat.search((r.get("question") or "").replace("radar.json ", ""))]
    if bad:
        return False, f"{len(bad)} prose-looking row(s) the resolver's pattern cannot read: {', '.join(bad[:6])}"
    return True, "resolve_forecasts.py scores the prose form (insider ledger only) and its pattern reads every prose-looking row filed"


def check_ins025_tests_green():
    """INS-025. The offline suite (formula, strictness, guards, scope, old-vs-new replay) is green."""
    import subprocess
    if not _ins025_os.path.exists(_ins025_TESTS):
        return False, "insider-radar/tests/test_ins025_prose_forecast.py missing"
    try:
        r = subprocess.run(["/opt/anaconda3/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", _ins025_TESTS],
                           capture_output=True, text=True, timeout=600)
    except Exception as e:
        return False, f"could not run the INS-025 suite: {type(e).__name__}: {e}"
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return (r.returncode == 0), (f"INS-025 suite {'green' if r.returncode == 0 else 'RED (rc %d)' % r.returncode}: {tail}")


# ---------------------------------------------------------------- INS-026
import os as _ins026_os   # noqa: E402

_ins026_ROOT = f"{_ins026_os.path.expanduser('~')}/insider-radar"
_ins026_AUDIT = f"{_ins026_ROOT}/price_audit.py"
_ins026_QUOTE = f"{_ins026_ROOT}/agent/stale_quote.py"
_ins026_TESTS = f"{_ins026_ROOT}/tests/test_ins026_settled_fill.py"


def check_ins026_every_ref_mismatch_disclosed():
    """INS-026. price_audit.py (read-only, run on its own bar cache) reports no UNDISCLOSED REF_MISMATCH: every open row whose recorded
    price differs from the owed reference carries, on its own row, a [REF-GAP INS-026] note that matches the gap exactly - the audit
    marks that with `disclosed: true` on the record (and prints "disclosed (INS-026), awaiting ruling"). The audit still FAILS those
    rows (no waiver exists: that is a ruling); this check asks only that no mismatch is silent. Fails loud if the audit cannot be
    read or is the pre-INS-026 audit (no `disclosed` marker) - it cannot then tell a disclosed gap from a silent one."""
    import json
    import subprocess
    if not _ins026_os.path.exists(_ins026_AUDIT):
        return False, "insider-radar/price_audit.py missing"
    try:
        r = subprocess.run(["/opt/anaconda3/bin/python", _ins026_AUDIT, "--open-only", "--json"],
                           capture_output=True, text=True, timeout=300)
        b = json.loads(r.stdout)
    except Exception as e:
        return False, f"price_audit.py --open-only --json could not be read ({type(e).__name__}) - cannot say the gaps are disclosed"
    mism = b.get("REF_MISMATCH", [])
    if any("disclosed" not in x for x in mism):
        return False, ("price_audit.py predates INS-026 (its REF_MISMATCH records carry no `disclosed` marker): "
                       f"{[(x['ticker'], x['date'], x['price_at_call'], x.get('owed')) for x in mism]}")
    silent = [x for x in mism if not x["disclosed"]]
    if silent:
        return False, ("UNDISCLOSED REF_MISMATCH: " + ", ".join(
            f"{x['ticker']} {x['date']} recorded {x['price_at_call']} vs owed {x.get('owed')} ({x.get('owed_day')})" for x in silent))
    return True, (f"REF_MISMATCH {len(mism)}, every one disclosed on its own row"
                  + (": " + ", ".join(f"{x['ticker']} {x['date']} {x['price_at_call']} vs {x['owed']}" for x in mism) +
                     " (the audit still exits 1 until a ruling: restate, or waive)" if mism else "")
                  + f"; REF_OK {len(b.get('REF_OK', []))}")


def check_ins026_writer_fix_holds():
    """INS-026. The writer's fix, exercised for real on a scratch ledger (no network, nothing shared is written): a fill session
    that has NOT settled is not filled - the in-session first print is never recorded as the official open - once it has settled
    the row is filled at the settled bar's open, and with no calendar the writer fills NOTHING and returns non-zero (fail closed).
    Then the INS-026 offline suite must be green."""
    import contextlib
    import csv
    import datetime as dt
    import importlib.util as iu
    import io
    import subprocess
    import tempfile
    import zoneinfo
    if not _ins026_os.path.exists(_ins026_QUOTE):
        return False, "insider-radar/agent/stale_quote.py missing"
    try:
        sp = iu.spec_from_file_location("_ins026_q", _ins026_QUOTE)
        q = iu.module_from_spec(sp)
        sp.loader.exec_module(q)
        pt = zoneinfo.ZoneInfo("America/Los_Angeles")
        head = ["date", "ticker", "call", "thesis", "price_at_call", "check_date", "price_at_check", "outcome",
                "stale_quote", "tags", "void_reason"]
        row = {"date": "2026-09-28", "ticker": "SYN", "call": "long", "check_date": "2026-10-28", "stale_quote": "no",
               "tags": "fund", "thesis": "[insider] 2 insiders bought $0.18M within 14d [QUEUED at 2026-09-28T08:35 PT "
                                         "(INS-020/REG-PP-002): fixture]"}
        forming = {"2026-09-29": (5.83, 6.0, 5.4, 5.6, 1_000_000)}                   # the first print as the open
        settled = {"2026-09-29": (5.84, 6.0, 5.4, 5.6, 1_000_000), "2026-09-30": (5.60, 5.7, 5.5, 5.6, 900_000)}
        with tempfile.TemporaryDirectory() as td:
            led = f"{td}/ledger.csv"
            with open(led, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=head)
                w.writeheader()
                w.writerow({k: row.get(k, "") for k in head})
            price = lambda: list(csv.DictReader(open(led)))[0]["price_at_call"]
            sink = io.StringIO()
            with contextlib.redirect_stdout(sink):
                q.daily_bars = lambda tk, since: forming
                q.fill_queued(led, now=dt.datetime(2026, 9, 29, 8, 38, tzinfo=pt))
                in_session = price()
                q.daily_bars = lambda tk, since: settled
                q.fill_queued(led, now=dt.datetime(2026, 9, 30, 8, 35, tzinfo=pt))
                after_settle = price()
            led2 = f"{td}/ledger_nocal.csv"                                          # the same queued row, no calendar available
            with open(led2, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=head)
                w.writeheader()
                w.writerow({k: row.get(k, "") for k in head})
            real_sess = q._SESS
            q._SESS = None
            try:
                with contextlib.redirect_stdout(sink):
                    rc_nocal = q.fill_queued(led2, now=dt.datetime(2026, 9, 30, 14, 0, tzinfo=pt))
            finally:
                q._SESS = real_sess
            nocal_price = list(csv.DictReader(open(led2)))[0]["price_at_call"]
    except Exception as e:
        return False, f"could not exercise fill_queued ({type(e).__name__}: {e})"
    if in_session != "":
        return False, (f"fill_queued FILLED a row from a session still trading (recorded {in_session!r}, the in-session first "
                       "print) - the INS-026 defect is live")
    if after_settle != "5.84":
        return False, f"fill_queued did not fill the SETTLED open once the session settled (got {after_settle!r}, want '5.84')"
    if nocal_price != "" or not rc_nocal:
        return False, (f"fill_queued does not fail CLOSED with no calendar (price {nocal_price!r}, returned {rc_nocal!r}): it must "
                       "fill nothing and return non-zero")
    if not _ins026_os.path.exists(_ins026_TESTS):
        return False, "insider-radar/tests/test_ins026_settled_fill.py missing"
    try:
        r = subprocess.run(["/opt/anaconda3/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", _ins026_TESTS],
                           capture_output=True, text=True, timeout=300)
    except Exception as e:
        return False, f"could not run the INS-026 suite: {type(e).__name__}: {e}"
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        return False, f"INS-026 suite RED (rc {r.returncode}): {tail}"
    return True, f"in-session bar not filled; settled open filled (5.84); no calendar -> nothing filled; INS-026 suite green: {tail}"


def _ins026_main():
    for fn in (check_ins025_prose_rows_resolved, check_ins025_resolver_reads_prose_form, check_ins025_tests_green,
               check_ins026_every_ref_mismatch_disclosed, check_ins026_writer_fix_holds):
        ok, msg = fn()
        print(("PASS" if ok else "FAIL"), fn.__name__, "-", msg)


if __name__ == "__main__":
    _ins026_main()

"""REGISTRY Clause B (pre-registered 2026-09-04) - applied 2026-10-17 to insider-radar's forecast book. Offline; every write goes to a tmp book.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_clause_b.py

Clause B: at n=40 resolved, if skill <= 0 (Clause A having passed), the discretionary p is retired and every later
row is filed at the running climatological base rate. No third branch, no extension. It tripped on 2026-10-05 and was
found, unapplied, by the 2026-10-17 lab audit.

Numbered:
 1 once the flag is set, the writer files p at the running base rate (YES share of resolved rows) and ignores the caller's p
 2 the retired discretionary p is named in `notes`, with a parseable stamp  base= k= n=
 3 a caller that omits p entirely still gets a row (the AGENT.md instruction is "p is the writer's")
 4 no flag, no override: a book without clause_b.json files the caller's p untouched (the clause is gated on the verdict)
 5 rows already filed are not altered by a Clause B append (BENCH-002)
 6 the base rate is score_forecasts.py's climatology: void rows and unresolved rows out; yes/no/true/false accepted
 7 an all-NO / all-YES / empty book refuses loudly (a p of 0 or 1 is never invented)
 8 a broken flag file refuses loudly instead of silently filing a discretionary p
 9 the flag the repo ships matches the real book: n=40 was reached on 2026-10-05 at skill -0.055 with sd(p) 0.106 >= 0.05
10 the resolver-style check: passes on a correctly filed row; fails on a discretionary row, on a missing REGISTRY entry and
   on a forged stamp; tolerates the base drifting after the row was filed; and the writer's real output passes it
11 REGISTRY.md carries the verdict entry and the Clause B text it applies is unchanged
"""
import csv
import importlib.util
import json
import os
import re
import shutil
import statistics
import sys

import pytest

HOME = os.path.expanduser("~")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "agent"))
sys.path.insert(0, REPO)
import forecast_write as FW  # noqa: E402

COLS = ["date", "instrument", "horizon_days", "question", "p", "check_date", "outcome", "notes"]
FLAG = {"clause": "test", "tripped_at_n": 40, "tripped_on": "2026-10-05", "skill_at_trip": -0.055}
NEW = {"date": "2026-10-19", "instrument": "TSM", "horizon_days": "5",
       "question": "TSM closes higher on 2026-10-26 than its settled 2026-10-16 close 100.0",
       "p": "0.47", "notes": "[insider] discretionary"}


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# INS-034 (insider-radar ef671e60, 2026-10-17): PROPOSED_resolver_check_clause_b.py, the file this test was written against, moved
# into the firm's resolver as check_ins_clause_b_applied 32 minutes after this test was committed, and the old path made the
# whole file fail to collect (AUDIT_2026-10-26_repos 4a). The check is loaded from where it lives now. The resolver exists only on
# the estate's Mac; anywhere else the six check tests skip and the rest still run.
RESOLVER = os.path.join(HOME, "command-center", "council", "resolver.py")
CHECK = _mod("clause_b_check", RESOLVER) if os.path.exists(RESOLVER) else None
needs_check = pytest.mark.skipif(CHECK is None, reason="needs command-center/council/resolver.py (INS-034 moved the check there)")


def _book(dirpath, outcomes, cols=COLS, extra=None, flag=True):
    """A tmp forecasts.csv: `outcomes` is a list of '1' / '0' / '' (unresolved) / other spellings."""
    os.makedirs(dirpath, exist_ok=True)
    path = os.path.join(dirpath, "forecasts.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, o in enumerate(outcomes):
            r = {"date": f"2026-09-{(i % 20) + 1:02d}", "instrument": f"T{i}", "horizon_days": "5",
                 "question": f"T{i} closes higher on 2026-10-05", "p": "0.5", "check_date": "2026-10-05",
                 "outcome": o, "notes": f"row {i}"}
            r.update((extra or {}).get(i, {}))
            w.writerow({k: r.get(k, "") for k in cols})
    if flag:
        json.dump(FLAG, open(os.path.join(dirpath, "clause_b.json"), "w"))
    return path


def _rows(path):
    return list(csv.DictReader(open(path)))


# 1, 2 ------------------------------------------------------------------------------------------------------------
def test_flag_set_files_p_at_the_running_base_rate_and_names_the_retired_p(tmp_path):
    path = _book(str(tmp_path), ["1", "1", "1", "0", "0", "0", "0", "0", "0", "0", ""])   # 3 / 10 resolved
    FW.append_forecast(dict(NEW), path)
    last = _rows(path)[-1]
    assert float(last["p"]) == pytest.approx(0.3)          # not the caller's 0.47
    assert last["outcome"] == ""                            # a forecast is never born scored
    assert last["check_date"] == "2026-10-26"               # INS-019 still governs
    n = last["notes"]
    assert n.startswith("[insider] discretionary")          # the caller's own note is kept
    assert "[CLAUSE-B" in n and "discretionary p (0.47) is retired" in n
    assert re.search(r"base=0\.3000 k=3 n=10", n)           # the stamp the resolver check parses
    assert "tripped at n=40 on 2026-10-05" in n and "-0.0550" in n


def test_base_rate_is_rounded_to_four_places(tmp_path):
    path = _book(str(tmp_path), ["1"] * 12 + ["0"] * 35)    # 12 / 47, the live book's figure on 2026-10-17
    FW.append_forecast(dict(NEW), path)
    assert _rows(path)[-1]["p"] == "0.2553"


# 3 ---------------------------------------------------------------------------------------------------------------
def test_a_caller_may_omit_p(tmp_path):
    path = _book(str(tmp_path), ["1", "0", "0", "0"])
    r = dict(NEW)
    del r["p"]
    FW.append_forecast(r, path)
    last = _rows(path)[-1]
    assert float(last["p"]) == pytest.approx(0.25) and "none supplied" in last["notes"]


# 4 ---------------------------------------------------------------------------------------------------------------
def test_without_the_flag_the_callers_p_is_untouched(tmp_path):
    path = _book(str(tmp_path), ["1", "0", "0", "0"], flag=False)
    FW.append_forecast(dict(NEW), path)
    last = _rows(path)[-1]
    assert last["p"] == "0.47" and "CLAUSE-B" not in last["notes"]


# 5 ---------------------------------------------------------------------------------------------------------------
def test_filed_rows_are_not_altered(tmp_path):
    path = _book(str(tmp_path), ["1", "0", "0", "1", ""],
                 extra={4: {"p": "0.57", "notes": "[insider] discretionary, filed before the verdict was applied"}})
    before = _rows(path)
    FW.append_forecast(dict(NEW), path)
    after = _rows(path)
    assert after[:-1] == before and len(after) == len(before) + 1
    assert after[4]["p"] == "0.57" and after[4]["outcome"] == ""    # the open discretionary row stands as filed


# 6 ---------------------------------------------------------------------------------------------------------------
def test_running_base_rate_filters_match_the_scorer(tmp_path):
    cols = COLS + ["void"]
    path = _book(str(tmp_path), ["1", "0", "yes", "no", "TRUE", "false", "", "1", "0"], cols=cols,
                 extra={7: {"void": "bad bar"}, 8: {"p": "1.7"}})          # a voided YES and an out-of-range p are out
    k, n = FW.running_base_rate(_rows(path))
    assert (k, n) == (3, 6)                                                 # 1, yes, TRUE are YES; 0, no, false are NO
    scorer = os.path.join(HOME, "bin", "score_forecasts.py")
    if not os.path.exists(scorer):
        pytest.skip("score_forecasts.py not present")
    S = _mod("score_forecasts_for_clause_b", scorer)
    rows = S._read(path, None)
    assert len(rows) == n and S.murphy(rows, 5)["base"] == pytest.approx(k / n)


def test_running_base_rate_matches_the_scorer_on_the_real_book():
    scorer = os.path.join(HOME, "bin", "score_forecasts.py")
    if not os.path.exists(scorer):
        pytest.skip("score_forecasts.py not present")
    S = _mod("score_forecasts_for_clause_b_real", scorer)
    real = os.path.join(REPO, "agent", "forecasts.csv")
    k, n = FW.running_base_rate(_rows(real))
    rows = S._read(real, None)
    assert n == len(rows) and k == sum(o for _, o, _ in rows)


# 7, 8 ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("outcomes", [[], [""], ["0"] * 8, ["1"] * 8])
def test_degenerate_base_rate_refuses_and_writes_nothing(tmp_path, outcomes):
    path = _book(str(tmp_path), outcomes)
    before = open(path).read()
    with pytest.raises(ValueError, match="CLAUSE-B"):
        FW.append_forecast(dict(NEW), path)
    assert open(path).read() == before


def test_broken_flag_refuses_instead_of_filing_a_discretionary_p(tmp_path):
    path = _book(str(tmp_path), ["1", "0", "0", "0"], flag=False)
    for bad in ("{not json", json.dumps({"tripped_at_n": 40})):
        open(os.path.join(str(tmp_path), "clause_b.json"), "w").write(bad)
        before = open(path).read()
        with pytest.raises(ValueError, match="CLAUSE-B"):
            FW.append_forecast(dict(NEW), path)
        assert open(path).read() == before


# 9 ---------------------------------------------------------------------------------------------------------------
def test_the_shipped_flag_matches_the_real_book():
    flag = json.load(open(os.path.join(REPO, "agent", "clause_b.json")))
    assert flag["tripped_at_n"] == 40 and flag["tripped_on"] == "2026-10-05" and flag["skill_at_trip"] == -0.055
    rows = _rows(os.path.join(REPO, "agent", "forecasts.csv"))
    dated = []
    for i, r in enumerate(rows):
        if (r["outcome"] or "").strip() in ("0", "1"):
            stamp = re.findall(r"RESOLVED\s+(\d{4}-\d{2}-\d{2})", r["notes"])
            dated.append((stamp[-1] if stamp else r["check_date"], i, r))
    at_trip = [r for d, _, r in sorted(dated, key=lambda t: (t[0], t[1])) if d <= flag["tripped_on"]]
    assert len(at_trip) == 40                                   # the 40th resolved row landed on the trip date, not later
    base = sum(int(r["outcome"]) for r in at_trip) / 40
    bs = sum((float(r["p"]) - int(r["outcome"])) ** 2 for r in at_trip) / 40
    bs_clim = sum((base - int(r["outcome"])) ** 2 for r in at_trip) / 40
    assert round(1 - bs / bs_clim, 3) == -0.055                 # skill <= 0: Clause B
    sd = statistics.stdev(float(r["p"]) for r in at_trip)
    assert sd >= 0.05 and round(sd, 3) == 0.106                 # Clause A passed (it is the precondition)


# 10 --------------------------------------------------------------------------------------------------------------
def _root(tmp_path, outcomes, last_note, last_p, registry="Clause B tripped at n=40 on 2026-10-05"):
    agent = os.path.join(str(tmp_path), "agent")
    path = _book(agent, outcomes + [""], extra={len(outcomes): {"p": str(last_p), "notes": last_note}}, flag=False)
    open(os.path.join(str(tmp_path), "REGISTRY.md"), "w").write("### Clause B\n" + registry + "\n")
    return str(tmp_path), path


@needs_check
def test_check_passes_on_a_row_filed_at_the_base_rate(tmp_path):
    root, _ = _root(tmp_path, ["1", "0", "0", "0"], "[CLAUSE-B: ... base=0.2500 k=1 n=4 (YES share of resolved rows)]", 0.25)
    ok, msg = CHECK.check_ins_clause_b_applied(root)
    assert ok, msg


@needs_check
def test_check_fails_on_a_discretionary_row(tmp_path):
    root, _ = _root(tmp_path, ["1", "0", "0", "0"], "[insider] p_cal=0.47", 0.47)
    ok, msg = CHECK.check_ins_clause_b_applied(root)
    assert not ok and "not the base rate" in msg


@needs_check
def test_check_fails_without_the_registry_entry(tmp_path):
    root, _ = _root(tmp_path, ["1", "0", "0", "0"], "[CLAUSE-B: ... base=0.2500 k=1 n=4 ...]", 0.25, registry="nothing here")
    ok, msg = CHECK.check_ins_clause_b_applied(root)
    assert not ok and "REGISTRY.md lacks" in msg


@needs_check
def test_check_fails_on_a_forged_stamp(tmp_path):
    root, _ = _root(tmp_path, ["1", "0", "0", "0"], "[CLAUSE-B: ... base=0.4700 k=47 n=100 ...]", 0.47)
    ok, msg = CHECK.check_ins_clause_b_applied(root)
    assert not ok and "far from today's running base" in msg


@needs_check
def test_check_tolerates_the_base_drifting_after_filing(tmp_path):
    # filed at 12/47 = 0.2553; two NOs have since resolved, so the base is now 12/49 = 0.2449 - still the stamped row
    root, _ = _root(tmp_path, ["1"] * 12 + ["0"] * 37, "[CLAUSE-B: ... base=0.2553 k=12 n=47 ...]", 0.2553)
    ok, msg = CHECK.check_ins_clause_b_applied(root)
    assert ok, msg


@needs_check
def test_the_writers_own_output_passes_the_check(tmp_path):
    root = str(tmp_path)
    path = _book(os.path.join(root, "agent"), ["1"] * 12 + ["0"] * 35)
    open(os.path.join(root, "REGISTRY.md"), "w").write("Clause B tripped at n=40 on 2026-10-05\n")
    FW.append_forecast(dict(NEW), path)
    ok, msg = CHECK.check_ins_clause_b_applied(root)
    assert ok, msg


# 11 --------------------------------------------------------------------------------------------------------------
def test_registry_carries_the_verdict_and_the_clause_is_unchanged():
    reg = open(os.path.join(REPO, "REGISTRY.md")).read()
    assert "Clause B tripped at n=40 on 2026-10-05, skill −0.055; applied 2026-10-17" in reg
    # the pre-registered text is untouched: the verdict was appended under it, nothing above it was edited
    assert "### Clause B — the verdict (evaluated at n=40, **only if Clause A passes**)" in reg
    assert "all subsequent rows are filed at the running climatological base rate" in reg
    assert "No third branch, no extension, and no re-derivation of these thresholds after the number is visible." in reg

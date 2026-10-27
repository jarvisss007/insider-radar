"""INS-036 (fix pass 2026-10-26; AUDIT_2026-10-26_repos 4b): ~/bin/grade_all_due.py crashed with float('') on a due insider row that
has NO ENTRY PRICE - a [QUEUED] call whose official open was never recorded. 11 such rows fall due 2026-11-23 and 3 on 2026-11-25.
The grader now skips each one with a loud "NO ENTRY PRICE: not gradable" line, fetches nothing for it, writes no outcome, and grades
every other due row as before. Offline; every write goes to a tmp ledger.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins036_no_entry_price.py
"""
import datetime as dt
import importlib.util
import os

import pytest

GRADER = "/Users/anupampatil/bin/grade_all_due.py"
pytestmark = pytest.mark.skipif(not os.path.exists(GRADER), reason="needs the estate's ~/bin/grade_all_due.py")

HERE = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location("_ins018_harness", os.path.join(HERE, "test_ins018_grader.py"))
H = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(H)                      # the INS-018 harness: FixtureFetch, _ledger, _row, _run, the loaded grader G


class CountingFetch(H.FixtureFetch):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.asked = []

    def bars(self, tk, start, end, d0=None):
        self.asked.append(tk)
        return super().bars(tk, start, end, d0)


def _bars(*days_closes):
    return [H._b(d, c) for d, c in days_closes]


def test_a_queued_row_without_an_entry_is_skipped_loudly_and_the_rest_grade(tmp_path):
    tmp = str(tmp_path)
    q = H._row("BORR", "2026-10-23", "2026-11-23", "", thesis="[insider] fixture [QUEUED] [QUEUED at 2026-10-23T08:39 PT (REG-PP-002)]")
    ok = H._row("AAA", "2026-10-23", "2026-11-23", "10.00")
    p = H._ledger(tmp, [q, ok])
    before = open(p, newline="").read()
    fx = CountingFetch(bars={"AAA": _bars(("2026-11-20", 10.5), ("2026-11-23", 11.0))})
    n, lines = H._run(p, fx, "2026-11-23", "2026-11-23", home=tmp)
    assert n == 1                                                    # AAA graded, the run did not crash
    assert any("BORR due 2026-11-23" in l and "NO ENTRY PRICE: not gradable" in l and l.lstrip().startswith("!!") for l in lines), lines
    assert "BORR" not in fx.asked                                    # nothing fetched for it
    rows = {r["ticker"]: r for r in H._read(p)}
    assert rows["BORR"]["outcome"] == "" and rows["BORR"]["price_at_check"] == "" and rows["BORR"]["price_at_call"] == ""
    assert rows["BORR"]["thesis"] == q["thesis"]                     # no stamp, no write on the row
    assert rows["AAA"]["outcome"] == "right"
    assert before.splitlines()[1] == open(p, newline="").read().splitlines()[1]   # BORR's line byte-identical


def test_decide_insider_itself_refuses_a_row_with_no_entry():
    # even on the paths that grade without a price (unfetchable / delisted), a never-entered row is not graded `wrong`
    row = H._row("ZZZZ", "2026-10-23", "2026-11-23", "")
    dec = H.G.decide_insider(row=row, cd=dt.date(2026, 11, 23), settled=dt.date(2026, 11, 23), today=dt.date(2026, 11, 23),
                             fetch_error=None, probe=("no_series", "fixture 404"), spy=(True, "SPY ok"), bars=[], splits=[],
                             delisting=lambda: {"status": "effective", "form": "25", "accession": "x", "cik": "1", "filed": "2026-11-01",
                                                "effective": "2026-11-11"})
    assert dec == {"kind": "stall", "reason": H.G.NO_ENTRY_PRICE}


def test_a_dry_run_writes_nothing_and_still_names_the_row(tmp_path):
    tmp = str(tmp_path)
    p = H._ledger(tmp, [H._row("CTY", "2026-10-23", "2026-11-23", "")])
    before = open(p, newline="").read()
    n, lines = H._run(p, H.FixtureFetch(), "2026-11-23", "2026-11-23", dry=True, home=tmp)
    assert n == 0 and open(p, newline="").read() == before
    assert any("NO ENTRY PRICE" in l for l in lines) and any("1 DUE BUT UNPRICEABLE" in l for l in lines)

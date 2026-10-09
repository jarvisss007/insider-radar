"""FCST-011 - an EQUITY / ETF whose tape is dead (all-zero volume in the window) cannot resolve a forecast. Offline; no network.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_fcst011_equity_dead_tape.py

The defect (council/issues.json FCST-011, found by the 2026-10-02 audit): FCST-007's refusal in ~/bin/resolve_forecasts.py::_carry_forward
fired only when the 10-day window's volume SUM was above zero, so a name whose whole window is zero (WBHC: volume 0, close 550.00 on all ten
bars to 2026-10-01 - a quote Yahoo carried, not a market) escaped it and resolved NO in a dry run, while grade_all_due._traded() refuses any
zero-volume bar. The fix: for an EQUITY or ETF - Yahoo's own instrumentType, read from the same chart payload as the bars
(yfinance Ticker.history_metadata) - zero volume on the resolution date is a carry-forward whatever the rest of the window did. Everything
else keeps the FCST-007 rule: FX, indices and futures carry no volume (INS-015's own tape test), and a tape whose type Yahoo did not supply
(None) is judged exactly as before.

 1 a dead EQUITY tape and a dead ETF tape are refused on the production path AND on the fallback, in the fallback's own wording; the
   pre-change resolver scored both (the defect, shown)
 2 CURRENCY / INDEX / FUTURE tapes with no volume at all resolve identically to the pre-change resolver (no signal to read)
 3 an equity that TRADED on the resolution date resolves identically, even when the window holds zero-volume days before it
 4 an equity with zero volume on d inside a window that trades (FCST-007's case) is refused by both versions, unchanged
 5 an instrumentType Yahoo did not supply (absent, or the lookup raises) falls back to the FCST-007 rule: identical to the pre-change resolver
 6 all three readers of the rule pass the type (production veto, fallback, NSE reader) - one definition, no second copy
 7 a seeded fuzz over equity-typed and non-equity-typed tapes: old and new differ ONLY on an equity/ETF row whose resolution-date bar is zero-volume
 8 BENCH-002: a row that already carries an outcome is never re-examined, even on a dead equity tape
"""
import ast
import os
import random
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_fcst007_production_zero_volume import (CF, RESOLVER, _b, _cf, _e, _home, _ledger_norm, _row, _rows, _run, norm_out, norm_row,  # noqa: E402
                                                 _week)

HOME = os.path.expanduser("~")
RESOLVER_OLD = os.environ.get("FCST011_RESOLVER_OLD", f"{HOME}/bin/resolve_forecasts_BACKUP_1008_FCST-011.py")
DAYS = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24",
        "2026-09-25", "2026-09-28"]


def dead(px=550.0, upto="2026-09-28"):
    """WBHC: every bar in the window is the same carried quote with volume 0."""
    return [[d, px, px, px, px, 0.0] for d in DAYS if d <= upto]


def both(tmp, rows, entries, production=True):
    ho, fo = _home(tmp / "old", {"insider-radar": rows}, entries, production)
    hn, fn = _home(tmp / "new", {"insider-radar": rows}, entries, production)
    return ho, hn, _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)


@pytest.mark.parametrize("production", [True, False], ids=["production-path", "fallback-path"])
def test_01_a_dead_equity_or_etf_tape_cannot_resolve(tmp_path, production):
    rows = [_row("WBHC", "WBHC closes above 100 on 2026-09-28"), _row("DEADETF", "Will DEADETF close at or above 100 on 2026-09-28?"),
            _row("LIVE", "LIVE closes above 100 on 2026-09-28")]
    ent = {"WBHC": _e(dead(), type="EQUITY"), "DEADETF": _e(dead(), type="ETF"), "LIVE": _e(_week(last=105.0), type="EQUITY")}
    ho, hn, oo, no = both(tmp_path, rows, ent, production)
    old, new = _rows(ho), _rows(hn)
    for tk in ("WBHC", "DEADETF"):
        assert old[tk]["outcome"] in ("0", "1"), f"{tk}: the pre-change resolver should have scored the dead tape - that is the defect\n{oo}"
        assert new[tk]["outcome"] == "" and new[tk]["notes"] == "[insider] fixture", f"{tk}: a dead equity tape must not resolve\n{no}"
        line = [l for l in no.splitlines() if l.startswith(f"  SKIP (no close): {tk} —")]
        assert len(line) == 1 and f"the 2026-09-28 bar is a {CF}" in line[0], (tk, line, no)
    assert new["LIVE"]["outcome"] == "1" and norm_row(old["LIVE"]) == norm_row(new["LIVE"])     # a name that traded is untouched


@pytest.mark.parametrize("typ", ["CURRENCY", "INDEX", "FUTURE", "CRYPTOCURRENCY"])
def test_02_a_non_equity_tape_with_no_volume_resolves_as_before(tmp_path, typ):
    rows = [_row("EURUSD=X", "closes above 100 on 2026-09-28")]
    ho, hn, oo, no = both(tmp_path, rows, {"EURUSD=X": _e(dead(105.0), type=typ)})
    assert _rows(hn)["EURUSD=X"]["outcome"] == "1"
    assert _ledger_norm(ho) == _ledger_norm(hn) and norm_out(oo) == norm_out(no) and CF not in no


def test_03_an_equity_that_traded_on_d_resolves_identically(tmp_path):
    bars = [_cf(d, 100.0) if d < "2026-09-25" else _b(d, 100.0) for d in DAYS]     # zero-volume days EARLY in the window, a real print on d
    bars[-1] = _b("2026-09-28", 105.0)
    rows = [_row("TRDD", "TRDD closes above 100 on 2026-09-28")]
    ho, hn, oo, no = both(tmp_path, rows, {"TRDD": _e(bars, type="EQUITY")})
    assert _rows(hn)["TRDD"]["outcome"] == "1" and _ledger_norm(ho) == _ledger_norm(hn) and norm_out(oo) == norm_out(no)


def test_04_zero_volume_on_d_inside_a_trading_window_is_refused_by_both(tmp_path):
    rows = [_row("CFWIN", "CFWIN closes above 100 on 2026-09-28")]
    ho, hn, oo, no = both(tmp_path, rows, {"CFWIN": _e(_week(("2026-09-28",), last=105.0), type="EQUITY")})
    assert _rows(ho)["CFWIN"]["outcome"] == "" and _rows(hn)["CFWIN"]["outcome"] == ""      # FCST-007's case: refused before and after
    assert norm_out(oo) == norm_out(no) and f"the 2026-09-28 bar is a {CF}" in no


@pytest.mark.parametrize("typ", [None, "RAISE"], ids=["type-absent", "type-lookup-raises"])
def test_05_an_unreadable_type_keeps_the_fcst007_rule(tmp_path, typ):
    """KNOWN RESIDUAL, pinned: with no instrumentType the all-zero window is judged as FCST-007 judged it (resolves). Yahoo supplies the
    type in the same payload as the bars, so this is the library changing, not a normal day."""
    kw = {} if typ is None else {"type": typ}
    rows = [_row("UNK", "UNK closes above 100 on 2026-09-28")]
    ho, hn, oo, no = both(tmp_path, rows, {"UNK": _e(dead(), **kw)})
    assert _rows(hn)["UNK"]["outcome"] in ("0", "1") and _ledger_norm(ho) == _ledger_norm(hn) and norm_out(oo) == norm_out(no)


def test_06_every_reader_of_the_rule_passes_the_type():
    src = open(RESOLVER).read()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_carry_forward"]
    assert len(calls) == 3, "production veto, fallback and the NSE reader are the only callers of _carry_forward"
    for c in calls:
        assert len(c.args) == 3 and "_itype" in ast.dump(c.args[2]), ast.dump(c)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_carry_forward")
    assert [a.arg for a in fn.args.args] == ["h", "d", "itype"] and fn.args.defaults and isinstance(fn.args.defaults[0], ast.Constant) \
        and fn.args.defaults[0].value is None


def test_07_seeded_fuzz_only_equity_zero_volume_on_d_differs(tmp_path):
    rng = random.Random(20261008)
    types = ["EQUITY", "ETF", "INDEX", "CURRENCY", "FUTURE", None]
    rows, ent, expect_diff = [], {}, set()
    for i in range(48):
        tk, typ = f"F{i:02d}", rng.choice(types)
        vol = [rng.choice([0.0, 0.0, 500.0, 2000.0]) for _ in DAYS]
        if rng.random() < 0.3:
            vol = [0.0] * len(DAYS)                                   # a dead window
        bars = [[d, 100.0, 100.0, 100.0, 100.0 + (5.0 if d == "2026-09-28" else 0.0), v] for d, v in zip(DAYS, vol)]
        kw = {} if typ is None else {"type": typ}
        ent[tk] = _e(bars, **kw)
        rows.append(_row(tk, f"{tk} closes above 100 on 2026-09-28"))
        zero_d = vol[-1] == 0.0
        old_refuses = zero_d and sum(vol) > 0                         # FCST-007's rule, restated independently
        new_refuses = zero_d if typ in ("EQUITY", "ETF") else old_refuses
        if new_refuses != old_refuses:
            expect_diff.add(tk)
    ho, hn, oo, no = both(tmp_path, rows, ent)
    old, new = _rows(ho), _rows(hn)
    changed = {tk for tk in old if norm_row(old[tk]) != norm_row(new[tk])}
    assert changed == expect_diff and expect_diff, (sorted(changed ^ expect_diff), len(expect_diff))
    for tk in expect_diff:                                            # and every difference is old-resolved -> new-deferred, never the reverse
        assert old[tk]["outcome"] in ("0", "1") and new[tk]["outcome"] == ""


def test_08_a_scored_row_is_never_reexamined_even_on_a_dead_equity_tape(tmp_path):
    rows = [_row("DONE", "DONE closes above 100 on 2026-09-28", outcome="1", notes="[insider] RESOLVED 2026-09-29 earlier")]
    ho, hn, oo, no = both(tmp_path, rows, {"DONE": _e(dead(), type="EQUITY")})
    assert _rows(hn)["DONE"]["outcome"] == "1" and _rows(hn)["DONE"]["notes"] == "[insider] RESOLVED 2026-09-29 earlier"
    assert _ledger_norm(ho) == _ledger_norm(hn)

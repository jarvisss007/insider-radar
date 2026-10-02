"""FCST-007 - the forecast resolver's PRODUCTION price path refuses a zero-volume carry-forward bar. Offline; no network.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_fcst007_production_zero_volume.py

The defect (council/issues.json FCST-007, class (d)): ~/bin/resolve_forecasts.py has two price paths. INS-018 item C put the
zero-volume refusal in the yfinance FALLBACK only; the PRODUCTION path - stock-radar/options_settle.close_on - reads the close
alone, so a close Yahoo had carried forward (KDOZF 2026-09-25: a zero-volume bar, read as 0.10) could resolve a forecast.
INS-025's test 5 says so in its own docstring ("a separate, pre-existing gap"). The fix lives INSIDE resolve_forecasts.py
(options_settle.py is not edited): before any close resolves a forecast it asks the tape the fallback reads, with the same rule
and the same wording. These tests run the production path for real: the isolated HOME carries a stub options_settle.py that
behaves as the real one does (the close alone, no volume), so the OLD resolver demonstrably resolves the carry-forward rows
and the NEW one defers them.

Numbered:
 1 every question form (A, W, C, R both legs, P both spellings): a production close that sits on a zero-volume bar on a tape
   that trades elsewhere is refused - the row stays blank and says so; the OLD resolver scored it (the defect, shown)
 2 the stall wording is the fallback's own, character for character
 3 a tape with no volume at all (FX, indices) has no carry-forward signal: the production close stands, identical to old
 4 everything that is not a carry-forward resolves identically: old vs new, row by row and byte by byte, on a seeded fuzz
   (zero-volume / NaN / missing bars, five question forms) - the two differ ONLY on rows that read a carry-forward bar
 5 it fails CLOSED: if the volume cannot be checked (yfinance raises, or returns nothing) the production close does not resolve
   a forecast, and the row says why
 6 a tape that was read but has no bar dated d, or a bar with no close (the day's daily bar not posted yet; SETTLE-001's same-day
   quote), keeps the close - nothing printed is nothing to refuse
 7 india-radar's ".NS" rows never used the production path: identical to old
 8 a full re-open replay of the four REAL forecast ledgers on a pinned tape: only rows that read a carry-forward bar differ
 9 one rule, one definition: the production veto and the fallback both call _carry_forward (no second copy to drift)
10 BENCH-002: a row that already has an outcome is never re-examined, restated or annotated - even on a carry-forward bar
"""
import ast
import csv
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import zlib

import pytest

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVER = os.environ.get("FCST007_RESOLVER", f"{HOME}/bin/resolve_forecasts.py")
RESOLVER_OLD = os.environ.get("FCST007_RESOLVER_OLD", f"{HOME}/bin/resolve_forecasts_BACKUP_1001_FCST-007.py")
FAKE_YF = os.path.join(HERE, "fixtures", "fake_yf")
PY = "/opt/anaconda3/bin/python"
COLS = ["date", "instrument", "horizon_days", "question", "p", "check_date", "outcome", "notes"]

STUB_SESSIONS = '''
import datetime as dt
SETTLED = dt.date(2026, 9, 30)
HOLIDAYS = {dt.date(2026, 9, 7)}
def _d(x): return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])
def is_session(d): d = _d(d); return d.weekday() < 5 and d not in HOLIDAYS
def settled_session(now=None, cutoff=None): return SETTLED
def sessions_between(a, b):
    a, b = _d(a), _d(b); out = []; d = a + dt.timedelta(days=1)
    while d <= b:
        if is_session(d): out.append(d)
        d += dt.timedelta(days=1)
    return out
'''

# The PRODUCTION reader as it is today (stock-radar/options_settle.py): close_on returns the CLOSE ALONE - it has no volume - drops a
# bar whose close is null, and answers a request for the day itself from the quote when the daily bar has not posted (SETTLE-001).
STUB_SETTLE = '''
import json, os
class NotSettled(ValueError): pass
def close_on(tk, day):
    day = str(day)[:10]
    e = json.load(open(os.environ["FAKE_YF_FIXTURE"])).get(tk, {})
    if e.get("prod") == "RAISE":
        raise ConnectionError("fake production-reader failure")
    for b in e.get("prod_bars", e.get("bars")) or []:
        if b[0] == day and b[4] is not None:
            return float(b[4])
    q = e.get("quote")
    if q and q[0] == day:
        return float(q[1])
    return None
'''


def _b(d, c, v=1000.0):
    return [d, c, c, c, c, v]


def _cf(d, prev_close):
    """A carry-forward bar as Yahoo prints it on a name that did not trade: the last price, volume 0."""
    return [d, prev_close, prev_close, prev_close, prev_close, 0.0]


def _e(bars, **kw):
    return dict(bars=bars, splits=[], **kw)


def _home(tmp, ledgers, entries, production=True):
    """An isolated HOME: the stub calendar, (optionally) the stub production reader, the ledgers {lab: [row dicts]}, and the
    fake-yfinance tape {ticker: entry}."""
    h = str(tmp)
    os.makedirs(os.path.join(h, "stock-radar"), exist_ok=True)
    with open(os.path.join(h, "stock-radar", "sessions.py"), "w") as f:
        f.write(STUB_SESSIONS)
    if production:
        with open(os.path.join(h, "stock-radar", "options_settle.py"), "w") as f:
            f.write(STUB_SETTLE)
    for lab, rows in ledgers.items():
        p = os.path.join(h, lab, "agent", "forecasts.csv")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in COLS})
    fx = os.path.join(h, "yf.json")
    json.dump(entries, open(fx, "w"))
    return h, fx


def _run(script, home, fx, *args, pypath=None):
    env = dict(os.environ, HOME=home, FAKE_YF_FIXTURE=fx, PYTHONPATH=pypath or FAKE_YF)
    r = subprocess.run([PY, script, *args], capture_output=True, text=True, env=env, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def _rows(home, lab="insider-radar"):
    return {r["instrument"]: r for r in csv.DictReader(open(os.path.join(home, lab, "agent", "forecasts.csv")))}


def _ledger_bytes(home, lab="insider-radar"):
    return open(os.path.join(home, lab, "agent", "forecasts.csv"), "rb").read()


def _ledger_norm(home, lab="insider-radar"):
    """The ledger's bytes with the run date in each RESOLVED stamp masked (two runs a few seconds apart must compare equal)."""
    return re.sub(rb"RESOLVED \d{4}-\d{2}-\d{2}", b"RESOLVED D", _ledger_bytes(home, lab))


def _row(tk, q, cd="2026-09-28", **kw):
    r = {"date": "2026-09-21", "instrument": tk, "horizon_days": "5", "question": q, "p": "0.3", "check_date": cd,
         "notes": "[insider] fixture"}
    r.update(kw)
    return r


norm_out = lambda s: re.sub(r"resolve_forecasts \d{4}-\d{2}-\d{2}:", "R:", s)
norm_row = lambda r: dict(r, notes=re.sub(r"RESOLVED \d{4}-\d{2}-\d{2}", "RESOLVED D", r["notes"]))
CF = "zero-volume carry-forward"


def _week(zero_on=(), px=100.0, last=None):
    """09-14 .. 09-28 at `px` (every bar traded), the days in `zero_on` carry-forward bars (volume 0); `last` overrides the 09-28 close."""
    out, prev = [], px
    for d in ("2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18",
              "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28"):
        c = last if (d == "2026-09-28" and last is not None) else px
        out.append(_cf(d, prev) if d in zero_on else _b(d, c))
        prev = out[-1][4]
    return out


# ---------------------------------------------------------------- 1, 2: every form, both legs; the fallback's wording
FORMS = [  # (ticker, question, tape for the ticker, the date whose bar is the carry-forward)
    ("ZA", "ZA closes above 100 on 2026-09-28", _week(("2026-09-28",), last=105.0), "2026-09-28"),
    ("ZW", "Will ZW close at or below 101 on 2026-09-28?", _week(("2026-09-28",)), "2026-09-28"),
    ("ZC", "abs(ZC last on 2026-09-28 / 100 - 1) >= 0.10", _week(("2026-09-28",), last=111.0), "2026-09-28"),
    ("ZR1", "ZR1 closes higher on 2026-09-28 than it closes on 2026-09-21", _week(("2026-09-28",), last=101.0), "2026-09-28"),
    ("ZR2", "ZR2 closes higher on 2026-09-28 than it closes on 2026-09-21", _week(("2026-09-21",), last=101.0), "2026-09-21"),
    ("ZP1", "Absolute ZP1 5-session move from its 2026-09-21 close exceeds 10% on 2026-09-28", _week(("2026-09-28",), last=120.0), "2026-09-28"),
    ("ZP2", "Absolute ZP2 5-session move from its 2026-09-21 close exceeds 10% on 2026-09-28", _week(("2026-09-21",), last=120.0), "2026-09-21"),
    ("ZP3", "Absolute ZP3 5-session move from 100 exceeds 10% on 2026-09-28", _week(("2026-09-28",), last=120.0), "2026-09-28"),
    ("CT=F", "closes above 100 on 2026-09-28", _week(("2026-09-28",), last=105.0), "2026-09-28"),   # a thin FUTURES tape: '=' is not exempt
]
CONTROLS = [  # the same questions on tapes that traded: they must resolve, identically, in both versions
    ("CA", "CA closes above 100 on 2026-09-28", _week(last=105.0)),
    ("CW", "Will CW close at or below 101 on 2026-09-28?", _week()),
    ("CC", "abs(CC last on 2026-09-28 / 100 - 1) >= 0.10", _week(last=111.0)),
    ("CR", "CR closes higher on 2026-09-28 than it closes on 2026-09-21", _week(last=101.0)),
    ("CP", "Absolute CP 5-session move from its 2026-09-21 close exceeds 10% on 2026-09-28", _week(last=120.0)),
    ("CP3", "Absolute CP3 5-session move from 100 exceeds 10% on 2026-09-28", _week(last=120.0)),
]


def _forms_home(tmp, production=True):
    rows = [_row(t, q) for t, q, _tape, _d in FORMS] + [_row(t, q) for t, q, _tape in CONTROLS]
    ent = {t: _e(tape) for t, _q, tape, _d in FORMS}
    ent.update({t: _e(tape) for t, _q, tape in CONTROLS})
    return _home(tmp, {"insider-radar": rows}, ent, production)


def test_01_production_close_on_a_carry_forward_bar_is_refused_in_every_form(tmp_path):
    ho, fo = _forms_home(tmp_path / "old")
    hn, fn = _forms_home(tmp_path / "new")
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    old, new = _rows(ho), _rows(hn)
    for tk, _q, _tape, d in FORMS:
        assert old[tk]["outcome"] in ("0", "1"), f"{tk}: the OLD resolver should have scored it off the carried-forward close - that is the defect\n{oo}"
        assert new[tk]["outcome"] == "" and new[tk]["notes"] == "[insider] fixture", f"{tk}: the production close on a carry-forward bar must not resolve\n{no}"
        line = [l for l in no.splitlines() if l.startswith(f"  SKIP (no close): {tk} —")]
        assert len(line) == 1 and f"the {d} bar is a {CF}" in line[0], (tk, line, no)
        assert "(unparsed)" not in line[0]
    for tk, _q, _tape in CONTROLS:                                   # a name that traded: identical in every field
        assert old[tk]["outcome"] in ("0", "1") and norm_row(old[tk]) == norm_row(new[tk]), tk
    assert f"{len(FORMS)} left" in no and f"{len(CONTROLS)} scored" in no


def test_02_the_stall_wording_is_the_fallbacks_own(tmp_path):
    """The same carry-forward bar read (a) on the production path and (b) on the fallback (no options_settle.py in the HOME)
    gives the same stall line, character for character."""
    hp, fp = _forms_home(tmp_path / "prod", production=True)
    hf, ff = _forms_home(tmp_path / "fallback", production=False)
    op, of = _run(RESOLVER, hp, fp), _run(RESOLVER, hf, ff)
    skip = lambda s: sorted(l for l in s.splitlines() if l.startswith("  SKIP (no close)"))
    assert skip(op) == skip(of) and len(skip(op)) == len(FORMS)
    assert _ledger_norm(hp) == _ledger_norm(hf)                      # and the two paths now leave the very same ledger


# ---------------------------------------------------------------- 3: no carry-forward signal on a tape with no volume
def test_03_a_tape_with_no_volume_at_all_is_not_a_carry_forward(tmp_path):
    flat = lambda last: [_b(d, 100.0, 0.0) if d != "2026-09-28" else _b(d, last, 0.0)
                         for d in ("2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28")]
    rows = [_row("EURUSD=X", "closes above 100 on 2026-09-28"), _row("FXC", "abs(FXC last on 2026-09-28 / 100 - 1) >= 0.01")]
    ent = {"EURUSD=X": _e(flat(105.0)), "FXC": _e(flat(102.0))}
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows}, ent)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows}, ent)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    assert _rows(hn)["EURUSD=X"]["outcome"] == "1" and _rows(hn)["FXC"]["outcome"] == "1"
    assert _ledger_norm(ho) == _ledger_norm(hn)
    assert norm_out(oo) == norm_out(no) and CF not in no


# ---------------------------------------------------------------- 4: nothing else changes (seeded fuzz, independent oracle)
SESS = [d for d in (dt.date(2026, 8, 3) + dt.timedelta(days=i) for i in range(60)) if d.weekday() < 5 and d != dt.date(2026, 9, 7)]


def _oracle_carry_forward(tape, day):
    """The rule, re-stated independently of the resolver: the bar dated `day` exists with zero (or missing) volume while the tape
    shows volume somewhere in the 10 calendar days up to and including `day`."""
    lo = (dt.date.fromisoformat(day) - dt.timedelta(days=10)).isoformat()
    window = [b for b in tape if lo <= b[0] <= day]
    bar = [b for b in window if b[0] == day]
    return bool(bar) and not (bar[0][5] or 0) and sum((b[5] or 0) for b in window) > 0


def _fuzz(seed, n=200):
    rng = random.Random(seed)
    rows, ent, legs = [], {}, {}
    for i in range(n):
        tk, px, tape = f"Q{i:03d}", rng.uniform(1, 400), []
        for d in SESS:
            r = rng.random()
            if r < 0.04:
                continue                                                    # a missing bar
            c = round(px * (1 + rng.gauss(0, 0.03)), rng.choice([2, 3, 4]))
            v = 1000.0
            if r < 0.08:
                c = None                                                    # not printed
            elif r < 0.33:
                v = 0.0                                                     # carry-forward
                c = px
            tape.append([d.isoformat(), px, px, px, c, v])
            px = c if c is not None else px
        ent[tk] = _e(tape)
        d1 = rng.choice([d for d in SESS if d <= dt.date(2026, 9, 30)]).isoformat()
        d0 = rng.choice([d for d in SESS if d.isoformat() < d1] or [SESS[0]]).isoformat()
        n_ = f"{rng.uniform(1, 400):.2f}"
        kind = rng.choice(["A", "W", "C", "R", "P0", "P1", "U"])
        q, lg = {
            "A": (f"{tk} closes above {n_} on {d1}", [d1]),
            "W": (f"Will {tk} close at or below {n_} on {d1}?", [d1]),
            "C": (f"abs({tk} last on {d1} / {n_} - 1) >= 0.05", [d1]),
            "R": (f"{tk} closes higher on {d1} than it closes on {d0}", [d1, d0]),
            "P0": (f"Absolute {tk} 5-session move from its {d0} close exceeds 5% on {d1}", [d1, d0]),
            "P1": (f"Absolute {tk} 5-session move from {n_} exceeds 5% on {d1}", [d1]),
            "U": (f"{tk} close on {d1} < its close on {d0}", []),                # unparsable
        }[kind]
        rows.append(_row(tk, q, cd=d1))
        legs[tk] = lg
    return rows, ent, legs


def test_04_nothing_else_changes_old_vs_new_on_a_seeded_fuzz(tmp_path):
    rows, ent, legs = _fuzz(7)
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows}, ent)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows}, ent)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    old, new = _rows(ho), _rows(hn)
    prod_close = lambda tk, d: any(b[0] == d and b[4] is not None for b in ent[tk]["bars"])
    refused = {tk for tk, lg in legs.items()
               if any(prod_close(tk, d) and _oracle_carry_forward(ent[tk]["bars"], d) for d in lg)}
    same = set(old) - refused
    assert len(refused) >= 15 and len(same) >= 80, (len(refused), len(same))
    for tk in same:
        assert norm_row(old[tk]) == norm_row(new[tk]), tk                          # every field, notes included
        ol = [l for l in oo.splitlines() if re.search(rf"^  (SKIP \((?:no close|unparsed)\): )?{tk}\b", l)]
        nl = [l for l in no.splitlines() if re.search(rf"^  (SKIP \((?:no close|unparsed)\): )?{tk}\b", l)]
        assert ol == nl, (tk, ol, nl)                                              # and its output line
    for tk in refused:
        assert new[tk]["outcome"] == "" and new[tk]["notes"] == "[insider] fixture", tk
        assert any(l.startswith(f"  SKIP (no close): {tk} —") and CF in l for l in no.splitlines()), tk
    assert sum(1 for tk in refused if old[tk]["outcome"]) >= 8                      # the old resolver really scored carried-forward rows
    assert sum(1 for r in new.values() if r["outcome"]) < sum(1 for r in old.values() if r["outcome"])


# ---------------------------------------------------------------- 5: fails closed
def test_05_when_the_volume_cannot_be_checked_the_production_close_does_not_resolve(tmp_path):
    good = _week(last=105.0)
    rows = [_row("YRS", "YRS closes above 100 on 2026-09-28"), _row("YEM", "YEM closes above 100 on 2026-09-28"),
            _row("YOK", "YOK closes above 100 on 2026-09-28")]
    ent = {"YRS": dict(bars="RAISE", splits=[], prod_bars=good),            # yfinance raises; production has the close
           "YEM": dict(bars=[], splits=[], prod_bars=good),                 # yfinance returns an empty frame
           "YOK": _e(good)}
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows}, ent)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows}, ent)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    assert [_rows(ho)[t]["outcome"] for t in ("YRS", "YEM", "YOK")] == ["1", "1", "1"]          # old: unverified closes resolved
    n = _rows(hn)
    assert [n[t]["outcome"] for t in ("YRS", "YEM", "YOK")] == ["", "", "1"]
    assert re.search(r"SKIP \(no close\): YRS — YRS 2026-09-28: options_settle read a close for 2026-09-28, but its volume could not be "
                     r"checked: yfinance failed: ConnectionError: fake timeout for YRS", no), no
    assert re.search(r"SKIP \(no close\): YEM — YEM 2026-09-28: options_settle read a close for 2026-09-28, but its volume could not be "
                     r"checked: yfinance returned no bars around 2026-09-28", no), no
    assert n["YRS"]["notes"] == n["YEM"]["notes"] == "[insider] fixture"


# ---------------------------------------------------------------- 6: no bar (or an empty bar) dated d on a tape that was read
def test_06_a_tape_without_the_days_close_keeps_the_production_close(tmp_path):
    """SETTLE-001: on the day itself Yahoo's daily bar can lag - absent, or posted with no values - and the production reader answers
    from the quote stamped >= 16:00 ET on that day. The volume tape then has nothing to refuse (no bar dated d, or a bar with no close:
    "not printed", not a carried price) and the close stands, exactly as before."""
    tape = _week()[:-1]                                                      # bars through 09-25 only
    ent = {"SDQ": dict(bars=tape, splits=[], quote=["2026-09-28", 105.0]),                                  # no bar dated 09-28
           "SDE": dict(bars=tape + [["2026-09-28", None, None, None, None, None]], splits=[],               # a 09-28 bar with no values
                       quote=["2026-09-28", 105.0])}
    rows = [_row("SDQ", "SDQ closes above 100 on 2026-09-28"), _row("SDE", "SDE closes above 100 on 2026-09-28")]
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows}, ent)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows}, ent)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    for t in ("SDQ", "SDE"):
        assert _rows(hn)[t]["outcome"] == "1" and norm_row(_rows(ho)[t]) == norm_row(_rows(hn)[t]), t
    assert norm_out(oo) == norm_out(no) and CF not in no


# ---------------------------------------------------------------- 7: ".NS" never used the production path
def test_07_india_radar_rows_are_unchanged(tmp_path):
    rows = [_row("INA", "INA closes above 100 on 2026-09-28"), _row("INB", "INB closes above 100 on 2026-09-28")]
    ent = {"INA.NS": _e(_week(("2026-09-28",), last=105.0)), "INB.NS": _e(_week(last=105.0))}
    ho, fo = _home(tmp_path / "old", {"india-radar": rows}, ent)
    hn, fn = _home(tmp_path / "new", {"india-radar": rows}, ent)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    assert _ledger_norm(ho, "india-radar") == _ledger_norm(hn, "india-radar")
    assert norm_out(oo) == norm_out(no)
    assert _rows(hn, "india-radar")["INA"]["outcome"] == "" and _rows(hn, "india-radar")["INB"]["outcome"] == "1"   # the fallback's refusal, as ever
    assert "the 2026-09-28 bar is a zero-volume carry-forward" in no


# ---------------------------------------------------------------- 8: re-open replay of the REAL ledgers
def _tape(tk, seed):
    k = zlib.crc32(tk.encode())
    rng = random.Random(k ^ seed)
    px, d, bars = 20 + (k % 500) / 5.0, dt.date(2026, 7, 1), []
    while d <= dt.date(2026, 10, 31):
        if d.weekday() < 5:
            c = round(px * (1 + rng.gauss(0, 0.025)), 4)
            v, ds = 1000.0 + (k % 97), d.isoformat()
            if k % 11 == 0 and ds >= "2026-09-10":
                c = None                                       # an unprinted close from 09-10
            elif k % 4 == 0 and d.weekday() in (1, 3):
                v, c = 0.0, px                                 # a carry-forward on Tuesdays and Thursdays
            bars.append([ds, px, max(px, c or px) * 1.01, min(px, c or px) * 0.99, c, v])
            px = c if c is not None else px
        d += dt.timedelta(days=1)
    return bars


def test_08_full_reopen_replay_of_the_real_forecast_ledgers(tmp_path):
    """Every row of the four REAL forecast ledgers is re-opened in an isolated HOME (stub production reader) and re-scored by the
    old resolver and the new one on a pinned synthetic tape. A row may differ only if it read a carry-forward bar: old scored it,
    new defers it and says so. Every other row is byte-identical and nothing real is touched."""
    labs = {"stock-radar": "", "insider-radar": "", "india-radar": ".NS", "macro-branch": ""}
    src = {lab: f"{HOME}/{lab}/agent/forecasts.csv" for lab in labs}
    if not all(os.path.exists(p) for p in src.values()) or not os.path.exists(f"{HOME}/stock-radar/sessions.py"):
        pytest.skip("the estate's forecast ledgers are not on this machine")
    live = {lab: list(csv.DictReader(open(p))) for lab, p in src.items()}
    src_text = open(RESOLVER).read()
    rx = {n: eval(re.search(rf"^{n} = (re\.compile\(.*\))\s*(?:#.*)?$", src_text, re.M).group(1), {"re": re}) for n in "ACRWP"}

    def build(label):
        h = str(tmp_path / label)
        os.makedirs(os.path.join(h, "stock-radar"))
        shutil.copy(f"{HOME}/stock-radar/sessions.py", os.path.join(h, "stock-radar", "sessions.py"))
        with open(os.path.join(h, "stock-radar", "sessions.py"), "a") as f:   # the real calendar, settled_session() frozen
            f.write("\n\ndef settled_session(now=None, cutoff=None):\n    return dt.date.fromisoformat('2026-09-30')\n")
        with open(os.path.join(h, "stock-radar", "options_settle.py"), "w") as f:
            f.write(STUB_SETTLE)
        fx = {}
        for lab, suf in labs.items():
            rows = [dict(r, outcome="") for r in live[lab]]              # re-open EVERY row
            for r in rows:
                q = r["question"].replace("radar.json ", "")
                for tk in {r["instrument"]} | {m.group(1).strip() for m in (rx[n].search(q) for n in "ACRWP") if m and m.group(1)}:
                    fx[tk + suf] = _e(_tape(tk + suf, 7))
            p = os.path.join(h, lab, "agent", "forecasts.csv")
            os.makedirs(os.path.dirname(p))
            with open(p, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(live[lab][0].keys()))
                w.writeheader()
                w.writerows(rows)
        json.dump(fx, open(os.path.join(h, "yf.json"), "w"))
        return h, os.path.join(h, "yf.json")

    ho, fo = build("old")
    hn, fn = build("new")
    _run(RESOLVER_OLD, ho, fo, "--dry"), _run(RESOLVER, hn, fn, "--dry")
    for lab in labs:   # --dry writes nothing
        assert open(os.path.join(ho, lab, "agent", "forecasts.csv"), "rb").read() == open(os.path.join(hn, lab, "agent", "forecasts.csv"), "rb").read()
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    differ, n_rows, scored_old, scored_new = [], 0, 0, 0
    for lab in labs:
        ro = list(csv.DictReader(open(os.path.join(ho, lab, "agent", "forecasts.csv"))))
        rn = list(csv.DictReader(open(os.path.join(hn, lab, "agent", "forecasts.csv"))))
        assert len(ro) == len(rn) == len(live[lab])
        for a, b, orig in zip(ro, rn, live[lab]):
            n_rows += 1
            scored_old += bool(a["outcome"])
            scored_new += bool(b["outcome"])
            if norm_row(a) != norm_row(b):
                differ.append((lab, a["instrument"], a, b, orig))
    assert n_rows >= 100 and scored_old >= 40 and len(differ) >= 3, (n_rows, scored_old, len(differ))   # the replay really exercised the guard
    for lab, ins, a, b, orig in differ:
        assert a["outcome"] and not b["outcome"], (lab, ins)                 # old scored it, new defers it - never a different outcome
        assert b["notes"] == orig["notes"], (lab, ins)                       # and a deferred row is not touched
        assert any(l.startswith(f"  SKIP (no close): {ins} —") and CF in l for l in no.splitlines()), (lab, ins)
    assert scored_new == scored_old - len(differ)
    # every output line that is not about a differing row is identical
    names = {ins for _l, ins, _a, _b, _o in differ}
    body = lambda s: [l for l in norm_out(s).splitlines() if not l.startswith("R:") and not any(re.search(rf"^  (SKIP \(no close\): )?{re.escape(n)}\b", l) for n in names)]
    assert body(oo) == body(no)


# ---------------------------------------------------------------- 9: one definition
def test_09_one_rule_for_both_paths():
    src = open(RESOLVER).read()
    tree = ast.parse(src)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert {"_yf_window", "_carry_forward", "_production_veto", "close_on"} <= set(fns)
    calls = lambda fn, name: [c for c in ast.walk(fns[fn]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == name]
    assert calls("_production_veto", "_carry_forward") and calls("close_on", "_carry_forward")        # production veto AND fallback
    assert calls("_production_veto", "_yf_window") and calls("close_on", "_yf_window")                # the same tape window
    assert calls("close_on", "_production_veto")                                                       # and the veto is consulted
    # the volume column is read in exactly one place - the rule is written once
    vol = [n for n in ast.walk(tree) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == "Volume"]
    inside = {id(n) for n in ast.walk(fns["_carry_forward"])}
    assert vol and all(id(n) in inside for n in vol), "a second reader of the Volume column has appeared outside _carry_forward"
    # the one tape call is the fallback's old call exactly: start d-10 days, end d+1 day, UNADJUSTED (the fake yfinance ignores
    # auto_adjust, so a drift here would be invisible to every behavioural test)
    hist = [c for c in ast.walk(fns["_yf_window"]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "history"]
    assert len(hist) == 1
    kw = {k.arg: ast.get_source_segment(src, k.value) for k in hist[0].keywords}
    assert set(kw) == {"start", "end", "auto_adjust"} and kw["auto_adjust"] == "False", kw
    assert "timedelta(days=10)" in kw["start"] and "timedelta(days=1)" in kw["end"], kw
    # and both paths state the refusal in the same words
    assert "bar is a zero-volume carry-forward" in ast.get_source_segment(src, fns["_production_veto"])
    assert "bar is a zero-volume carry-forward" in ast.get_source_segment(src, fns["close_on"])


# ---------------------------------------------------------------- 11: a tape that cannot be judged defers the row, it does not crash the run
NOVOL_YF = '''
import pandas as pd
class Ticker:
    def __init__(self, tk): self.tk = tk
    def history(self, start=None, end=None, auto_adjust=False, **kw):
        idx = pd.DatetimeIndex([pd.Timestamp("2026-09-28").tz_localize("America/New_York")])
        return pd.DataFrame({"Open": [100.0], "High": [100.0], "Low": [100.0], "Close": [105.0]}, index=idx)   # NO Volume column
'''


def test_11_a_tape_that_cannot_be_judged_defers_the_row_and_does_not_crash_the_run(tmp_path):
    """yfinance always returns a Volume column, so this is unreachable in practice - but the veto is a guard on every ledger at once,
    and a guard that crashes takes all four down with it (the whole volume test runs inside the veto's try). A frame with no Volume
    column must defer the row, named, and the run must finish and write what it can."""
    rows = [_row("VNA", "VNA closes above 100 on 2026-09-28")]
    ent = {"VNA": _e(_week(last=105.0))}
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows, "stock-radar": rows}, ent)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows, "stock-radar": rows}, ent)
    nv = tmp_path / "novol_yf"
    os.makedirs(nv / "yfinance")
    (nv / "yfinance" / "__init__.py").write_text(NOVOL_YF)
    oo = _run(RESOLVER_OLD, ho, fo, pypath=str(nv))
    no = _run(RESOLVER, hn, fn, pypath=str(nv))                       # rc 0 is asserted inside _run: the run finished
    assert _rows(ho)["VNA"]["outcome"] == "1" and _rows(ho, "stock-radar")["VNA"]["outcome"] == "1"     # old: resolved off the unchecked close
    for lab in ("insider-radar", "stock-radar"):
        assert _rows(hn, lab)["VNA"]["outcome"] == "" and _rows(hn, lab)["VNA"]["notes"] == "[insider] fixture", lab
    assert no.count("volume could not be checked: yfinance failed: KeyError: 'Volume'") == 2, no
    assert "0 scored, 2 left" in no


# ---------------------------------------------------------------- 10: BENCH-002
def test_10_a_scored_row_is_never_reexamined_even_on_a_carry_forward_bar(tmp_path):
    scored = _row("SCR", "SCR closes above 100 on 2026-09-28", outcome="0", notes="[insider] scored by hand")
    h, fx = _home(tmp_path, {"insider-radar": [scored]}, {"SCR": _e(_week(("2026-09-28",), last=105.0))})
    before = _ledger_bytes(h)
    out = _run(RESOLVER, h, fx)
    assert _ledger_bytes(h) == before and "SCR" not in out and "0 scored, 0 left" in out

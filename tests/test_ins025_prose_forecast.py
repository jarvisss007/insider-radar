"""INS-025 - the estate forecast resolver reads the prose question the insider desk files. Offline; no network.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins025_prose_forecast.py

The question forms (insider ledger only; see the P block in ~/bin/resolve_forecasts.py):
    "Absolute <T> <N>-session move from its <D0> close exceeds <X>% on <D1>"   |close(D1)/close(D0) - 1| > X/100
    "Absolute <T> <N>-session move from <A> exceeds <X>% on <D1>"              |close(D1)/A - 1| > X/100
"exceeds" is STRICT: a move of exactly X% is NO. Class (c): applied only on an explicit ruling (council/issues.json
INS-025). No existing form changes.

Numbered:
 1 date-anchored rows with a stated synthetic close resolve per the formula, strictly, in both directions
 2 an exact X% move is NO; one cent more is YES (the float trap 110.0/100.0 - 1 = 0.10000000000000009 is not taken)
 3 a Yahoo float32 close (4.400000095367432 for 4.40) does not turn an exact tie into a YES
 4 a stated numeric level ("from 4.435") resolves the same way
 5 the guards close_on() has: a NaN or zero-volume close on either date stalls the row, blank and named. NOTE these
   tests run close_on()'s yfinance FALLBACK path (the isolated HOME has no options_settle.py): the production path reads
   quote.close only, so the zero-volume refusal is the fallback's - a separate, pre-existing gap, not claimed here
 6 a row not yet due is not examined; a scored row is never touched (BENCH-002)
 7 check_date governs the resolution date (INS-019) and the row says so
 8 N is descriptive: the two dates decide, nothing is written about N; a from-date not strictly before the resolution
   date is refused, never scored
 9 scope: the same prose question in another lab's ledger stays "SKIP (unparsed)" (insider ledger only)
10 no new behaviour for the existing forms: old resolver vs new, row by row, on a mixed ledger, on a seeded fuzz
   (NaN / zero-volume / missing bars) and on a full-reopen replay of the four REAL forecast ledgers - only the prose-form
   insider rows differ
11 the notes of a resolved row carry both closes and the move, so each outcome can be re-derived from the row alone
"""
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import random
import zlib

import pytest

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVER = os.environ.get("INS025_RESOLVER", f"{HOME}/bin/resolve_forecasts.py")
RESOLVER_OLD = os.environ.get("INS025_RESOLVER_OLD", f"{HOME}/bin/resolve_forecasts_BACKUP_0930_INS-025.py")
FAKE_YF = os.path.join(HERE, "fixtures", "fake_yf")
PY = "/opt/anaconda3/bin/python"
COLS = ["date", "instrument", "horizon_days", "question", "p", "check_date", "outcome", "notes"]

# A deterministic calendar: weekdays except Labor Day 2026-09-07; settled_session() is frozen, so these tests read the
# same on every day they are run. (The resolver loads <HOME>/stock-radar/sessions.py by path.)
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


def _b(d, c, v=1000.0):
    return [d, c, c, c, c, v]


def _home(tmp, ledgers, bars):
    """An isolated HOME: the stub calendar, the given ledgers {lab: [row dicts]}, and the fake-yfinance tape."""
    h = str(tmp)
    os.makedirs(os.path.join(h, "stock-radar"), exist_ok=True)
    with open(os.path.join(h, "stock-radar", "sessions.py"), "w") as f:
        f.write(STUB_SESSIONS)
    for lab, rows in ledgers.items():
        p = os.path.join(h, lab, "agent", "forecasts.csv")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in COLS})
    fx = os.path.join(h, "yf.json")
    json.dump({k: {"bars": v, "splits": []} for k, v in bars.items()}, open(fx, "w"))
    return h, fx


def _run(script, home, fx, *args):
    env = dict(os.environ, HOME=home, FAKE_YF_FIXTURE=fx, PYTHONPATH=FAKE_YF)
    r = subprocess.run([PY, script, *args], capture_output=True, text=True, env=env, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def _rows(home, lab="insider-radar"):
    return {r["instrument"]: r for r in csv.DictReader(open(os.path.join(home, lab, "agent", "forecasts.csv")))}


def _prose(tk, d0, x, d1, n=5, anchor=None):
    frm = f"from its {d0} close" if anchor is None else f"from {anchor}"
    return f"Absolute {tk} {n}-session move {frm} exceeds {x}% on {d1}"


def _row(tk, q, cd="2026-09-28", **kw):
    r = {"date": "2026-09-21", "instrument": tk, "horizon_days": "5", "question": q, "p": "0.3", "check_date": cd,
         "notes": "[insider] fixture"}
    r.update(kw)
    return r


# ---------------------------------------------------------------- 1, 2, 3, 4, 11: the formula, strictly
CASES = [  # (ticker, from-close, check-close, X as written, expected outcome, why)
    ("UP1", 100.00, 111.00, "10", "1", "+11% exceeds 10%"),
    ("UP2", 100.00, 109.00, "10", "0", "+9% does not"),
    ("TIE", 100.00, 110.00, "10", "0", "exactly +10.000% does NOT exceed 10% (strict)"),
    ("OVR", 100.00, 110.01, "10", "1", "one cent past the tie does"),
    ("DTI", 100.00, 90.00, "10", "0", "exactly -10.000% does not exceed (absolute value, strict)"),
    ("DOV", 100.00, 89.99, "10", "1", "-10.01% does (absolute value)"),
    ("PEN", 3.50, 3.71, "6.0", "0", "a penny-grid tie: 3.50 -> 3.71 is exactly +6.000%"),
    ("PE2", 3.50, 3.72, "6.0", "1", "3.50 -> 3.72 is +6.286%"),
    ("F32", 4.0, 4.400000095367432, "10", "0", "Yahoo float32 noise on an exact +10% tie must not make it a YES"),
    ("F33", 5.840000152587891, 6.43, "10", "1", "float32 reference 5.84 -> 6.43 is +10.10%"),
    ("FLT", 100.0, 100.0, "0.5", "0", "no move"),
]


def test_01_02_03_formula_is_strict_and_exact(tmp_path):
    rows, bars = [], {}
    for tk, c0, c1, x, _want, _why in CASES:
        rows.append(_row(tk, _prose(tk, "2026-09-21", x, "2026-09-28")))
        bars[tk] = [_b("2026-09-21", c0), _b("2026-09-28", c1)]
    h, fx = _home(tmp_path, {"insider-radar": rows}, bars)
    out = _run(RESOLVER, h, fx)
    got = _rows(h)
    for tk, c0, c1, x, want, why in CASES:
        assert got[tk]["outcome"] == want, f"{tk}: {why} (got {got[tk]['outcome']!r})\n{out}"
    # 11: the row alone re-derives the outcome - both closes, the move and the bar
    n = got["TIE"]["notes"]
    assert re.search(r"RESOLVED \d{4}-\d{2}-\d{2} by resolve_forecasts\.py off close 110\.00 on 2026-09-28 "
                     r"vs 100 on 2026-09-21; \|move\| 10\.000% <= 10%", n), n
    assert "|move| 11.000% > 10%" in got["UP1"]["notes"]
    assert "(close 111.00 vs 100 on 2026-09-21; |move| 11.000% > 10%)" in out


def test_04_stated_numeric_level(tmp_path):
    cases = [("NM1", "4.435", "10.0", 4.88, "1"),    # +10.034%
             ("NM2", "4.435", "10.0", 4.87, "0"),    # +9.808%
             ("NM3", "4.435", "10.0", 3.99, "1"),    # -10.034%
             ("NM4", "4.435", "10.0", 3.995, "0"),   # -9.921%
             ("NM5", "100", "10", 110.0, "0"),       # exact tie
             ("NM6", "100.00", "10", 110.01, "1")]
    rows, bars = [], {}
    for tk, lvl, x, c1, _w in cases:
        rows.append(_row(tk, _prose(tk, None, x, "2026-09-28", anchor=lvl)))
        bars[tk] = [_b("2026-09-28", c1)]            # NO close on any from-date is needed: the level is stated
    h, fx = _home(tmp_path, {"insider-radar": rows}, bars)
    out = _run(RESOLVER, h, fx)
    got = _rows(h)
    for tk, lvl, x, c1, want in cases:
        assert got[tk]["outcome"] == want, f"{tk} level {lvl} -> {c1}: got {got[tk]['outcome']!r}\n{out}"
    assert "vs stated level 4.435; |move| 10.034% > 10.0%" in got["NM1"]["notes"]


# ---------------------------------------------------------------- 5 stalls: the C form's guards
def test_05_the_guards_close_on_has_stall_the_row_and_are_named(tmp_path):
    nan = None
    rows = [_row(t, _prose(t, "2026-09-21", "10", "2026-09-28")) for t in ("NAN", "ZVC", "NOF", "NOT", "OKK")]
    bars = {
        "NAN": [_b("2026-09-21", 100.0), ["2026-09-28", 120, 120, 120, nan, 800.0]],            # check close not printed
        "ZVC": [_b("2026-09-21", 100.0), _b("2026-09-22", 100.0), _b("2026-09-28", 120.0, 0.0)],  # carry-forward on the check date
        "NOF": [["2026-09-21", 100, 100, 100, nan, 800.0], _b("2026-09-28", 120.0)],            # from-date close not printed
        "NOT": [_b("2026-09-18", 100.0), _b("2026-09-28", 120.0)],                              # no bar ON the from-date
        "OKK": [_b("2026-09-21", 100.0), _b("2026-09-28", 120.0)],
    }
    h, fx = _home(tmp_path, {"insider-radar": rows}, bars)
    out = _run(RESOLVER, h, fx)
    got = _rows(h)
    assert [got[t]["outcome"] for t in ("NAN", "ZVC", "NOF", "NOT", "OKK")] == ["", "", "", "", "1"]
    assert "SKIP (no close): NAN" in out and "NaN" in out
    assert "SKIP (no close): ZVC" in out and "zero-volume" in out
    assert "SKIP (no close): NOF" in out and "2026-09-21" in out.split("SKIP (no close): NOF")[1].splitlines()[0]
    assert "SKIP (no close): NOT" in out and "no bar on 2026-09-21" in out
    assert "(unparsed)" not in out                                          # none of them is "unparsed" any more
    assert got["NAN"]["notes"] == "[insider] fixture"                       # a stalled row is not touched


def test_05c_a_non_positive_stated_level_is_refused_loudly(tmp_path):
    rows = [_row("ZER", _prose("ZER", None, "10", "2026-09-28", anchor="0"))]
    h, fx = _home(tmp_path, {"insider-radar": rows}, {"ZER": [_b("2026-09-28", 5.0)]})
    out = _run(RESOLVER, h, fx)
    assert _rows(h)["ZER"]["outcome"] == "" and "SKIP (unparsed): ZER" in out and "non-positive reference level" in out


# ---------------------------------------------------------------- 6 due, scored
def test_06_not_due_not_examined_and_scored_rows_untouched(tmp_path):
    scored = _row("SCR", _prose("SCR", "2026-09-21", "10", "2026-09-28"), outcome="0", notes="[insider] scored by hand")
    notdue = _row("NDU", _prose("NDU", "2026-09-28", "15", "2026-10-05"), cd="2026-10-05")
    h, fx = _home(tmp_path, {"insider-radar": [scored, notdue]},
                  {"SCR": [_b("2026-09-21", 100.0), _b("2026-09-28", 150.0)],
                   "NDU": [_b("2026-09-28", 100.0), _b("2026-10-05", 150.0)]})
    before = open(os.path.join(h, "insider-radar", "agent", "forecasts.csv"), "rb").read()
    out = _run(RESOLVER, h, fx)
    assert open(os.path.join(h, "insider-radar", "agent", "forecasts.csv"), "rb").read() == before
    assert "SCR" not in out and "NDU" not in out and "0 scored, 0 left" in out


# ---------------------------------------------------------------- 7 INS-019
def test_07_check_date_governs_and_the_row_says_so(tmp_path):
    q = _prose("GOV", "2026-09-21", "10", "2026-09-29")           # the question names 09-29 ...
    h, fx = _home(tmp_path, {"insider-radar": [_row("GOV", q, cd="2026-09-28")]},   # ... the recorded check_date is 09-28
                  {"GOV": [_b("2026-09-21", 100.0), _b("2026-09-28", 120.0), _b("2026-09-29", 100.0)]})
    _run(RESOLVER, h, fx)
    r = _rows(h)["GOV"]
    assert r["outcome"] == "1" and "off close 120.00 on 2026-09-28" in r["notes"]
    assert "INS-019: question names 2026-09-29; check_date 2026-09-28 governs" in r["notes"]


# ---------------------------------------------------------------- 8 N is descriptive; windows run forward
def test_08_n_is_descriptive_and_a_backward_window_is_refused(tmp_path):
    rows = [_row("N05", _prose("N05", "2026-09-21", "10", "2026-09-28", n=5)),       # 5 sessions: matches
            _row("N03", _prose("N03", "2026-09-21", "10", "2026-09-28", n=3)),       # says 3, the dates span 5: the dates decide
            _row("REV", _prose("REV", "2026-09-30", "10", "2026-09-29"), cd="2026-09-30"),   # from-date AFTER the question's date
            _row("EQL", _prose("EQL", "2026-09-28", "10", "2026-09-28"), cd="2026-09-28")]   # from-date == resolution date
    bars = {t: [_b("2026-09-21", 100.0), _b("2026-09-28", 120.0), _b("2026-09-29", 130.0), _b("2026-09-30", 130.0)]
            for t in ("N05", "N03", "REV", "EQL")}
    h, fx = _home(tmp_path, {"insider-radar": rows}, bars)
    out = _run(RESOLVER, h, fx)
    g = _rows(h)
    assert g["N05"]["outcome"] == "1" and g["N03"]["outcome"] == "1"
    assert "INS-025" not in g["N05"]["notes"] and "INS-025" not in g["N03"]["notes"]   # nothing is written about N
    assert g["REV"]["outcome"] == "" and g["EQL"]["outcome"] == ""                       # refused, not scored "130 vs 130"
    assert "SKIP (unparsed): REV — the from-date 2026-09-30 is not before the resolution date 2026-09-30" in out
    assert "SKIP (unparsed): EQL — the from-date 2026-09-28 is not before the resolution date 2026-09-28" in out


# ---------------------------------------------------------------- 9 scope
def test_09_other_labs_stay_unparsed(tmp_path):
    q = _prose("AAA", None, "4.0", "2026-09-28", anchor="1830.20")
    rows = [_row("AAA", q)]
    h, fx = _home(tmp_path, {"india-radar": rows, "stock-radar": [dict(rows[0], instrument="BBB", question=q.replace("AAA", "BBB"))]},
                  {"AAA.NS": [_b("2026-09-28", 2000.0)], "BBB": [_b("2026-09-28", 2000.0)]})
    out = _run(RESOLVER, h, fx)
    assert _rows(h, "india-radar")["AAA"]["outcome"] == "" and _rows(h, "stock-radar")["BBB"]["outcome"] == ""
    assert out.count("SKIP (unparsed)") == 2


# ---------------------------------------------------------------- 10 no new behaviour for the existing forms
def _mixed_rows():
    rows, bars = [], {}

    def add(tk, q, tape):
        rows.append(_row(tk, q))
        bars[tk] = tape
    add("FA1", "FA1 closes above 100 on 2026-09-28", [_b("2026-09-28", 101.0)])
    add("FA2", "FA2 last < 100 on 2026-09-28", [_b("2026-09-28", 101.0)])
    add("FW1", "Will FW1 close at or below 101 on 2026-09-28?", [_b("2026-09-28", 101.0)])
    add("FC1", "abs(FC1 last on 2026-09-28 / 100 - 1) >= 0.10", [_b("2026-09-28", 110.0)])      # a C tie: >= is YES
    add("FC2", "abs(FC2 last on 2026-09-28 / 100 - 1) >= 0.10", [_b("2026-09-28", 109.0)])
    add("FR1", "FR1 closes higher on 2026-09-28 than it closes on 2026-09-21", [_b("2026-09-21", 100.0), _b("2026-09-28", 101.0)])
    add("FN1", "FN1 closes above 100 on 2026-09-28", [["2026-09-28", 1, 1, 1, None, 5.0]])     # NaN: stalls, both versions
    add("FP1", _prose("FP1", "2026-09-21", "10", "2026-09-28"), [_b("2026-09-21", 100.0), _b("2026-09-28", 120.0)])
    add("FU1", "something else entirely on 2026-09-28", [_b("2026-09-28", 1.0)])               # unparsed, both versions
    return rows, bars


def test_10a_existing_forms_identical_old_vs_new(tmp_path):
    rows, bars = _mixed_rows()
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows}, bars)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows}, bars)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    old, new = _rows(ho), _rows(hn)
    assert {k for k in old if old[k] != new[k]} == {"FP1"}                  # the only row that differs is the prose row
    assert old["FP1"]["outcome"] == "" and new["FP1"]["outcome"] == "1"
    for k in old:
        if k != "FP1":
            assert old[k] == new[k], k                                      # every field, notes included
    assert old["FC1"]["outcome"] == "1" and old["FC2"]["outcome"] == "0" and old["FN1"]["outcome"] == ""
    body = lambda s: [l for l in re.sub(r"resolve_forecasts \d{4}-\d{2}-\d{2}:", "R:", s).splitlines()
                      if "FP1" not in l and not l.startswith("R:")]
    assert body(oo) == body(no)                                             # every other output line, identical
    assert "SKIP (unparsed): FP1" in oo and "SKIP (unparsed): FP1" not in no and "SKIP (unparsed): FU1" in no




def test_10c_seeded_fuzz_existing_forms_identical(tmp_path):
    """150 random A/W/C/R and unparsable questions over random tapes with NaN closes, zero-volume carry-forward bars and
    missing bars: the old resolver and the new one agree on every output line and every ledger byte."""
    rng = random.Random(11)
    sessions = [d for d in (dt.date(2026, 8, 3) + dt.timedelta(days=i) for i in range(60)) if d.weekday() < 5 and d != dt.date(2026, 9, 7)]
    rows, bars = [], {}
    for i in range(150):
        tk, px, tape = f"Z{i:03d}", rng.uniform(1, 400), []
        for d in sessions:
            r = rng.random()
            if r < 0.04:
                continue                                                    # a missing bar
            c = round(px * (1 + rng.gauss(0, 0.03)), rng.choice([2, 3, 4]))
            v = 1000.0
            if r < 0.08:
                c = None                                                    # not printed
            elif r < 0.13:
                v = 0.0                                                     # carry-forward
            tape.append([d.isoformat(), px, px, px, c, v])
            px = c if c is not None else px
        bars[tk] = tape
        d1 = rng.choice([d for d in sessions if d <= dt.date(2026, 9, 30)]).isoformat()
        d0 = rng.choice([d for d in sessions if d.isoformat() < d1] or [sessions[0]]).isoformat()
        n = f"{rng.uniform(1, 400):.2f}"
        q = rng.choice([f"{tk} closes above {n} on {d1}", f"{tk} last < {n} on {d1}", f"Will {tk} close at or below {n} on {d1}?",
                        f"abs({tk} last on {d1} / {n} - 1) >= 0.05", f"{tk} closes higher on {d1} than it closes on {d0}",
                        f"{tk} close on {d1} < its close on {d0}"])                      # the last one is unparsable
        rows.append(_row(tk, q, cd=d1))
    ho, fo = _home(tmp_path / "old", {"insider-radar": rows, "india-radar": rows}, bars)
    hn, fn = _home(tmp_path / "new", {"insider-radar": rows, "india-radar": rows}, bars)
    oo, no = _run(RESOLVER_OLD, ho, fo), _run(RESOLVER, hn, fn)
    for lab in ("insider-radar", "india-radar"):
        assert open(os.path.join(ho, lab, "agent", "forecasts.csv"), "rb").read() == open(os.path.join(hn, lab, "agent", "forecasts.csv"), "rb").read()
    assert re.sub(r"resolve_forecasts \d{4}-\d{2}-\d{2}:", "R:", oo) == re.sub(r"resolve_forecasts \d{4}-\d{2}-\d{2}:", "R:", no)
    assert oo.count("SKIP (no close)") > 10 and oo.count("SKIP (unparsed)") > 10 and sum(1 for r in _rows(ho).values() if r["outcome"]) > 40


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
            elif k % 13 == 0 and ds in ("2026-09-15", "2026-09-22", "2026-09-29"):
                v = 0.0                                        # zero-volume carry-forward bars
            bars.append([ds, px, max(px, c or px) * 1.01, min(px, c or px) * 0.99, c, v])
            px = c if c is not None else px
        d += dt.timedelta(days=1)
    return bars


def test_10b_full_reopen_replay_of_the_real_forecast_ledgers(tmp_path):
    """Every row of the four REAL forecast ledgers is re-opened in an isolated HOME and re-scored by the old resolver and
    the new one on a pinned synthetic tape. Every row the old one reads must come out byte-identical; only the prose-form
    rows of the insider ledger may differ - and nothing real is touched."""
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
        fx = {}
        for lab, suf in labs.items():
            rows = [dict(r, outcome="") for r in live[lab]]              # re-open EVERY row
            for r in rows:
                q = r["question"].replace("radar.json ", "")
                for tk in {r["instrument"]} | {m.group(1).strip() for m in (rx[n].search(q) for n in "ACRWP") if m and m.group(1)}:
                    fx[tk + suf] = {"bars": _tape(tk + suf, 7), "splits": []}
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
    prose = {("insider-radar", r["instrument"]) for r in live["insider-radar"]
             if rx["P"].search(r["question"]) and not any(rx[n].search(r["question"]) for n in "ACRW")}
    norm = lambda r: dict(r, notes=re.sub(r"RESOLVED \d{4}-\d{2}-\d{2}", "RESOLVED D", r["notes"]))
    differ, scored_old, scored_new, n_rows = set(), 0, 0, 0
    for lab in labs:
        ro = list(csv.DictReader(open(os.path.join(ho, lab, "agent", "forecasts.csv"))))
        rn = list(csv.DictReader(open(os.path.join(hn, lab, "agent", "forecasts.csv"))))
        assert len(ro) == len(rn)
        for a, b in zip(ro, rn):
            n_rows += 1
            scored_old += bool(a["outcome"])
            scored_new += bool(b["outcome"])
            if norm(a) != norm(b):
                differ.add((lab, a["instrument"]))
    assert n_rows >= 100 and scored_old >= 40, (n_rows, scored_old)        # the replay really exercised the old forms
    assert differ <= prose, f"rows that differ and are NOT prose-form insider rows: {sorted(differ - prose)}"
    assert scored_new - scored_old == len(differ)                            # and every difference is a newly scored prose row
    body = lambda s: [l for l in re.sub(r"resolve_forecasts \d{4}-\d{2}-\d{2}:", "R:", s).splitlines()
                      if not l.startswith("R:") and "— Absolute" not in l and "|move|" not in l]
    assert body(oo) == body(no)
    # another lab's prose rows are still listed as unparsed by BOTH versions
    assert [l for l in oo.splitlines() if "SKIP (unparsed): NIFTY" in l] == [l for l in no.splitlines() if "SKIP (unparsed): NIFTY" in l] != []

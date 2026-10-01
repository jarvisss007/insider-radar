"""INS-026 - a queued row is filled at the SETTLED official open, and a disclosed reference gap stays visible. Offline.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins026_settled_fill.py

The defect: stale_quote.fill_queued() filled DFDV (5.83) and ATCH (0.1926) mid-session off the still-forming daily bar,
whose open is the first print; the settled bar carries the official open (5.84, 0.193) that price_audit.py tests.
Writer fix: class (d) (the same one stock-radar took as FILL-002 (d)); the note on each row and the audit TAG are class (a).
The audit does NOT waive anything: whether to restate the two rows or to waive the gap is a ruling (INS-020 / INS-026).

Writer (stale_quote.fill_queued):
 1 the OLD writer fills the in-session first print (the defect, reproduced); the NEW one waits, writes nothing, says why
 2 after the session settles it fills the SETTLED official open, stamped, and never fills twice
 3 the boundary is the estate's: 13:04 PT waits, 13:05 PT fills (sessions.settled_session)
 4 a zero-volume fill session rolls to the next traded bar - and only once THAT bar has settled
 5 a Friday-queued row waits through Monday's session and fills on Tuesday's run
 6 FAILS CLOSED: no calendar, one that raises, or a clock with no time zone -> nothing filled, a loud line, return 2, no row\n   aged toward UNFILLABLE
 6b --dry writes nothing; the branches the fix did not touch (not yet, UNFILLABLE) still report
Audit (price_audit.py):
 7 an undisclosed mismatch fails (exit 1) and is printed UNDISCLOSED
 8 a note that matches exactly only TAGS the row ("disclosed (INS-026), awaiting ruling"): still REF_MISMATCH, still exit 1
 9 a wrong, stale or borrowed note tags nothing (recorded price, official open, day, basis); nor does any fill session from 2026-10-01 on
10 a tagged row beside an untagged one: both stay failing, each shows its own tag; the verdict never depends on the note
10b the audit's own selftest passes
10c the audit FAILS CLOSED with no calendar (it used to treat today as settled at any hour)
10d a stamped "[QUEUED at ..." row is named as queued, with when it fills - not "NO [QUEUED] marker - unfillable row"
11 the two live rows: recorded numbers untouched, unscored, disclosed once, with the reviewer-required wording
12 AGENT.md step 1b tells the daily agent that "has not settled" is expected and a row is never filled by hand
"""
import csv
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AGENT = os.path.join(ROOT, "agent")
QUOTE, QUOTE_OLD = os.path.join(AGENT, "stale_quote.py"), os.path.join(AGENT, "stale_quote_BACKUP_0930_INS-026.py")
AUDIT = os.path.join(ROOT, "price_audit.py")
PY = "/opt/anaconda3/bin/python"
PT = importlib.import_module("zoneinfo").ZoneInfo("America/Los_Angeles")
HEADER = ["date", "ticker", "call", "thesis", "price_at_call", "check_date", "price_at_check", "outcome",
          "stale_quote", "tags", "void_reason"]


def _load(path, name):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _at(y, mo, d, h, mi):
    return dt.datetime(y, mo, d, h, mi, tzinfo=PT)


def _queued(tk="SYN", date="2026-09-28", reg="08:35", live="5.55"):
    th = (f"[insider] 2 insiders bought $0.18M within 14d [QUEUED at {date}T{reg} PT (INS-020/REG-PP-002): written before "
          f"the {date} close settled; the live print {live} is NOT the reference - fills at the first official open "
          f"after registration]")
    return {"date": date, "ticker": tk, "call": "long", "thesis": th, "price_at_call": "", "check_date": "2026-10-28",
            "price_at_check": "", "outcome": "", "stale_quote": "no", "tags": "fund", "void_reason": ""}


def _ledger(tmp_path, rows):
    p = str(tmp_path / "ledger.csv")
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    return p


def _bar(o, v=1_000_000):
    return (o, o + 0.2, o - 0.3, o - 0.1, v)       # (open, high, low, close, volume)


@pytest.fixture
def Q():
    return _load(QUOTE, "q_new_ins026")


@pytest.fixture
def Qold():
    return _load(QUOTE_OLD, "q_old_ins026")


# the same Yahoo reads, whenever they are made: the forming 09-29 bar shows the first print, the settled one the official open
FORMING = {"2026-09-29": _bar(5.83)}
SETTLED = {"2026-09-29": _bar(5.84), "2026-09-30": _bar(5.60)}       # 09-30 is itself still forming on the morning of 09-30


# ---------------------------------------------------------------- 1
def test_01_old_writer_fills_the_first_print_new_writer_waits(tmp_path, monkeypatch, capsys, Q, Qold):
    now = _at(2026, 9, 29, 8, 38)
    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    pa = _ledger(tmp_path / "old", [_queued()])
    monkeypatch.setattr(Qold, "daily_bars", lambda tk, since: FORMING)
    Qold.fill_queued(pa, now=now)
    old = list(csv.DictReader(open(pa)))[0]
    assert old["price_at_call"] == "5.83"                                 # the defect: the in-session first print, recorded as "official"
    # the new writer, same moment, same bar
    pb = _ledger(tmp_path / "new", [_queued()])
    before = open(pb, "rb").read()
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: FORMING)
    capsys.readouterr()
    rc = Q.fill_queued(pb, now=now)
    out = capsys.readouterr().out
    assert rc == 0 and open(pb, "rb").read() == before                    # nothing written
    assert "the 2026-09-29 session has not settled" in out and "0 filled, 1 still queued" in out


# ---------------------------------------------------------------- 2
def test_02_fills_the_settled_open_after_the_session_and_only_once(tmp_path, monkeypatch, capsys, Q):
    p = _ledger(tmp_path, [_queued()])
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: SETTLED)
    Q.fill_queued(p, now=_at(2026, 9, 30, 8, 35))
    r = list(csv.DictReader(open(p)))[0]
    assert r["price_at_call"] == "5.84"
    assert "[FILLED 2026-09-29 official open 5.84 (REG-PP-002 queued-fill, INS-020)]" in r["thesis"]
    assert r["outcome"] == "" and r["check_date"] == "2026-10-28"        # the fill session and check_date are what they were
    again = open(p, "rb").read()
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: {"2026-09-29": _bar(9.99)})
    Q.fill_queued(p, now=_at(2026, 9, 30, 14, 0))
    assert open(p, "rb").read() == again                                  # idempotent: a filled row is never refilled


# ---------------------------------------------------------------- 3
@pytest.mark.parametrize("hm,filled", [((13, 4), False), ((13, 5), True)])
def test_03_boundary_is_the_estates_settled_session(tmp_path, monkeypatch, Q, hm, filled):
    p = _ledger(tmp_path, [_queued()])
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: {"2026-09-29": _bar(5.84)})
    Q.fill_queued(p, now=_at(2026, 9, 29, *hm))
    assert (list(csv.DictReader(open(p)))[0]["price_at_call"] == "5.84") is filled


# ---------------------------------------------------------------- 4
def test_04_zero_volume_fill_session_rolls_forward_only_to_a_settled_bar(tmp_path, monkeypatch, Q):
    p = _ledger(tmp_path, [_queued()])
    bars = {"2026-09-29": _bar(5.83, v=0), "2026-09-30": _bar(5.90, v=500)}   # 09-29 never traded; 09-30 is the first traded bar
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: bars)
    Q.fill_queued(p, now=_at(2026, 9, 30, 8, 35))                       # 09-30 is still forming: its open is provisional
    assert list(csv.DictReader(open(p)))[0]["price_at_call"] == ""
    Q.fill_queued(p, now=_at(2026, 9, 30, 13, 10))                      # after 09-30 settles: its official open
    r = list(csv.DictReader(open(p)))[0]
    assert r["price_at_call"] == "5.90" and "[FILLED 2026-09-30 official open 5.90" in r["thesis"]


# ---------------------------------------------------------------- 5
def test_05_friday_queue_waits_through_monday_and_fills_on_tuesday(tmp_path, monkeypatch, Q):
    p = _ledger(tmp_path, [_queued(date="2026-09-25")])
    bars = {"2026-09-28": _bar(7.10), "2026-09-29": _bar(7.30)}
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: bars)
    Q.fill_queued(p, now=_at(2026, 9, 28, 8, 35))                       # Monday morning: Monday has not settled
    assert list(csv.DictReader(open(p)))[0]["price_at_call"] == ""
    Q.fill_queued(p, now=_at(2026, 9, 29, 8, 35))                       # Tuesday morning: Monday's settled open
    assert list(csv.DictReader(open(p)))[0]["price_at_call"] == "7.10"


# ---------------------------------------------------------------- 6 fails closed
def _boom(*a, **k):
    raise RuntimeError("calendar exhausted")


@pytest.mark.parametrize("fault", ["no_calendar", "calendar_raises"])
def test_06_no_calendar_fills_nothing_says_so_and_ages_no_row(tmp_path, monkeypatch, capsys, Q, fault):
    if fault == "no_calendar":
        monkeypatch.setattr(Q, "_SESS", None)
    else:
        monkeypatch.setattr(Q._SESS, "settled_session", _boom)
    p = _ledger(tmp_path, [_queued(), _queued(date="2026-09-10", tk="OLD")])    # OLD is 19 days past its fill session
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: {"2026-09-29": _bar(5.84), "2026-09-11": _bar(3.0)})
    before = open(p, "rb").read()
    capsys.readouterr()
    rc = Q.fill_queued(p, now=_at(2026, 9, 30, 14, 0))
    out = capsys.readouterr().out
    assert rc == 2 and open(p, "rb").read() == before                      # nothing written, non-zero exit
    assert "CALENDAR UNAVAILABLE" in out and "NOTHING is filled" in out
    assert "UNFILLABLE" not in out                                          # a fault is not evidence a row can never fill


def test_06a_a_clock_with_no_time_zone_fills_nothing(tmp_path, monkeypatch, capsys, Q):
    p = _ledger(tmp_path, [_queued()])
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: SETTLED)
    before = open(p, "rb").read()
    rc = Q.fill_queued(p, now=dt.datetime(2026, 9, 30, 14, 0))             # naive: the PT clock is not known to be PT
    assert rc == 2 and open(p, "rb").read() == before and "CALENDAR UNAVAILABLE" in capsys.readouterr().out


def test_06b_dry_writes_nothing_and_the_untouched_branches_still_report(tmp_path, monkeypatch, capsys, Q):
    p = _ledger(tmp_path, [_queued(date="2026-09-30", tk="FUT"), _queued(date="2026-09-10", tk="OLD"), _queued()])
    monkeypatch.setattr(Q, "daily_bars", lambda tk, since: SETTLED if tk == "SYN" else {})
    before = open(p, "rb").read()
    Q.fill_queued(p, now=_at(2026, 9, 30, 14, 0), dry=True)
    assert open(p, "rb").read() == before                                   # --dry writes nothing
    out = capsys.readouterr().out
    assert "FILLED  SYN 2026-09-28 -> 2026-09-29 open 5.84" in out          # what a real run would do
    assert "FUT 2026-09-30: fills at the 2026-10-01 open (not yet)" in out  # a fill session in the future still says so
    assert "OLD 2026-09-10: no traded open on/after 2026-09-11 yet" in out and "UNFILLABLE so far" in out
    Q.fill_queued(p, now=_at(2026, 9, 30, 14, 0))
    got = {r["ticker"]: r["price_at_call"] for r in csv.DictReader(open(p))}
    assert got == {"FUT": "", "OLD": "", "SYN": "5.84"}


# ---------------------------------------------------------------- audit rows
NOTE = " [REF-GAP INS-026: recorded 5.83 vs settled official open 5.84 on 2026-09-29 (gap -0.01, -0.171%). fixture]"
FILLED = ("[insider] 2 insiders bought $0.18M within 14d [QUEUED at 2026-09-28T08:35 PT (INS-020/REG-PP-002): fixture] "
          "[FILLED 2026-09-29 official open 5.83 (REG-PP-002 queued-fill, INS-020)]")
BARS = {"2026-09-28": [5.30, 5.90, 5.70, 5.50, 1000], "2026-09-29": [5.40, 5.87, 5.84, 5.57, 1889400],
        "2026-10-01": [5.30, 5.95, 5.84, 5.60, 800]}


def _audit(tmp_path, rows, cache=None, *args, patch_quote=None):
    """price_audit.py as shipped, run in a scratch root (its own ledger, its own bar cache - no network, no live file)."""
    root = tmp_path / "root"
    (root / "agent").mkdir(parents=True)
    (root / "data").mkdir()
    shutil.copy(AUDIT, root / "price_audit.py")
    shutil.copy(QUOTE, root / "agent" / "stale_quote.py")
    if patch_quote:
        t = open(root / "agent" / "stale_quote.py").read()
        open(root / "agent" / "stale_quote.py", "w").write(patch_quote(t))
    with open(root / "agent" / "ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    json.dump(cache or {}, open(root / "data" / "price_audit_cache.json", "w"))
    r = subprocess.run([PY, str(root / "price_audit.py"), "--open-only", *args], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def _row(tk, thesis, price, date="2026-09-28", **kw):
    r = {"date": date, "ticker": tk, "call": "long", "thesis": thesis, "price_at_call": price, "check_date": "2026-10-28",
         "price_at_check": "", "outcome": "", "stale_quote": "no", "tags": "fund", "void_reason": ""}
    r.update(kw)
    return r


def _counts(out):
    m = re.search(r"REF_OK (\d+)\s+REF_MISMATCH (\d+)\s+REF_LEGACY (\d+)\s+REF_PENDING (\d+)", out)
    return tuple(map(int, m.groups()))


def _line(out, tk):
    return [l for l in out.splitlines() if l.strip().startswith(f"REF_MISMATCH {tk}")][0]


# ---------------------------------------------------------------- 7
def test_07_an_undisclosed_mismatch_fails_and_is_printed_undisclosed(tmp_path):
    rc, out = _audit(tmp_path, [_row("SYA", FILLED, "5.83")], {"SYA": BARS})
    assert rc == 1 and _counts(out) == (0, 1, 0, 0)
    assert _line(out, "SYA").endswith("| UNDISCLOSED") and "1 are UNDISCLOSED" not in out    # no note -> no disclosure sentence at all
    assert "FAIL" in out


# ---------------------------------------------------------------- 8
def test_08_an_exact_note_only_tags_the_row_it_does_not_waive_it(tmp_path):
    rc, out = _audit(tmp_path, [_row("SYA", FILLED + NOTE, "5.83")], {"SYA": BARS})
    assert rc == 1 and _counts(out) == (0, 1, 0, 0)                       # still REF_MISMATCH, still failing
    assert _line(out, "SYA").endswith("| disclosed (INS-026), awaiting ruling")
    assert "1 of them carry a matching [REF-GAP INS-026] disclosure and await a ruling" in out and "0 are UNDISCLOSED" in out
    # the same fact in the machine-readable output, for the resolver check
    rc, js = _audit(tmp_path / "j", [_row("SYA", FILLED + NOTE, "5.83")], {"SYA": BARS}, "--json")
    rec = json.loads(js)["REF_MISMATCH"]
    assert rc == 1 and len(rec) == 1 and rec[0]["disclosed"] is True and "REF_DISCLOSED" not in json.loads(js)


# ---------------------------------------------------------------- 9
@pytest.mark.parametrize("why,thesis,price", [
    ("another recorded price", FILLED + NOTE.replace("recorded 5.83", "recorded 5.82"), "5.83"),
    ("another official open", FILLED + NOTE.replace("open 5.84", "open 5.90"), "5.83"),
    ("another day", FILLED + NOTE.replace("on 2026-09-29", "on 2026-09-30"), "5.83"),
    ("the price moved after the note", FILLED + NOTE, "5.80"),
    ("no queued-fill basis", "[insider] 2 insiders bought $0.18M within 14d" + NOTE, "5.83"),
])
def test_09_a_wrong_stale_or_borrowed_note_tags_nothing(tmp_path, why, thesis, price):
    rc, out = _audit(tmp_path, [_row("SYA", thesis, price)], {"SYA": BARS})
    assert rc == 1 and _counts(out)[1] == 1, why
    assert _line(out, "SYA").endswith("| UNDISCLOSED"), why


# ---------------------------------------------------------------- 10
def test_10_one_note_hides_no_other_row_and_never_changes_a_verdict(tmp_path):
    rc, out = _audit(tmp_path, [_row("SYA", FILLED + NOTE, "5.83"), _row("SYC", FILLED, "5.83")], {"SYA": BARS, "SYC": BARS})
    assert rc == 1 and _counts(out) == (0, 2, 0, 0)
    assert _line(out, "SYA").endswith("awaiting ruling") and _line(out, "SYC").endswith("UNDISCLOSED")
    assert "1 of them carry a matching" in out and "1 are UNDISCLOSED" in out
    # the same row with and without the note: identical bucket and exit code
    a = _audit(tmp_path / "w", [_row("SYA", FILLED + NOTE, "5.83")], {"SYA": BARS})
    b = _audit(tmp_path / "n", [_row("SYA", FILLED, "5.83")], {"SYA": BARS})
    assert a[0] == b[0] == 1 and _counts(a[1]) == _counts(b[1])
    # a post-fix style fill (session 2026-10-01) with a typed note is still a failing mismatch
    postfix = ("[insider] 2 insiders bought $0.18M within 14d [QUEUED at 2026-09-30T08:35 PT (INS-020/REG-PP-002): fixture] "
               "[FILLED 2026-10-01 official open 5.83 (REG-PP-002 queued-fill, INS-020)]" + NOTE.replace("2026-09-29", "2026-10-01"))
    bars_b = {"2026-09-30": [5.30, 5.90, 5.70, 5.50, 1000], "2026-10-01": BARS["2026-10-01"]}
    rc, out = _audit(tmp_path / "pf", [_row("SYB", postfix, "5.83", date="2026-09-30")], {"SYB": bars_b})
    assert rc == 1 and _counts(out)[1] == 1 and _line(out, "SYB").endswith("| UNDISCLOSED")     # never tagged from the fix date on


def test_10b_the_audits_own_selftest_passes():
    r = subprocess.run([PY, AUDIT, "--selftest"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "selftest: all passed" in r.stdout and "disclosure tag:" in r.stdout


def test_10c_the_audit_fails_closed_with_no_calendar(tmp_path):
    no_cal = lambda t: re.sub(r'"[^"\n]*/stock-radar/sessions\.py"', '"/nonexistent/sessions.py"', t)     # the calendar cannot load
    rc, out = _audit(tmp_path, [_row("SYA", FILLED, "5.83")], {"SYA": BARS}, patch_quote=no_cal)
    assert rc == 2 and "the sessions calendar is unavailable" in out and "nothing is cached or tested" in out   # 2 = could not look
    assert "REF_OK" not in out                                              # no verdict is produced on a guess


def test_10d_a_stamped_queued_row_is_named_queued_with_when_it_fills(tmp_path):
    queued = _queued(tk="SYQ", date="2026-09-30")["thesis"]
    rc, out = _audit(tmp_path, [_row("SYQ", queued, "", date="2026-09-30"), _row("SYU", "[insider] x", "", date="2026-09-30")])
    lines = {l.split()[1]: l for l in out.splitlines() if l.strip().startswith("QUEUED")}
    assert "[QUEUED] present - fills after the 2026-10-01 session settles (INS-026)" in lines["SYQ"]
    assert "NO [QUEUED] marker" not in lines["SYQ"]
    assert "price_at_call empty and NO [QUEUED] marker" in lines["SYU"]      # a blank price with no marker is still INS-007


# ---------------------------------------------------------------- 11 the two live rows
def test_11_the_two_live_rows_keep_their_recorded_numbers_and_carry_the_disclosure():
    rows = {(r["ticker"], r["date"]): r for r in csv.DictReader(open(os.path.join(AGENT, "ledger.csv")))}
    want = {("DFDV", "2026-09-28"): ("5.83", "5.84", "2026-09-29", "2026-10-28"),
            ("ATCH", "2026-09-29"): ("0.1926", "0.193", "2026-09-30", "2026-10-29")}
    for key, (rec, off, day, check) in want.items():
        r = rows[key]
        assert r["price_at_call"] == rec                                   # the recorded number stands
        assert r["outcome"] == "" and r["price_at_check"] == ""            # and the row is unscored
        t = r["thesis"]
        assert f"[REF-GAP INS-026: recorded {rec} vs settled official open {off} on {day}" in t
        assert f"[FILLED {day} official open {rec} " in t                   # the original fill stamp is still there, unedited
        assert t.count("[REF-GAP INS-026:") == 1
        assert "Recorded value unchanged pending a ruling (INS-026)" in t and f"freezes it at scoring on {check}" in t
        assert f"the outcome differs only if the 30-day close lands in ({rec}, {off}]" in t     # the flip band
        assert "NOT restated" not in t and "fixed forward" not in t       # no disposition claim, no claim the writer is verified
        assert "$" not in t.split("[REF-GAP")[1] and "VOIDED" not in t     # nothing a downstream thesis parser keys on


# ---------------------------------------------------------------- 12 the lab's instructions
def test_12_agent_step_1b_says_waiting_is_expected_and_rows_are_never_hand_filled():
    t = open(os.path.join(AGENT, "AGENT.md")).read()
    i = t.index("1b. **Fill queued calls")
    j = t.index("2. **Score due calls", i)
    s = t[i:j]
    assert "INS-026" in s and "has not settled" in s and "never fill or price a row by hand" in s
    assert "REF_OK / REF_MISMATCH / REF_LEGACY / REF_PENDING" in s          # the audit's verdict names are unchanged

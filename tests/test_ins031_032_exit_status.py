"""INS-031 + INS-032 - the insider price audit FAILS when it cannot check a row, and the residual exit-0 paths are closed. Offline.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins031_032_exit_status.py

INS-031 (ruled by Anupam 2026-10-04, option (a)): exit 3 on any unverifiable OPEN row - UNFETCHABLE, or NO_BAR for a settled day - with a ONE-SESSION GRACE: a bar
missing for the latest settled session alone does not fail; the same row one session later does. INS-032 (decided under that policy): a blank price with no
[QUEUED] marker fails (BLANK, exit 1); a queued row past its fill session fails (QUEUED_OVERDUE, exit 3) while one before it is legitimately pending; REF_PENDING
is pending only while the owed session has not settled (grace on the latest settled one, exit 3 before it).
Every test runs the audit as shipped in a scratch root with a stubbed network and a pinned settled session (the helpers of test_ins029_price_audit.py).
 1 the grace: a row dated the latest settled session with no bar exits 0 (tagged grace); the SAME row once the next session has settled exits 3
 2 an older settled session's missing bar exits 3; a Saturday call date exits 3; a 404 and a 429 both exit 3 (never cached as a verdict)
 3 BLANK: a blank price with no [QUEUED] marker exits 1, names the row, and is no longer filed under QUEUED
 4 QUEUED before its fill session (and AT the latest settled session: the filler has not run since) is pending, exit 0, reads nothing; PAST it exits 3, still reads nothing
 5 a fill session that cannot be computed is overdue, not pending
 6 REF_PENDING: the latest settled session = grace (exit 0); an older one = past the settle point (exit 3); null-close non-queued rows follow the same rule
 7 the exit-code table: violation > unverified > waiting; BLANK is a violation; waiting rows never fail
 8 --json carries the same exit status and the new buckets, and stays pure JSON
 9 the live-shaped regression: a priced row inside its bar and a QUEUED row before its fill session exit 0 (the INS-028 monitor stays green on a healthy book)
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_ins029_price_audit import (GOOD, SETTLED, _chart, _http, _ledger, _main, _row, _Source, pa)  # noqa: F401,E402  (pa is a fixture)

QUEUED_0930 = ("[insider] x [QUEUED at 2026-09-30T08:35 PT (INS-020/REG-PP-002): written before the 2026-09-30 close settled; "
               "fills at the first official open after registration]")           # registered after the open -> fill session 2026-10-01


def _pin(pa, monkeypatch, day):
    monkeypatch.setattr(pa, "_settled_day", lambda: day)


# ---------------------------------------------------------------- 1
def test_01_the_latest_settled_session_gets_one_session_of_grace_and_not_two(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", SETTLED, "10.0")])                      # SETTLED = 2026-10-01; the source serves 09-29 and 09-30 only
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "NO_BAR 1" in out and "inside the one-session grace" in out and "UNVERIFIED" not in out
    assert "WAITING — 1 row(s)" in out and "OK for the rows it could check - not for the WAITING rows above." in out
    # the next session has settled and the same bar is STILL missing: the grace is spent
    _pin(pa, monkeypatch, "2026-10-02")
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 3 and "no bar dated 2026-10-01 for SYA" in out and "inside the one-session grace" not in out
    assert "UNVERIFIED — 1 open row(s)" in out and "NO_BAR 1" in out and "Exit 3." in out
    b = pa.audit(open_only=True)
    assert "grace" not in b["NO_BAR"][0] and "unsettled" not in b["NO_BAR"][0]


# ---------------------------------------------------------------- 2
def test_02_older_gaps_and_every_failed_read_exit_3(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-09-28", "10.0")])                 # an older settled session with no bar
    _Source(monkeypatch, pa, _chart(GOOD))
    assert _main(pa, monkeypatch, capsys)[0] == 3
    _ledger(pa, [_row("SYB", "2026-09-26", "10.0")])                 # a Saturday: no bar can exist
    _Source(monkeypatch, pa, _chart(GOOD))
    assert _main(pa, monkeypatch, capsys)[0] == 3
    for err in (_http(404), _http(429), _http(503)):
        _ledger(pa, [_row("GONE", "2026-09-29", "10.0")])
        _Source(monkeypatch, pa, err)
        rc, out = _main(pa, monkeypatch, capsys)
        assert rc == 3 and "UNFETCHABLE 1" in out, err
        assert pa.NOT_FOUND in json.load(open(pa.CACHE)) or json.load(open(pa.CACHE)) == {}            # never a permanent per-ticker verdict
        assert "GONE" not in json.load(open(pa.CACHE))


# ---------------------------------------------------------------- 3
def test_03_a_blank_price_with_no_queued_marker_fails(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-09-29", "", "[insider] x - the writer left the price blank and never queued it")])
    src = _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 1 and "BLANK 1" in out and "QUEUED 0" in out and "NO [QUEUED] marker" in out
    assert "FAIL — 1 row(s) carry no price and no [QUEUED] marker" in out and "OK" not in out.split("FAIL —")[-1]
    assert src.calls == 0                                              # nothing to read for an unpriced row
    b = pa.audit(open_only=True)
    assert len(b["BLANK"]) == 1 and b["QUEUED"] == [] and b["QUEUED_OVERDUE"] == [] and pa.exit_code(b) == 1
    # a violation wins over an unverified neighbour
    _ledger(pa, [_row("SYA", "2026-09-29", "", "[insider] x"), _row("SYB", "2026-09-29", "10.0")])
    _Source(monkeypatch, pa, _http(429))
    assert _main(pa, monkeypatch, capsys)[0] == 1


# ---------------------------------------------------------------- 4
def test_04_a_queued_row_is_pending_until_its_fill_session_is_behind_the_latest_settled_one(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYQ", "2026-09-30", "", QUEUED_0930)])        # fill session 2026-10-01
    src = _Source(monkeypatch, pa, _http(429))                       # a queued row has no price to audit: never read
    _pin(pa, monkeypatch, "2026-09-30")                              # before its fill session
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "QUEUED 1" in out and "QUEUED_OVERDUE 0" in out and "fills after the 2026-10-01 session settles" in out
    _pin(pa, monkeypatch, "2026-10-01")                              # the fill session has just settled: the filler has not had a run since
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "QUEUED 1" in out and "QUEUED_OVERDUE 0" in out
    _pin(pa, monkeypatch, "2026-10-02")                              # a full session later and still blank: PAST its fill session
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 3 and "QUEUED_OVERDUE 1" in out and "QUEUED 0" in out and "past its fill session 2026-10-01" in out
    assert "UNVERIFIED — 1 open row(s)" in out and "QUEUED_OVERDUE 1" in out and "Exit 3." in out
    assert src.calls == 0                                            # the verdict needs no read at all
    # a row stamped before the open fills at THAT day's open
    early = QUEUED_0930.replace("2026-09-30T08:35", "2026-10-01T05:10")
    _ledger(pa, [_row("SYE", "2026-10-01", "", early)])
    _pin(pa, monkeypatch, "2026-10-01")
    assert _main(pa, monkeypatch, capsys)[0] == 0
    _pin(pa, monkeypatch, "2026-10-02")
    assert _main(pa, monkeypatch, capsys)[0] == 3


# ---------------------------------------------------------------- 5
def test_05_a_fill_session_that_cannot_be_computed_is_not_pending(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYQ", "2026-09-30", "", QUEUED_0930)])
    _pin(pa, monkeypatch, "2026-09-30")
    monkeypatch.setattr(pa._Q, "fill_session_for", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("calendar")))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 3 and "QUEUED_OVERDUE 1" in out and "could not be computed" in out


# ---------------------------------------------------------------- 6
ZV = {"2026-09-29": (9.0, 11.0, 9.5, 10.0, 1000), "2026-09-30": (11.0, 11.0, 11.0, 11.0, 0)}          # 09-30 printed nothing: a zero-volume carry-forward


def test_06_ref_pending_is_pending_only_while_the_owed_session_is_not_behind_the_latest_settled_one(pa, monkeypatch, capsys):
    filled = ("[insider] x [QUEUED at 2026-09-29T09:00 PT] [FILLED 2026-09-30 official open 11.0]")   # fill session 09-30: zero volume -> the owed open rolls on
    _ledger(pa, [_row("SYZ", "2026-09-29", "11.0", filled)])
    _pin(pa, monkeypatch, "2026-09-30")                              # 09-30 is the latest settled session and has not traded yet: the grace
    _Source(monkeypatch, pa, _chart(ZV))
    b = pa.audit(open_only=True)
    assert len(b["REF_PENDING"]) == 1 and b["REF_PENDING"][0]["grace"] is True and "waiting" not in b["REF_PENDING"][0] and pa.exit_code(b) == 0
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "REF_PENDING 1" in out and "inside the one-session grace" in out
    _pin(pa, monkeypatch, "2026-10-01")                              # a later session settled and the source still serves no traded bar after 09-30
    _Source(monkeypatch, pa, _chart(ZV))
    b = pa.audit(open_only=True)
    assert len(b["REF_PENDING"]) == 1 and not b["REF_PENDING"][0].get("grace") and not b["REF_PENDING"][0].get("waiting") and pa.exit_code(b) == 3
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 3 and "PAST THE SETTLE POINT" in out and "UNVERIFIED — 1 open row(s)" in out and "REF_PENDING 1" in out
    # a non-queued row whose settled bar carries a null close
    nc = {"2026-09-29": (9.0, 11.0, 9.5, None, 1000), "2026-09-30": (9.5, 11.5, 10.0, 10.5, 900)}
    _ledger(pa, [_row("SYN", "2026-09-29", "10.0")])
    _pin(pa, monkeypatch, "2026-09-30")
    _Source(monkeypatch, pa, _chart(nc))
    b = pa.audit(open_only=True)
    assert len(b["REF_PENDING"]) == 1 and not b["REF_PENDING"][0].get("grace") and pa.exit_code(b) == 3      # 09-29 is behind the latest settled 09-30
    _ledger(pa, [_row("SYM", "2026-09-30", "10.0")])
    _Source(monkeypatch, pa, _chart({"2026-09-29": (9.0, 11.0, 9.5, 10.0, 1000), "2026-09-30": (9.5, 11.5, 10.0, None, 900)}))
    b = pa.audit(open_only=True)
    assert len(b["REF_PENDING"]) == 1 and b["REF_PENDING"][0]["grace"] is True and pa.exit_code(b) == 0       # 09-30 IS the latest settled


# ---------------------------------------------------------------- 7
def test_07_the_exit_code_table(pa):
    base = {k: [] for k in ("PASS", "FAIL", "NO_BAR", "UNFETCHABLE", "QUEUED", "VOID", "REF_OK", "REF_MISMATCH", "REF_LEGACY", "REF_PENDING", "BLANK", "QUEUED_OVERDUE")}
    ec = pa.exit_code
    assert ec(base) == 0
    assert ec({**base, "QUEUED": [{}], "VOID": [{}], "REF_LEGACY": [{}]}) == 0                                # pending / excluded / reported-only: green
    assert ec({**base, "NO_BAR": [{"unsettled": True}, {"grace": True}]}) == 0                                # waiting + grace: green
    assert ec({**base, "REF_PENDING": [{"waiting": True}, {"grace": True}]}) == 0
    assert ec({**base, "NO_BAR": [{"unsettled": True}, {}]}) == 3                                             # one plain NO_BAR is enough
    assert ec({**base, "UNFETCHABLE": [{}]}) == 3
    assert ec({**base, "REF_PENDING": [{}]}) == 3
    assert ec({**base, "QUEUED_OVERDUE": [{}]}) == 3
    assert ec({**base, "FAIL": [{}], "UNFETCHABLE": [{}]}) == 1                                               # a violation wins
    assert ec({**base, "REF_MISMATCH": [{}], "NO_BAR": [{}]}) == 1
    assert ec({**base, "BLANK": [{}], "QUEUED_OVERDUE": [{}]}) == 1                                           # BLANK is a violation
    assert ec({"PASS": [], "FAIL": [], "REF_MISMATCH": []}) == 0                                              # an old-shape dict (no new buckets) still reads
    assert {k for k, _r, _w in pa.unverified({**base, "NO_BAR": [{}], "UNFETCHABLE": [{}], "REF_PENDING": [{}], "QUEUED_OVERDUE": [{}]})} == {
        "NO_BAR", "UNFETCHABLE", "REF_PENDING", "QUEUED_OVERDUE"}


# ---------------------------------------------------------------- 8
def test_08_json_mode_carries_the_exit_status_and_the_new_buckets(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYQ", "2026-09-30", "", QUEUED_0930), _row("SYB", "2026-09-29", "", "[insider] x")])
    _pin(pa, monkeypatch, "2026-10-02")
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys, "--json")
    d = json.loads(out)                                              # stdout is pure JSON
    assert rc == 1 and len(d["BLANK"]) == 1 and d["BLANK"][0]["ticker"] == "SYB" and len(d["QUEUED_OVERDUE"]) == 1 and d["QUEUED_OVERDUE"][0]["ticker"] == "SYQ"
    assert d["QUEUED_OVERDUE"][0]["fill_session"] == "2026-10-01" and d["QUEUED"] == []
    _ledger(pa, [_row("SYQ", "2026-09-30", "", QUEUED_0930)])
    rc, out = _main(pa, monkeypatch, capsys, "--json")
    assert rc == 3 and json.loads(out)["QUEUED_OVERDUE"][0]["ticker"] == "SYQ"


# ---------------------------------------------------------------- 9
def test_09_a_healthy_book_stays_green(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-09-29", "10.0"), _row("SYQ", "2026-09-30", "", QUEUED_0930)])
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "PASS 1" in out and "QUEUED 1" in out and "OK — every priced row sits inside its call-day bar." in out

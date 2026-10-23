"""PORT-006 - append_call() reads the firm-wide halt (stock-radar/firm_halt.py) and, under one, still APPENDS the call (the lab's own
scored record, prereg P5) but with the ACCOUNT-WITHHELD marker and a row in agent/halt_refusals_insider.csv. Offline; temp HALTS.json
through the `halts` seam; the live HALTS.json is never read or written here.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_port006_append_call_gate.py
"""
import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
import stale_quote as sq

FIRM_HALT = os.path.join(os.path.expanduser("~"), "stock-radar", "firm_halt.py")
pytestmark = pytest.mark.skipif(not os.path.exists(FIRM_HALT), reason="needs stock-radar/firm_halt.py")


def _row(t="ACME", call="long"):
    return {"date": "2026-10-01", "ticker": t, "call": call, "thesis": "[insider] 2 insiders bought $1.0M within 14d", "price_at_call": "10.00",
            "check_date": "2026-10-30", "stale_quote": "no", "tags": "fund", "void_reason": ""}


def _rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def harness(monkeypatch, tmp_path):
    monkeypatch.setattr(sq, "issuer_quote_type", lambda tk: "EQUITY")
    monkeypatch.setattr(sq, "call_day_settled", lambda *a, **k: True)
    led = tmp_path / "ledger.csv"
    halts = tmp_path / "HALTS.json"

    def go(halted, row=None):
        if halted is not None:
            halts.write_text(json.dumps({"halted": halted}))
        return sq.append_call(row or _row(), ledger=str(led), halts=str(halts)), led
    return go, led, tmp_path


def test_no_firm_halt_the_row_is_unchanged(harness):
    go, led, tmp = harness
    r, _ = go({"position": "the desk's own halt is not a firm-wide key"})
    rows = _rows(led)
    assert len(rows) == 1 and rows[0]["ticker"] == "ACME" and "[ACCOUNT-WITHHELD" not in rows[0]["thesis"]
    assert not os.path.exists(tmp / "halt_refusals_insider.csv")


def test_kill_key_keeps_the_call_marks_it_and_records_the_refusal(harness):
    go, led, tmp = harness
    r, _ = go({"portfolio-kill": "2026-09-30"})
    rows = _rows(led)
    assert len(rows) == 1 and rows[0]["ticker"] == "ACME" and rows[0]["price_at_call"] == "10.00"        # the lab's scored call is kept
    assert rows[0]["thesis"].startswith("[insider] 2 insiders")                                           # lead tags untouched (TAG-004)
    assert "[ACCOUNT-WITHHELD PORT-006: portfolio-kill since 2026-09-30" in rows[0]["thesis"]
    rec = _rows(tmp / "halt_refusals_insider.csv")
    assert len(rec) == 1 and rec[0]["desk"] == "insider" and rec[0]["ticker"] == "ACME" and rec[0]["side"] == "long"
    assert rec[0]["halt_class"] == "portfolio-kill" and rec[0]["halt_since"] == "2026-09-30" and rec[0]["date"] == "2026-10-01"


def test_regime_key_withholds_a_long_and_passes_a_short(harness):
    go, led, tmp = harness
    go({"portfolio-regime": {"since": "2026-09-30"}}, _row("LNG", "long"))
    go(None, _row("SHT", "short"))
    rows = {r["ticker"]: r for r in _rows(led)}
    assert "[ACCOUNT-WITHHELD" in rows["LNG"]["thesis"] and "[ACCOUNT-WITHHELD" not in rows["SHT"]["thesis"]
    assert [r["ticker"] for r in _rows(tmp / "halt_refusals_insider.csv")] == ["LNG"]


def test_unreadable_halts_withholds_never_assumes_no_halt(harness):
    go, led, tmp = harness
    r, _ = go(None)                                            # HALTS.json never written: missing
    rows = _rows(led)
    assert "[ACCOUNT-WITHHELD PORT-006: HALTS-unreadable" in rows[0]["thesis"]
    assert _rows(tmp / "halt_refusals_insider.csv")[0]["halt_class"] == "HALTS-unreadable"

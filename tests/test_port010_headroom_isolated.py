"""PORT-010: no test in this repo can reach the firm's live settled reading or its live admissions record (conftest's autouse fixture).
The headroom test itself is tested in stock-radar/tests/test_port010_headroom.py. Skipped where stock-radar is not on the machine."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent"))
import stale_quote as sq


def test_the_firm_gate_is_isolated_for_every_test_here(tmp_path):
    fh = sq._firm_halt()
    if fh is None or not hasattr(fh, "HEADROOM_FROM"):
        pytest.skip("stock-radar/firm_halt.py (with the PORT-010 headroom test) is not on this machine")
    live = os.path.join(os.path.expanduser("~"), "stock-radar")
    assert fh.HEADROOM_FROM == "" and fh.headroom_in_force("insider") is False
    for name in ("RISK_FILE", "ADMITS", "IPO_STRATEGY"):
        assert not os.path.abspath(getattr(fh, name)).startswith(live + os.sep), name
    before = os.path.exists(os.path.join(live, "agent", "budget_admits.csv")), os.path.getsize(os.path.join(live, "agent", "budget_admits.csv")) if os.path.exists(os.path.join(live, "agent", "budget_admits.csv")) else None
    row = {"date": "2026-10-01", "ticker": "ZZZT", "call": "long", "thesis": "[insider] test row", "price_at_call": "10.00"}
    sq.append_call(row, ledger=str(tmp_path / "ledger.csv"), check_issuer_type=False)             # no `halts=`: the case the fixture exists for
    after = os.path.exists(os.path.join(live, "agent", "budget_admits.csv")), os.path.getsize(os.path.join(live, "agent", "budget_admits.csv")) if os.path.exists(os.path.join(live, "agent", "budget_admits.csv")) else None
    assert before == after

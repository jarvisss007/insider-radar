"""INS-030 - append_call() refuses non-equity issuers (funds, ETFs); an unverifiable issuer type is refused too. Offline.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins030_equity_only.py
"""
import os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
import stale_quote as sq


def _row(t="ACME"):
    return {"date": "2026-10-01", "ticker": t, "call": "long", "thesis": "t", "price_at_call": "10.00",
            "check_date": "2026-10-31", "stale_quote": "no", "tags": "fund", "void_reason": ""}


def _go(monkeypatch, tmp_path, qt, t="ACME"):
    monkeypatch.setattr(sq, "issuer_quote_type", lambda tk: qt)
    monkeypatch.setattr(sq, "call_day_settled", lambda *a, **k: True)
    led = tmp_path / "ledger.csv"
    return sq.append_call(_row(t), ledger=str(led)), led


def test_equity_passes(monkeypatch, tmp_path):
    _, led = _go(monkeypatch, tmp_path, "EQUITY")
    assert "ACME" in led.read_text()


@pytest.mark.parametrize("qt,t", [("MUTUALFUND", "BBASX"), ("ETF", "SPY"), ("MONEYMARKET", "X"), ("INDEX", "Y")])
def test_non_equity_refused(monkeypatch, tmp_path, qt, t):
    with pytest.raises(ValueError, match="INS-030"):
        _go(monkeypatch, tmp_path, qt, t)
    assert not (tmp_path / "ledger.csv").exists()


def test_lookup_failure_refused(monkeypatch, tmp_path):
    def boom(tk):
        raise RuntimeError("network down")
    monkeypatch.setattr(sq, "issuer_quote_type", boom)
    with pytest.raises(ValueError, match="issuer type unverifiable"):
        sq.append_call(_row(), ledger=str(tmp_path / "ledger.csv"))
    assert not (tmp_path / "ledger.csv").exists()


def test_empty_quotetype_refused(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="unverifiable"):
        _go(monkeypatch, tmp_path, None)


def test_explicit_skip_for_tests(monkeypatch, tmp_path):
    monkeypatch.setattr(sq, "issuer_quote_type", lambda tk: (_ for _ in ()).throw(AssertionError("must not be called")))
    monkeypatch.setattr(sq, "call_day_settled", lambda *a, **k: True)
    sq.append_call(_row(), ledger=str(tmp_path / "l.csv"), check_issuer_type=False)

# Pre-edit snapshots (NAME_BACKUP_<date>_<id>.py) are kept beside the file they back up; they are not suites.
collect_ignore_glob = ["*_BACKUP_*"]


# PORT-010 (stock-radar/firm_halt.py, 2026-11-14): append_call() loads the firm's gate by path. Since the pre-entry headroom test, a
# call made with no `halts=` would read the firm's LIVE settled reading and write its LIVE admissions record (a phantom $2,000
# insider admission that counts against the desk's real room). No test here may: every test gets the headroom test switched OFF and
# scratch paths for the reading and the record, patched on the by-path module itself. The headroom test's own suite is
# stock-radar/tests/test_port010_headroom.py.
import os as _os
import sys as _sys

import pytest as _pytest

_AGENT = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "agent")
HEADROOM_PATHS = (("RISK_FILE", "portfolio_risk.json"), ("ADMITS", "budget_admits.csv"), ("IPO_STRATEGY", "ipo_strategy.csv"))


@_pytest.fixture(autouse=True)
def _firm_headroom_never_live(tmp_path_factory, monkeypatch):
    if _AGENT not in _sys.path:
        _sys.path.insert(0, _AGENT)
    import stale_quote as _sq
    fh = _sq._firm_halt()
    if fh is not None and hasattr(fh, "HEADROOM_FROM"):
        scratch = tmp_path_factory.mktemp("firm_headroom")
        monkeypatch.setattr(fh, "HEADROOM_FROM", "")
        for name, leaf in HEADROOM_PATHS:
            monkeypatch.setattr(fh, name, str(scratch / leaf))
    yield


"""Offline stand-in for yfinance used by test_ins018_grader.py (test 10, test 12).

Reads bars from the JSON file named by $FAKE_YF_FIXTURE:
  {"TICKER": {"bars": [[date, open, high, low, close, volume], ...] | "RAISE", "splits": [[date, ratio], ...]}}
A null in a bar is NaN. history(start, end) returns the bars with start <= date < end.
"""
import json, os
import pandas as pd

__version__ = "fake-ins018"


def _fx():
    return json.load(open(os.environ["FAKE_YF_FIXTURE"]))


class Ticker:
    def __init__(self, tk):
        self.tk = tk
        self._d = _fx().get(tk, {"bars": [], "splits": []})

    def history(self, start=None, end=None, auto_adjust=False, **kw):
        if self._d.get("bars") == "RAISE":
            raise ConnectionError(f"fake timeout for {self.tk}")
        rows = [b for b in self._d.get("bars", []) if (start is None or b[0] >= start) and (end is None or b[0] < end)]
        idx = pd.DatetimeIndex([pd.Timestamp(b[0]).tz_localize("America/New_York") for b in rows])
        nan = float("nan")
        f = lambda x: nan if x is None else float(x)
        return pd.DataFrame({"Open": [f(b[1]) for b in rows], "High": [f(b[2]) for b in rows],
                             "Low": [f(b[3]) for b in rows], "Close": [f(b[4]) for b in rows],
                             "Volume": [f(b[5]) for b in rows]}, index=idx)

    @property
    def splits(self):
        sp = self._d.get("splits", [])
        idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("America/New_York") for d, _ in sp])
        return pd.Series([float(v) for _, v in sp], index=idx, dtype=float)

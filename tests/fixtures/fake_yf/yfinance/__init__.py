"""Offline stand-in for yfinance used by test_ins018_grader.py (test 10, test 12).

Reads bars from the JSON file named by $FAKE_YF_FIXTURE:
  {"TICKER": {"bars": [[date, open, high, low, close, volume], ...] | "RAISE", "splits": [[date, ratio], ...]}}
A null in a bar is NaN. history(start, end) returns the bars with start <= date < end.

INS-022: history(period="max", actions=True, ...) — the full-history split lookup — returns the entry's "max"
rows ([[date, o, h, l, c, v], ...]; default: its "bars") with a "Stock Splits" column (0 = none; a split date
missing from the rows is added as an all-NaN row, as Yahoo's split-day hole). "max" may instead be
"RAISE" (the lookup raises), "EMPTY" (an empty frame, what raise_errors=False hands back on a failed fetch) or
"NOCOL" (the rows without a "Stock Splits" column). `.splits` (the pre-INS-022 reader) is unchanged.
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

    def history(self, start=None, end=None, auto_adjust=False, period=None, **kw):
        if self._d.get("bars") == "RAISE":
            raise ConnectionError(f"fake timeout for {self.tk}")
        if period == "max":
            return self._max()
        rows = [b for b in self._d.get("bars", []) if (start is None or b[0] >= start) and (end is None or b[0] < end)]
        idx = pd.DatetimeIndex([pd.Timestamp(b[0]).tz_localize("America/New_York") for b in rows])
        nan = float("nan")
        f = lambda x: nan if x is None else float(x)
        return pd.DataFrame({"Open": [f(b[1]) for b in rows], "High": [f(b[2]) for b in rows],
                             "Low": [f(b[3]) for b in rows], "Close": [f(b[4]) for b in rows],
                             "Volume": [f(b[5]) for b in rows]}, index=idx)

    @property
    def history_metadata(self):
        # FCST-011: real yfinance 0.2.66 fills this from the same chart payload as the bars; {"instrumentType": "EQUITY" | "ETF" |
        # "INDEX" | "CURRENCY" | "FUTURE" | ...}. An entry's optional "type" feeds it; no "type" = no instrumentType (an empty dict),
        # and "type": "RAISE" makes the property raise, as the real one does when history() has not been called.
        t = self._d.get("type")
        if t == "RAISE":
            raise RuntimeError(f"fake history_metadata failure for {self.tk}")
        return {"instrumentType": t} if t else {}

    @property
    def splits(self):
        # Real yfinance 0.2.66: `.splits` reads history(period="max") with raise_errors=False, so a failed
        # full-history fetch comes back as an EMPTY Series — the defect INS-022 closes. Emulated here.
        if self._d.get("bars") == "RAISE" or self._d.get("max") in ("RAISE", "EMPTY"):
            return pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
        sp = self._d.get("splits", [])
        idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("America/New_York") for d, _ in sp])
        return pd.Series([float(v) for _, v in sp], index=idx, dtype=float)

    def _max(self):
        mx = self._d.get("max", self._d.get("bars", []))
        if mx == "RAISE":
            raise ConnectionError(f"fake full-history failure for {self.tk}")
        if mx == "EMPTY":
            return pd.DataFrame()
        rows = [list(b) for b in (self._d.get("bars", []) if mx == "NOCOL" else mx)]
        sp = {d: float(v) for d, v in self._d.get("splits", [])}
        have = {b[0] for b in rows}
        rows += [[d, None, None, None, None, None] for d in sp if d not in have]
        rows.sort(key=lambda b: b[0])
        idx = pd.DatetimeIndex([pd.Timestamp(b[0]).tz_localize("America/New_York") for b in rows])
        nan = float("nan")
        f = lambda x: nan if x is None else float(x)
        cols = {"Open": [f(b[1]) for b in rows], "High": [f(b[2]) for b in rows], "Low": [f(b[3]) for b in rows],
                "Close": [f(b[4]) for b in rows], "Volume": [f(b[5]) for b in rows]}
        if mx != "NOCOL":
            cols["Dividends"] = [0.0] * len(rows)
            cols["Stock Splits"] = [sp.get(b[0], 0.0) for b in rows]
        return pd.DataFrame(cols, index=idx)

"""INS-018 — the insider grader implements AGENT.md step 2 as written. Offline; no network.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins018_grader.py

Numbered as the prereg-reviewer's list (2026-09-29):
 1 replaying the 10 rows graded 2026-09-28 gives identical output (log lines and ledger bytes)
 2 GRML shape (hole on 08-24, 9.71 on 08-25) grades on 08-25, stamped, check_date kept
 3 roll-forward skips a zero-volume bar (and a NaN one); a zero-volume / NaN bar ON the check date stalls
 4 no later bar + no Form 25 -> stall, nothing written
 5 same with an effective Form 25 -> wrong, blank price, accession stamped
 6 "Not Found" with SPY OK -> wrong
 7 "Not Found" with SPY failing, or a timeout -> stall
 8 unknown CIK -> stall
 9 scored rows byte-identical before/after
10 stock-radar and india-radar fixtures byte-identical (old grader vs new grader)
11 earnings void never applied to insider rows
12 a NaN close in resolve_forecasts is not resolved, and the row is named
"""
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import types

import pytest

REAL_HOME = "/Users/anupampatil"
GRADER = f"{REAL_HOME}/bin/grade_all_due.py"
GRADER_OLD = f"{REAL_HOME}/bin/grade_all_due_BACKUP_0929b_INS-018.py"
RESOLVER = f"{REAL_HOME}/bin/resolve_forecasts.py"
RESOLVER_OLD = f"{REAL_HOME}/bin/resolve_forecasts_BACKUP_0929b_INS-018.py"
LIVE_INSIDER = f"{REAL_HOME}/insider-radar/agent/ledger.csv"
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FAKE_YF = os.path.join(FIX, "fake_yf")
PY = "/opt/anaconda3/bin/python"
D = dt.date.fromisoformat


def _load_grader():
    sp = importlib.util.spec_from_file_location("gad_ins018", GRADER)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


G = _load_grader()


# ---------------------------------------------------------------- fixture fetcher
class FixtureFetch:
    """Stands in for LiveFetch. bars[tk] is a list of [date, o, h, l, c, v] or an Exception."""

    def __init__(self, bars=None, splits=None, probe=None, spy=(True, "SPY fixture"), delist=None, default_bars=None):
        self._bars = bars or {}
        self._splits = splits or {}
        self._probe = probe or {}
        self._spy = spy
        self._delist = delist or {}
        self._default = default_bars
        self.delist_calls = []

    def bars(self, tk, start, end):
        b = self._bars.get(tk)
        if b is None and self._default:
            b = self._default(tk, start, end)
        if isinstance(b, Exception):
            raise b
        rows = []
        for x in b or []:
            d = D(x[0]) if isinstance(x[0], str) else x[0]
            if start <= d < end:
                rows.append({"date": d, "open": x[1], "high": x[2], "low": x[3], "close": x[4], "volume": x[5]})
        return rows, [(D(a), float(r)) for a, r in self._splits.get(tk, [])]

    def probe(self, tk):
        return self._probe.get(tk, ("series", "fixture"))

    def spy(self, settled):
        return self._spy

    def delisting(self, tk, call_date, settled):
        self.delist_calls.append(tk)
        return self._delist.get(tk, {"status": "none", "detail": "fixture: no Form 25"})

    def sec_map_note(self, tk, call_date):
        return f"fixture SEC map note for {tk}"


def _ledger(tmp, rows, name="insider-radar/agent/ledger.csv", cols=None):
    p = os.path.join(tmp, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cols = cols or ["date", "ticker", "call", "thesis", "price_at_call", "check_date", "price_at_check",
                    "outcome", "stale_quote", "tags", "void_reason"]
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return p


def _row(tk, date, check, p0, thesis="[insider] fixture"):
    return {"date": date, "ticker": tk, "call": "long", "thesis": thesis, "price_at_call": p0,
            "check_date": check, "stale_quote": "no", "tags": "fund"}


def _run(path, fetch, settled, today, dry=False, home=None):
    lines = []
    old = G.HOME
    if home:
        G.HOME = home
    try:
        n = G.grade_insider(path, fetch, D(settled), D(today), dry, sessions_between=lambda a, b: len(
            [x for x in range((b - a).days) if (a + dt.timedelta(days=x + 1)).weekday() < 5]), out=lines.append)
    finally:
        G.HOME = old
    return n, lines


def _read(path):
    return list(csv.DictReader(open(path)))


def _b(d, c, v=1000.0):
    return [d, c, c, c, c, v]


HOLE = lambda d: [d, None, None, None, None, None]


# ---------------------------------------------------------------- 1 replay 09-28
def test_01_replay_0928_identical(tmp_path):
    tmp = str(tmp_path)
    p = os.path.join(tmp, "insider-radar/agent/ledger.csv")
    os.makedirs(os.path.dirname(p))
    shutil.copy(os.path.join(FIX, "ledger_pre_0928_grade.csv"), p)
    fx = json.load(open(os.path.join(FIX, "bars_0928.json")))
    rec = fx.pop("_recorded_0928_closes")
    bars, splits = {}, {}
    for tk, v in fx.items():
        if tk.startswith("_"):
            continue
        bs = [list(b) for b in v["bars"]]
        for b in bs:
            if b[0] == "2026-09-28" and tk in rec:
                b[4] = rec[tk]            # the close the 13:40 PT grader actually read
        bars[tk] = bs
        splits[tk] = v["splits"]
    n, lines = _run(p, FixtureFetch(bars=bars, splits=splits), "2026-09-28", "2026-09-28", home=tmp)
    expected = """insider-radar/agent/ledger.csv: 10 graded
   NGL long 17.77 -> 14.88 (-16.26%) = wrong
   SCOR long 5.28 -> 4.86 (-7.95%) = wrong
   BXSY long 18.2 -> 17.25 (-5.22%) = wrong
   APCX long 0.359 -> 0.24 (-33.15%) = wrong
   YORW long 33.81 -> 30.62 (-9.44%) = wrong
   MAIR long 26.28 -> 24.97 (-4.98%) = wrong
   VENU long 2.04 -> 1.43 (-29.90%) = wrong
   SLNH long 1.1 -> 1.18 (+7.27%) = right
   UNB long 23.5 -> 23.14 (-1.53%) = wrong
   BMRA long 2.15 -> 2.39 (+11.16%) = right""".splitlines()
    assert n == 10
    assert lines == expected
    assert open(p, "rb").read() == open(os.path.join(FIX, "ledger_post_0928_grade.csv"), "rb").read()


# ---------------------------------------------------------------- 2 GRML shape
@pytest.mark.parametrize("hole_as", ["all_nan_bar", "zero_rows"])
def test_02_grml_shape(tmp_path, hole_as):
    p = _ledger(str(tmp_path), [_row("GRML", "2026-07-25", "2026-08-24", "0.2")])
    bars = [_b("2026-08-20", 0.21), _b("2026-08-21", 0.203)]
    if hole_as == "all_nan_bar":
        bars.append(HOLE("2026-08-24"))
    bars.append(_b("2026-08-25", 9.71))
    f = FixtureFetch(bars={"GRML": bars}, splits={"GRML": [["2026-08-24", 0.02]]})
    n, lines = _run(p, f, "2026-08-25", "2026-08-25")
    r = _read(p)[0]
    assert n == 1
    assert r["check_date"] == "2026-08-24"                      # never rewritten
    assert r["price_at_check"] == "9.71"
    assert "[INS-012: no bar on 2026-08-24; scored on the 2026-08-25 close, the next session with a traded bar]" in r["thesis"]
    assert "[SPLIT ADJUSTED x50" in r["thesis"] and r["price_at_call"] == "10.0000"
    assert r["outcome"] == "wrong"                               # 9.71 < 10.00 post-split basis


# ---------------------------------------------------------------- 3 roll-forward skips non-traded bars
def test_03_rollforward_skips_zero_volume_and_nan(tmp_path):
    p = _ledger(str(tmp_path), [_row("RFX", "2026-08-01", "2026-09-14", "5")])
    bars = [_b("2026-09-11", 5.0), _b("2026-09-15", 5.5, 0.0), ["2026-09-16", 5.4, 5.6, 5.3, None, 900.0],
            _b("2026-09-17", 4.9)]
    n, lines = _run(p, FixtureFetch(bars={"RFX": bars}), "2026-09-18", "2026-09-18")
    r = _read(p)[0]
    assert n == 1 and r["price_at_check"] == "4.90" and r["outcome"] == "wrong"
    assert "scored on the 2026-09-17 close" in r["thesis"] and r["check_date"] == "2026-09-14"


@pytest.mark.parametrize("bar,why", [(_b("2026-09-14", 5.5, 0.0), "zero-volume"),
                                     (["2026-09-14", 5.4, 5.6, 5.3, None, 900.0], "NaN")])
def test_03b_nontraded_bar_on_check_date_stalls(tmp_path, bar, why):
    p = _ledger(str(tmp_path), [_row("CFX", "2026-08-01", "2026-09-14", "5")])
    before = open(p, "rb").read()
    n, lines = _run(p, FixtureFetch(bars={"CFX": [_b("2026-09-11", 5.0), bar, _b("2026-09-15", 6.0)]}),
                    "2026-09-15", "2026-09-15")
    assert n == 0 and open(p, "rb").read() == before
    assert any("CFX due 2026-09-14" in l and why in l and "INS-015" in l for l in lines)


# ---------------------------------------------------------------- 4 no later bar, no Form 25
def test_04_no_later_bar_no_form25_stalls(tmp_path):
    p = _ledger(str(tmp_path), [_row("HALT", "2026-08-01", "2026-09-14", "5")])
    before = open(p, "rb").read()
    f = FixtureFetch(bars={"HALT": [_b("2026-09-10", 5.0), _b("2026-09-15", 5.0, 0.0)]})
    n, lines = _run(p, f, "2026-09-18", "2026-09-18")
    assert n == 0 and open(p, "rb").read() == before
    assert f.delist_calls == ["HALT"]
    msg = [l for l in lines if "HALT due 2026-09-14" in l][0]
    assert "INS-012: waiting for next traded bar" in msg and "4 session(s) since check_date" in msg
    assert "no limit" in msg


# ---------------------------------------------------------------- 5 effective Form 25
def test_05_effective_form25_wrong_blank_accession(tmp_path):
    p = _ledger(str(tmp_path), [_row("GONE", "2026-08-01", "2026-09-14", "5")])
    ev = {"status": "effective", "form": "25-NSE", "accession": "0001234567-26-000123", "filed": D("2026-09-01"),
          "effective": D("2026-09-11"), "cik": 1234567}
    f = FixtureFetch(bars={"GONE": [_b("2026-09-10", 5.0)]}, delist={"GONE": ev})
    n, lines = _run(p, f, "2026-09-18", "2026-09-18")
    r = _read(p)[0]
    assert n == 1 and r["outcome"] == "wrong" and r["price_at_check"] == ""
    assert "0001234567-26-000123" in r["thesis"] and "[SURVIVORSHIP: delisted" in r["thesis"]
    assert r["check_date"] == "2026-09-14"


class _Resp:
    def __init__(self, code, payload=None, text=None):
        self.status_code = code
        self._p = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._p is None:
            raise ValueError("not json")
        return self._p


def _submissions(rows):
    return {"filings": {"recent": {"form": [r[0] for r in rows], "filingDate": [r[1] for r in rows],
                                   "accessionNumber": [r[2] for r in rows]}}}


@pytest.mark.parametrize("filings,settled,status", [
    ([("25-NSE", "2026-09-01", "A1")], "2026-09-18", "effective"),   # effective 09-11 <= 09-18
    ([("25-NSE", "2026-09-10", "A2")], "2026-09-18", "none"),        # effective 09-20 > 09-18: pending
    ([("25", "2026-07-01", "A3")], "2026-09-18", "none"),            # filed BEFORE the call date: not this row's evidence
    ([("4", "2026-09-01", "A4"), ("8-K", "2026-09-02", "A5")], "2026-09-18", "none"),
])
def test_05b_livefetch_form25_rule(filings, settled, status):
    class F(G.LiveFetch):
        def issuer_cik(self, tk, call_date):
            return 1234567, "fixture"

        def _sec_get(self, url):
            assert "data.sec.gov/submissions/CIK0001234567.json" in url
            return _Resp(200, _submissions(filings))
    ev = F().delisting("X", D("2026-08-01"), D(settled))
    assert ev["status"] == status
    if status == "effective":
        assert ev["accession"] == "A1" and ev["effective"] == D("2026-09-11")


# ---------------------------------------------------------------- 6 / 7 unfetchable
def test_06_not_found_with_spy_ok_is_wrong(tmp_path):
    p = _ledger(str(tmp_path), [_row("VNSH", "2026-08-01", "2026-09-14", "5")])
    f = FixtureFetch(bars={"VNSH": []}, probe={"VNSH": ("no_series", "HTTP 404 Not Found")})
    n, lines = _run(p, f, "2026-09-18", "2026-09-18")
    r = _read(p)[0]
    assert n == 1 and r["outcome"] == "wrong" and r["price_at_check"] == ""
    assert "[SURVIVORSHIP: unfetchable — no series for VNSH on 2026-09-18 while SPY priced; AGENT.md step 2]" in r["thesis"]
    assert "fixture SEC map note for VNSH" in r["thesis"]


@pytest.mark.parametrize("case", ["spy_down", "bars_timeout", "probe_timeout"])
def test_07_not_found_with_spy_down_or_timeout_stalls(tmp_path, case):
    p = _ledger(str(tmp_path), [_row("VNSH", "2026-08-01", "2026-09-14", "5")])
    before = open(p, "rb").read()
    kw = {"bars": {"VNSH": []}, "probe": {"VNSH": ("no_series", "HTTP 404 Not Found")}}
    if case == "spy_down":
        kw["spy"] = (False, "SPY chart probe: error timeout")
    elif case == "bars_timeout":
        kw["bars"] = {"VNSH": TimeoutError("read timed out")}
    else:
        kw["probe"] = {"VNSH": ("error", "Timeout: read timed out")}
    n, lines = _run(p, FixtureFetch(**kw), "2026-09-18", "2026-09-18")
    assert n == 0 and open(p, "rb").read() == before
    assert any("VNSH due 2026-09-14" in l for l in lines)
    if case == "spy_down":
        assert any("source down" in l for l in lines)


@pytest.mark.parametrize("resp,expect", [
    (_Resp(404, {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"}}}), "no_series"),
    (_Resp(200, {"chart": {"result": None, "error": None}}), "no_series"),
    (_Resp(200, {"chart": {"result": [{"meta": {}, "timestamp": [1, 2, 3]}], "error": None}}), "series"),
    (_Resp(429, None, text="Too Many Requests"), "error"),
    (_Resp(404, None, text="<html>not found</html>"), "error"),          # a 404 that is not a symbol-level answer
    (_Resp(500, {"chart": {"result": None, "error": {"code": "Internal"}}}), "error"),
    (TimeoutError("timed out"), "error"),
])
def test_06_07_probe_classification(monkeypatch, resp, expect):
    import requests

    def fake_get(url, **kw):
        assert "range" in kw["params"] and kw["params"]["range"] == "max"
        if isinstance(resp, Exception):
            raise resp
        return resp
    monkeypatch.setattr(requests, "get", fake_get)
    assert G.LiveFetch().probe("XYZ")[0] == expect


def test_07_spy_control(monkeypatch):
    class F(G.LiveFetch):
        def __init__(self, pr, bars):
            super().__init__(); self._pr = pr; self._b = bars

        def probe(self, tk):
            return self._pr

        def bars(self, tk, a, b):
            if isinstance(self._b, Exception):
                raise self._b
            return self._b, []
    s = D("2026-09-18")
    ok = [{"date": s, "open": 1, "high": 1, "low": 1, "close": 700.0, "volume": 1e7}]
    assert F(("series", ""), ok).spy(s)[0] is True
    assert F(("error", "429"), ok).spy(s)[0] is False
    assert F(("series", ""), TimeoutError("x")).spy(s)[0] is False
    assert F(("series", ""), [dict(ok[0], volume=0.0)]).spy(s)[0] is False


# ---------------------------------------------------------------- 8 unknown CIK
def test_08_unknown_cik_stalls(tmp_path):
    p = _ledger(str(tmp_path), [_row("NOCIK", "2026-08-01", "2026-09-14", "5")])
    before = open(p, "rb").read()
    f = FixtureFetch(bars={"NOCIK": []}, delist={"NOCIK": {"status": "unknown", "detail": "issuer CIK unknown (fixture)"}})
    n, lines = _run(p, f, "2026-09-18", "2026-09-18")
    assert n == 0 and open(p, "rb").read() == before
    assert any("NOCIK due 2026-09-14" in l and "delisting unestablished" in l for l in lines)


@pytest.mark.parametrize("feed,expect_none", [((None, ""), True),
                                              (({"purchases": [{"ticker": "OTHER", "acc": "x"}]}, "abc"), True)])
def test_08b_livefetch_cik_unknown_paths(feed, expect_none):
    class F(G.LiveFetch):
        def _feed_as_of(self, date):
            return feed

        def _sec_get(self, url):
            raise AssertionError("must not reach EDGAR without a CIK")
    f = F()
    cik, how = f.issuer_cik("NOCIK", D("2026-08-01"))
    assert cik is None
    ev = f.delisting("NOCIK", D("2026-08-01"), D("2026-09-18"))
    assert ev["status"] == "unknown"


def test_08c_livefetch_cik_edgar_failing_is_unknown():
    class F(G.LiveFetch):
        def _feed_as_of(self, date):
            return {"purchases": [{"ticker": "EDF", "acc": "0000000001-26-000001"}]}, "abc"

        def _sec_get(self, url):
            raise RuntimeError("HTTP 503")
    assert F().delisting("EDF", D("2026-08-01"), D("2026-09-18"))["status"] == "unknown"


def test_08d_livefetch_cik_from_feed_accession():
    class F(G.LiveFetch):
        def _feed_as_of(self, date):
            return {"purchases": [{"ticker": "KRMN", "acc": "0001193125-26-395095"}]}, "abc"

        def _sec_get(self, url):
            if "efts.sec.gov" in url:
                return _Resp(200, {"hits": {"hits": [{"_id": "0001193125-26-395095:ownership.xml", "_source": {
                    "adsh": "0001193125-26-395095", "ciks": ["0002054316", "0002040127"]}}]}})
            assert url.endswith("/2054316/000119312526395095/ownership.xml")
            return _Resp(200, None, text="<issuer><issuerCik>0002040127</issuerCik></issuer>")
    assert F().issuer_cik("KRMN", D("2026-09-18"))[0] == 2040127


def test_no_ticker_aliases_at_grading_time():
    src = open(GRADER).read()
    assert "ticker_aliases" not in src.split('"""', 2)[2].replace("Ticker aliases are NEVER read", "")


def test_no_n_session_limit():
    body = open(GRADER).read()
    for bad in ("MAX_STALL", "max_sessions", "after N sessions ->", "stall_limit"):
        assert bad not in body


# ---------------------------------------------------------------- 9 scored rows byte-identical
def test_09_scored_rows_byte_identical(tmp_path):
    tmp = str(tmp_path)
    p = os.path.join(tmp, "ledger.csv")
    shutil.copy(LIVE_INSIDER, p)
    before_txt = open(p, newline="").read()
    before = list(csv.reader(io.StringIO(before_txt)))

    def weekdays(tk, a, b):
        out, d = [], a
        while d < b:
            if d.weekday() < 5:
                out.append(_b(d.isoformat(), 1.0))
            d += dt.timedelta(days=1)
        return out
    n, lines = _run(p, FixtureFetch(default_bars=weekdays), "2026-10-16", "2026-10-16")
    after_txt = open(p, newline="").read()
    after = list(csv.reader(io.StringIO(after_txt)))
    assert n > 0                                               # the run did grade the open rows
    assert len(before) == len(after) and before[0] == after[0]
    oi = before[0].index("outcome")
    scored = [i for i in range(1, len(before)) if before[i][oi].strip()]
    assert len(scored) > 100
    bl, al = before_txt.splitlines(), after_txt.splitlines()
    assert len(bl) == len(before) and len(al) == len(after)    # no embedded newlines: line i == record i
    for i in scored:
        assert before[i] == after[i]
        assert bl[i] == al[i]


# ---------------------------------------------------------------- 10 stock/india unchanged
def _write_fx(path, data):
    json.dump(data, open(path, "w"))
    return path


def _legacy_fixture_home(tmp):
    """A HOME with a stock-radar and an india-radar ledger that exercise every legacy branch."""
    sr_cols = ['date', 'ticker', 'call', 'thesis', 'price_at_call', 'check_date', 'price_at_check', 'outcome',
               'close_at_check', 'fill_date']
    live_sr = list(csv.DictReader(open(f"{REAL_HOME}/stock-radar/agent/ledger.csv")))
    extra = [
        {"date": "2026-09-01", "ticker": "AAA", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "BBB", "call": "short", "thesis": "[earnings] INTO the print", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "CCC", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "DDD", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "EEE", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "FFF", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "GGG", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "HHH", "call": "short", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-13"},
        {"date": "2026-09-01", "ticker": "ZZZ", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
        {"date": "2026-09-01", "ticker": "ALL0", "call": "long", "thesis": "fixture", "price_at_call": "10", "check_date": "2026-09-15"},
    ]
    _ledger(tmp, live_sr + extra, "stock-radar/agent/ledger.csv", sr_cols)
    _ledger(tmp, [{"date": "2026-09-01", "ticker": "RELI", "call": "long", "thesis": "fixture", "price_at_call": "100",
                   "check_date": "2026-09-15"}], "india-radar/agent/ledger.csv",
            ['date', 'ticker', 'call', 'thesis', 'price_at_call', 'check_date', 'price_at_check', 'outcome'])
    fx = {
        "AAA": {"bars": [_b("2026-09-12", 10.5), _b("2026-09-15", 11.0)]},
        "BBB": {"bars": [_b("2026-09-15", 10.1)]},
        "CCC": {"bars": [_b("2026-09-12", 10.0), _b("2026-09-15", 10.0, 0.0)]},
        "DDD": {"bars": [_b("2026-09-12", 10.0), ["2026-09-15", 10, 10, 10, None, 500.0]]},
        "EEE": {"bars": [_b("2026-09-12", 10.0), HOLE("2026-09-15"), _b("2026-09-16", 12.0)]},
        "FFF": {"bars": [_b("2026-09-15", 2.5)], "splits": [["2026-09-10", 4.0]]},
        "GGG": {"bars": "RAISE"},
        "HHH": {"bars": [_b("2026-09-14", 9.0)]},
        "ZZZ": {"bars": []},
        "ALL0": {"bars": [_b("2026-09-12", 10.0, 0.0), _b("2026-09-15", 10.2, 0.0)]},
        "RELI.NS": {"bars": [_b("2026-09-15", 101.0)]},
    }
    return _write_fx(os.path.join(tmp, "yf.json"), fx)


def _run_script(script, home, fx, *args):
    env = dict(os.environ, HOME=home, FAKE_YF_FIXTURE=fx, PYTHONPATH=FAKE_YF)
    r = subprocess.run([PY, script, *args], capture_output=True, text=True, env=env, timeout=300)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_10_stock_and_india_byte_identical(tmp_path):
    old_home, new_home = str(tmp_path / "old"), str(tmp_path / "new")
    fx_old, fx_new = _legacy_fixture_home(old_home), _legacy_fixture_home(new_home)
    out_old = _run_script(GRADER_OLD, old_home, fx_old)
    out_new = _run_script(GRADER, new_home, fx_new)
    assert out_old == out_new
    assert "5 graded" in out_old and "DUE BUT UNPRICEABLE" in out_old   # every branch was exercised
    for led in ("stock-radar/agent/ledger.csv", "india-radar/agent/ledger.csv"):
        assert open(os.path.join(old_home, led), "rb").read() == open(os.path.join(new_home, led), "rb").read()
    # and the legacy semantics survived: EEE's hole is NOT rolled forward on a stock-radar row
    assert "!! EEE due 2026-09-15" in out_new and "EEE long" not in out_new
    assert "!! ZZZ due 2026-09-15 — no bar at the check date" in out_new
    assert "BBB short 10.0 -> 10.10 (+1.00%) = void" in out_new


# ---------------------------------------------------------------- 11 no earnings void on insider rows
@pytest.mark.parametrize("close,expect", [(5.05, "right"), (4.95, "wrong"), (5.0, "wrong")])
def test_11_no_earnings_void_on_insider_rows(tmp_path, close, expect):
    p = _ledger(str(tmp_path), [_row("ERN", "2026-08-01", "2026-09-14", "5",
                                     thesis="[insider] [earnings] cluster INTO the print")])
    n, lines = _run(p, FixtureFetch(bars={"ERN": [_b("2026-09-14", close)]}), "2026-09-14", "2026-09-14")
    assert _read(p)[0]["outcome"] == expect


def test_11b_main_routes_insider_ledger_away_from_legacy():
    src = open(GRADER).read()
    assert "os.path.abspath(path) == os.path.abspath(INSIDER_LEDGER)" in src
    assert "grade_insider(path, LiveFetch()" in src
    assert "os.path.abspath(path) != os.path.abspath(INSIDER_LEDGER)" in src   # belt and braces in the void branch


# ---------------------------------------------------------------- 12 resolve_forecasts NaN
def test_12_resolve_forecasts_refuses_nan_and_names_it(tmp_path):
    def home(tag):
        h = str(tmp_path / tag)
        _ledger(h, [
            {"date": "2026-09-01", "instrument": "NANX", "horizon_days": "14", "question": "NANX closes above 10 on 2026-09-15", "p": "0.5", "check_date": "2026-09-15"},
            {"date": "2026-09-01", "instrument": "ZVX", "horizon_days": "14", "question": "ZVX closes above 10 on 2026-09-15", "p": "0.5", "check_date": "2026-09-15"},
            {"date": "2026-09-01", "instrument": "OKX", "horizon_days": "14", "question": "OKX closes above 10 on 2026-09-15", "p": "0.5", "check_date": "2026-09-15"},
        ], "insider-radar/agent/forecasts.csv", ["date", "instrument", "horizon_days", "question", "p", "check_date", "outcome", "notes"])
        fx = {"NANX": {"bars": [_b("2026-09-12", 11.0), ["2026-09-15", 11, 11, 11, None, 800.0]]},
              "ZVX": {"bars": [_b("2026-09-12", 11.0), _b("2026-09-15", 11.0, 0.0)]},
              "OKX": {"bars": [_b("2026-09-15", 11.0)]}}
        return h, _write_fx(os.path.join(h, "yf.json"), fx)
    h_new, fx_new = home("new")
    out = _run_script(RESOLVER, h_new, fx_new)
    rows = {r["instrument"]: r for r in csv.DictReader(open(os.path.join(h_new, "insider-radar/agent/forecasts.csv")))}
    assert rows["NANX"]["outcome"] == "" and rows["ZVX"]["outcome"] == "" and rows["OKX"]["outcome"] == "1"
    assert "SKIP (no close): NANX" in out and "NaN" in out
    assert "SKIP (no close): ZVX" in out and "zero-volume" in out
    # the defect this closes: the old resolver scored the NaN row
    h_old, fx_old = home("old")
    _run_script(RESOLVER_OLD, h_old, fx_old)
    old = {r["instrument"]: r for r in csv.DictReader(open(os.path.join(h_old, "insider-radar/agent/forecasts.csv")))}
    assert old["NANX"]["outcome"] == "0"


# ---------------------------------------------------------------- D strata / attribution disclosure
def _load(path, name):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def test_13_blank_price_wrong_counts_in_hit_rate_and_is_disclosed(tmp_path, capsys):
    p = _ledger(str(tmp_path), [
        dict(_row("AAA", "2026-08-01", "2026-09-01", "10", "[insider] 2 insiders bought $5.0M"), price_at_check="11", outcome="right"),
        dict(_row("GONE", "2026-08-01", "2026-09-01", "10", "[insider] 2 insiders bought $6.0M"), price_at_check="", outcome="wrong"),
    ])
    st = _load(f"{REAL_HOME}/insider-radar/agent/strata.py", "strata_t")
    st.LEDGER = p
    monkey_argv = sys.argv
    sys.argv = ["strata.py"]
    try:
        st.main()
    finally:
        sys.argv = monkey_argv
    out = capsys.readouterr().out
    assert "2 scored" in out and "50%" in out and "excludes 1 delisted rows (return unknown)" in out

    at = _load(f"{REAL_HOME}/insider-radar/attribution.py", "attr_t")
    at.LEDGER, at.FORECASTS, at.OUT = p, str(tmp_path / "none.csv"), str(tmp_path / "attr.csv")
    at.feed_as_of = lambda d: ({"purchases": [
        {"ticker": t, "insider": i, "value": 3e6, "role": "Director", "price": 10, "shares": 1, "filed": "2026-07-30"}
        for t in ("AAA", "GONE") for i in ("x", "y")]}, "fixture")
    at.main()
    out = capsys.readouterr().out
    assert "2 scored" in out
    assert "big cluster (>= $5M)         n=2   dates=1   hit  50%  avg +10.0%  (avg excludes 1 delisted rows (return unknown))" in out
    assert "_blank_wrong" not in open(at.OUT).read()

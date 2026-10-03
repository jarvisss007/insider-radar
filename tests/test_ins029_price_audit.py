"""INS-029 - price_audit.py no longer turns a failed read into a permanent verdict, and no longer calls an unchecked row a pass. Offline.

Run:  /opt/anaconda3/bin/python -m pytest -q ~/insider-radar/tests/test_ins029_price_audit.py

The defect: bars() cached ANY exception (a 429, a timeout) as a permanent "UNFETCHABLE", so one transient error could hide a row's verification for good
(an AAPL row priced 1.00 stayed unchecked once the cache was poisoned). The EXIT STATUS is deliberately NOT changed here (HEAD's clause: NO_BAR / UNFETCHABLE do
not fail the audit; changing it is a ruling) - what changes is the cache and the closing line. Every test runs the audit as shipped, in a scratch root
(its own ledger, its own bar cache), with the network replaced by a stub and the settled session pinned - no live file, no clock dependence.

Source reads (_bars):
 1 a transient failure (429, 5xx, URL error, timeout, a body that is not JSON, a reply of the wrong shape, an unknown error body) is reported as
   transient and NEVER written to the cache; the next read goes to the source and succeeds
 2 a 404 is remembered for the settled session it was said in and not asked again inside it; after the next close it is asked again; --refresh asks
 3 a `Not Found` error body and a reply with no bars are definitive too; an error body of any other code is not
 4 a pre-INS-029 permanent "UNFETCHABLE" marker proves nothing: it is ignored and replaced
 5 a failed refresh never overwrites good bars already cached; bars already held still verify the rows they cover after a later "not found"
 6 a ticker that failed transiently is not read again within a run
The audit's verdict (main):
 7 a transient failure on a priced open row: UNFETCHABLE 1 with the cause on the record (`source: transient`), nothing cached, an UNVERIFIED paragraph, a
   qualified OK ("OK for the rows it could check"), and the exit status UNCHANGED (0)
 8 a settled day with no bar (NO_BAR), and a call dated a non-session: the same UNVERIFIED reading, exit 0
 9 a bar whose session has not settled is not a missing bar: NO_BAR tagged `unsettled`, named as waiting, never "every priced row sits inside its bar"
 9b the boundary: a row dated EXACTLY the last settled session with no bar is missing (not unsettled); the next session is waiting
10 QUEUED rows alone leave the plain OK (they are not priced rows); beside an unsettled row the OK is qualified
11 a violation wins: FAIL plus UNFETCHABLE exits 1 and prints both; a clean run prints the plain OK and exits 0
12 --json: the exit status is HEAD's (1 only for FAIL / REF_MISMATCH), stdout is still only the JSON the resolver parses, records carry `source` / `unsettled`
"""
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import urllib.error

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HEADER = ["date", "ticker", "call", "thesis", "price_at_call", "check_date", "price_at_check", "outcome",
          "stale_quote", "tags", "void_reason"]
SETTLED = "2026-10-01"          # the pinned last settled session (a Thursday)


@pytest.fixture
def pa(tmp_path, monkeypatch):
    """price_audit.py as shipped, loaded from a scratch root so its LEDGER / CACHE / agent dir are the scratch ones; calendar pinned."""
    root = tmp_path / "root"
    (root / "agent").mkdir(parents=True)
    (root / "data").mkdir()
    shutil.copy(os.path.join(ROOT, "price_audit.py"), root / "price_audit.py")
    shutil.copy(os.path.join(ROOT, "agent", "stale_quote.py"), root / "agent" / "stale_quote.py")
    sp = importlib.util.spec_from_file_location("price_audit_ins029", root / "price_audit.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    monkeypatch.setattr(m, "_settled_day", lambda: SETTLED)
    m.ROOT_FOR_TEST = root
    return m


class _Resp:
    def __init__(self, obj):
        self._b = json.dumps(obj).encode()

    def read(self, *a):
        return self._b


def _chart(bars):
    """A Yahoo chart reply for {day: (low, high, open, close, volume)}."""
    days = sorted(bars)
    ts = [int(dt.datetime(*map(int, d.split("-")), 21, tzinfo=dt.timezone.utc).timestamp()) for d in days]
    q = {k: [bars[d][i] for d in days] for i, k in enumerate(("low", "high", "open", "close", "volume"))}
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [q]}}], "error": None}}


GOOD = {"2026-09-29": (9.0, 11.0, 9.5, 10.0, 1000), "2026-09-30": (9.5, 11.5, 10.0, 10.5, 900)}


def _http(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(b"{}"))


class _Source:
    """Replaces urllib.request.urlopen; `script` is a list of replies (an Exception is raised, anything else returned as the JSON body)."""
    def __init__(self, monkeypatch, pa, *script):
        self.script, self.calls = list(script), 0
        monkeypatch.setattr(pa.urllib.request, "urlopen", self)

    def __call__(self, req, timeout=None):
        self.calls += 1
        r = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(r, Exception):
            raise r
        return _Resp(r)


def _ledger(pa, rows):
    p = pa.LEDGER
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


def _row(tk="SYA", date="2026-09-29", price="10.0", thesis="[insider] x", **kw):
    r = {"date": date, "ticker": tk, "call": "long", "thesis": thesis, "price_at_call": price, "check_date": "2026-10-29",
         "price_at_check": "", "outcome": "", "stale_quote": "no", "tags": "fund", "void_reason": ""}
    r.update(kw)
    return r


def _main(pa, monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["price_audit.py", "--open-only", *args])
    rc = pa.main()
    return rc, capsys.readouterr().out


# ---------------------------------------------------------------- 1
@pytest.mark.parametrize("why,err", [
    ("HTTP 429", _http(429)), ("HTTP 503", _http(503)), ("HTTP 403", _http(403)),
    ("URLError", urllib.error.URLError("dns")), ("timeout", socket.timeout("t")),
    ("a body that is not JSON", ValueError("not json")),
    ("a reply of the wrong shape", {"chart": {"result": [{"timestamp": [1]}], "error": None}}),
    ("an unknown error body", {"chart": {"result": None, "error": {"code": "Internal Error"}}}),
    ("no chart key", {"oops": 1}),
])
def test_01_a_transient_failure_is_reported_and_never_cached(pa, monkeypatch, why, err):
    cache = {}
    src = _Source(monkeypatch, pa, err)
    b, msg, kind = pa._bars("SYA", cache, need="2026-09-30")
    assert b is None and kind == "transient" and "transient fetch error" in msg and "not cached" in msg, why
    assert cache == {}, f"{why}: a failed read left a trace in the cache: {cache}"       # no ticker entry, no _not_found section
    src2 = _Source(monkeypatch, pa, _chart(GOOD))
    b, msg, kind = pa._bars("SYA", cache, need="2026-09-30")
    assert kind == "ok" and set(b) == set(GOOD) and cache["SYA"] == b and src2.calls == 1       # the next run reads the source and succeeds


# ---------------------------------------------------------------- 2
def test_02_a_404_is_remembered_for_its_session_only(pa, monkeypatch):
    cache = {}
    src = _Source(monkeypatch, pa, _http(404))
    b, msg, kind = pa._bars("GONE", cache)
    assert b is None and kind == "not_found" and "HTTP 404" in msg
    ent = cache[pa.NOT_FOUND]["GONE"]
    assert ent["settled"] == SETTLED and ent["why"] == "HTTP 404 Not Found" and ent["at"]
    assert "GONE" not in cache                                                       # no series entry, no "UNFETCHABLE" string
    b, msg, kind = pa._bars("GONE", cache)                                           # same settled session: not asked again
    assert b is None and kind == "not_found" and src.calls == 1 and "asked again after the next close" in msg
    monkeypatch.setattr(pa, "_settled_day", lambda: "2026-10-02")                     # the next close has settled: asked again
    b, msg, kind = pa._bars("GONE", cache)
    assert kind == "not_found" and src.calls == 2 and cache[pa.NOT_FOUND]["GONE"]["settled"] == "2026-10-02"
    monkeypatch.setattr(pa, "_settled_day", lambda: "2026-10-05")                     # a later session; the symbol now exists (a new listing): the memory clears
    _Source(monkeypatch, pa, _chart(GOOD))
    b, msg, kind = pa._bars("GONE", cache)
    assert kind == "ok" and "GONE" not in cache.get(pa.NOT_FOUND, {}) and cache["GONE"] == b
    monkeypatch.setattr(pa, "_settled_day", lambda: "2026-10-02")
    cache2 = {pa.NOT_FOUND: {"GONE": {"why": "HTTP 404 Not Found", "settled": "2026-10-02", "at": "x"}}}
    src3 = _Source(monkeypatch, pa, _http(404))
    pa._bars("GONE", cache2)                                                         # inside its session -> remembered
    assert src3.calls == 0
    pa._bars("GONE", cache2, refresh=True)                                           # --refresh asks anyway
    assert src3.calls == 1


# ---------------------------------------------------------------- 3
def test_03_a_not_found_body_and_an_empty_reply_are_definitive_other_codes_are_not(pa, monkeypatch):
    for body, want, frag in [
        ({"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"}}}, "not_found", "Not Found"),
        ({"chart": {"result": [{"indicators": {"quote": [{}]}}], "error": None}}, "not_found", "no bars in range"),
        ({"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{}]}}], "error": None}}, "not_found", "no bars in range"),
        ({"chart": {"result": None, "error": {"code": "Too Many Requests"}}}, "transient", "no result"),
        ({"chart": {"result": None, "error": None}}, "transient", "no error code"),
    ]:
        cache = {}
        _Source(monkeypatch, pa, body)
        b, msg, kind = pa._bars("SYA", cache)
        assert b is None and kind == want and frag in msg, (body, msg)
        assert (pa.NOT_FOUND in cache) == (want == "not_found")


# ---------------------------------------------------------------- 4
def test_04_a_pre_ins029_permanent_marker_is_ignored_and_replaced(pa, monkeypatch):
    cache = {"SYA": "UNFETCHABLE"}
    src = _Source(monkeypatch, pa, _chart(GOOD))
    b, msg, kind = pa._bars("SYA", cache, need="2026-09-30")
    assert src.calls == 1 and kind == "ok" and cache["SYA"] == b                    # the marker was not believed
    cache = {"SYA": "UNFETCHABLE"}
    src = _Source(monkeypatch, pa, _http(429))
    b, msg, kind = pa._bars("SYA", cache)
    assert src.calls == 1 and b is None and kind == "transient"                      # it did not short-circuit the read either


# ---------------------------------------------------------------- 5
def test_05_a_failed_refresh_never_overwrites_good_bars(pa, monkeypatch):
    good = {d: list(v) for d, v in GOOD.items()}
    for err in (_http(429), _http(404)):
        cache = {"SYA": {d: list(v) for d, v in good.items()}}
        _Source(monkeypatch, pa, err)
        b, msg, kind = pa._bars("SYA", cache, need="2026-10-01")                     # the cache lacks 10-01, so a refresh is tried
        assert b is None and cache["SYA"] == good, "a failed refresh replaced the good bars"


def test_05b_bars_already_held_still_verify_their_rows_after_a_later_not_found(pa, monkeypatch):
    good = {d: list(v) for d, v in GOOD.items()}
    cache = {"SYA": {d: list(v) for d, v in good.items()}}
    src = _Source(monkeypatch, pa, _http(404))
    b, msg, kind = pa._bars("SYA", cache, need="2026-10-01")                         # a newer day is wanted: the refresh is tried and the source says not found
    assert b is None and kind == "not_found" and cache["SYA"] == good and cache[pa.NOT_FOUND]["SYA"]["settled"] == SETTLED and src.calls == 1
    b, msg, kind = pa._bars("SYA", cache, need="2026-09-30")                         # a day we hold: still verified from the held bars, no read
    assert kind == "ok" and b == good and src.calls == 1
    b, msg, kind = pa._bars("SYA", cache, need="2026-10-01")                         # the newer day: not asked again inside this session
    assert b is None and kind == "not_found" and src.calls == 1


# ---------------------------------------------------------------- 6
def test_06_a_transient_failure_is_not_read_again_within_a_run(pa, monkeypatch):
    _ledger(pa, [_row("SYA", "2026-09-29"), _row("SYA", "2026-09-30", "10.2")])
    src = _Source(monkeypatch, pa, _http(429))
    b = pa.audit(open_only=True)
    assert src.calls == 1 and len(b["UNFETCHABLE"]) == 2 and all(r["source"] == "transient" for r in b["UNFETCHABLE"])
    assert not os.path.exists(pa.CACHE) or json.load(open(pa.CACHE)) == {}          # nothing was written for it


# ---------------------------------------------------------------- 7
def test_07_a_transient_failure_on_a_priced_row_is_named_not_cached_and_not_called_ok(pa, monkeypatch, capsys):
    _ledger(pa, [_row("AAPL", price="1.00")])                                         # a wrong price nobody can check this run
    _Source(monkeypatch, pa, _http(429))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0                                                                    # HEAD's exit clause stands: whether this should fail the audit is a ruling
    assert "UNFETCHABLE 1" in out and "transient fetch error (HTTP 429)" in out
    assert "UNVERIFIED — 1 priced row(s) were not checked: UNFETCHABLE 1, NO_BAR for a settled day 0, bar not settled yet 0" in out
    assert "OK for the rows it could check - not for the UNVERIFIED rows above." in out and "OK — every priced row sits inside" not in out
    assert json.load(open(pa.CACHE)) == {}                                           # the poisoned-cache path is closed
    # and with the source back, the same row is checked, and the wrong price is caught
    _Source(monkeypatch, pa, _chart({"2026-09-29": (150.0, 155.0, 151.0, 154.0, 5000)}))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 1 and "below low" in out and "UNVERIFIED" not in out


# ---------------------------------------------------------------- 8
def test_08_a_settled_day_with_no_bar_and_a_non_session_call_date_are_unverified(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-09-28", "10.0")])                                  # settled (09-28 <= 10-01), but the source has no 09-28 bar
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "NO_BAR 1" in out and "no bar dated 2026-09-28 for SYA" in out
    assert "UNVERIFIED — 1 priced row(s) were not checked: UNFETCHABLE 0, NO_BAR for a settled day 1, bar not settled yet 0" in out and "OK — every priced row" not in out
    _ledger(pa, [_row("SYB", "2026-09-26", "10.0")])                                  # a Saturday
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "no bar dated 2026-09-26 for SYB" in out and "UNVERIFIED — 1" in out


# ---------------------------------------------------------------- 9
def test_09_a_bar_that_has_not_settled_is_waiting_not_missing(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-10-02", "10.0")])                                  # 10-02 is after the pinned settled session
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "NO_BAR 1" in out and "has not settled yet - not a missing bar" in out
    assert "UNVERIFIED — 1 priced row(s) were not checked: UNFETCHABLE 0, NO_BAR for a settled day 0, bar not settled yet 1" in out
    assert "OK for the rows it could check" in out and "OK — every priced row sits inside" not in out
    b = pa.audit(open_only=True)
    assert b["NO_BAR"][0]["unsettled"] is True


def test_09b_the_settled_session_itself_is_missing_the_next_one_is_waiting(pa, monkeypatch):
    _Source(monkeypatch, pa, _chart(GOOD))
    _ledger(pa, [_row("SYA", SETTLED, "10.0")])                                       # the last SETTLED session: its bar must exist, so its absence is a finding
    b = pa.audit(open_only=True)
    assert len(b["NO_BAR"]) == 1 and not b["NO_BAR"][0].get("unsettled") and b["NO_BAR"][0]["note"] == f"no bar dated {SETTLED} for SYA"
    _ledger(pa, [_row("SYB", "2026-10-02", "10.0")])                                  # the day after: not settled yet, so waiting
    b = pa.audit(open_only=True)
    assert len(b["NO_BAR"]) == 1 and b["NO_BAR"][0]["unsettled"] is True


# ---------------------------------------------------------------- 10
def test_10_queued_rows_are_not_priced_rows(pa, monkeypatch, capsys):
    queued = ("[insider] x [QUEUED at 2026-09-30T08:35 PT (INS-020/REG-PP-002): written before the 2026-09-30 close settled; "
              "fills at the first official open after registration]")
    _ledger(pa, [_row("SYQ", "2026-09-30", "", queued)])
    _Source(monkeypatch, pa, _http(429))                                              # never read: a QUEUED row has no price to audit
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "QUEUED 1" in out and "fills after the" in out and "OK — every priced row sits inside its call-day bar." in out
    assert "UNVERIFIED" not in out                                                    # a QUEUED row is waiting by design: it does not qualify the OK
    _ledger(pa, [_row("SYQ", "2026-09-30", "", queued), _row("SYA", "2026-10-02", "10.0")])
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "QUEUED 1" in out and "NO_BAR 1" in out and "OK for the rows it could check" in out


# ---------------------------------------------------------------- 11
def test_11_a_violation_wins_and_a_clean_run_is_plainly_ok(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-09-29", "12.0"), _row("SYB", "2026-09-29", "10.0")])
    _Source(monkeypatch, pa, _chart(GOOD), _http(429))                                # SYA's bar: price 12.0 is above the 9-11 range -> FAIL; SYB's read fails
    rc, out = _main(pa, monkeypatch, capsys)                                          # a post-fix REF_MISMATCH wins over an unreadable neighbour
    assert rc == 1 and "FAIL — 1 open row(s) dated >= 2026-09-28 do not carry the price the rule owes" in out
    assert "UNVERIFIED — 1 priced row(s) were not checked" in out and "OK for the rows it could check" not in out
    _ledger(pa, [_row("SYL", "2026-09-25", "12.0"), _row("SYB", "2026-09-29", "10.0")])
    _Source(monkeypatch, pa, _chart({"2026-09-25": (9.0, 11.0, 9.5, 10.0, 1000)}), _http(429))
    rc, out = _main(pa, monkeypatch, capsys)                                          # a legacy range FAIL (dated before the reference test) wins too
    assert rc == 1 and "FAIL — 1 row(s) priced outside their own call-day bar" in out and "UNVERIFIED — 1 priced row(s)" in out
    _ledger(pa, [_row("SYA", "2026-09-29", "10.0")])
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys)
    assert rc == 0 and "OK — every priced row sits inside its call-day bar." in out and "UNVERIFIED" not in out


# ---------------------------------------------------------------- 12
def test_12_json_mode_keeps_the_exit_status_and_stays_pure_json(pa, monkeypatch, capsys):
    _ledger(pa, [_row("SYA", "2026-09-29", "10.0"), _row("SYB", "2026-09-29", "10.0")])
    _Source(monkeypatch, pa, _chart(GOOD), _http(429))
    rc, out = _main(pa, monkeypatch, capsys, "--json")
    d = json.loads(out)                                                               # the resolver's checks json.loads(stdout): nothing else may print
    assert rc == 0 and len(d["UNFETCHABLE"]) == 1 and d["UNFETCHABLE"][0]["ticker"] == "SYB" and d["UNFETCHABLE"][0]["source"] == "transient"
    assert len(d["PASS"]) == 1 and d["REF_MISMATCH"] == [] and d["FAIL"] == [] and "REF_OK" in d
    _ledger(pa, [_row("SYA", "2026-09-29", "12.0")])
    _Source(monkeypatch, pa, _chart(GOOD))
    rc, out = _main(pa, monkeypatch, capsys, "--json")
    assert rc == 1 and len(json.loads(out)["REF_MISMATCH"]) == 1                      # a violation still exits 1, as at HEAD
    _ledger(pa, [_row("SYA", "2026-09-29", "10.0")])
    rc, out = _main(pa, monkeypatch, capsys, "--json")
    assert rc == 0 and json.loads(out)["UNFETCHABLE"] == []

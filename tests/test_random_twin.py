"""RANDOM-TWIN/v1 - the insider desk against matched random twins (research/random_twin/PREREG_RANDOM_TWIN_v1.md). MEASUREMENT ONLY.

Pinned here so a later edit turns a test red instead of quietly changing what the pre-registration meant:
  * RULE is frozen: its SHA-256 is a literal here and on the prereg page (a change is RANDOM-TWIN/v2, never an edit);
  * the desk's own conventions: entry at the named official open or the call-day close, exit at the first traded bar on/after
    check_date, zero-volume / unprinted bars dropped (Firm Brain s18), settled bars only;
  * the population is an allowlist (right|wrong); void/open/blank are out; a delisted wrong is out of the cells, in the -100% line;
  * Twin A (C1): post-exit only and market-adjusted; on zero-skill test worlds (dip-selected entries; a market regime shift) it reads
    near zero and never BEATS/TRAILS - the two-sided draft read +4.4 pp on the dip world;
  * Twin B: same entry bar, same cell (bucket x sector, bucket-only below 10), never the desk ticker or a name near an insider buy;
  * the frozen pool refuses a changed file (C3); the replica gate (C2); week-mean-of-means sign (C6); NOT JUDGED blocks (C7);
    registration refusals (C8); the fetch gate (C9); deterministic bars-read freeze (C10); strata (C5); no desk reader (C12);
  * blank is never zero; CR1 t is the house formula; RETRO / FORWARD split at the registration date; counts only before the look.
No network: every price comes from synthetic bars or a fake fetcher.
Run: python -m pytest -q tests/test_random_twin.py
"""
import datetime as dt
import gzip
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

IR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IR / "research" / "random_twin"))
import random_twin as R  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "random_twin"
PINNED_RULE_SHA = "deca2c0ce78f453fc1241fc597e55486e1c1f9a4f52b32915f0e31b89b931d75"
ASOF = "2026-10-30"


# ------------------------------------------------------------------------------------------------ synthetic bars
def weekdays(a, b):
    d, out = dt.date.fromisoformat(a), []
    while d <= dt.date.fromisoformat(b):
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def bars(a="2026-01-02", b="2027-06-30", start=10.0, step=0.0, vol=1000, skip=(), zero=()):
    """{day: [low, high, open, close, volume]}: open = close - 0.1, close climbs by `step` a session."""
    out, px = {}, start
    for d in weekdays(a, b):
        px += step
        if d in skip:
            continue
        out[d] = [px - 0.5, px + 0.5, round(px - 0.1, 6), round(px, 6), 0 if d in zero else vol]
    return out


FLAT_MKT = R.traded(bars("2025-12-01", "2027-12-31"))


def row(ticker="DESK", date="2026-08-03", check="2026-09-02", et="close", eb=None, ret=10.0, thesis=""):
    eb = eb or date
    return {"i": 0, "ticker": ticker, "date": date, "check_date": check, "outcome": "right", "p_call": 10.0, "p_check": 11.0,
            "ret": ret, "delisted": False, "entry_type": et, "entry_bar": eb, "week": R.iso_week(eb),
            "segment": R.segment({"date": date}), "thesis": thesis}


class FakePrices:
    def __init__(self, table, transient=()):
        self.table, self.why, self.transient = table, {}, set(transient)

    def get(self, s):
        if s not in self.table:
            self.why[s] = "no price series (fixture)"
        return self.table.get(s)


# ------------------------------------------------------------------------------------------------ the frozen rule
def test_rule_sha_is_pinned_and_on_the_prereg_page():
    assert R.RULE_SHA == PINNED_RULE_SHA, "RULE changed: that is RANDOM-TWIN/v2 in the evolution ledger, never an edit"
    assert hashlib.sha256(json.dumps(R.RULE, sort_keys=True).encode()).hexdigest() == PINNED_RULE_SHA
    page = (IR / "research" / "random_twin" / "PREREG_RANDOM_TWIN_v1.md").read_text()
    assert PINNED_RULE_SHA in page and R.RULE["pool_sha256"] in page


def test_bar_values_match_the_page():
    assert abs(R.alpha_k() - 0.025321) < 1e-6                      # K = 2 (C14 BLOCK, option a: Twin B judged only)
    assert round(R.t_bar(10), 3) == 2.677 and R.t_bar(11) == 2.67 and R.t_bar(12) == 2.67 and R.t_bar(80) == 2.67
    assert R.t_bar(1) is None
    assert R.RULE["K"] == len(R.RULE["cells"]) == 2 and R.RULE["cells"] == ["RETRO-B", "FWD-B"]


# ------------------------------------------------------------------------------------------------ the desk's own conventions
def test_entry_convention_follows_the_fill_note():
    plain = {"date": "2026-08-03", "thesis": "[insider] 2 insiders bought $0.5M"}
    filled = {"date": "2026-08-04", "thesis": "x [QUEUED at ...] [FILLED 2026-08-05 official open 5.00 (REG-PP-002)]"}
    restated = {"date": "2026-09-08", "thesis": "x [RESTATED 2026-09-27 (INS-020): ... owe the first official open after registration: "
                                                "the 2026-09-09 official open 3.47. Original kept.]"}
    both = {"date": "2026-09-08", "thesis": "the 2026-09-09 official open 3.47 ... [FILLED 2026-09-10 official open 3.50]"}
    assert R.entry_of(plain) == ("close", "2026-08-03")
    assert R.entry_of(filled) == ("open", "2026-08-05")
    assert R.entry_of(restated) == ("open", "2026-09-09")
    assert R.entry_of(both) == ("open", "2026-09-10")              # the last note written wins


def test_population_is_an_allowlist_and_delisted_goes_to_the_minus_100_line():
    rows = R.load_ledger(FX / "ledger.csv")
    pop, excl = R.population(rows)
    got = {r["ticker"]: r for r in pop}
    assert set(got) == {"DESK", "QQQQ", "RRRR", "GONE", "LATE", "FWD1"}   # void, open and the unpriced void are out
    assert got["DESK"]["entry_type"] == "close" and got["DESK"]["entry_bar"] == "2026-08-03"
    assert got["QQQQ"]["entry_type"] == "open" and got["QQQQ"]["entry_bar"] == "2026-08-05"
    assert got["RRRR"]["entry_type"] == "open" and got["RRRR"]["entry_bar"] == "2026-08-06"
    assert math.isclose(got["DESK"]["ret"], 10.0) and math.isclose(got["QQQQ"]["ret"], -20.0)
    assert got["GONE"]["delisted"] and got["GONE"]["ret"] == -100.0
    assert any(e["ticker"] == "GONE" and "-100%" in e["why"] for e in excl)
    assert got["LATE"]["segment"] == "RETRO" and got["FWD1"]["segment"] == "FORWARD"


def test_segment_boundary_is_the_registration_date():
    assert R.segment({"date": "2026-10-30"}) == "RETRO"
    assert R.segment({"date": "2026-10-31"}) == "FORWARD"
    assert R.segment({"date": "2026-11-02"}) == "FORWARD"


def test_carry_forward_and_unprinted_bars_are_not_traded():
    b = bars("2026-08-03", "2026-08-07", zero=("2026-08-05",))
    b["2026-08-06"][3] = None                                      # an unprinted close
    assert [d for d, _o, _c in R.traded(b)] == ["2026-08-03", "2026-08-04", "2026-08-07"]


def test_exit_rolls_to_the_first_traded_bar_within_ten_days_and_never_past_asof():
    tb = R.traded(bars("2026-08-03", "2026-08-31", skip=("2026-08-10", "2026-08-11"), zero=("2026-08-12",)))
    assert R.exit_bar(tb, "2026-08-08", ASOF)[0] == "2026-08-13"   # weekend, two missing bars and a zero-volume bar skipped
    assert R.exit_bar(tb, "2026-08-03", ASOF)[0] == "2026-08-03"
    gap = R.traded(bars("2026-08-03", "2026-08-31", skip=tuple(weekdays("2026-08-04", "2026-08-20"))))
    assert R.exit_bar(gap, "2026-08-05", ASOF) is None             # next traded bar 16 days later: beyond the 10-day roll
    assert R.exit_bar(tb, "2026-08-20", "2026-08-19") is None      # never past the settled session


def test_settled_bars_only_from_the_source(monkeypatch):
    ts = lambda d: int(dt.datetime.fromisoformat(d + "T09:30:00").replace(tzinfo=R.NY).timestamp())
    body = {"chart": {"result": [{"timestamp": [ts("2026-10-29"), ts("2026-10-30"), ts("2026-11-02")],
                                  "indicators": {"quote": [{"low": [1, 1, 1], "high": [2, 2, 2], "open": [1.5, 1.5, 1.5],
                                                            "close": [1.6, 1.7, 1.8], "volume": [10, 10, 10]}]}}]}}

    class Resp:
        def read(self):
            return json.dumps(body).encode()

    monkeypatch.setattr(R.urllib.request, "urlopen", lambda *a, **k: Resp())
    out, kind, _ = R._fetch("ABC", "2026-10-30")
    assert kind == "ok" and sorted(out) == ["2026-10-29", "2026-10-30"]


def test_prices_cache_transient_is_never_cached_not_found_is(tmp_path, monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    calls = []

    def fetcher(sym, asof):
        calls.append(sym)
        return (None, "transient", "HTTP 429") if sym == "FLAKY" else (None, "not_found", "HTTP 404")

    p = R.Prices(ASOF, cache_path=tmp_path / "c.json", fetcher=fetcher, pause=0)
    assert p.get("FLAKY") is None and "transient" in p.why["FLAKY"] and "FLAKY" in p.transient
    assert calls.count("FLAKY") == 3                               # tried, then retried twice
    assert p.get("NOPE") is None
    p.save()
    c = json.loads((tmp_path / "c.json").read_text())
    assert "FLAKY" not in c and c["NOPE"]["nf"] is True
    off = R.Prices(ASOF, cache_path=tmp_path / "none.json", offline=True, fetcher=lambda *a: pytest.fail("network in offline mode"))
    assert off.get("ANY") is None and "offline" in off.why["ANY"]


def test_bars_read_freeze_is_deterministic(tmp_path):                 # C10
    p = R.Prices(ASOF, cache_path=tmp_path / "c.json", offline=True)
    p.c = {"AAA": {"asof": ASOF, "bars": bars("2026-08-03", "2026-08-07")}}
    p.get("AAA")
    p.get("MISSING")
    s1 = p.freeze_read(tmp_path / "a.json.gz")
    s2 = p.freeze_read(tmp_path / "b.json.gz")
    assert s1 == s2 == hashlib.sha256((tmp_path / "a.json.gz").read_bytes()).hexdigest()
    got = json.loads(gzip.decompress((tmp_path / "a.json.gz").read_bytes()))
    assert set(got) == {"AAA", "MISSING"} and got["MISSING"] is None


# ------------------------------------------------------------------------------------------------ Twin A (post-exit, market-adjusted)
def test_twin_a_is_post_exit_only_keeps_the_geometry_and_avoids_windows_and_buys():
    tb = R.traded(bars(step=0.01))
    r = row(date="2026-08-03", check="2026-09-02")
    wins = R.desk_windows([{"ticker": "DESK", "date": "2026-08-03", "check_date": "2026-09-02", "thesis": ""},
                           {"ticker": "DESK", "date": "2026-11-02", "check_date": "2026-12-02", "thesis": ""}])["DESK"]
    buys = ["2027-01-20"]
    a = R.twin_a(r, tb, buys, wins, "2027-06-30", FLAT_MKT)
    assert len(a["twins"]) == R.RULE["k_a"] and a["pre_entry_share"] == 0
    lo = R.plus("2026-09-02", 10)
    assert a["window"] == [lo, R.plus(lo, 183)]
    span = (dt.date(2026, 9, 2) - dt.date(2026, 8, 3)).days
    by = {d: (o, c) for d, o, c in tb}
    for s, p0, x, p1, ret, m in a["twins"]:
        assert lo < s <= R.plus(lo, 183)                           # strictly after the row's own blocked window
        assert x == R.exit_bar(tb, R.plus(s, span), "2027-06-30")[0]
        assert p0 == R.r4(by[s][1]) and p1 == R.r4(by[x][1])      # close entry, close exit
        assert not R.overlaps(s, x, wins)                          # never inside any desk window of the ticker
        assert not R.has_purchase(buys, R.plus(s, -14), x)          # never near a known insider buy
        assert m == 0.0                                            # a flat market adjusts nothing
    assert a["excluded"]["overlaps_a_desk_window"] > 0 and a["excluded"]["insider_purchase_near"] > 0
    assert R.twin_a(r, tb, buys, wins, "2027-06-30", FLAT_MKT) == a     # seeded: the same row always draws the same twins
    other = R.twin_a(row(date="2026-08-04", check="2026-09-03"), tb, buys, wins, "2027-06-30", FLAT_MKT)
    assert other["twins"] != a["twins"]                                 # the seed is per row


def test_twin_a_open_entry_uses_the_open_and_market_adjusts():
    tb = R.traded(bars(step=0.01))
    mkt = R.traded(bars("2025-12-01", "2027-12-31", step=0.02))
    a = R.twin_a(row(et="open", eb="2026-08-04", date="2026-08-03", check="2026-09-02"), tb, [], [], "2027-06-30", mkt)
    by, mb = {d: (o, c) for d, o, c in tb}, {d: (o, c) for d, o, c in mkt}
    for s, p0, x, p1, ret, m in a["twins"]:
        assert p0 == R.r4(by[s][0])
        assert math.isclose(m, (mb[x][1] / mb[s][0] - 1) * 100, abs_tol=1e-3)
    assert math.isclose(a["mean"], a["mean_raw"] - R.mean([t[5] for t in a["twins"]]), abs_tol=1e-3)


def test_twin_a_is_blank_with_a_reason_when_no_post_exit_window_yet():
    tb = R.traded(bars(step=0.01))
    a = R.twin_a(row(date="2026-09-28", check="2026-10-28"), tb, [], [], ASOF, FLAT_MKT)
    assert "twins" not in a and "mean" not in a and "fewer than 5" in a["why"]


def _world(seed, n, select, regime):
    """Zero-skill prices. select='dip': entry = first day in Jul 15 - Sep 28 2026 after a > 35% fall over 100 sessions (as insiders
    buy); 'random': a random day. regime=True: stock = market + noise, the market rising Jan-Jun 2026, falling Jul-Dec 2026."""
    rng = random.Random(seed)
    days = weekdays("2025-12-01", "2027-06-30")
    mpx, mk = 100.0, {}
    for d in days:
        o = mpx
        drift = (0.0011 if d < "2026-07-01" else -0.0013 if d < "2027-01-01" else 0.0004) if regime else 0.0
        mpx *= math.exp(drift + rng.gauss(0, 0.01))
        mk[d] = [min(o, mpx), max(o, mpx), o, mpx, 1000]
    mtb = R.traded(mk)
    mlog = {d: math.log(mk[d][3] / mk[d][2]) for d in days}
    recs = []
    for k in range(n):
        px, b = 10.0, {}
        for d in days:
            o = px
            px *= math.exp((mlog[d] if regime else 0.0) + rng.gauss(0, 0.03))
            b[d] = [min(o, px), max(o, px), o, px, 1000]
        tb = R.traded(b)
        closes = {d: c for d, _o, c in tb}
        cand = [d for d in days if "2026-07-15" <= d <= "2026-09-28"]
        if select == "dip":
            ok = [d for d in cand if days.index(d) >= 100 and closes[d] / closes[days[days.index(d) - 100]] - 1 < -0.35]
            if not ok:
                continue
            e = ok[0]
        else:
            e = rng.choice(cand)
        chk = R.plus(e, 30)
        x = R.exit_bar(tb, chk, "2027-06-30")
        r = row(ticker=f"S{k}", date=e, check=chk, ret=(x[1] / closes[e] - 1) * 100)
        wins = R.desk_windows([{"ticker": f"S{k}", "date": e, "check_date": chk, "thesis": ""}])[f"S{k}"]
        a = R.twin_a(r, tb, [], wins, "2027-06-30", mtb)
        m_desk = R.mkt_ret(mtb, e, "close", x[0])
        if "mean" not in a or m_desk is None:
            continue
        assert a["pre_entry_share"] == 0
        recs.append({"week": r["week"], "d_a": (r["ret"] - m_desk) - a["mean"]})
    return recs


@pytest.mark.parametrize("select,regime", [("dip", False), ("random", True), ("dip", True)])
def test_zero_skill_worlds_read_near_zero_and_never_pass(select, regime):   # C1: the reviewer's test worlds
    recs = []
    for s in range(3):
        recs += _world(7000 + s, 260, select, regime)
    xs = [r["d_a"] for r in recs]
    mu = sum(xs) / len(xs)
    se = (sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 / len(xs) ** 0.5
    assert len(xs) >= 150
    assert abs(mu) < 2 * se, f"{select}/{regime}: mean d_A {mu:+.2f} pp (se {se:.2f}) is not near zero"
    v = R.judge(recs, "d_a")
    assert v["n_weeks"] >= 10 and v["verdict"] == "NO-DIFFERENCE", v


# ------------------------------------------------------------------------------------------------ Twin B
def test_pool_filter_buckets_and_cells():
    pool = R.load_pool(FX / "pool.csv", verify=False)
    assert "SECD" not in pool and "ADR1" not in pool and "NOCP" not in pool   # secondary listing, DR, no market cap
    assert pool["DESK"] == ("micro", "Finance") and pool["SM01"] == ("small", "Finance") and pool["BRK-B"] == ("large", "Finance")
    assert R.cell_of("DESK", pool) == ("micro", "Finance")          # 13 micro banks >= 10
    assert R.cell_of("BIO1", pool) == ("micro", "*")                # 2 micro biotechs < 10: the whole bucket
    assert R.cell_of("LONE", pool) == ("small", "*")
    assert R.cell_of("ZZZZ", pool) is None
    assert R.bucket_of(3e8) == "small" and R.bucket_of(2.99e8) == "micro" and R.bucket_of(1e10) == "large"
    assert R.panel(("micro", "Finance"), pool) == sorted(s for s, v in pool.items() if v == ("micro", "Finance"))


def test_the_frozen_pool_refuses_a_changed_file(tmp_path):            # C3
    with pytest.raises(SystemExit, match="not the frozen pool"):
        R.load_pool(FX / "pool.csv")
    real = IR / "research" / "random_twin" / "pool_universe_2026-10-17.csv"
    assert R.sha256_file(real) == R.RULE["pool_sha256"]
    assert len(R.load_pool(real)) > 4000
    bad = tmp_path / "pool.csv"
    bad.write_text(real.read_text().replace("Finance", "Financx", 1))
    with pytest.raises(SystemExit, match="not the frozen pool"):
        R.load_pool(bad)


def test_panel_is_seeded_and_capped():
    pool = {f"S{i:03d}": ("micro", "Finance") for i in range(100)}
    p1, p2 = R.panel(("micro", "Finance"), pool), R.panel(("micro", "Finance"), pool)
    assert p1 == p2 and len(p1) == R.RULE["panel_size"] and set(p1) <= set(pool)


def test_twin_b_same_day_same_cell_excludes_desk_ticker_buyers_and_dead_names():
    pool = R.load_pool(FX / "pool.csv", verify=False)
    table = {s: bars(step=0.01 * (k + 1)) for k, s in enumerate(sorted(pool))}
    table["DEAD"] = bars("2026-01-02", "2026-08-20")                # stops trading before the exit
    table["BK10"] = bars(skip=("2026-08-03",))                      # no bar on the entry day: no substitution
    feed = {"BUYR": ["2026-08-10"]}
    r = row(ticker="DESK", date="2026-08-03", check="2026-09-02")
    cell = R.cell_of("DESK", pool)
    b = R.twin_b(r, cell, R.panel(cell, pool), FakePrices(table), feed, {}, ASOF)
    assert {t[0] for t in b["twins"]} == {f"BK0{i}" for i in range(1, 10)}
    assert b["excluded"]["desk_ticker"] == 1 and b["excluded"]["insider_purchase_near"] == 1
    assert b["excluded"]["no_settled_exit"] == 1 and b["excluded"]["no_trade_on_entry_bar"] == 1
    for s, p0, x, p1, ret in b["twins"]:
        assert x == R.exit_bar(R.traded(table[s]), "2026-09-02", ASOF)[0]
        assert p0 == R.r4(table[s]["2026-08-03"][3])                # the close on the desk's own entry bar
    assert R.twin_b(r, cell, R.panel(cell, pool), FakePrices(table), feed, {}, ASOF) == b


def test_twin_b_blank_with_reason_and_panel_fetch_failures_named():   # C9: panel failures get their own reason
    b = R.twin_b(row(ticker="ZZZZ"), None, [], FakePrices({}), {}, {}, ASOF)
    assert "not in the pool snapshot" in b["why"] and "mean" not in b
    pool = R.load_pool(FX / "pool.csv", verify=False)
    pan = R.panel(("micro", "Finance"), pool)
    b2 = R.twin_b(row(), ("micro", "Finance"), pan, FakePrices({}, transient={"BK01", "BK02"}), {}, {}, ASOF)
    assert "fewer than 5" in b2["why"] and "mean" not in b2
    assert b2["excluded"]["panel_fetch_failed"] == 2 and b2["excluded"]["no_price_series"] == 10


def test_build_row_blank_is_not_zero():
    pool = R.load_pool(FX / "pool.csv", verify=False)
    rec = R.build_row(row(ticker="ZZZZ"), FakePrices({}), {}, {}, pool, ASOF, FLAT_MKT)
    assert rec["d_a"] is None and rec["d_b"] is None and rec["twin_a"]["why"] and rec["twin_b"]["why"]
    j = R.judge([dict(rec, week=202632)], "d_a")
    assert j["n_rows"] == 0 and j["blank_rows"] == 1 and j["verdict"] == "UNREADABLE"
    deferred = R.build_row(row(ticker="ZZZZ"), FakePrices({}), {}, {}, pool, ASOF, FLAT_MKT, build_a=False)
    assert "deferred" in deferred["twin_a"] and deferred["d_a"] is None


def test_fetch_gate_refuses_on_a_desk_ticker_or_the_market():        # C9
    p = FakePrices({}, transient={"DESK"})
    with pytest.raises(SystemExit, match="desk ticker / market"):
        R.fetch_gate(p, {"DESK", "IWM"}, {"BK01"})
    p = FakePrices({}, transient={"IWM"})
    with pytest.raises(SystemExit, match="desk ticker / market"):
        R.fetch_gate(p, {"DESK", "IWM"}, {"BK01"})
    p = FakePrices({}, transient={f"P{i}" for i in range(6)})
    with pytest.raises(SystemExit, match="failed transiently"):
        R.fetch_gate(p, {"DESK", "IWM"}, {f"P{i}" for i in range(98)})
    R.fetch_gate(FakePrices({}, transient={"P1"}), {"DESK", "IWM"}, {f"P{i}" for i in range(98)})   # 1 of 100: allowed


# ------------------------------------------------------------------------------------------------ inference
def test_cr1_t_is_the_house_formula():
    vals = [1.0, 2.0, -1.0, 3.0, 0.5, 2.5, -0.5, 1.5]
    wk = [1, 1, 2, 2, 3, 3, 4, 4]
    n, G, m = len(vals), 4, sum(vals) / len(vals)
    sums = {}
    for v, w in zip(vals, wk):
        sums[w] = sums.get(w, 0) + (v - m)
    var = (G / (G - 1)) * sum(s * s for s in sums.values()) / n ** 2
    assert math.isclose(R.cr1_t(vals, wk), m / math.sqrt(var), rel_tol=1e-12)
    pe = Path.home() / "spy-trading" / "src" / "pattern_engine_run.py"
    if pe.exists():                                               # same as the pattern desk's own copy, if it is on this machine
        assert "var = (G / (G - 1)) * float((s ** 2).sum()) / n ** 2" in pe.read_text()


def recs_for(weeks, per_week, f, key="d_a"):
    return [{"week": w, key: f(k, j)} for k, w in enumerate(weeks) for j in range(per_week)]


WEEKS = [202629 + k for k in range(12)]


def test_verdict_beats_trails_no_difference_unreadable():
    beats = recs_for(WEEKS, 4, lambda k, j: 5.0 + (j - 1.5) * 0.5 + (k % 3) * 0.2)
    assert R.judge(beats, "d_a")["verdict"] == "BEATS-TWIN"
    trails = recs_for(WEEKS, 4, lambda k, j: -(5.0 + (j - 1.5) * 0.5 + (k % 3) * 0.2))
    assert R.judge(trails, "d_a")["verdict"] == "TRAILS-TWIN"
    noisy = recs_for(WEEKS, 4, lambda k, j: (1 if k % 2 else -1) * 3.0 + j * 0.1)
    assert R.judge(noisy, "d_a")["verdict"] == "NO-DIFFERENCE"
    j9 = R.judge(recs_for(WEEKS[:9], 4, lambda k, j: 5.0 + j * 0.1), "d_a")     # 9 weeks: below the minimum
    assert j9["verdict"] == "UNREADABLE" and "10 entry weeks" in j9["why"]
    few = recs_for(WEEKS, 2, lambda k, j: 5.0 + j * 0.1 + k * 0.01)             # 24 rows: below 30
    assert R.judge(few, "d_a")["verdict"] == "UNREADABLE"


def test_both_halves_and_drop_best_week_can_veto_a_pass():
    jh = R.judge(recs_for(WEEKS, 4, lambda k, j: (8.0 if k >= 6 else -0.2) + j * 0.01), "d_a")
    assert jh["halves"]["first"]["mean_d_pp"] < 0 and jh["verdict"] != "BEATS-TWIN"
    jw = R.judge(recs_for(WEEKS, 4, lambda k, j: (400.0 if k == 5 else -1.0) + j * 0.01), "d_a")
    assert jw["drop_best_week"]["week"] == WEEKS[5] and jw["drop_best_week"]["mean_d_pp"] < 0 and jw["verdict"] != "BEATS-TWIN"


def test_week_mean_of_means_must_share_the_sign(monkeypatch):        # C6 (Brain s17)
    recs = []
    for k, w in enumerate(WEEKS):
        if k in (0, 1, 6, 7):                                                         # four broad weeks, two in each half
            recs += [{"week": w, "d_a": 3.0 + 0.01 * j} for j in range(60)]
        else:
            recs += [{"week": w, "d_a": -2.0 + 0.01 * j} for j in range(2)]          # eight narrow losing weeks
    monkeypatch.setattr(R, "cr1_t", lambda v, w: 10.0)                               # isolate the sign rule from t
    j = R.judge(recs, "d_a")
    assert j["mean_d_pp"] > 0 and j["halves"]["first"]["mean_d_pp"] > 0 and j["halves"]["second"]["mean_d_pp"] > 0
    assert j["drop_best_week"]["mean_d_pp"] > 0 and j["week_mean_of_means_pp"] < 0
    assert j["verdict"] == "NO-DIFFERENCE"                                           # only the week-mean sign blocked the pass
    for r in recs:
        r["d_a"] = abs(r["d_a"])
    assert R.judge(recs, "d_a")["verdict"] == "BEATS-TWIN"


def test_replica_gate_makes_a_disagreeing_pass_data_sensitive():     # C2
    good = recs_for(WEEKS, 4, lambda k, j: 5.0 + (j - 1.5) * 0.5 + (k % 3) * 0.2)
    for r in good:
        r["d_a_replica"] = r["d_a"] if r["week"] != WEEKS[0] else -40.0
    g = R.gated(R.judge(good, "d_a"), R.judge(good, "d_a_replica"))
    assert g["ledger_verdict"] == "BEATS-TWIN" and g["replica_verdict"] != "BEATS-TWIN"
    assert g["verdict"] == "DATA-SENSITIVE" and g["data_sensitive"]
    for r in good:
        r["d_a_replica"] = r["d_a"]
    assert R.gated(R.judge(good, "d_a"), R.judge(good, "d_a_replica"))["verdict"] == "BEATS-TWIN"


def test_overall_routes_only_a_forward_pass_and_retro_never():      # R4
    for v in ("BEATS-TWIN", "TRAILS-TWIN", "NO-DIFFERENCE", "UNREADABLE", "DATA-SENSITIVE"):
        t = R.overall_b({"verdict": v}, retro=True)
        assert t.startswith("RETROSPECTIVE") and "edge-refute" not in t and "SEPARATED" not in t.replace("NOT SEPARATED", "")
    assert "/edge-refute" in R.overall_b({"verdict": "BEATS-TWIN"}, retro=False)
    for v in ("TRAILS-TWIN", "NO-DIFFERENCE", "DATA-SENSITIVE"):
        assert R.overall_b({"verdict": v}, retro=False).startswith("NOT SEPARATED")
    assert R.overall_b({"verdict": "UNREADABLE"}, retro=False).startswith("UNREADABLE")


def _full(recs):
    for r in recs:
        r.update({"d_b": r["d_a"], "d_a_replica": r["d_a"], "d_b_replica": r["d_a"], "delisted": False, "desk_ret": 1.0,
                  "replica_ret": 1.0, "twin_a": {"mean": 0.0}, "twin_b": {"mean": 0.0, "cell": ["micro", "Finance"]},
                  "context_iwm_same_bars_ret": 0.0, "entry_type": "close", "key": "X|2026-08-03|2026-09-02", "ticker": "X",
                  "check_date": "2026-09-02", "cluster_usd": 50000.0 if r["week"] % 2 else 250000.0})
    return recs


def test_reading_keeps_delisted_out_and_shows_strata():               # C5
    good = _full(recs_for(WEEKS, 4, lambda k, j: 1.0 + j))
    dead = dict(good[0], delisted=True, d_a=-100.0, d_b=-100.0, desk_ret=-100.0)
    rd = R.reading(good + [dead], [], account_keys={"X|2026-09-02"})
    assert rd["cells"]["B_same_day_similar_stock"]["n_rows"] == len(good)
    assert rd["delisted_at_minus_100"]["rows"] == 1 and rd["delisted_at_minus_100"]["B_mean_d_pp"] < rd["cells"]["B_same_day_similar_stock"]["mean_d_pp"]
    st = rd["shown"]["strata_ins002"]
    assert st["ge_100k"]["rows"] + st["lt_100k"]["rows"] + st["unknown"]["rows"] == len(good)
    assert st["ge_100k"]["rows"] > 0 and st["lt_100k"]["rows"] > 0
    assert rd["shown"]["account_held_vs_withheld_port006"]["held_by_the_account"] == len(good)
    assert rd["overall"].startswith(("NOT SEPARATED", "BEATS SAME-DAY", "UNREADABLE"))


def test_never_judged_blocks_print_no_verdict():                      # C7
    good = _full(recs_for(WEEKS, 4, lambda k, j: 5.0 + (j - 1.5) * 0.5 + (k % 3) * 0.2))
    rd = R.reading(good, [], judged=False)
    text = json.dumps(rd)
    assert "overall" not in rd and rd["status"].startswith("NOT JUDGED")
    for c in rd["cells"].values():
        assert c["status"] == "NOT JUDGED" and "verdict" not in c
    assert "BEATS-TWIN" not in text and "SEPARATED" not in text and "edge-refute" not in text


def test_strata_use_the_ins002_parser():
    assert R.cluster_usd("[insider] 2 insiders bought $22.0M cluster") == 22_000_000
    assert R.cluster_usd("[insider] 2 insiders bought $0.43M within 14d") == 430_000
    assert R.cluster_usd("no amount here") is None


def test_twin_a_is_shown_only_and_never_judged():                     # C14 BLOCK, option a
    good = _full(recs_for(WEEKS, 4, lambda k, j: 5.0 + (j - 1.5) * 0.5 + (k % 3) * 0.2))
    rd = R.reading(good, [], retro=False)
    a = rd["cells"]["A_same_stock_post_exit_shown_only"]
    assert R.judge(good, "d_a")["verdict"] == "BEATS-TWIN"                  # it would pass if it were judged...
    assert a["status"] == "NOT JUDGED" and "verdict" not in a and "replica_verdict" not in a   # ...but it is shown only
    assert "beta" in a["caveat"] and "+1.76" in a["caveat"] and "-2.72" in a["caveat"]
    assert rd["cells"]["B_same_day_similar_stock"]["verdict"] == "BEATS-TWIN"
    assert "A_" not in rd["overall"] and "Twin A" not in rd["overall"]


def test_prefetch_fixes_the_symbol_set_before_any_row(tmp_path, monkeypatch):   # R2
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    calls = {"BK01": 0}

    def fetcher(sym, asof):
        if sym == "BK01":
            calls["BK01"] += 1
            if calls["BK01"] <= 3:
                return None, "transient", "HTTP 429"                       # fails its first read (and both retries) ...
        return bars(step=0.01), "ok", ""                                    # ... and would succeed if asked again
    pool = R.load_pool(FX / "pool.csv", verify=False)
    cell = R.cell_of("DESK", pool)
    pan = R.panel(cell, pool)
    p = R.Prices(ASOF, cache_path=tmp_path / "c.json", fetcher=fetcher, pause=0)
    p.prefetch(set(pan) | {"DESK", "IWM"})
    assert p.offline and "BK01" in p.transient
    r1, r2 = row(date="2026-08-03", check="2026-09-02"), row(date="2026-08-10", check="2026-09-09")
    b1 = R.twin_b(r1, cell, pan, p, {}, {}, ASOF)
    b2 = R.twin_b(r2, cell, pan, p, {}, {}, ASOF)
    assert b1["excluded"]["panel_fetch_failed"] == b2["excluded"]["panel_fetch_failed"] == 1
    assert "BK01" not in {t[0] for t in b1["twins"]} | {t[0] for t in b2["twins"]}
    assert calls["BK01"] == 3                                               # never re-asked after the prefetch
    with pytest.raises(SystemExit, match="desk ticker / market"):
        R.fetch_gate(p, {"BK01", "IWM"}, set())


# ------------------------------------------------------------------------------------------------ discipline
def test_look_prints_counts_only_before_the_look(monkeypatch, capsys):
    monkeypatch.setattr(R, "LEDGER", FX / "ledger.csv")
    monkeypatch.setattr(R, "settled_asof", lambda: "2027-09-29")
    for name in ("compute", "feed_union", "twin_a", "twin_b", "judge", "registration_check", "load_pool"):
        monkeypatch.setattr(R, name, lambda *a, **k: pytest.fail("evaluated before the look"))
    R.main(["look"])
    out = capsys.readouterr().out
    assert "counts only" in out and "FORWARD 1 scored rows" in out


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True)


def _commit(repo):
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "fixture", "--allow-empty")


def _setup(tmp_path, gens, issues=None):
    repo = tmp_path / "insider-radar"
    for rel in R.FROZEN:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(f"{rel}\n")
    _git(repo, "init", "-q")
    _commit(repo)
    cc = tmp_path / "command-center"
    (cc / "council").mkdir(parents=True)
    (cc / R.EVO_REL).write_text(json.dumps({"generations": gens}))
    (cc / "council" / "issues.json").write_text(json.dumps({"_": "register", "rows": issues or []}))
    _git(cc, "init", "-q")
    _commit(cc)
    shas = {f"insider-radar/{rel}": R.sha256_file(repo / rel) for rel in R.FROZEN}
    kw = dict(me=repo / R.SCRIPT_REL, repo=repo, evo=cc / R.EVO_REL, cc_repo=cc, issues=cc / "council" / "issues.json")
    return repo, cc, shas, kw


def _reg(shas, **over):
    g = {"gen": 46, "id": "RANDOM-TWIN/v1", "trials_charged": 2, "frozen_sha256": shas,
         "variants": [{"id": f"RANDOM-TWIN/v1/{c}", "status": "registered"} for c in ("RETRO-B", "FWD-B")]}
    g.update(over)
    return g


def test_run_refuses_outside_the_committed_repo_copy(tmp_path):
    with pytest.raises(SystemExit, match="refusing - run the committed repo copy"):
        R.registration_check(me=tmp_path / "random_twin.py", repo=tmp_path / "repo", evo=tmp_path / "evo.json")


def test_registration_refusals_and_the_pass(tmp_path):                # C8
    repo, cc, shas, kw = _setup(tmp_path, [{"gen": 1, "id": "OTHER"}])
    with pytest.raises(SystemExit, match="id exactly RANDOM-TWIN/v1"):
        R.registration_check(**kw)
    extra = _reg(shas)["variants"] + [{"id": "RANDOM-TWIN/v1/RETRO-A", "status": "registered"}]
    for bad, msg in ((_reg(shas, trials_charged=4), "charge K=2"), (_reg(shas, variants=[]), "charge K=2"),
                     (_reg(shas, variants=extra), "charge K=2"), (_reg(shas, variants=extra[:1]), "charge K=2"),
                     (_reg({k: "0" * 64 for k in shas}), "freezes these")):
        (cc / R.EVO_REL).write_text(json.dumps({"generations": [bad]}))
        _commit(cc)
        with pytest.raises(SystemExit, match=msg):
            R.registration_check(**kw)
    (cc / R.EVO_REL).write_text(json.dumps({"generations": [_reg(shas)]}))
    _commit(cc)
    ok = R.registration_check(**kw)
    assert ok["ledger_gen"] == 46 and ok["ledger_id"] == "RANDOM-TWIN/v1" and re.fullmatch(r"[0-9a-f]{40}", ok["commit"])
    judged = _reg(shas, variants=[dict(v, status="judged") for v in _reg(shas)["variants"]])          # R3: status may change later
    (cc / R.EVO_REL).write_text(json.dumps({"generations": [judged]}))
    _commit(cc)
    assert R.registration_check(**kw)["ledger_gen"] == 46
    (cc / R.EVO_REL).write_text(json.dumps({"generations": [_reg(shas)], "x": 1}))                  # uncommitted ledger change
    with pytest.raises(SystemExit, match="uncommitted"):
        R.registration_check(**kw)
    (cc / R.EVO_REL).write_text(json.dumps({"generations": [_reg(shas), {"gen": 47, "id": "RANDOM-TWIN/v1 result"}]}))
    _commit(cc)
    with pytest.raises(SystemExit, match="already holds"):
        R.registration_check(**kw)
    R.registration_check(**kw, result_id="RANDOM-TWIN/v1 look result")                                # the look is its own one-shot
    (repo / R.TEST_REL).write_text("edited\n")
    with pytest.raises(SystemExit, match="committed and clean"):
        R.registration_check(**kw)


def test_a_zero_trial_amendment_needs_an_issue_row_naming_the_study(tmp_path):   # C8 (the MSH C13 rule)
    repo, cc, shas, kw = _setup(tmp_path, [])
    old = _reg({k: "0" * 64 for k in shas})
    amend = {"gen": 48, "id": "RANDOM-TWIN/v1 amendment", "trials_charged": 0, "issue": "INS-099", "frozen_sha256": shas}
    (cc / R.EVO_REL).write_text(json.dumps({"generations": [old, amend]}))
    (cc / "council" / "issues.json").write_text(json.dumps({"_": "r", "rows": [{"id": "INS-099", "title": "unrelated fix"}]}))
    _commit(cc)
    with pytest.raises(SystemExit, match="freezes these"):
        R.registration_check(**kw)
    (cc / "council" / "issues.json").write_text(json.dumps({"_": "r", "rows": [{"id": "INS-099", "title": "RANDOM-TWIN/v1 bug fix"}]}))
    _commit(cc)
    assert R.registration_check(**kw)["ledger_gen"] == 48
    (cc / R.EVO_REL).write_text(json.dumps({"generations": [old, dict(amend, trials_charged=1)]}))
    _commit(cc)
    with pytest.raises(SystemExit, match="freezes these"):
        R.registration_check(**kw)


def test_any_git_error_refuses(tmp_path):                              # C14 condition 3
    repo, cc, shas, kw = _setup(tmp_path, [])
    not_git = tmp_path / "plain"
    (not_git / "council").mkdir(parents=True)
    (not_git / R.EVO_REL).write_text(json.dumps({"generations": [_reg(shas)]}))
    with pytest.raises(SystemExit, match="git status --porcelain failed"):
        R.registration_check(**{**kw, "cc_repo": not_git, "evo": not_git / R.EVO_REL})
    with pytest.raises(SystemExit, match="cannot read the feed's git history"):
        R.feed_union(repo=not_git, events=tmp_path / "none.json")


def test_the_look_reads_only_the_frozen_retro_result(tmp_path):      # C14 condition 2
    out = tmp_path / "random_twin.json"
    out.write_text(json.dumps({"retro_closed": {"rows": []}}))
    evo = tmp_path / "evo.json"
    evo.write_text(json.dumps({"generations": [{"gen": 46, "id": "RANDOM-TWIN/v1"}]}))
    with pytest.raises(SystemExit, match="no 'RANDOM-TWIN/v1 result'"):
        R.retro_result_check(out=out, evo=evo)
    key = f"insider-radar/{R.OUT_REL}"
    evo.write_text(json.dumps({"generations": [{"gen": 47, "id": "RANDOM-TWIN/v1 result", "frozen_sha256": {key: "0" * 64}}]}))
    with pytest.raises(SystemExit, match="not the file the result generation froze"):
        R.retro_result_check(out=out, evo=evo)
    evo.write_text(json.dumps({"generations": [{"gen": 47, "id": "RANDOM-TWIN/v1 result", "frozen_sha256": {key: R.sha256_file(out)}}]}))
    assert R.retro_result_check(out=out, evo=evo) == {"retro_closed": {"rows": []}}
    out.unlink()
    with pytest.raises(SystemExit, match="missing"):
        R.retro_result_check(out=out, evo=evo)


def test_the_script_writes_no_book():
    src = (IR / "research" / "random_twin" / "random_twin.py").read_text()
    assert not re.search(r"open\([^)]*,\s*['\"][wa]", src)           # no write/append-mode open() anywhere
    for line in src.splitlines():
        if ".write_text(" in line or ".write_bytes(" in line:
            assert re.search(r"\b(tmp\.|HERE / \"dry\")", line), line
        if re.search(r"\b(ISSUES|EVO|LEDGER|PORTFOLIO_JS)\b", line) and re.search(r"write|replace\(|unlink|open\([^)]*['\"][wax]", line):
            pytest.fail(f"a book path near a write: {line}")
    assert "import atomicio" not in src and "from atomicio" not in src           # it holds no book lock because it writes no book
    for book in ("HALTS.json", "account.json"):
        assert book not in src


def test_no_desk_reader_consumes_the_twin_output():                  # C12, widened by C14 condition 4 / R6
    H = Path.home()
    readers = [H / "command-center" / "desk_review.py", H / "stock-radar" / "portfolio_layer.py", H / "stock-radar" / "firm_halt.py",
               H / "stock-radar" / "portfolio_data.py", H / "stock-radar" / "account.py", H / "stock-radar" / "options_memory.py",
               H / "insider-radar" / "ins033_floor_test.py"]
    present = [p for p in readers if p.exists()]
    if not present:
        pytest.skip("none of the desk's readers are on this machine (a cloud checkout)")
    missing = [str(p) for p in readers if not p.exists()]
    assert not missing, f"a named reader moved or was renamed - re-point this guard: {missing}"
    readers += [p for p in (H / "command-center").glob("desk_review*.py") if "_BACKUP_" not in p.name]
    for p in readers:
        assert "random_twin" not in p.read_text(), f"{p} reads the twin study"

"""INS-033/v1 - the $5 entry-price floor, pre-registered forward test (2026-10-14).

Pinned here, so a later edit is caught by a red test and not by a quiet change to what a pre-registration meant:
  * RULE is frozen: its SHA-256 is a literal in this file; editing RULE is a NEW variant (evolution ledger), never an edit;
  * desk_review.summarize('insider') and BENCHMARK['insider'] are the metric, unchanged - a fixture pins every number it returns,
    and the SHA of its source is pinned in RULE;
  * the row builder equals the desk's own blotter feed (portfolio.js) row for row, so the scorer reads what the desk review reads;
  * stamp is idempotent, buckets by the FIRST non-blank price, puts exactly 5.00 in GE5, honours the call-date window, and a
    restatement never moves a row;
  * score prints COUNTS ONLY before a look date - it never touches the benchmark, summarize, D or t;
  * the decision rule: min n, D > 0, t against the Sidak-taxed bar, drop-best-week in either bucket;
  * a pause of the insider desk ends the cohort on the pause date, and the end survives the pause being lifted;
  * no writer here truncates a book in place (BOOK-001).
Run: python -m pytest -q tests/test_ins033_floor_test.py
"""
import ast
import csv
import datetime as dt
import hashlib
import inspect
import json
import os
import re
import sys
from pathlib import Path

import pytest

IR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IR))
import ins033_floor_test as F  # noqa: E402

PINNED_RULE_SHA = "ee0cbe2552899b062ec5eee6d051594fbe1a3a38c68de54d0e08c3d54642051b"
HOME = Path.home()
HAVE_DR = (HOME / "command-center" / "desk_review.py").exists() and (HOME / "stock-radar" / "sessions.py").exists()
needs_dr = pytest.mark.skipif(not HAVE_DR, reason="command-center/desk_review.py (and stock-radar) are not on this machine")

COLS = ["date", "ticker", "call", "thesis", "price_at_call", "check_date", "price_at_check", "outcome", "stale_quote", "tags", "void_reason"]
FILLED = "[insider] 2 insiders bought $0.50M within 14d [QUEUED at 2026-10-15T08:35 PT (INS-020/REG-PP-002): written before the close settled; fills at the first official open after registration] [FILLED 2026-10-16 official open {px} (REG-PP-002 queued-fill, INS-020)]"


def L(date, ticker, price="", outcome="", exit_px="", check=None, thesis=None, call="long"):
    chk = check or (dt.date.fromisoformat(date) + dt.timedelta(days=30)).isoformat()
    return {"date": date, "ticker": ticker, "call": call, "thesis": thesis or f"[insider] 2 insiders bought $0.50M within 14d", "price_at_call": price,
            "check_date": chk, "price_at_check": exit_px, "outcome": outcome, "stale_quote": "no", "tags": "fund", "void_reason": ""}


def write_ledger(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def read_cohort(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "LEDGER", str(tmp_path / "ledger.csv"))
    monkeypatch.setattr(F, "COHORT", str(tmp_path / "ins033_cohort.csv"))
    monkeypatch.setattr(F, "STATE", str(tmp_path / "ins033_state.json"))
    monkeypatch.setattr(F, "HALTS", str(tmp_path / "HALTS.json"))
    monkeypatch.setattr(F, "REVIEW_DIR", str(tmp_path / "desk_review"))
    monkeypatch.setattr(F.atomicio, "_HELD", {})
    return tmp_path


# ── RULE ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rule_sha_is_the_sha256_of_the_canonical_rule_and_is_pinned():
    assert F.RULE_SHA == hashlib.sha256(json.dumps(F.RULE, sort_keys=True).encode()).hexdigest()
    assert F.RULE_SHA == PINNED_RULE_SHA, "RULE changed: INS-033/v1 is frozen. A change is a NEW variant in the evolution ledger, never an edit."


def test_rule_carries_the_frozen_spec_numbers():
    R = F.RULE
    assert R["rule_id"] == "INS-033/v1" and R["generation"] == 22
    assert (R["population"]["call_date_first"], R["population"]["call_date_last"]) == ("2026-10-15", "2026-12-01")
    assert R["bucket"]["cutoff"] == "5.00" and R["looks"] == ["2026-12-31", "2027-03-31"]
    assert R["min_n_each_bucket"] == {"entry_days": 15, "entry_weeks": 6, "rows": 30}
    assert R["metric"]["lot_usd"] == 2000.0 and R["decision"]["adoption_entry_days_each_bucket"] == 30


def test_luck_tax_numbers_follow_from_k():
    lt = F.RULE["luck_tax"]
    assert lt["K"] == 20
    assert round(F.sidak_z(lt["K"], lt["family_wise_alpha_one_sided"]), 4) == lt["sidak_z"]
    assert lt["pass_t_min"] == round(max(lt["lab_floor_t"], F.sidak_z(lt["K"])), 4) == F.PASS_T


# ── the metric is desk_review.summarize, unchanged ───────────────────────────────────────────────────────────────────────
IWM = {"2026-10-01": 100.0, "2026-10-02": 101.0, "2026-10-05": 102.0, "2026-10-06": 99.0, "2026-10-07": 100.0, "2026-10-08": 103.0,
       "2026-10-09": 104.0, "2026-10-12": 102.0, "2026-10-13": 105.0}


def fixture_rows():
    mk = lambda t, e, x, ret, usd: dict(desk="insider", ticker=t, side="long", entry=e, exit=x, ret=ret, usd=usd)
    return [mk("A", "2026-10-01", "2026-10-08", 4.0, 80.0), mk("B", "2026-10-01", "2026-10-08", -2.0, -40.0),
            mk("C", "2026-10-02", "2026-10-09", 1.0, 20.0), mk("D", "2026-10-05", "2026-10-12", -6.0, -120.0),
            mk("E", "2026-10-06", "2026-10-13", 10.0, 200.0), mk("F", "2026-10-06", "2026-10-13", -100.0, -2000.0)]


@needs_dr
def test_summarize_is_pinned_row_for_row(monkeypatch):
    dr = F.load_desk_review()
    monkeypatch.setitem(dr._BENCH, "IWM", IWM)
    assert dr.BENCHMARK["insider"] == "IWM"
    rows = fixture_rows()
    s = dr.summarize("insider", rows, "2026-10-13")
    assert s == {"desk": "insider", "lab": "insider-radar", "benchmark": "IWM", "n": 6, "entry_days": 4, "days_with_reading": 4, "made_money": 3,
                 "hit": 0.5, "median_ret": -0.5, "mean_day_excess": -15.26, "t": -1.27, "usd_total": -1860, "largest_usd": -2000}
    assert [round(r["exc"], 4) for r in rows] == [1.0, -5.0, -1.9703, -6.0, 3.9394, -106.0606]      # the -100% row is charged its full loss


@needs_dr
def test_summarize_source_is_the_one_rule_froze():
    dr = F.load_desk_review()
    sha = hashlib.sha256(inspect.getsource(dr.summarize).encode()).hexdigest()
    assert sha == F.RULE["metric"]["summarize_source_sha256"], \
        "desk_review.summarize() changed: INS-033 freezes the metric through 2026-12-31. An edit is a NEW variant, not a fix."


@needs_dr
def test_row_builder_equals_the_desk_blotter_feed_row_for_row():
    pj = HOME / "stock-radar" / "data" / "portfolio.js"
    if not pj.exists() or not (IR / "agent" / "ledger.csv").exists():
        pytest.skip("portfolio.js / the live ledger are not on this machine")
    t = pj.read_text()
    js = {}
    for r in json.loads(t[t.index("{"): t.rindex("}") + 1])["rows"]:
        if r.get("desk") == "insider" and r.get("status") == "closed" and r.get("pnl_pct") is not None:
            js.setdefault((r["ticker"], r["entry_date"], r["exit_date"]), []).append((r["pnl_pct"], r["pnl_usd"]))
    mine = {}
    for r in F.read_ledger(str(IR / "agent" / "ledger.csv")):
        b = F.blotter_row(r)
        if b and not b["delisted"]:
            mine.setdefault((b["ticker"], b["entry"], b["exit"]), []).append((b["ret"], b["usd"]))
    common = [k for k in js if k in mine]
    assert len(common) >= 0.9 * len(js) and len(js) > 100, "portfolio.js insider rows are not found in the builder's rows"
    assert [k for k in common if sorted(js[k]) != sorted(mine[k])] == []


def test_a_wrong_row_with_no_usable_price_counts_minus_100():
    r = L("2026-10-20", "GONE", "3.00", "wrong", "")
    b = F.blotter_row(r)
    assert (b["ret"], b["usd"], b["delisted"]) == (-100.0, -2000.0, True)
    assert F.blotter_row(L("2026-10-20", "X", "3.00", "right", "")) is None            # only `wrong` is the delisted case
    assert F.blotter_row(L("2026-10-20", "X", "3.00", "", "3.5")) is None               # open rows are not scored
    assert F.blotter_row(L("2026-10-20", "X", "3.00", "void", "3.5")) is None           # a lowercase void is out
    ok = F.blotter_row(L("2026-10-20", "X", "4.00", "right", "5.00"))
    assert (ok["ret"], ok["usd"], ok["entry"], ok["exit"]) == (25.0, 500.0, "2026-10-20", "2026-11-19")


def test_entry_date_follows_the_blotter_regex():
    assert F.entry_date(L("2026-10-20", "X", thesis="[insider] x. restated to the first official open after registration: the 2026-10-21 official open 4.1")) == "2026-10-21"
    assert F.entry_date(L("2026-10-20", "X", thesis=FILLED.format(px="4.10"))) == "2026-10-20"     # 'FILLED ... official open' has no 'the': call date, as the desk reads it


# ── stamp ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_window_edges_and_the_5_00_boundary(env):
    write_ledger(F.LEDGER, [L("2026-10-14", "OLD", "3.00"), L("2026-10-15", "FIRST", "5.00"), L("2026-10-15", "LOW", "4.99"),
                            L("2026-10-16", "EXACT", "5.0"), L("2026-10-16", "JUST", "4.9999999999999999"), L("2026-10-19", "ABOVE", "5.000001"),
                            L("2026-12-01", "LASTDAY", "7.00"), L("2026-12-02", "TOOLATE", "7.00")])
    s = F.stamp()
    got = {r["ticker"]: r["bucket"] for r in read_cohort(F.COHORT)}
    assert got == {"FIRST": "GE5", "LOW": "LT5", "EXACT": "GE5", "JUST": "LT5", "ABOVE": "GE5", "LASTDAY": "GE5"}
    assert s["added"] == 6 and "OLD" not in got and "TOOLATE" not in got       # in-sample 10-14 and the calendar rule 12-02 stay out


def test_blank_price_is_not_stamped_until_the_fill_writes_one(env):
    write_ledger(F.LEDGER, [L("2026-10-15", "QUEUED", "", thesis="[insider] x [QUEUED at 2026-10-15T08:35 PT]"), L("2026-10-15", "PRICED", "12.00")])
    s = F.stamp()
    assert [r["ticker"] for r in read_cohort(F.COHORT)] == ["PRICED"] and s["unfilled"] == 1
    write_ledger(F.LEDGER, [L("2026-10-15", "QUEUED", "4.20", thesis=FILLED.format(px="4.20")), L("2026-10-15", "PRICED", "12.00")])
    F.stamp()
    rows = {r["ticker"]: r for r in read_cohort(F.COHORT)}
    assert rows["QUEUED"]["bucket"] == "LT5" and rows["QUEUED"]["price_at_call"] == "4.20"
    assert (rows["QUEUED"]["fill_date"], rows["QUEUED"]["fill_note_px"]) == ("2026-10-16", "4.20")


def test_stamp_is_idempotent_and_never_moves_a_row(env):
    write_ledger(F.LEDGER, [L("2026-10-15", "AAA", "4.50"), L("2026-10-15", "BBB", "9.00")])
    F.stamp()
    first = Path(F.COHORT).read_bytes()
    F.stamp()
    assert Path(F.COHORT).read_bytes() == first                       # a second run changes nothing, not even stamped_at
    # a restatement (a reverse-split basis repair) rewrites the ledger's price; the stamped row stays where it was stamped
    write_ledger(F.LEDGER, [L("2026-10-15", "AAA", "9.50"), L("2026-10-15", "BBB", "2.00"), L("2026-10-16", "CCC", "6.00")])
    s = F.stamp()
    rows = {r["ticker"]: r for r in read_cohort(F.COHORT)}
    assert s["added"] == 1 and rows["AAA"]["bucket"] == "LT5" and rows["AAA"]["price_at_call"] == "4.50"
    assert rows["BBB"]["bucket"] == "GE5" and rows["BBB"]["price_at_call"] == "9.00"
    assert list(rows) == ["AAA", "BBB", "CCC"] and rows["AAA"]["stamped_at"] == [r for r in read_cohort(F.COHORT)][0]["stamped_at"]


def test_a_void_row_with_a_price_is_stamped_but_never_scored(env):
    write_ledger(F.LEDGER, [L("2026-10-15", "V", "3.00", "void", "3.1"), L("2026-10-15", "R", "3.00", "right", "3.3"), L("2026-10-16", "NOPRICE", "", "void")])
    s = F.stamp()
    assert sorted(r["ticker"] for r in read_cohort(F.COHORT)) == ["R", "V"] and s["voided_unpriced"] == 1
    by = F.classify(read_cohort(F.COHORT), F.read_ledger())
    assert (by["LT5"]["void"], len(by["LT5"]["rows"]), by["LT5"]["stamped"]) == (1, 1, 2)


def test_two_rows_with_one_key_fail_loud(env):
    write_ledger(F.LEDGER, [L("2026-10-15", "DUP", "3.00"), L("2026-10-15", "DUP", "6.00")])
    with pytest.raises(F.Broken):
        F.stamp()


def test_a_missing_ledger_is_broken_not_a_clean_zero(env, capsys):
    assert F.main(["stamp"]) == 3 and "BROKEN" in capsys.readouterr().out
    assert F.main([]) == 2                                           # no verb: usage, nothing run


def test_stamp_never_truncates_a_book_in_place():
    def truncating_calls(src):
        out = []
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name) and f.id == "open":
                    mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
                    if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and mode.value[:1] in "wa" and "tmp" not in ast.unparse(n.args[0]):
                        out.append(n.lineno)
                elif isinstance(f, ast.Attribute) and f.attr in ("write_text", "write_bytes"):
                    out.append(n.lineno)
        return out
    for name in ("ins033_floor_test.py", "research/ins033_cuts_looked_at.py"):
        assert truncating_calls((IR / name).read_text()) == [], name


# ── score: counts only before a look date ────────────────────────────────────────────────────────────────────────────────
def synthetic_cohort(env, gap=0.08, weeks_days=None):
    """One GE5 row ($10) and one LT5 row ($2) on every weekday of the window; exits are a deterministic function of the day."""
    rows, d, i = [], dt.date(2026, 10, 15), 0
    while d <= dt.date(2026, 12, 1):
        if d.weekday() < 5 and (weeks_days is None or d.isoformat() in weeks_days):
            wob = 0.01 * ((i % 3) - 1)
            chk = (d + dt.timedelta(days=30))
            rows.append(L(d.isoformat(), f"G{i}", "10.00", "right", f"{10 * (1 + gap + wob):.4f}", chk.isoformat()))
            rows.append(L(d.isoformat(), f"L{i}", "2.00", "wrong", f"{2 * (1 - gap + wob):.4f}", chk.isoformat()))
            i += 1
        d += dt.timedelta(days=1)
    write_ledger(F.LEDGER, rows)
    F.stamp()
    return rows


def flat_iwm(monkeypatch):
    dr = F.load_desk_review()
    d, closes = dt.date(2026, 9, 1), {}
    while d <= dt.date(2027, 4, 30):
        closes[d.isoformat()] = 100.0
        d += dt.timedelta(days=1)
    monkeypatch.setitem(dr._BENCH, "IWM", closes)


def test_counts_only_before_the_first_look_date(env, monkeypatch):
    synthetic_cohort(env)
    def boom(*a, **k):
        raise AssertionError("a pre-look score must not evaluate: no benchmark, no summarize, no D, no t")
    monkeypatch.setattr(F, "evaluate", boom)
    monkeypatch.setattr(F, "load_desk_review", boom)
    out = F.score("2026-12-30")
    assert "COUNTS ONLY" in out and "2026-12-31" in out and "stamped rows" in out and "minimum n met" in out
    for leak in ("Welch", "DECISION", "PASS", "FAIL", "CONTINUE", "D (", "beat IWM", "dollars", "excess", "pp"):
        assert leak not in out, f"a pre-look score leaked {leak!r}"
    assert not re.search(r"(?<![A-Za-z])[Dt] =", out), "a pre-look score printed a D or a t"
    assert F.main(["score", "--asof", "2026-12-30"]) == 0


@needs_dr
def test_the_look_dates_pick_the_look(env, monkeypatch):
    synthetic_cohort(env)
    flat_iwm(monkeypatch)
    assert "LOOK 1 of 2 - 2026-12-31" in F.score("2026-12-31")
    assert "LOOK 1 of 2 - 2026-12-31" in F.score("2027-03-30")
    assert "LOOK 2 of 2 - 2027-03-31" in F.score("2027-03-31")


@needs_dr
def test_a_clear_floor_effect_passes_and_only_proposes(env, monkeypatch):
    synthetic_cohort(env, gap=0.08)
    flat_iwm(monkeypatch)
    out = F.score("2026-12-31")
    assert "DECISION: PASS" in out and "PROPOSES a $5 floor" in out and "30 entry days" in out
    assert "D (entry-week clustered, GE5 minus LT5) = +16.00 pp" in out


@needs_dr
def test_the_reverse_fails_and_retires(env, monkeypatch):
    synthetic_cohort(env, gap=-0.08)
    flat_iwm(monkeypatch)
    out = F.score("2026-12-31")
    assert "DECISION: FAIL" in out and "-16.00 pp" in out


@needs_dr
def test_too_few_days_is_continue_whatever_the_effect(env, monkeypatch):
    few = {"2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-26", "2026-10-27", "2026-11-02", "2026-11-03", "2026-11-09", "2026-11-10"}
    synthetic_cohort(env, gap=0.20, weeks_days=few)                 # 5 weeks, 10 entry days, 10 rows a bucket: min n unmet
    flat_iwm(monkeypatch)
    out = F.score("2026-12-31")
    assert "DECISION: CONTINUE" in out and "min n met in both buckets: NO" in out


@needs_dr
def test_the_final_look_closes_continue_undecided(env, monkeypatch):
    few = {"2026-10-15", "2026-10-16"}
    synthetic_cohort(env, weeks_days=few)
    flat_iwm(monkeypatch)
    assert "no third look" in F.score("2027-03-31")


def test_drop_the_best_week_of_either_bucket_blocks_a_pass(monkeypatch):
    """The t bar is zeroed here to isolate the clause: D > 0 must survive losing the week that does most for the floor, on either side."""
    monkeypatch.setattr(F, "PASS_T", 0.0)
    n = dict(rows=40, entry_days=20, entry_weeks=8)
    tiny = [0.1, -0.1, 0.1, -0.1, 0.1, -0.1, 0.1, -0.1]
    # (a) GE5 has one very good week: D > 0, but D <= 0 once GE5's best week goes
    ge_carried = [8.0, -0.2, -0.3, -0.25, -0.2, -0.3, -0.25, -0.2]
    v = F.decide(ge_carried, tiny, n, n, 0)
    assert v["D"] > 0 and v["D_drop_best_hi"] < 0 and v["decision"] == "CONTINUE"
    # (b) LT5 has one very bad week: D > 0, but D <= 0 once LT5's worst week goes (the week that does most for the floor)
    lt_carried = [-8.0, 0.2, 0.3, 0.25, 0.2, 0.3, 0.25, 0.2]
    ge_flat = [-0.1, 0.1, -0.1, 0.1, -0.1, 0.1, -0.1, 0.1]
    v2 = F.decide(ge_flat, lt_carried, n, n, 0)
    assert v2["D"] > 0 and v2["D_drop_best_lo"] < 0 and v2["decision"] == "CONTINUE"
    # (c) a broad effect survives both drops
    v3 = F.decide([6.0, 7.0, 5.0, 6.5, 5.5, 6.2, 5.8, 6.1], [-6.0, -5.0, -7.0, -6.5, -5.5, -6.2, -5.8, -6.1], n, n, 0)
    assert v3["D_drop_best_hi"] > 0 and v3["D_drop_best_lo"] > 0 and v3["decision"] == "PASS"


def test_decision_rule_unit():
    n = dict(rows=40, entry_days=20, entry_weeks=8)
    short = dict(rows=40, entry_days=20, entry_weeks=5)
    hi = [6.0, 7.0, 5.0, 6.5, 5.5, 6.2, 5.8, 6.1]
    lo = [-6.0, -5.0, -7.0, -6.5, -5.5, -6.2, -5.8, -6.1]
    assert F.decide(hi, lo, n, n, 0)["decision"] == "PASS"
    assert F.decide(hi, lo, n, short, 0)["decision"] == "CONTINUE"                                  # min n unmet in ONE bucket
    assert F.decide(lo, hi, n, n, 0)["decision"] == "FAIL"                                          # D <= 0, min n met
    assert F.decide(lo, hi, n, short, 0)["decision"] == "CONTINUE"                                  # FAIL also needs min n
    flat = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
    assert F.decide(flat, flat, n, n, 0)["decision"] == "FAIL"                                      # D == 0 is not > 0
    # one huge week carries D: positive overall but nowhere near the bar
    carried = [30.0, 0.5, -0.5, 0.4, -0.4, 0.3, -0.3, 0.2]
    zero = [0.1, -0.1, 0.1, -0.1, 0.1, -0.1, 0.1, -0.1]
    v = F.decide(carried, zero, n, n, 0)
    assert v["D"] > 0 and v["t"] < F.PASS_T and v["decision"] == "CONTINUE"
    assert v["final_look"] is False and F.decide(hi, lo, n, n, 1)["final_look"] is True
    # a bucket with one entry week cannot be tested: no t, no PASS
    assert F.decide([5.0], lo, n, n, 0)["t"] is None and F.decide([5.0], lo, n, n, 0)["decision"] == "CONTINUE"
    # empty buckets: nothing to compare
    assert F.decide([], [], dict(rows=0, entry_days=0, entry_weeks=0), dict(rows=0, entry_days=0, entry_weeks=0), 0)["decision"] == "CONTINUE"


def test_welch_matches_the_textbook_case():
    t, df = F.welch([5.0, 6.0, 7.0, 8.0], [1.0, 2.0, 3.0, 4.0])
    assert round(t, 4) == 4.3818 and round(df, 3) == 6.0
    assert F.welch([1.0], [1.0, 2.0]) == (None, None)


# ── pause ends the cohort ────────────────────────────────────────────────────────────────────────────────────────────────
def days(*ds):
    return [L(d, f"T{d[5:]}", "6.00") for d in ds]


def test_a_halt_ends_the_cohort_on_its_since_date_and_the_end_survives_a_lift(env):
    write_ledger(F.LEDGER, days("2026-10-15", "2026-11-02", "2026-11-03", "2026-11-04"))
    Path(F.HALTS).write_text(json.dumps({"halted": {"insider": "pause (since=2026-11-03)"}}))
    s = F.stamp()
    assert sorted(r["date"] for r in read_cohort(F.COHORT)) == ["2026-10-15", "2026-11-02"] and s["cohort_end"] == "2026-11-03"
    assert json.load(open(F.STATE))["cohort_end"] == "2026-11-03"
    os.remove(F.HALTS)                                               # the halt is lifted later; the cohort stays ended
    assert F.cohort_end()[0] == "2026-11-03"
    by = F.classify(read_cohort(F.COHORT), F.read_ledger(), "2026-11-02")      # score drops calls on or after the end date even if stamped earlier
    assert by["GE5"]["stamped"] == 1


def test_a_propose_pause_in_a_review_after_the_first_call_date_ends_the_cohort(env):
    rd = Path(F.REVIEW_DIR)
    rd.mkdir()
    old = {"week_end": "2026-10-09", "desks": [{"desk": "insider", "decision": "PROPOSE-PAUSE"}]}
    (rd / "2026-10-09.json").write_text(json.dumps(old))
    assert F.detect_pause() == (None, None)                            # a review from before the cohort began is not a pause of the cohort
    (rd / "2026-11-06.json").write_text(json.dumps({"week_end": "2026-11-06", "desks": [{"desk": "insider", "decision": "PROPOSE-PAUSE"}, {"desk": "position", "decision": "PAUSED"}]}))
    (rd / "2026-11-13.json").write_text(json.dumps({"week_end": "2026-11-13", "desks": [{"desk": "insider", "decision": "KEEP"}]}))
    assert F.detect_pause() == ("2026-11-06", "desk_review 2026-11-06 PROPOSE-PAUSE")


def test_another_desks_halt_does_not_end_the_cohort(env):
    Path(F.HALTS).write_text(json.dumps({"halted": {"position": "x since=2026-09-28"}}))
    assert F.detect_pause() == (None, None)


def test_an_unreadable_halts_file_stamps_and_warns(env):
    write_ledger(F.LEDGER, days("2026-10-15"))
    Path(F.HALTS).write_text("{not json")
    s = F.stamp()
    assert s["added"] == 1 and "unreadable" in s["warning"]

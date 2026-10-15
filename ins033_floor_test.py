#!/usr/bin/env python3
"""INS-033/v1 - does a $5 entry-price floor help the insider desk?  A pre-registered FORWARD test.

Anupam, 2026-10-14 ("ok" to Claude's four-item proposal, register row INS-033): the desk keeps trading exactly as it does -
nothing is bought or refused differently - and its own forward rows priced at or above $5 are compared with those under $5.
The cut was found in the desk's own data (one of several cuts looked at, see research/INS-033_cuts_looked_at.txt), so it is a
mined hypothesis, luck-taxed with K, and only forward rows count.

RULE below is the authority; research/PREREG_INS-033.md is the same thing in words. RULE_SHA is the SHA-256 of
json.dumps(RULE, sort_keys=True); the evolution ledger entry INS-033/v1 carries it as spec_sha256. Editing RULE changes RULE_SHA:
a change is a NEW variant, never an edit.

Subcommands (read the code before running anything in this estate bare; this one prints usage and does nothing without a verb):
  stamp   idempotent. Adds every newly filled cohort row (call date in the window, price_at_call first written non-blank by the
          INS-020/INS-026 fill) to agent/ins033_cohort.csv, ONCE, with stamped_at. A later restatement never moves a row. Writes
          through atomicio under the book's lock. Wire: ~/bin/views-rebuild.sh (weekdays 14:50 PT).
  score   COUNTS ONLY before a look date (2026-12-31, 2027-03-31). On or after one, prints the decision with the full evidence.
          Writes nothing.
  rule    prints RULE and RULE_SHA. Read-only.

Paper only. Nothing here places, sizes or advises a trade.
"""
import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import re
import statistics as st
import sys
from decimal import Decimal, InvalidOperation
from statistics import NormalDist
from zoneinfo import ZoneInfo

IR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, IR)
import atomicio  # noqa: E402  BOOK-001: a book is only ever rewritten whole, under its lock

HOME = os.path.expanduser("~")
PT = ZoneInfo("America/Los_Angeles")

# ── THE FROZEN RULE ───────────────────────────────────────────────────────────────────────────────────────────────────────
RULE = {
    "rule_id": "INS-033/v1",
    "generation": 22,
    "kind": "computed variant; touches no live book. Nothing is bought, sized, exited or refused differently.",
    "hypothesis": "Among insider-desk longs, D = (mean excess vs IWM of rows with entry price >= 5.00) - (mean excess vs IWM of rows with entry price < 5.00) is > 0.",
    "population": {
        "book": "insider-radar/agent/ledger.csv",
        "call": "long",
        "call_date_first": "2026-10-15",
        "call_date_last": "2026-12-01",
        "calendar_rule": "a call dated after 2026-12-01 cannot close (30-day clock) by 2026-12-31, so it cannot be in the first look",
        "in_sample": "calls dated 2026-10-14 or earlier are in-sample even if they fill on 2026-10-15; they are never in the cohort",
        "scored": "outcome is exactly 'right' or 'wrong' as written by the 13:40 PT grader (INS-018); blank = still open; lowercase 'void' is excluded",
    },
    "bucket": {
        "field": "price_at_call",
        "stamp": "the first non-blank price_at_call written by the INS-020/INS-026 fill, stamped ONCE into agent/ins033_cohort.csv with stamped_at; a later restatement never moves a row",
        "cutoff": "5.00",
        "ge": "GE5: price >= 5.00 (exactly 5.00 is in GE5)",
        "lt": "LT5: price < 5.00",
        "comparison": "decimal, never float",
    },
    "metric": {
        "function": "command-center/desk_review.py summarize('insider', rows, week_end), unchanged",
        "summarize_source_sha256": "2c013c58205ac323b42061ad3ef67c39cc8b64a04dd437f4af13dcb0fde6162b",
        "benchmark": "desk_review.BENCHMARK['insider'] = IWM",
        "row_return": "round((price_at_check - price_at_call) / price_at_call * 100, 2) on the ledger as it stands; usd = round(2000 * return / 100, 2) (SIZE-001 lot)",
        "entry": "the entry date the desk review's blotter feed assigns (stock-radar portfolio_data.read_labs): the call date, unless the thesis names a restated fill session as 'the YYYY-MM-DD official open'",
        "exit": "check_date",
        "excess": "row return minus IWM close-to-close over entry to exit (summarize), IWM close on or before each date",
        "delisted_or_unfetchable": "a 'wrong' row with no usable price_at_check counts as a return of -100%, counted in its bucket",
        "lot_usd": 2000.0,
    },
    "statistic": {
        "cluster_primary": "entry week (ISO week of the entry date); a week's value is the mean excess of its rows",
        "cluster_also_printed": "entry day (summarize's own mean of per-day means and day-clustered t)",
        "bucket_value": "the equal-weighted mean of the bucket's entry-week values",
        "D": "bucket value of GE5 minus bucket value of LT5",
        "t": "one-sided Welch t on the two buckets' entry-week values (sample variances)",
    },
    "min_n_each_bucket": {"entry_days": 15, "entry_weeks": 6, "rows": 30},
    "min_n_counts": "scored (right/wrong) rows that have a return and an IWM reading; entry days are their distinct entry dates, entry weeks their distinct ISO weeks; voids, open and unfilled rows are printed per bucket and never counted",
    "decision": {
        "PASS": "min n met in BOTH buckets AND D > 0 AND Welch t >= pass_t_min AND D > 0 after dropping the best entry week of the GE5 bucket AND D > 0 after dropping the best entry week of the LT5 bucket, 'best' meaning the week that does most for the floor (GE5's highest week; LT5's lowest week). PASS only PROPOSES a floor to Anupam; adopting it also needs 30 entry days in each bucket.",
        "FAIL": "min n met in both buckets AND D <= 0. Retired permanently; no re-cut at $3 or $10.",
        "CONTINUE": "everything else. At the final look (2027-03-31) CONTINUE closes the test undecided: no third look.",
        "adoption_entry_days_each_bucket": 30,
    },
    "looks": ["2026-12-31", "2027-03-31"],
    "before_a_look": "the scorer prints counts only: never D, t, hit rate, dollars or excess",
    "shown_never_judged": ["hit rate vs IWM", "dollars", "each bucket's own excess"],
    "luck_tax": {
        "K": 20,
        "K_basis": "cells of the audit's six cut families rebuilt on the in-sample insider ledger (price 9, side 1, desk 1, exit month 3, structure 1, tenor 2 = 17) plus the entry-month cut the same audit table also printed (3); a one-level family counts 1; see research/INS-033_cuts_looked_at.txt",
        "family_wise_alpha_one_sided": 0.05,
        "sidak_z": 2.7992,
        "lab_floor_t": 2.67,
        "pass_t_min": 2.7992,
    },
    "prior": "About 8 entry weeks per bucket gives this bar low power: CONTINUE is the likeliest outcome and is not a refutation. The desk's own record says no edge; a PASS would still owe an edge-refute panel before anyone acts.",
    "implementation": {
        "scorer": "insider-radar/ins033_floor_test.py (RULE, stamp, score)",
        "cohort_book": "insider-radar/agent/ins033_cohort.csv, written only through atomicio under the book's lock",
        "pause_state": "insider-radar/agent/ins033_state.json",
        "prereg": "insider-radar/research/PREREG_INS-033.md",
        "cuts": "insider-radar/research/INS-033_cuts_looked_at.txt",
        "stamp_wiring": "~/bin/views-rebuild.sh, weekdays 14:50 PT",
    },
    "frozen_through": "2026-12-31",
    "frozen": [
        "cluster detection and any price or size filter",
        "INS-020 queued fill",
        "INS-026 settled fill",
        "the 30-day clock and the INS-012 roll",
        "the grader (INS-018)",
        "the $2,000 lot (SIZE-001)",
        "IWM as desk_review.BENCHMARK['insider']",
    ],
    "pause": "a pause of the insider desk (a desk_review PROPOSE-PAUSE for insider in a review dated on or after the first call date, or an 'insider' key in stock-radar/agent/HALTS.json) ends the cohort on the pause date: calls dated before it count, calls dated on or after it do not",
}
RULE_SHA = hashlib.sha256(json.dumps(RULE, sort_keys=True).encode()).hexdigest()

# ── paths (module attributes so the tests can point them at a scratch tree) ───────────────────────────────────────────────
LEDGER = os.path.join(IR, "agent", "ledger.csv")
COHORT = os.path.join(IR, "agent", "ins033_cohort.csv")
STATE = os.path.join(IR, "agent", "ins033_state.json")
HALTS = os.path.join(HOME, "stock-radar", "agent", "HALTS.json")
REVIEW_DIR = os.path.join(HOME, "command-center", "council", "desk_review")
DESK_REVIEW = os.path.join(HOME, "command-center", "desk_review.py")

COHORT_COLS = ["key", "date", "ticker", "check_date", "price_at_call", "bucket", "stamped_at", "fill_date", "fill_note_px", "rule_sha"]
LEDGER_NEED = ["date", "ticker", "call", "thesis", "price_at_call", "check_date", "price_at_check", "outcome"]

FIRST, LAST = RULE["population"]["call_date_first"], RULE["population"]["call_date_last"]
CUTOFF = Decimal(RULE["bucket"]["cutoff"])
LOOKS = tuple(RULE["looks"])
MIN_N = RULE["min_n_each_bucket"]
PASS_T = RULE["luck_tax"]["pass_t_min"]
LOT = RULE["metric"]["lot_usd"]
BUCKETS = ("GE5", "LT5")


class Broken(Exception):
    """A loud failure: the test cannot be read, which is never a clean zero."""


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def sidak_z(K, alpha=0.05):
    """One-sided normal critical value at the Sidak per-test level for K looks and family-wise alpha."""
    per_test = 1.0 - (1.0 - alpha) ** (1.0 / K)
    return NormalDist().inv_cdf(1.0 - per_test)


def today_pt():
    return dt.datetime.now(PT).date().isoformat()


def utc_stamp(now=None):
    return (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fnum(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def price_dec(v):
    """Decimal price, None when blank; raises Broken on a non-blank value that is not a positive number."""
    s = (v or "").strip()
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise Broken(f"price_at_call {s!r} is not a number")
    if not d.is_finite() or d <= 0:
        raise Broken(f"price_at_call {s!r} is not a positive price")
    return d


def bucket_of(price):
    return "GE5" if price >= CUTOFF else "LT5"


def week_of(day):
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def in_window(day):
    return FIRST <= day <= LAST


def read_ledger(path=None):
    path = path or LEDGER
    try:
        with open(path, newline="") as f:
            rd = csv.DictReader(f)
            missing = [c for c in LEDGER_NEED if c not in (rd.fieldnames or [])]
            if missing:
                raise Broken(f"{path} lacks columns {missing}")
            return list(rd)
    except OSError as e:
        raise Broken(f"cannot read {path} ({e})")


def read_cohort(path=None):
    path = path or COHORT
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames != COHORT_COLS:
            raise Broken(f"{path} header {rd.fieldnames} is not {COHORT_COLS}")
        return list(rd)


def keyed(ledger):
    """[(key, row)], key = date|ticker|ordinal among the ledger rows that share that date and ticker. The ledger only grows at the end
    and a row is never deleted (BENCH-002), so a row's ordinal never moves. check_date is deliberately NOT in the key: a SESSION-001
    roll rewrites it, and a key that moved would orphan a stamped row."""
    n, out = {}, []
    for r in ledger:
        base = f"{(r.get('date') or '').strip()}|{(r.get('ticker') or '').strip()}"
        i = n.get(base, 0)
        n[base] = i + 1
        out.append((f"{base}|{i}", r))
    return out


# ── pause (the cohort ends on the pause date) ─────────────────────────────────────────────────────────────────────────────
def detect_pause():
    """-> (date, source) of the earliest sign that the insider desk is paused, or (None, None).
    Sources: stock-radar/agent/HALTS.json 'insider' (date = its since=, else today) and any desk_review JSON whose insider
    line is PROPOSE-PAUSE (date = that review's week_end), counting only reviews dated on or after the first call date."""
    found = []
    try:
        halted = (json.load(open(HALTS)).get("halted") or {})
    except FileNotFoundError:
        halted = {}
    except (OSError, ValueError) as e:
        raise Broken(f"HALTS.json unreadable ({type(e).__name__}): cannot tell whether the insider desk is paused")
    if "insider" in halted:
        m = re.search(r"since=(\d{4}-\d{2}-\d{2})", str(halted["insider"]))
        found.append((m.group(1) if m else today_pt(), "HALTS.json"))
    try:
        names = sorted(n for n in os.listdir(REVIEW_DIR) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", n))
    except FileNotFoundError:
        names = []
    for n in names:
        if n[:10] < FIRST:
            continue
        try:
            js = json.load(open(os.path.join(REVIEW_DIR, n)))
        except (OSError, ValueError) as e:
            raise Broken(f"desk review {n} unreadable ({type(e).__name__}): cannot tell whether the insider desk is paused")
        for d in js.get("desks") or []:
            if d.get("desk") == "insider" and d.get("decision") == "PROPOSE-PAUSE":
                found.append((js.get("week_end") or n[:10], f"desk_review {n[:10]} PROPOSE-PAUSE"))
    return min(found) if found else (None, None)


def cohort_end():
    """-> (date, source) from the persisted state if there is one, else a live detection; (None, None) = the cohort is open."""
    try:
        s = json.load(open(STATE))
        if s.get("cohort_end"):
            return s["cohort_end"], s.get("source") or "state"
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        raise Broken(f"{STATE} unreadable ({type(e).__name__})")
    return detect_pause()


# ── stamp ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def stamp(now=None):
    """Add newly filled cohort rows to the cohort book. Returns a dict of counts. Idempotent: a row already stamped is never touched."""
    atomicio.hold_book(COHORT)                      # BOOK-001: lock from the first read to the last write
    ledger = read_ledger()
    have = read_cohort()
    keys = {r["key"] for r in have}
    warn = None
    try:
        end, src = cohort_end()
    except Broken as e:        # stamping a price promptly matters more than knowing about a pause: stamp, and say so LOUDLY
        end, src, warn = None, None, f"pause state unreadable, stamped as if the desk were not paused: {e}"
    persisted = False
    try:
        persisted = bool(json.load(open(STATE)).get("cohort_end"))
    except (OSError, ValueError):
        pass
    if end and not persisted:
        atomicio.atomic_json(STATE, {"cohort_end": end, "source": src, "recorded_at": utc_stamp(now), "rule_sha": RULE_SHA}, indent=1)
    new, unfilled, nonlong, void_nop, after_end = [], 0, 0, 0, 0
    for k, r in keyed(ledger):
        d = (r.get("date") or "").strip()
        if not in_window(d):
            continue
        if (r.get("call") or "").strip() != "long":
            nonlong += 1
            continue
        if end and d >= end:
            after_end += 1
            continue
        p = price_dec(r.get("price_at_call"))
        if p is None:
            if (r.get("outcome") or "").strip() == "void":
                void_nop += 1
            else:
                unfilled += 1
            continue
        if k in keys:
            continue
        m = re.search(r"\[FILLED (\d{4}-\d{2}-\d{2}) official open ([0-9.]+)", r.get("thesis") or "")
        new.append({"key": k, "date": d, "ticker": r["ticker"], "check_date": r.get("check_date", ""),
                    "price_at_call": r["price_at_call"].strip(), "bucket": bucket_of(p), "stamped_at": utc_stamp(now),
                    "fill_date": m.group(1) if m else "", "fill_note_px": m.group(2) if m else "", "rule_sha": RULE_SHA[:16]})
    if new or not os.path.exists(COHORT):
        atomicio.atomic_csv(COHORT, COHORT_COLS, have + new, lineterminator="\n")
    return dict(added=len(new), total=len(have) + len(new), unfilled=unfilled, voided_unpriced=void_nop, nonlong=nonlong,
                after_end=after_end, cohort_end=end, cohort_end_source=src, warning=warn)


# ── rows the metric reads ─────────────────────────────────────────────────────────────────────────────────────────────────
def entry_date(r):
    """The entry date stock-radar's blotter feed (portfolio_data.read_labs) gives an insider row."""
    m = re.search(r"the (\d{4}-\d{2}-\d{2}) official open", r.get("thesis") or "")
    return m.group(1) if m else r.get("date", "")


def blotter_row(r):
    """A scored ledger row as the desk review sees it: dict(desk, ticker, side, entry, exit, ret, usd, outcome, delisted), or None
    when the row is not scored or has no return. A 'wrong' row with no usable price_at_check is the delisted/unfetchable case
    (AGENT.md step 2) and counts -100% (INS-033); the desk's own blotter leaves such a row without a return."""
    oc = (r.get("outcome") or "").strip()
    if oc not in ("right", "wrong"):
        return None
    entry, exit_v = fnum(r.get("price_at_call")), fnum(r.get("price_at_check")) or None
    if entry in (None, 0):
        return None
    delisted = False
    if exit_v is None or exit_v <= 0:
        if oc != "wrong":
            return None
        pct, delisted = -100.0, True
    else:
        pct = round((exit_v - entry) / entry * 100.0, 2)
    return dict(desk="insider", ticker=r["ticker"], side="long", entry=entry_date(r), exit=(r.get("check_date") or None),
                ret=pct, usd=round(LOT * pct / 100.0, 2), outcome=oc, delisted=delisted)


def classify(cohort, ledger, end=None):
    """Join the stamped cohort to the live ledger. -> dict bucket -> {'rows': [blotter rows], 'open': n, 'void': n, 'noret': n, 'restated': n}."""
    by_key = dict(keyed(ledger))
    out = {b: dict(stamped=0, rows=[], open=0, void=0, noret=0, restated=0, other=0) for b in BUCKETS}
    for c in cohort:
        if end and c["date"] >= end:
            continue
        b = out[c["bucket"]]
        b["stamped"] += 1
        r = by_key.get(c["key"])
        if r is None:
            raise Broken(f"cohort row {c['key']} is no longer in the ledger: a stamped row never leaves (BENCH-002)")
        if r.get("price_at_call", "").strip() != c["price_at_call"]:
            b["restated"] += 1
        oc = (r.get("outcome") or "").strip()
        if oc == "":
            b["open"] += 1
        elif oc == "void":
            b["void"] += 1
        elif oc in ("right", "wrong"):
            br = blotter_row(r)
            if br is None:
                b["noret"] += 1
            else:
                b["rows"].append(br)
        else:
            b["other"] += 1
    return out


def counts_of(rows):
    return dict(rows=len(rows), entry_days=len({r["entry"] for r in rows}), entry_weeks=len({week_of(r["entry"]) for r in rows}))


def min_n_met(c):
    return c["rows"] >= MIN_N["rows"] and c["entry_days"] >= MIN_N["entry_days"] and c["entry_weeks"] >= MIN_N["entry_weeks"]


# ── the look ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
_DR = []


def load_desk_review():
    """desk_review.py, loaded the way desk_review loads its own siblings. Cached."""
    if not _DR:
        if not os.path.exists(DESK_REVIEW):
            raise Broken(f"{DESK_REVIEW} is missing: the metric is summarize('insider') and cannot be computed without it")
        sp = importlib.util.spec_from_file_location("_ins033_desk_review", DESK_REVIEW)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        _DR.append(m)
    return _DR[0]


def week_values(rows):
    """{iso week: mean excess} over rows that have a reading."""
    wk = {}
    for r in rows:
        if r.get("exc") is not None:
            wk.setdefault(week_of(r["entry"]), []).append(r["exc"])
    return {w: st.mean(v) for w, v in wk.items()}


def welch(a, b):
    """-> (t for mean(a) > mean(b), df), (None, None) when it cannot be computed."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None, None
    va, vb = st.variance(a) / na, st.variance(b) / nb
    if va + vb == 0:
        return None, None
    t = (st.mean(a) - st.mean(b)) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / ((va ** 2 / (na - 1) if va else 0) + (vb ** 2 / (nb - 1) if vb else 0))
    return t, df


def decide(hi_weeks, lo_weeks, n_hi, n_lo, look_index):
    """Apply the frozen decision rule to the two buckets' entry-week values (lists) and their count dicts."""
    met = min_n_met(n_hi) and min_n_met(n_lo)
    out = dict(min_n_met=met, D=None, t=None, df=None, D_drop_best_hi=None, D_drop_best_lo=None)
    if hi_weeks and lo_weeks:
        out["D"] = st.mean(hi_weeks) - st.mean(lo_weeks)
        out["t"], out["df"] = welch(hi_weeks, lo_weeks)
        # "best" = the week that does most for the floor: GE5's highest week, LT5's LOWEST week (a bad week in LT5 raises D)
        if len(hi_weeks) > 1:
            out["D_drop_best_hi"] = st.mean(sorted(hi_weeks)[:-1]) - st.mean(lo_weeks)
        if len(lo_weeks) > 1:
            out["D_drop_best_lo"] = st.mean(hi_weeks) - st.mean(sorted(lo_weeks)[1:])
    D = out["D"]
    robust = out["D_drop_best_hi"] is not None and out["D_drop_best_lo"] is not None and out["D_drop_best_hi"] > 0 and out["D_drop_best_lo"] > 0
    if met and D is not None and D > 0 and out["t"] is not None and out["t"] >= PASS_T and robust:
        out["decision"] = "PASS"
    elif met and D is not None and D <= 0:
        out["decision"] = "FAIL"
    else:
        out["decision"] = "CONTINUE"
    out["final_look"] = look_index == len(LOOKS) - 1
    return out


def evaluate(by_bucket, asof, look_index):
    """The full read. Calls desk_review.summarize('insider') once per non-empty bucket on the very rows it would be given."""
    dr = load_desk_review()
    res = {}
    for b in BUCKETS:
        rows = by_bucket[b]["rows"]
        s = dr.summarize("insider", rows, asof) if rows else None       # summarize() divides by len(rows): never call it empty
        res[b] = dict(summary=s, n_rows=len(rows), weeks=week_values(rows), counts=counts_of([r for r in rows if r.get("exc") is not None]),
                      noreading=sum(1 for r in rows if r.get("exc") is None), delisted=sum(1 for r in rows if r.get("delisted")),
                      usd=round(sum(r["usd"] for r in rows)), beat=(sum(1 for r in rows if (r.get("exc") or 0) > 0) / len(rows)) if rows else None,
                      row_mean=(st.mean(r["exc"] for r in rows if r.get("exc") is not None) if any(r.get("exc") is not None for r in rows) else None))
    hi, lo = list(res["GE5"]["weeks"].values()), list(res["LT5"]["weeks"].values())
    res["verdict"] = decide(hi, lo, res["GE5"]["counts"], res["LT5"]["counts"], look_index)
    day_hi, day_lo = (res["GE5"]["summary"] or {}).get("mean_day_excess"), (res["LT5"]["summary"] or {}).get("mean_day_excess")
    res["D_day"] = None if day_hi is None or day_lo is None else day_hi - day_lo
    res["D_row"] = None if res["GE5"]["row_mean"] is None or res["LT5"]["row_mean"] is None else res["GE5"]["row_mean"] - res["LT5"]["row_mean"]
    return res


def fmt(x, nd=2, sign=True):
    return "n/a" if x is None else (f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}")


def render_look(res, look_date, look_index, asof, extra):
    v = res["verdict"]
    L = [f"INS-033/v1 LOOK {look_index + 1} of {len(LOOKS)} - {look_date}   (asof {asof}; RULE_SHA {RULE_SHA[:16]})",
         f"DECISION: {v['decision']}" + ("  (final look: CONTINUE closes the test undecided, no third look)" if v["decision"] == "CONTINUE" and v["final_look"] else ""),
         f"  min n met in both buckets: {'yes' if v['min_n_met'] else 'NO'}   "
         f"(each bucket needs >= {MIN_N['entry_days']} entry days, >= {MIN_N['entry_weeks']} entry weeks, >= {MIN_N['rows']} rows)",
         f"  D (entry-week clustered, GE5 minus LT5) = {fmt(v['D'])} pp   one-sided Welch t = {fmt(v['t'])} (df {fmt(v['df'], 1, False)})   bar t >= {PASS_T} (max of lab floor {RULE['luck_tax']['lab_floor_t']} and Sidak z for K={RULE['luck_tax']['K']})",
         f"  D after dropping GE5's best (highest) entry week = {fmt(v['D_drop_best_hi'])}   after dropping LT5's best-for-the-floor (lowest) entry week = {fmt(v['D_drop_best_lo'])}",
         f"  beside it: D row-pooled = {fmt(res['D_row'])}   D entry-day clustered (summarize's mean of day means) = {fmt(res['D_day'])}"]
    if v["decision"] == "PASS":
        c = RULE["decision"]["adoption_entry_days_each_bucket"]
        L.append(f"  PASS only PROPOSES a $5 floor to Anupam. Adoption also needs {c} entry days in each bucket: GE5 {res['GE5']['counts']['entry_days']}, LT5 {res['LT5']['counts']['entry_days']}.")
    L.append("  Shown, never judged:")
    for b in BUCKETS:
        r, s, c = res[b], res[b]["summary"], res[b]["counts"]
        L.append(f"    {b}: rows {r['n_rows']}  entry days {c['entry_days']}  entry weeks {c['entry_weeks']}  "
                 f"own excess (week-clustered) {fmt(mean_or_none(r['weeks']))} pp  beat IWM {fmt(None if r['beat'] is None else r['beat'] * 100, 0, False)}%  "
                 f"made money {fmt(None if not s else s['hit'] * 100, 0, False)}%  dollars {r['usd']:+d}  "
                 f"-100% delisted rows {r['delisted']}  rows without a reading {r['noreading']}")
    L += extra
    return "\n".join(L)


def mean_or_none(weeks):
    return st.mean(weeks.values()) if weeks else None


def render_counts(by_bucket, ledger_counts, asof, end, nxt):
    L = [f"INS-033/v1 floor test   RULE_SHA {RULE_SHA[:16]}   cohort = calls {FIRST}..{LAST}   asof {asof} (PT)",
         f"COUNTS ONLY until the first look ({', '.join(LOOKS)}). Next look: {nxt[0]} ({nxt[1]} day(s) away).",
         f"{'':32}{'GE5':>8}{'LT5':>8}"]
    cs = {b: counts_of(by_bucket[b]["rows"]) for b in BUCKETS}
    for label, key in (("stamped rows", "stamped"), ("scored (right/wrong)", None), ("open (not yet graded)", "open"),
                       ("void (excluded)", "void"), ("scored without a return", "noret"), ("restated since stamp", "restated"),
                       ("other outcome (excluded)", "other")):
        vals = [len(by_bucket[b]["rows"]) if key is None else by_bucket[b][key] for b in BUCKETS]
        L.append(f"{label:32}{vals[0]:>8}{vals[1]:>8}")
    for label, key, need in (("entry days (scored)", "entry_days", MIN_N["entry_days"]), ("entry weeks (scored)", "entry_weeks", MIN_N["entry_weeks"]),
                             ("rows (scored)", "rows", MIN_N["rows"])):
        L.append(f"{label + ' / needed ' + str(need):32}{cs['GE5'][key]:>8}{cs['LT5'][key]:>8}")
    L.append(f"{'minimum n met':32}{('yes' if min_n_met(cs['GE5']) else 'no'):>8}{('yes' if min_n_met(cs['LT5']) else 'no'):>8}")
    L.append(f"in the window with no price yet (bucket unknown): {ledger_counts['unfilled']}; voided before any price: {ledger_counts['void_unpriced']}; not a long: {ledger_counts['nonlong']}")
    L.append(f"cohort end: {end[0] + ' (' + end[1] + ')' if end[0] else 'none (the insider desk is not paused)'}")
    return "\n".join(L)


def window_counts(ledger, end):
    c = dict(unfilled=0, void_unpriced=0, nonlong=0)
    for r in ledger:
        d = (r.get("date") or "").strip()
        if not in_window(d) or (end and d >= end):
            continue
        if (r.get("call") or "").strip() != "long":
            c["nonlong"] += 1
        elif not (r.get("price_at_call") or "").strip():
            c["void_unpriced" if (r.get("outcome") or "").strip() == "void" else "unfilled"] += 1
    return c


def score(asof=None):
    asof = asof or today_pt()
    ledger, cohort = read_ledger(), read_cohort()
    end = cohort_end()
    by_bucket = classify(cohort, ledger, end[0])
    wc = window_counts(ledger, end[0])
    reached = [i for i, d in enumerate(LOOKS) if asof >= d]
    if not reached:
        nxt = (LOOKS[0], (dt.date.fromisoformat(LOOKS[0]) - dt.date.fromisoformat(asof)).days)
        return render_counts(by_bucket, wc, asof, end, nxt)                 # NOTHING below this line runs: no IWM fetch, no summarize, no D
    i = reached[-1]
    res = evaluate(by_bucket, asof, i)
    due =sum(1 for r in ledger if in_window((r.get("date") or "").strip()) and (r.get("check_date") or "") <= LOOKS[i]
              and (r.get("price_at_call") or "").strip() and not (r.get("outcome") or "").strip())
    extra = [f"  voids per bucket: GE5 {by_bucket['GE5']['void']}, LT5 {by_bucket['LT5']['void']}; other outcomes (excluded): GE5 {by_bucket['GE5']['other']}, LT5 {by_bucket['LT5']['other']}; open per bucket: GE5 {by_bucket['GE5']['open']}, LT5 {by_bucket['LT5']['open']}; "
             f"no price yet (bucket unknown): {wc['unfilled']}; restated since stamp (bucket frozen): GE5 {by_bucket['GE5']['restated']}, LT5 {by_bucket['LT5']['restated']}"]
    if due:
        extra.append(f"  WARNING: {due} cohort row(s) are due on or before {LOOKS[i]} but not yet graded; the 13:40 PT grader may not have run. This look is premature until they are.")
    if end[0]:
        extra.append(f"  cohort ended {end[0]} ({end[1]}); calls dated on or after it are not counted")
    return render_look(res, LOOKS[i], i, asof, extra)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ins033_floor_test.py", description="INS-033/v1 forward test of a $5 entry-price floor (paper only).")
    sub = ap.add_subparsers(dest="verb")
    sub.add_parser("stamp", help="add newly filled cohort rows to agent/ins033_cohort.csv (idempotent)")
    sp = sub.add_parser("score", help="counts only before a look date; the decision on or after one")
    sp.add_argument("--asof", help="YYYY-MM-DD (PT); default today. For rehearsal; the look still needs the date to have come.")
    sub.add_parser("rule", help="print RULE and RULE_SHA")
    a = ap.parse_args(argv)
    if not a.verb:
        ap.print_usage(sys.stderr)
        return 2
    try:
        if a.verb == "rule":
            print(json.dumps(RULE, indent=1, sort_keys=True))
            print(f"RULE_SHA {RULE_SHA}")
        elif a.verb == "stamp":
            s = stamp()
            print(f"ins033 stamp: +{s['added']} stamped (cohort {s['total']}); in window with no price yet {s['unfilled']}; "
                  f"cohort end {s['cohort_end'] or 'none'}; RULE_SHA {RULE_SHA[:16]}")
            if s["warning"]:
                print(f"ins033: WARNING - {s['warning']}")
        else:
            print(score(a.asof))
    except Broken as e:
        print(f"ins033: BROKEN - {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

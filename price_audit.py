#!/opt/anaconda3/bin/python
"""INS-014 auditor — the call price must lie inside the call-day bar.

    /opt/anaconda3/bin/python price_audit.py [--open-only] [--since YYYY-MM-DD]
                                             [--json] [--refresh]

WHY THIS FILE EXISTS
--------------------
INS-014 (2026-09-05): 23 open rows carried `price_at_call` BELOW the entry day's
own low while `stale_quote` read "no". The writer had taken Yahoo's "latest daily
close", which on a same-day run is often the PRIOR session's close, and
`is_stale()` could not see it because that check watches whether closes MOVE, not
whether the quote's own date is the call date.

AGENT.md §INS-014 and `agent/stale_quote.py:237` both named "the daily price audit
(price_audit.py)" as the enforcement behind that rule. **The file did not exist.**
The Resolver's test `insider_call_price_guard_is_enforceable` was attached on
2026-09-07 and failed on exactly that: a rule whose auditor is imaginary is
Firm Brain §10 — a rule enforced only where it cannot bind, which reads as healthy
for as long as nobody checks. This is the auditor.

WHAT IT ASSERTS
---------------
For every ledger row that carries a `price_at_call`, the price must fall within
the [low, high] range of that ticker's daily bar DATED the row's own `date`.
That is a strictly weaker claim than "it is the close", and deliberately so: it
is the claim that can be checked without redefining any reference price, which
BENCH-002 forbids on written rows.

WHAT IT REFUSES TO DO
---------------------
It is READ-ONLY. It never edits the ledger, never restates a price, never scores
a row and never touches `outcome`. A restatement is a ruling for Anupam, not a
side effect of an audit run (INS-014 executed exactly one, disclosed per row).

EVERY VERDICT CARRIES ITS REASON (Firm Brain §3)
------------------------------------------------
A row is never silently passed over. Each lands in exactly one bucket:
  PASS          price inside the call-day bar's range
  FAIL          price outside it — the INS-014 defect, by how much and on which side
  NO_BAR        the call date is not a trading day for this ticker (halt, pre-IPO,
                or the date is not a session) — a real finding, never a pass
  UNFETCHABLE   the ticker could not be priced at all (delisted, bad symbol)
  QUEUED        `price_at_call` is empty and the row says [QUEUED] — the documented
                state for a call written before its bar existed, awaiting the next
                official open. Correct, not a violation.
  VOID          outcome=void — an excluded row, per INS-007
Counts for every bucket are printed even when zero.

THE REFERENCE TEST (INS-020, ruled 2026-09-27 option a) - a second, stronger axis
----------------------------------------------------------------------------------
"Inside the bar" could not tell a settled close from a live mid-session print, because
the cache stored only [low, high]; 35 of 39 open rows turned out to be live prints. The
cache now stores [low, high, open, close, volume] for SETTLED days only (a bar dated a
session that has not settled is never cached - it is still moving), and every OPEN priced
row is tested against the price the written rule owes:
  queued-fill rows   ([QUEUED / [FILLED / INS-020 restated)  -> the FIRST official open
                     after registration that traded (volume > 0), REG-PP-002
  every other row    -> the call-day's settled official CLOSE (INS-014: the bar dated the
                     call date), and that close must have printed (volume > 0)
Verdicts: REF_OK, REF_MISMATCH, REF_PENDING (owed bar not settled/printed yet). A mismatch
on a row dated >= REF_TEST_FROM (the first session after the fix) FAILS the audit; a
mismatch on an older open row is REF_LEGACY - reported loudly, never failing, because its
disposal is a ruling (BENCH-002), not a side effect. Scored rows are not reference-tested:
their numbers are frozen either way.

EXIT CODE: 1 if any row is FAIL or any post-fix row is REF_MISMATCH, else 0. NO_BAR / UNFETCHABLE do not fail the
audit — they are reported, loudly, because they are not evidence of a violation
and must not be laundered into one either.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, "agent", "ledger.csv")
CACHE = os.path.join(ROOT, "data", "price_audit_cache.json")
CHART = ("https://query1.finance.yahoo.com/v8/finance/chart/{t}"
         "?period1={p1}&period2={p2}&interval=1d")
UA = {"User-Agent": "Mozilla/5.0"}

# Tolerance on the bar's own edges. Yahoo publishes split/dividend-adjusted OHLC
# and rounds; a price that agrees with the bar to a tenth of a percent is the same
# price, and flagging that as the INS-014 defect would bury the real ones. The
# defect this auditor was built for ran +2.38pp against the day's low on average —
# twenty-three times this tolerance — so the band cannot hide it.
EPS = 0.001
REF_TEST_FROM = "2026-09-28"   # INS-020: first session after the writer fix; rows from here must match exactly

# The queued-fill helpers live on the write path (one definition, two readers - Firm Brain S6).
sys.path.insert(0, os.path.join(ROOT, "agent"))
import stale_quote as _Q  # noqa: E402


def _load_cache() -> dict:
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(c: dict) -> None:
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(c, f)
    os.replace(tmp, CACHE)


def _settled_day() -> str:
    """Last settled NYSE session (SESSION-001), PT clock. A later bar is still moving."""
    try:
        return _Q._SESS.settled_session().isoformat()
    except Exception:
        return date.today().isoformat()


def bars(ticker: str, cache: dict, refresh: bool = False, need: str | None = None) -> dict | None:
    """{'YYYY-MM-DD': [low, high, open, close, volume]} for this ticker, or None if unfetchable.

    Cached on disk: settled historical bars are facts, not live quotes (Firm Brain S11), so
    re-running is idempotent. INS-020: the cache used to hold only [low, high], which made
    "settled close or live print?" unanswerable; it now holds open/close/volume too, and ONLY
    for settled days - a bar for a session still trading is never written to the cache.
    Refetched when the cache is in the old two-field shape, or lacks a settled day `need`.
    """
    settled = _settled_day()
    v = cache.get(ticker)
    stale = (v is None or refresh
             or (isinstance(v, dict) and any(len(x) < 5 for x in v.values()))
             or (isinstance(v, dict) and need and need <= settled and need not in v
                 and (not v or max(v) < need)))
    if not stale:
        return None if v == "UNFETCHABLE" else v
    p1 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(time.time())
    url = CHART.format(t=urllib.parse.quote(ticker), p1=p1, p2=p2)
    try:
        req = urllib.request.Request(url, headers=UA)
        d = json.load(urllib.request.urlopen(req, timeout=30))
        res = d["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        out = {}
        for i, ts in enumerate(res["timestamp"]):
            lo, hi = q["low"][i], q["high"][i]
            if lo is None or hi is None:
                continue
            day = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
            if day > settled:
                continue                     # INS-020: never cache a bar that is still moving
            op, cl, vol = q["open"][i], q["close"][i], q["volume"][i]
            out[day] = [round(float(lo), 4), round(float(hi), 4),
                        None if op is None else round(float(op), 4),
                        None if cl is None else round(float(cl), 4),
                        int(vol or 0)]
        cache[ticker] = out
        return out
    except Exception:
        cache[ticker] = "UNFETCHABLE"
        return None


def reference(r: dict, b: dict) -> tuple:
    """INS-020: (verdict, basis, owed_day, owed_px) for one OPEN priced row against settled bars b."""
    th = str(r.get("thesis") or "")
    d = (r.get("date") or "").strip()
    px = float(str(r.get("price_at_call")).strip())
    if _Q.queued_fill_basis(th):
        fs = _Q.fill_session_for(d, _Q.registered_at(th))
        basis = "first traded official open after registration (REG-PP-002)"
        tup = {k: (v[2], v[1], v[0], v[3], v[4]) for k, v in b.items()}   # -> (open, high, low, close, vol)
        got = _Q.owed_open(tup, fs)
        if got is None:
            return "REF_PENDING", basis, fs.isoformat(), None
        day, owed = got
    else:
        basis = "call-day settled official close (INS-014)"
        bar = b.get(d)
        if bar is None:
            return "REF_PENDING", basis, d, None
        day, owed = d, bar[3]
        if owed is None:
            return "REF_PENDING", basis, d, None
        if not bar[4]:
            return "REF_MISMATCH", basis + " - the call-day bar is a ZERO-VOLUME carry-forward, not a printed close", d, owed
    ok = abs(px - owed) <= max(abs(owed) * EPS, 1e-9)
    return ("REF_OK" if ok else "REF_MISMATCH"), basis, day, owed


def audit(ledger: str = LEDGER, open_only: bool = False,
          since: str | None = None, refresh: bool = False) -> dict:
    rows = list(csv.DictReader(open(ledger)))
    cache = _load_cache()
    buckets = {k: [] for k in
               ("PASS", "FAIL", "NO_BAR", "UNFETCHABLE", "QUEUED", "VOID",
                "REF_OK", "REF_MISMATCH", "REF_LEGACY", "REF_PENDING")}
    try:
        for r in rows:
            if since and r.get("date", "") < since:
                continue
            if open_only and str(r.get("outcome", "")).strip():
                continue
            tick = (r.get("ticker") or "").strip()
            d = (r.get("date") or "").strip()
            rec = {"ticker": tick, "date": d, "check_date": r.get("check_date", ""),
                   "price_at_call": r.get("price_at_call", ""),
                   "stale_quote": r.get("stale_quote", ""),
                   "outcome": r.get("outcome", "")}
            if str(r.get("outcome", "")).strip() == "void":
                buckets["VOID"].append(rec)
                continue
            raw = str(r.get("price_at_call") or "").strip()
            if not raw:
                rec["note"] = ("[QUEUED] present"
                               if "[QUEUED]" in str(r.get("thesis", ""))
                               else "price_at_call empty and NO [QUEUED] marker "
                                    "— unfillable row, INS-007")
                buckets["QUEUED"].append(rec)
                continue
            try:
                px = float(raw)
            except ValueError:
                rec["note"] = f"price_at_call not numeric: {raw!r}"
                buckets["FAIL"].append(rec)
                continue
            _th, _need, _rd = str(r.get("thesis") or ""), d, d
            if _Q.queued_fill_basis(_th):
                # INS-020: a queued-fill price comes from the FILL session's bar, so the range test
                # reads that bar - testing it against the call-day bar would fail a correct fill.
                _need = _rd = max(d, _Q.fill_session_for(d, _Q.registered_at(_th)).isoformat())
            b = bars(tick, cache, refresh, need=_need)
            if b is None:
                rec["note"] = "no series from source"
                buckets["UNFETCHABLE"].append(rec)
                continue
            if _rd != d:
                got = _Q.owed_open({k: (v[2], v[1], v[0], v[3], v[4]) for k, v in b.items()},
                                   date.fromisoformat(_rd))
                _rd = got[0] if got else _rd       # a zero-volume fill session rolls to the traded bar
            if _rd not in b:
                rec["note"] = f"no bar dated {_rd} for {tick}"
                buckets["NO_BAR"].append(rec)
                continue
            lo, hi = b[_rd][0], b[_rd][1]
            rec["range_bar"] = _rd
            rec["low"], rec["high"] = lo, hi
            if px < lo * (1 - EPS):
                rec["side"] = "below low"
                rec["gap_pct"] = round((lo - px) / lo * 100, 3)
                buckets["FAIL"].append(rec)
            elif px > hi * (1 + EPS):
                rec["side"] = "above high"
                rec["gap_pct"] = round((px - hi) / hi * 100, 3)
                buckets["FAIL"].append(rec)
            else:
                buckets["PASS"].append(rec)
            # INS-020: the reference test, OPEN rows only (a scored number is frozen, BENCH-002).
            if not str(r.get("outcome", "")).strip():
                v, basis, oday, owed = reference(r, b)
                ref = dict(rec, basis=basis, owed_day=oday, owed=owed)
                if v == "REF_MISMATCH" and d < REF_TEST_FROM:
                    v = "REF_LEGACY"
                    # the checker cannot see a legacy row's write time: if it was written mid-session
                    # (the morning run), the rule owes the next traded open instead - show both.
                    if not _Q.queued_fill_basis(_th):
                        alt = _Q.owed_open({k: (x[2], x[1], x[0], x[3], x[4]) for k, x in b.items()},
                                           _Q._next_session(date.fromisoformat(d)))
                        ref["alt_next_open"] = alt[1] if alt else None
                        ref["alt_day"] = alt[0] if alt else None
                buckets[v].append(ref)
    finally:
        _save_cache(cache)
    return buckets


def _selftest() -> int:
    """INS-020 reference test, offline: synthetic settled bars [low, high, open, close, volume]."""
    b = {"2026-09-28": [9.0, 11.0, 9.5, 10.0, 1000], "2026-09-29": [10.0, 12.0, 10.5, 11.0, 800],
         "2026-09-30": [11.0, 11.0, 11.0, 11.0, 0], "2026-10-01": [11.0, 12.0, 11.2, 11.5, 50]}
    cases = [
        ({"date": "2026-09-28", "price_at_call": "10.0", "thesis": "[insider] x"}, "REF_OK"),
        ({"date": "2026-09-28", "price_at_call": "10.4", "thesis": "[insider] x"}, "REF_MISMATCH"),
        ({"date": "2026-09-28", "price_at_call": "10.5",
          "thesis": "[insider] x [QUEUED at 2026-09-28T08:35 PT] [FILLED 2026-09-29 official open 10.5]"}, "REF_OK"),
        ({"date": "2026-09-28", "price_at_call": "10.0",
          "thesis": "[insider] x [QUEUED at 2026-09-28T08:35 PT] [FILLED 2026-09-29 official open 10.0]"}, "REF_MISMATCH"),
        ({"date": "2026-09-28", "price_at_call": "9.5",
          "thesis": "[insider] x [QUEUED at 2026-09-28T05:10 PT] [FILLED 2026-09-28 official open 9.5]"}, "REF_OK"),
        ({"date": "2026-09-29", "price_at_call": "11.2",
          "thesis": "[insider] x [QUEUED at 2026-09-29T09:00 PT]"}, "REF_OK"),        # 09-30 is zero-volume -> 10-01 open
        ({"date": "2026-09-30", "price_at_call": "11.0", "thesis": "[insider] x"}, "REF_MISMATCH"),  # carry-forward close
        ({"date": "2026-10-02", "price_at_call": "12.0", "thesis": "[insider] x"}, "REF_PENDING"),
        ({"date": "2026-09-28", "price_at_call": "10.4",
          "thesis": "prose: the AGENT.md [QUEUED] branch was not available"}, "REF_MISMATCH"),  # prose is not a marker
    ]
    bad = 0
    for row, want in cases:
        got = reference(row, b)[0]
        ok = got == want
        bad += not ok
        print(("PASS " if ok else "FAIL ") + f"{row['date']} {row['price_at_call']:>5} -> {got} (want {want})")
    print("selftest:", "all passed" if not bad else f"{bad} FAILED")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--open-only", action="store_true",
                    help="audit only rows with an empty outcome")
    ap.add_argument("--since", help="only rows with date >= this")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the on-disk bar cache")
    ap.add_argument("--selftest", action="store_true", help="INS-020 reference test, offline")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    b = audit(open_only=a.open_only, since=a.since, refresh=a.refresh)
    if a.json:
        print(json.dumps(b, indent=1))
        return 1 if (b["FAIL"] or b["REF_MISMATCH"]) else 0
    n = {k: len(v) for k, v in b.items()}
    print(f"INS-014 price audit — {date.today().isoformat()}")
    print(f"  PASS {n['PASS']}  FAIL {n['FAIL']}  NO_BAR {n['NO_BAR']}  "
          f"UNFETCHABLE {n['UNFETCHABLE']}  QUEUED {n['QUEUED']}  VOID {n['VOID']}")
    for k in ("FAIL", "NO_BAR", "UNFETCHABLE", "QUEUED"):
        for r in b[k]:
            extra = (f"{r.get('side')} by {r.get('gap_pct')}% "
                     f"(bar {r.get('low')}-{r.get('high')})"
                     if k == "FAIL" and "side" in r else r.get("note", ""))
            print(f"  {k:12s} {r['ticker']:6s} {r['date']}  "
                  f"price_at_call={r['price_at_call']:>10s}  "
                  f"stale_quote={r['stale_quote'] or '(empty)':<7s} {extra}")
    print(f"  INS-020 reference (open rows): REF_OK {n['REF_OK']}  REF_MISMATCH {n['REF_MISMATCH']}  "
          f"REF_LEGACY {n['REF_LEGACY']}  REF_PENDING {n['REF_PENDING']}  (exact from {REF_TEST_FROM})")
    for k in ("REF_MISMATCH", "REF_LEGACY", "REF_PENDING"):
        for r in b[k]:
            print(f"  {k:12s} {r['ticker']:6s} {r['date']}  price_at_call={r['price_at_call']:>10s}  "
                  f"owed={r.get('owed')!s:>10s} ({r.get('owed_day')}; {r.get('basis')})"
                  + (f" | if written mid-session: {r['alt_day']} open {r['alt_next_open']}"
                     if r.get("alt_day") else ""))
    if b["REF_MISMATCH"]:
        print(f"\nFAIL — {n['REF_MISMATCH']} open row(s) dated >= {REF_TEST_FROM} do not carry the price "
              "the rule owes (INS-020). The writer queues unsettled calls; find what bypassed it.")
        return 1
    if b["FAIL"]:
        print(f"\nFAIL — {n['FAIL']} row(s) priced outside their own call-day bar. "
              "INS-014 is live. Restatement of UNSCORED rows is a ruling "
              "(BENCH-002 forbids touching scored ones).")
        return 1
    print("\nOK — every priced row sits inside its call-day bar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

EXIT CODE: 1 if any row is FAIL, else 0. NO_BAR / UNFETCHABLE do not fail the
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


def bars(ticker: str, cache: dict, refresh: bool = False) -> dict | None:
    """{'YYYY-MM-DD': [low, high]} for this ticker, or None if unfetchable.

    Cached on disk: the audit re-reads the same historical bars every run and
    those are settled facts, not live quotes. Only a SETTLED source may be
    re-derived freely (Firm Brain §11) — that is exactly what this is, and it is
    why re-running this auditor is idempotent and safe.
    """
    if not refresh and ticker in cache:
        v = cache[ticker]
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
        for ts, lo, hi in zip(res["timestamp"], q["low"], q["high"]):
            if lo is None or hi is None:
                continue
            day = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
            out[day] = [round(float(lo), 4), round(float(hi), 4)]
        cache[ticker] = out
        return out
    except Exception:
        cache[ticker] = "UNFETCHABLE"
        return None


def audit(ledger: str = LEDGER, open_only: bool = False,
          since: str | None = None, refresh: bool = False) -> dict:
    rows = list(csv.DictReader(open(ledger)))
    cache = _load_cache()
    buckets = {k: [] for k in
               ("PASS", "FAIL", "NO_BAR", "UNFETCHABLE", "QUEUED", "VOID")}
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
            b = bars(tick, cache, refresh)
            if b is None:
                rec["note"] = "no series from source"
                buckets["UNFETCHABLE"].append(rec)
                continue
            if d not in b:
                rec["note"] = f"no bar dated {d} for {tick}"
                buckets["NO_BAR"].append(rec)
                continue
            lo, hi = b[d]
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
    finally:
        _save_cache(cache)
    return buckets


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--open-only", action="store_true",
                    help="audit only rows with an empty outcome")
    ap.add_argument("--since", help="only rows with date >= this")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the on-disk bar cache")
    a = ap.parse_args()
    b = audit(open_only=a.open_only, since=a.since, refresh=a.refresh)
    if a.json:
        print(json.dumps(b, indent=1))
        return 1 if b["FAIL"] else 0
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
    if b["FAIL"]:
        print(f"\nFAIL — {n['FAIL']} row(s) priced outside their own call-day bar. "
              "INS-014 is live. Restatement of UNSCORED rows is a ruling "
              "(BENCH-002 forbids touching scored ones).")
        return 1
    print("\nOK — every priced row sits inside its call-day bar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

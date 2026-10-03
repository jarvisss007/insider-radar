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
                or the date is not a session) — a real finding, never a pass. A bar whose
                session has simply not SETTLED yet is not a missing bar: it is tagged
                `unsettled` (waiting, not missing; INS-029)
  UNFETCHABLE   the ticker could not be priced: the source said not-found (delisted, bad
                symbol) or did not answer (429, 5xx, timeout). The record says which (INS-029)
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

DISCLOSED REFERENCE GAPS (INS-026, 2026-09-30) - a tag, not a waiver
--------------------------------------------------------------------
stale_quote.fill_queued() used to fill a queued row mid-session off the still-forming bar, whose open is the
first print rather than the official open: DFDV was written at 5.83 against a settled official open of 5.84,
ATCH at 0.1926 against 0.193. Each row carries a note,
    [REF-GAP INS-026: recorded <px> vs settled official open <px> on <YYYY-MM-DD> ...]
and when the note matches this row's gap exactly (queued-fill basis; recorded price == price_at_call; official
open and day == what the settled bar says now) the audit prints the REF_MISMATCH line tagged "disclosed
(INS-026), awaiting ruling" - for fill sessions before 2026-10-01 only (the writer reads settled bars only from then,
so a gap there is a bug, never a legacy disclosure). The tag changes nothing else: the row stays REF_MISMATCH and the audit still
exits 1 - INS-020 ruled that an entry dated 2026-09-28 or later must match the owed reference, so whether to
restate these rows or to waive the gap is a ruling, not a side effect. A mismatch with no matching note is
printed "UNDISCLOSED".

A FAILED READ IS NOT A VERDICT, AND AN UNCHECKED ROW IS NOT A PASS (INS-029, 2026-10-02)
-----------------------------------------------------------------------------------------
bars() used to cache ANY exception - a 429, a timeout - as a permanent "UNFETCHABLE", so one transient error could hide a row's verification for good
(an AAPL row priced 1.00 stayed unchecked once the cache was poisoned). Now:
  * only a definitive answer is remembered: HTTP 404, a `Not Found` error body, or a reply with no bars in range. It is kept in the cache's
    `_not_found` section, stamped with the settled session it was said in, and asked again after the next close (the TTL is one settled
    session - the data's own clock, never the wall clock). Anything else (429, 5xx, a timeout, a body that is not the chart) is TRANSIENT:
    reported this run, never cached, read again next run, and not re-read within a run. A pre-INS-029 permanent "UNFETCHABLE" marker proves
    nothing and is ignored; bars already held are never overwritten by a failed refresh.
  * the closing line no longer says "every priced row sits inside its call-day bar" when rows could not be checked: an UNVERIFIED paragraph names
    how many (UNFETCHABLE; NO_BAR for a settled day; a bar whose session has not settled yet), and the verdict reads "OK for the rows it could check".
THE EXIT CODE BELOW IS UNCHANGED ON PURPOSE. Whether an unchecked row should fail the audit - and so redden the wired INS-028 check - is a ruling, not a
defect fix (INS-029): the clause below was written deliberately, and changing it is the owner's decision.

EXIT CODE: 1 if any row is FAIL or any post-fix row is REF_MISMATCH, else 0. NO_BAR / UNFETCHABLE do not fail the
audit — they are reported, loudly, because they are not evidence of a violation
and must not be laundered into one either.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
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
TAG_ONLY_BEFORE = "2026-10-01"   # INS-026: the writer reads settled bars only for fill sessions from here; no note is ever tagged there
NOT_FOUND = "_not_found"         # INS-029: cache section {ticker: {why, settled, at}} - only the source's own "not found", only for the session it was said in
_GAP = re.compile(r"\[REF-GAP INS-026: recorded ([0-9]+(?:\.[0-9]+)?) vs settled official open "
                  r"([0-9]+(?:\.[0-9]+)?) on (\d{4}-\d{2}-\d{2})")

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
    """Last settled NYSE session (SESSION-001), PT clock. A later bar is still moving.

    INS-026: fails CLOSED. With no calendar the audit cannot say which bars are final, so it refuses - it used to fall back to
    today, which treats today as settled at any hour, caches a still-forming bar permanently, and disagrees with the writer
    (which waits for the settled session) under the same fault (Firm Brain S6)."""
    if _Q._SESS is None:
        print("price_audit: the sessions calendar is unavailable - cannot say which bars are settled, so nothing "
              "is cached or tested (INS-026)", file=sys.stderr)
        raise SystemExit(2)          # 2 = could not look; 1 stays "looked, and it FAILS"
    try:
        return _Q._SESS.settled_session().isoformat()
    except Exception as e:
        print(f"price_audit: the sessions calendar failed ({type(e).__name__}) - cannot say which bars are settled, "
              "so nothing is cached or tested (INS-026)", file=sys.stderr)
        raise SystemExit(2)


def _fetch(ticker: str, settled: str):
    """INS-029. One read of the source -> (bars, kind, why). kind is "ok"; "not_found" (the source ANSWERED that it has nothing: HTTP 404,
    a `Not Found` error body, or a reply with no bars in range - the only kind that may be remembered); or "transient" (it did not answer, or
    what it sent is not the chart: 429, 5xx, a timeout, DNS, TLS, a body that is not the chart JSON - never remembered, read again next run)."""
    p1 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(time.time())
    url = CHART.format(t=urllib.parse.quote(ticker), p1=p1, p2=p2)
    try:
        req = urllib.request.Request(url, headers=UA)
        d = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "not_found", "HTTP 404 Not Found"
        return None, "transient", f"HTTP {e.code}"
    except Exception as e:                       # URLError, timeout, TLS, a body that is not JSON
        return None, "transient", type(e).__name__
    try:
        chart = d["chart"]
        res = chart.get("result")
        if not res:
            code = str((chart.get("error") or {}).get("code") or "")
            if code.lower() == "not found":
                return None, "not_found", "error body: Not Found"
            return None, "transient", f"no result ({code or 'no error code'})"
        res = res[0]
        if not res.get("timestamp"):
            return None, "not_found", "no bars in range"
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
        return out, "ok", ""
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
        return None, "transient", f"unexpected reply shape ({type(e).__name__})"


def _bars(ticker: str, cache: dict, refresh: bool = False, need: str | None = None, run_fail: dict | None = None):
    """-> (bars, why, kind): {'YYYY-MM-DD': [low, high, open, close, volume]} for this ticker, or None with the reason and its kind
    ("not_found" | "transient"; "ok" with bars).

    Cached on disk: settled historical bars are facts, not live quotes (Firm Brain S11), so
    re-running is idempotent. INS-020: the cache used to hold only [low, high], which made
    "settled close or live print?" unanswerable; it now holds open/close/volume too, and ONLY
    for settled days - a bar for a session still trading is never written to the cache.
    Refetched when the cache is in the old two-field shape, or lacks a settled day `need`.

    INS-029: a failed read is never cached as a verdict. Only the source's own "not found" is remembered (cache[NOT_FOUND], stamped with the
    settled session it was said in and honoured only inside that session); a transient failure is reported, left out of the cache, and not
    retried again within this run (`run_fail`). Good bars already cached are never overwritten by a failed refresh."""
    settled = _settled_day()
    v = cache.get(ticker)
    if v == "UNFETCHABLE":                       # pre-INS-029 permanent marker, written for ANY exception: it proves nothing
        v = None
    stale = (v is None or refresh
             or (isinstance(v, dict) and any(len(x) < 5 for x in v.values()))
             or (isinstance(v, dict) and need and need <= settled and need not in v
                 and (not v or max(v) < need)))
    if not stale:
        return v, "", "ok"                       # bars already held are facts: a later "not found" does not take them away
    ent = (cache.get(NOT_FOUND) or {}).get(ticker)
    if ent and not refresh and str(ent.get("settled", "")) >= settled:
        return (None, f"the source said not found ({ent.get('why')}) in the {ent.get('settled')} session; asked again after the next close",
                "not_found")
    if run_fail is not None and ticker in run_fail:
        return None, run_fail[ticker], "transient"
    out, kind, why = _fetch(ticker, settled)
    if kind == "ok":
        cache[ticker] = out
        (cache.get(NOT_FOUND) or {}).pop(ticker, None)
        return out, "", "ok"
    if kind == "not_found":
        cache.setdefault(NOT_FOUND, {})[ticker] = {"why": why, "settled": settled,
                                                   "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        return None, f"the source said not found ({why}); remembered for the {settled} session only", kind
    msg = f"transient fetch error ({why}); not cached, read again next run"
    if run_fail is not None:
        run_fail[ticker] = msg
    return None, msg, kind


def bars(ticker: str, cache: dict, refresh: bool = False, need: str | None = None) -> dict | None:
    """The bars (see _bars), or None if the ticker could not be read; _bars says why."""
    return _bars(ticker, cache, refresh, need)[0]


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


def disclosed_gap(thesis, recorded: float, owed_day: str, owed_px: float):
    """INS-026: {recorded, owed, day} from the row's own [REF-GAP INS-026: ...] note if, and only if, it describes exactly this
    gap (queued-fill basis; recorded price == price_at_call; official open and day == what the settled bar says now), else None.
    It is a TAG only: nothing is waived and the row's verdict does not change. A fill session from TAG_ONLY_BEFORE on is never
    tagged: the writer reads settled bars only there, so a gap on such a fill is a bug, not a disclosed legacy gap."""
    if not _Q.queued_fill_basis(thesis) or str(owed_day) >= TAG_ONLY_BEFORE:
        return None
    for m in _GAP.finditer(str(thesis or "")):
        rec, off, day = float(m.group(1)), float(m.group(2)), m.group(3)
        if day == str(owed_day) and rec == recorded and abs(off - owed_px) <= max(abs(owed_px) * EPS, 1e-9):
            return {"recorded": rec, "owed": off, "day": day}
    return None


def audit(ledger: str = LEDGER, open_only: bool = False,
          since: str | None = None, refresh: bool = False) -> dict:
    rows = list(csv.DictReader(open(ledger)))
    cache = _load_cache()
    run_fail: dict = {}                      # INS-029: a ticker whose read failed transiently is not read again within this run
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
                if _Q.is_queued(r.get("thesis")):   # INS-026: the stamped "[QUEUED at ..." marker counts, not only the literal "[QUEUED]"
                    try:
                        fs = _Q.fill_session_for(d, _Q.registered_at(str(r.get("thesis") or ""))).isoformat()
                    except Exception:
                        fs = None
                    rec["note"] = "[QUEUED] present" + (f" - fills after the {fs} session settles (INS-026)" if fs else "")
                else:
                    rec["note"] = ("price_at_call empty and NO [QUEUED] marker "
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
            b, why, kind = _bars(tick, cache, refresh, need=_need, run_fail=run_fail)
            if b is None:
                rec["note"] = f"no series from source: {why}"
                rec["source"] = kind                   # INS-029: "not_found" (the source answered) | "transient" (it did not)
                buckets["UNFETCHABLE"].append(rec)
                continue
            if _rd != d:
                got = _Q.owed_open({k: (v[2], v[1], v[0], v[3], v[4]) for k, v in b.items()},
                                   date.fromisoformat(_rd))
                _rd = got[0] if got else _rd       # a zero-volume fill session rolls to the traded bar
            if _rd not in b:
                if _rd > _settled_day():           # INS-029: the owed bar belongs to a session that has not settled - not missing, not yet checkable
                    rec["note"] = f"the {_rd} bar has not settled yet - not a missing bar; checked once its session settles"
                    rec["unsettled"] = True
                else:
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
                elif v == "REF_MISMATCH":   # INS-026: a tag only - the row stays a mismatch and the audit still fails
                    ref["disclosed"] = bool(disclosed_gap(_th, px, oday, owed))
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
    # INS-026: a note TAGS exactly the gap it names, on a queued-fill row, and nothing else.
    q = "[insider] x [QUEUED at 2026-09-28T08:35 PT] [FILLED 2026-09-29 official open 5.83]"
    note = " [REF-GAP INS-026: recorded 5.83 vs settled official open 5.84 on 2026-09-29 (gap -0.01)]"
    gcases = [
        ("a matching note is tagged", q + note, 5.83, "2026-09-29", 5.84, True),
        ("no note is not", q, 5.83, "2026-09-29", 5.84, False),
        ("a note for another recorded price is not", q + note, 5.82, "2026-09-29", 5.84, False),
        ("a note whose official open no longer matches is not", q + note, 5.83, "2026-09-29", 5.90, False),
        ("a note for another day is not", q + note, 5.83, "2026-09-30", 5.84, False),
        ("a note on a non-fill row is not", "[insider] x" + note, 5.83, "2026-09-29", 5.84, False),
        ("a fill session from the fix date on is never tagged", q.replace("09-29", "10-01") + note.replace("09-29", "10-01"),
         5.83, "2026-10-01", 5.84, False),
    ]
    for why, th, rec, day, off, want in gcases:
        got = disclosed_gap(th, rec, day, off) is not None
        bad += got != want
        print(("PASS " if got == want else "FAIL ") + f"disclosure tag: {why} -> {got}")
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
                     if r.get("alt_day") else "")
                  + ((" | disclosed (INS-026), awaiting ruling" if r.get("disclosed") else " | UNDISCLOSED")
                     if k == "REF_MISMATCH" else ""))
    unv = len(b["UNFETCHABLE"]) + sum(1 for r in b["NO_BAR"] if not r.get("unsettled"))
    waiting = sum(1 for r in b["NO_BAR"] if r.get("unsettled"))
    if unv or waiting:                         # INS-029: say so before any verdict
        print(f"\nUNVERIFIED — {unv + waiting} priced row(s) were not checked: UNFETCHABLE {n['UNFETCHABLE']}, "
              f"NO_BAR for a settled day {unv - n['UNFETCHABLE']}, bar not settled yet {waiting}. An unchecked row is not a pass (INS-029). "
              "A 'transient' source error is read again next run, a 'not_found' one after the next close; the exit status does not change "
              "(whether an unchecked row should fail the audit is a ruling).")
    if b["REF_MISMATCH"]:
        n_disc = sum(1 for r in b["REF_MISMATCH"] if r.get("disclosed"))
        print(f"\nFAIL — {n['REF_MISMATCH']} open row(s) dated >= {REF_TEST_FROM} do not carry the price "
              "the rule owes (INS-020). The writer queues unsettled calls; find what bypassed it."
              + (f" {n_disc} of them carry a matching [REF-GAP INS-026] disclosure and await a ruling (restate, or waive); "
                 f"{n['REF_MISMATCH'] - n_disc} are UNDISCLOSED." if n_disc else ""))
        return 1
    if b["FAIL"]:
        print(f"\nFAIL — {n['FAIL']} row(s) priced outside their own call-day bar. "
              "INS-014 is live. Restatement of UNSCORED rows is a ruling "
              "(BENCH-002 forbids touching scored ones).")
        return 1
    if unv or waiting:
        print("\nOK for the rows it could check - not for the UNVERIFIED rows above.")
        return 0
    print("\nOK — every priced row sits inside its call-day bar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

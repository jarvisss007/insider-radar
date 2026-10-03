#!/usr/bin/env python3
"""stale_quote — the insider ledger's frozen-reference disclosure column.

WHY THIS EXISTS (council INS-004, 2026-08-10)
--------------------------------------------
Two rows in this ledger were priced off quotes that had stopped moving: WBHC
printed exactly 550.00 on 08-04/08-05/08-06, NWPP exactly 4.50 on
08-05/08-06/08-07. The lab caught both itself and said so in the brief — in
prose. Prose does not survive contact with a scoring script. On 2026-08-16 the
first seven rows come due, and without a machine-readable field somebody has to
decide THEN which references were frozen: a judgement made after outcomes are
visible, in the one week it matters.

WHAT IT IS AND IS NOT
---------------------
`stale_quote` is a DISCLOSURE field, decided at CALL time from the price series
that existed BEFORE the call. It changes no bar, drops no row, and scores
nothing differently. Scoring rules in AGENT.md are untouched: `outcome` is still
`right` iff `price_at_check > price_at_call`, for every row, flagged or not. The
only thing this column buys is the ability to split the sample honestly later.

VALUES
------
  yes    the last N complete closes before the call were identical to the cent
  no     they were not — the reference moved
  (empty) not established. Honest ignorance. Never guess this field; an empty
         cell is a true statement, a guessed one is a fabricated observation.
"""

from __future__ import annotations
# BOOK-001 (2026-09-07): atomic book writes via stock-radar/atomicio.py (loaded by path; plain write if unavailable).
try:
    import importlib.util as _iu2
    _sp2 = _iu2.spec_from_file_location("_atomicio", "/Users/anupampatil/stock-radar/atomicio.py")
    _ATOM = _iu2.module_from_spec(_sp2); _sp2.loader.exec_module(_ATOM)
except Exception:
    _ATOM = None
def _atomic_csv(path, fieldnames, rows, **kw):
    if _ATOM:
        _ATOM.hold_book(path); _ATOM.atomic_csv(path, fieldnames, rows, **kw); return
    import csv as _csv
    with open(path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=fieldnames, **kw); w.writeheader(); w.writerows(rows)
# SESSION-001 (2026-09-05): the estate's one NYSE calendar lives in stock-radar/sessions.py;
# loaded by path (this repo runs alone), weekday-only fallback if it is unavailable.
try:
    import importlib.util as _iu
    _sp = _iu.spec_from_file_location("_sessions", "/Users/anupampatil/stock-radar/sessions.py")
    _SESS = _iu.module_from_spec(_sp); _sp.loader.exec_module(_SESS)
except Exception:
    _SESS = None
def _is_session(d):
    return _SESS.is_session(d) if _SESS else d.weekday() < 5

import argparse
import csv
import json
import os
import sys
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
try:
    from zoneinfo import ZoneInfo
    _PT = ZoneInfo("America/Los_Angeles")
except Exception:   # pragma: no cover
    _PT = None

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")

# The ledger schema. `stale_quote` is appended LAST so every existing positional
# reader keeps working; the first eight fields are exactly as they always were.
#
# INS-011 (Resolver, 2026-08-21). `tags` was added to ledger.csv on 2026-08-20 under
# TAG-001 and was NOT added here, so this list ran NINE fields against a TEN-column
# file: any row written through append_call() would have landed short and silently
# dropped the very tag declaration TAG-001 was opened to obtain, and verify() reported
# the lab's own ledger as non-matching. No wrong row was produced -- the eight rows of
# 2026-08-21 were appended against the file's real schema -- but the write path and the
# file disagreed for a day. `tags` is appended LAST, in the file's own order.
# INS-011, fixed 2026-08-29. This was a hardcoded 9-column literal against a ledger that
# had grown to 10 with TAG-001's `tags`, and to 11 the same day `void_reason` was added
# for INS-012. A csv.DictWriter given fewer fieldnames than the file has silently drops
# the missing columns from every appended row, so each new call would have been written
# without its tags — and a hardcoded list drifts again the next time a column is added.
#
# Read the real header from the ledger instead, and keep the literal only as the shape
# a brand-new ledger is created with. A constant that must be kept in sync by hand will
# eventually not be.
_LEDGER_FALLBACK = [
    "date", "ticker", "call", "thesis", "price_at_call", "check_date",
    "price_at_check", "outcome", "stale_quote", "tags", "void_reason",
]


def ledger_header(path=None):
    """The ledger's ACTUAL columns, so the write path can never be narrower than the file."""
    p = path or LEDGER
    try:
        with open(p) as fh:
            head = next(csv.reader(fh))
        return head if head else list(_LEDGER_FALLBACK)
    except (FileNotFoundError, StopIteration):
        return list(_LEDGER_FALLBACK)


LEDGER_HEADER = _LEDGER_FALLBACK

# Three identical closes to the cent is the bar the lab used when it caught WBHC
# and NWPP by eye. Keeping the same bar keeps the backfilled rows and every
# future row on one definition.
STALE_SESSIONS = 3

CHART = ("https://query1.finance.yahoo.com/v8/finance/chart/"
         "{t}?range={r}&interval=1d")


def is_stale(closes, sessions: int = STALE_SESSIONS) -> bool:
    """True iff the last `sessions` complete closes are identical to the cent.

    A flat tape does not print the same number three sessions running. A name
    that did not trade does — the vendor carries the last print forward.

    INS-006 (2026-08-12): the window now ends at the CALL DATE rather than the day
    before it, so that a quote frozen only on the call date is visible. But
    checking just the final `sessions` bars of that widened window would SLIDE it
    forward and drop the oldest bar — implemented that way, NWPP flipped yes->no
    even though the lab had recorded it printing exactly 4.50 on 08-05, 06 and 07.
    Widening a detector must never make it blind to something it already caught.

    So the test is now: does ANY run of `sessions` consecutive identical closes
    appear anywhere in the window? That is strictly more sensitive than the old
    tail-only check and cannot turn an existing `yes` into a `no`.
    """
    vals = [round(float(c), 2) for c in closes if c is not None]
    if len(vals) < sessions:
        return False
    for i in range(len(vals) - sessions + 1):
        if len(set(vals[i:i + sessions])) == 1:
            return True
    return False


def closes_before(ticker: str, asof: str | None = None, rng: str = "3mo"):
    """Complete daily closes up to and INCLUDING `asof` (YYYY-MM-DD, default today).

    INS-006, ruled by Anupam 2026-08-12. This was strictly-before until then, and
    that left the freshness check unable to see the bar the reference price
    actually came from: AGENT.md defines price_at_call as the "latest daily
    close", and on NTSK that was 13.59 — the settled close of the CALL DATE
    itself — while this window read only 14.27 / 13.25 / 13.50 from the three
    days before. A quote that froze only ON the call date was therefore
    invisible to the exact check written to catch frozen quotes.

    The window now includes the call-date bar. The alternative fix — redefining
    price_at_call as the last COMPLETE close — was rejected because it rewrites
    reference prices on rows already written, which BENCH-002 forbids.

    Still safe against lookahead: this only ever reads CLOSES on or before the
    call date, never a price after it. A same-day run fires mid-session and the
    call-date bar is then incomplete, which shows up as a live intraday value
    rather than a settled close — the same condition the lab already discloses,
    and never a future price.
    """
    req = urllib.request.Request(CHART.format(t=ticker, r=rng),
                                 headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    res = d["chart"]["result"][0]
    stamps = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    cutoff = asof or date.today().isoformat()
    out = []
    for ts, c in zip(stamps, closes):
        if c is None:
            continue
        day = date.fromtimestamp(ts).isoformat()
        if day <= cutoff:          # INS-006: was `<`
            out.append((day, round(float(c), 2)))
    return out


def flag_for(ticker: str, asof: str | None = None,
             sessions: int = STALE_SESSIONS):
    """Return (flag, detail) for a call being written now.

    flag is "yes"/"no", or "" when the series cannot be established — an
    unreachable or barless ticker is unknown, not clean.
    """
    try:
        series = closes_before(ticker, asof)
    except Exception as e:  # network, delisting, junk symbol
        return "", f"{ticker}: no series ({type(e).__name__})"
    if len(series) < sessions:
        return "", f"{ticker}: only {len(series)} complete bars, cannot establish"
    # INS-006: the window ends at the call date, so it must be LONGER than the run
    # being looked for — otherwise widening it merely slides it forward and drops
    # the oldest bar. Implemented that way first, and NWPP flipped yes->no despite
    # the lab having recorded it printing exactly 4.50 on 08-05, 06 and 07: the
    # slice had moved to 08-06..08-10 and could no longer see the freeze. A window
    # of sessions+1 holds both the run before the call date and the call-date bar,
    # and is_stale() scans it for a run anywhere rather than only at its tail.
    tail = series[-(sessions + 1):]
    vals = [c for _, c in tail]
    flag = "yes" if is_stale(vals, sessions) else "no"
    span = f"{tail[0][0]}..{tail[-1][0]}"
    return flag, f"{ticker}: closes {vals} over {span} -> stale_quote={flag}"


# ---- INS-020 (ruled 2026-09-27, option a) + REG-PP-002 queued-fill -----------------------
# AGENT.md SS INS-014: "If today's bar is not out yet, never write yesterday's close as today's
# price: write the row with price_at_call EMPTY and [QUEUED], and fill it from the next session's
# official open." Until 2026-09-27 this write path REFUSED exactly that row (INS-007 below), so the
# morning run wrote a live intraday print instead and froze it as the 30-day reference - 35 of 39
# open rows dated 2026-09-14..09-21 (BENF +30.4% off its close). The rule, made executable:
#   * a call whose call-day close is NOT settled at write time carries no price: it is QUEUED
#     (stamped with its registration time) and any live print the caller passed is moved into
#     the thesis as a disclosure, never into price_at_call;
#   * fill_queued() fills it from the FIRST OFFICIAL OPEN AFTER REGISTRATION (REG-PP-002) - the
#     first bar dated on/after that session with volume > 0 (a zero-volume bar is a carry-forward,
#     not an open that printed: INS-015 / Firm Brain S18);
#   * a call written after the call-day close settled keeps the settled close (the bar DATED the
#     call date, INS-014); price_audit.py now stores and tests that reference (INS-020 checker);
#   * INS-026 (2026-09-30, class (d) correction): that open is FINAL only once its session has settled.
#     fill_queued() used to read the fill session's bar while it was still trading, and a forming bar's
#     open is the first print, not the official open: DFDV was filled at 5.83 and ATCH at 0.1926 mid-session
#     while the settled bars carry the official opens 5.84 and 0.193 that price_audit.py tests (the first
#     one-minute print of each session equals what was written; 5 other in-session fills agreed only because
#     their first print was the official open). So fill_queued() now fills only from a session that has
#     settled, and only from settled bars - the fix stock-radar's official_open() took as FILL-002 (d) - and
#     it fails CLOSED: with no calendar (or one that raises, or no PT clock) it fills nothing, says so and exits non-zero,
#     never guessing settledness from the clock. A fill therefore lands on the first run after the fill
#     session's close (typically D+2 rather than D+1 for a call written on D); the price owed, the fill
#     session and the 30-day check_date are unchanged. Fills made before this change stand as recorded and
#     are disclosed on their rows.
OPEN_PT = (6, 30)                     # NYSE 09:30 ET official open, in PT (NY and CA shift together)
QUEUED_TAG = "[QUEUED"   # prefix only; use is_queued()/queued_fill_basis() - prose can mention "[QUEUED] branch"


def is_queued(thesis) -> bool:
    """A row the write path queued: the literal [QUEUED] marker or a stamped [QUEUED at ...]."""
    th = str(thesis or "")
    return "[QUEUED]" in th or "[QUEUED at " in th


def queued_fill_basis(thesis) -> bool:
    """True if the row's reference is the queued-fill open: stamped [QUEUED at ..], [FILLED ..], or
    INS-020 restated. A bare "[QUEUED]" is NOT enough on a priced row - SHMD/ENOV (09-08) mention "the
    AGENT.md [QUEUED] branch" in prose while carrying a live print."""
    th = str(thesis or "")
    return "[QUEUED at " in th or "[FILLED " in th or "[RESTATED 2026-09-27 (INS-020" in th
_REG_AT = re.compile(r"(?:\[QUEUED at|registered) (\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")


def _now_pt():
    return datetime.now(_PT) if _PT else datetime.now()


def _next_session(d):
    if _SESS:
        return _SESS.next_session(d)
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def call_day_settled(call_date, now=None) -> bool:
    """True iff the call date's official close had settled at `now` (PT). SESSION-001 calendar."""
    d = date.fromisoformat(str(call_date)[:10])
    now = now or _now_pt()
    if _SESS:
        return _SESS.settled_session(now) >= d
    return now.date() > d or (now.date() == d and (now.hour, now.minute) >= (13, 5))


def registered_at(thesis):
    """The registration moment stamped on a queued/restated row, as a naive PT datetime, or None."""
    m = _REG_AT.search(str(thesis or ""))
    return datetime.fromisoformat(m.group(1)) if m else None


def fill_session_for(call_date, reg=None):
    """REG-PP-002: the session whose official open is the FIRST open after registration.

    Registered before 06:30 PT on a session day -> that day's open. Registered at/after the open,
    or on a non-session, or at an unknown time (assumed after the call date's open - the morning
    run fires at ~08:35 PT) -> the next session after it."""
    if reg is not None:
        rd = reg.date()
        if (_SESS.is_session(rd) if _SESS else rd.weekday() < 5) and (reg.hour, reg.minute) < OPEN_PT:
            return rd
        return _next_session(rd)
    return _next_session(date.fromisoformat(str(call_date)[:10]))


def daily_bars(ticker, since):
    """{YYYY-MM-DD: (open, high, low, close, volume)} from Yahoo's chart endpoint, bars dated >= since."""
    p1 = int(datetime(since.year, since.month, since.day).timestamp()) - 86400
    p2 = int(datetime.now().timestamp())
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ticker)}?period1={p1}&period2={p2}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    res = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = {}
    from datetime import timezone as _tz
    for i, ts in enumerate(res.get("timestamp") or []):
        day = datetime.fromtimestamp(ts, _tz.utc).date().isoformat()
        out[day] = tuple(q[k][i] for k in ("open", "high", "low", "close", "volume"))
    return out


def owed_open(bars, fill_session):
    """(day, open) of the first bar dated >= fill_session that actually traded (volume > 0, real
    open). Zero-volume bars are skipped and never used as a fill (INS-015 / S18). None = not yet."""
    for day in sorted(bars):
        if day < fill_session.isoformat():
            continue
        o, _h, _l, _c, v = bars[day]
        if o is None or not v:
            continue
        return day, float(o)
    return None


def fmt_px(x):
    """Price text: 4 dp, trailing zeros trimmed, never fewer than 2 dp (21.95, 0.587, 13.623)."""
    s = f"{float(x):.4f}".rstrip("0")
    whole, frac = s.split(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def _settled_for_fill(now):
    """INS-026: the last settled session (a date) as the sessions calendar states it, or None when it cannot be established.
    Fails CLOSED: a fill writes a price into a book, so with no calendar - or one that raises - or with a clock that carries no time
    zone (the PT clock is unavailable), the caller fills nothing. It is deliberately NOT call_day_settled(), whose clock fallback
    (13:05 PT) is left unchanged for scope."""
    if not _SESS or getattr(now, "tzinfo", None) is None:
        return None
    try:
        return _SESS.settled_session(now)
    except Exception:
        return None


def fill_queued(ledger: str = LEDGER, dry: bool = False, now=None) -> int:
    """REG-PP-002 / INS-020: fill every open QUEUED row from its owed official open. Idempotent.

    Only rows with outcome empty, price_at_call empty and a [QUEUED marker are touched; a filled
    row carries [FILLED <day> official open <px>] and is never filled twice. A queued row whose
    owed open has not printed waits and says so; one still unfilled 7+ calendar days after its fill
    session is reported UNFILLABLE (an INS-007 exclusion is a human's call, never automatic).

    INS-026: a row fills only once its fill session has SETTLED, and only from settled bars, so the price written is the
    official open price_audit.py tests - never the provisional first print of a session still trading. Until then the row
    waits and says why. If the settled session cannot be established the run fills NOTHING, says so and returns 2."""
    now = now or _now_pt()
    settled = _settled_for_fill(now)
    if settled is None:
        print("fill_queued: CALENDAR UNAVAILABLE (no sessions calendar, or no PT clock) - the settled session cannot be "
              "established, so NOTHING is filled (INS-026); queued rows keep waiting")
        return 2
    if _ATOM and not dry:
        _ATOM.hold_book(ledger)
    with open(ledger) as f:
        rows = list(csv.DictReader(f))
    header = ledger_header(ledger)
    filled, waiting = [], []
    for r in rows:
        if (r.get("outcome") or "").strip() or str(r.get("price_at_call") or "").strip():
            continue
        th = str(r.get("thesis") or "")
        if not is_queued(th):
            continue
        fs = fill_session_for(r["date"], registered_at(th))
        if fs > now.date():
            waiting.append(f"{r['ticker']} {r['date']}: fills at the {fs} open (not yet)")
            continue
        if fs > settled:   # INS-026: the official open is final only after its session settles
            waiting.append(f"{r['ticker']} {r['date']}: the {fs} session has not settled (last settled session {settled}); "
                           f"fills at its final official open after the close, on the next run (INS-026)")
            continue
        try:
            # INS-026: settled bars only - a bar for a session still trading carries a provisional (first-print) open
            got = owed_open({d: v for d, v in daily_bars(r["ticker"], fs).items() if d <= settled.isoformat()}, fs)
        except Exception as e:
            got, err = None, f"{type(e).__name__}"
        else:
            err = ""
        if got is None:
            late = (now.date() - fs).days >= 7
            waiting.append(f"{r['ticker']} {r['date']}: no traded open on/after {fs} yet"
                           + (f" ({err})" if err else "")
                           + (" - UNFILLABLE so far; INS-007 exclusion is Anupam's call" if late else ""))
            continue
        day, px = got
        r["price_at_call"] = fmt_px(px)
        r["thesis"] = (th + f" [FILLED {day} official open {fmt_px(px)} "
                            f"(REG-PP-002 queued-fill, INS-020)]").strip()
        filled.append(f"{r['ticker']} {r['date']} -> {day} open {fmt_px(px)}")
    if filled and not dry:
        _atomic_csv(ledger, header, rows)
    for x in filled:
        print(f"  FILLED  {x}")
    for x in waiting:
        print(f"  QUEUED  {x}")
    print(f"fill_queued: {len(filled)} filled, {len(waiting)} still queued{' [DRY]' if dry else ''}")
    return 0


def append_call(row: dict, ledger: str = LEDGER, sessions: int = STALE_SESSIONS, now=None):
    """Append ONE call to the ledger with stale_quote already decided.

    This is the write path. Anything logging a call goes through here so the
    disclosure cannot be forgotten: if the caller does not supply stale_quote,
    it is computed from the pre-call series. `price_at_check` and `outcome` are
    always written empty — a call is never born scored.
    """
    # WEEKEND CHECK-DATE GUARD (2026-08-31). Anupam caught SCTX on the desk page:
    # check_date 2026-08-30, a Sunday, still "open" past its exit plan — because the
    # date was computed as entry+30 CALENDAR days and no session exists to score it.
    # 45 pending rows carried the same defect. A check date must be a session: a
    # Sat/Sun date rolls forward to the next weekday AT WRITE TIME, deterministically
    # (the target is forced, so no kinder-day discretion — distinct from INS-012 §3a,
    # which governs missing bars on trading days and voids instead).
    cd_ = str(row.get("check_date") or "").strip()
    if cd_:
        import datetime as _dt
        try:
            _d = _dt.date.fromisoformat(cd_)
            if not _is_session(_d):
                _orig = cd_
                while not _is_session(_d):
                    _d += _dt.timedelta(days=1)
                row["check_date"] = _d.isoformat()
                row["thesis"] = (str(row.get("thesis") or "") +
                                 f" [check_date {_orig} was a weekend; rolled to the next "
                                 f"session {_d.isoformat()} at write time]").strip()
        except ValueError:
            pass
    # INS-020 (ruled 2026-09-27, option a): the call-day close must be SETTLED for a price to be
    # written. Otherwise the row is QUEUED (REG-PP-002) and the caller's live print becomes a
    # disclosure in the thesis - it is never the reference. Registration time is stamped so
    # fill_queued() and price_audit.py can compute the owed open without guessing.
    _now = now or _now_pt()
    _stamp = _now.strftime("%Y-%m-%dT%H:%M")
    _px_in = str(row.get("price_at_call") or "").strip()
    if _px_in and not call_day_settled(row.get("date"), _now):
        row["price_at_call"] = ""
        row["thesis"] = (str(row.get("thesis") or "") +
                         f" [QUEUED at {_stamp} PT (INS-020/REG-PP-002): written before the "
                         f"{row.get('date')} close settled; the live print {_px_in} is NOT the "
                         f"reference - fills at the first official open after registration]").strip()
    elif not _px_in and is_queued(row.get("thesis")) and not registered_at(row.get("thesis")):
        row["thesis"] = (str(row.get("thesis") or "") +
                         f" [QUEUED at {_stamp} PT (REG-PP-002)]").strip()
    # INS-014 (2026-09-05 audit): 25 rows carried the PRIOR session's close as price_at_call while
    # stale_quote said "no" — is_stale() watches whether closes MOVE, not whether the quote's own date
    # is the call date. A call price must come from a bar dated the call date; otherwise the row says
    # so and the auditor (price_audit.py) will see it.
    _qd = str(row.get("quote_date") or "").strip()
    if row.get("price_at_call") and _qd and _qd != str(row.get("date") or ""):
        row["stale_quote"] = "yes"
        row["thesis"] = (str(row.get("thesis") or "") + f" [quote dated {_qd}, not the call date — a prior-session close; treat the entry as unfillable until restated]").strip()
    if "stale_quote" not in row or row["stale_quote"] is None:
        flag, _ = flag_for(row["ticker"], row.get("date"), sessions)
        row["stale_quote"] = flag
    row.setdefault("price_at_check", "")
    row.setdefault("outcome", "")
    missing = [k for k in ledger_header() if k not in row]
    if missing:
        raise ValueError(f"call is missing fields: {missing}")
    # INS-007, ruled by Anupam 2026-08-14. A call with no entry price can NEVER
    # score: it sits `pending` forever, counts as open exposure in a book that
    # cannot resolve it, and is what made PORT-001 regress on 2026-08-13. Six such
    # rows had accumulated (VISTA, AXIA3, PNAQ and three CIK-only names — non-traded
    # BDCs and unlisted filers with no quote anywhere).
    #
    # An unpriceable cluster is a DISCLOSED EXCLUSION, not a position. The write
    # path refuses it here rather than trusting each caller to remember, which is
    # the same reason stale_quote is computed here instead of by the caller.
    # INS-020: the one blank price this path accepts is the QUEUED row the rule prescribes.
    if not str(row.get("price_at_call") or "").strip() and not is_queued(row.get("thesis")):
        raise ValueError(
            f"refusing to log {row.get('ticker')}: no price_at_call. An unpriceable "
            f"cluster can never score — record it as a disclosed exclusion, not an "
            f"open position (INS-007).")

    # INS-011, 2026-08-21. `tags` is a DECLARATION, not a derivation: TAG-001 exists
    # because the Calibration Observatory was inferring 81% of the desk's tags from a
    # regex over the thesis sentence. A default written here would be this file
    # guessing on the lab's behalf -- the same defect wearing the lab's name -- so the
    # write path refuses a blank instead. This lab's answer is `fund` on every row by
    # construction (an SEC Form 4 purchase) and agent/AGENT.md step 5 says so.
    if not str(row.get("tags") or "").strip():
        raise ValueError(
            f"refusing to log {row.get('ticker')}: blank `tags`. The tag is declared "
            f"at the lab, never inferred downstream (TAG-001); this lab's rows are "
            f"`fund` by construction -- see agent/AGENT.md step 5 (INS-011).")
    new = not os.path.exists(ledger) or os.path.getsize(ledger) == 0
    with open(ledger, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ledger_header(), extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: row[k] for k in LEDGER_HEADER})
    return row


def verify(ledger: str = LEDGER) -> int:
    """Parse the ledger back and print its schema and disclosure state."""
    with open(ledger) as f:
        rows = list(csv.DictReader(f))
    header = list(rows[0].keys()) if rows else []
    print("schema:", ",".join(header))
    ok = header == LEDGER_HEADER
    print("matches LEDGER_HEADER:", ok)
    counts = {"yes": 0, "no": 0, "": 0}
    for r in rows:
        counts[(r.get("stale_quote") or "").strip()] = counts.get(
            (r.get("stale_quote") or "").strip(), 0) + 1
    print(f"rows: {len(rows)}   stale_quote yes={counts.get('yes', 0)} "
          f"no={counts.get('no', 0)} empty={counts.get('', 0)}")
    for r in rows:
        if (r.get("stale_quote") or "").strip() == "yes":
            print(f"  flagged: {r['date']} {r['ticker']} ref {r['price_at_call']}")
    # A disclosure column must never have touched scoring.
    # INS-013 (council directive 2026-09-02, applied 2026-09-03): this counted `void`
    # as scored. A truthiness test on `outcome` is not the definition of "scored" this
    # lab uses -- INS-007 says void rows are "excluded from every hit rate, and `void`
    # is not a third outcome to be counted alongside right/wrong", and the lab's two
    # scoring consumers (agent/strata.py:104 and :145) use the ALLOWLIST. This file
    # exists to police disclosure, so it was the worst place on the desk to hold the
    # second definition (Firm Brain S6: two readers of one book must not disagree).
    scored = [r for r in rows if (r.get("outcome") or "").strip() in ("right", "wrong")]
    voided = [r for r in rows if (r.get("outcome") or "").strip() == "void"]
    print(f"scored rows: {len(scored)} (allowlist right/wrong; {len(voided)} void rows "
          f"excluded, never a third outcome -- INS-007)")
    return 0 if ok else 1


def audit(ledger: str = LEDGER) -> int:
    """Print — never write — the computed flag for every row in the ledger.

    Read-only on purpose. The backfill committed for INS-004 marks only the two
    rows the lab had already established in its own briefs (WBHC, NWPP); every
    other cell is empty because empty is a true statement and a guess is not.
    This mode shows what the same pre-call rule computes for the rest, so
    filling them is a mechanical decision someone takes deliberately rather
    than a judgement made on 08-16 with outcomes already on the screen.
    """
    with open(ledger) as f:
        rows = list(csv.DictReader(f))
    print(f"{'date':<12}{'ticker':<8}{'logged':<8}{'computed':<10}detail")
    for r in rows:
        flag, detail = flag_for(r["ticker"], r["date"])
        logged = (r.get("stale_quote") or "").strip() or "-"
        mark = "" if logged in ("-", flag) else "   <-- DISAGREES"
        print(f"{r['date']:<12}{r['ticker']:<8}{logged:<8}"
              f"{(flag or '-'):<10}{detail}{mark}")
    return 0


def fill(ledger: str = LEDGER) -> int:
    """Write the computed flag into every row that has none. Never overwrites.

    The deliberate counterpart to --audit. Run BEFORE outcomes exist: the rule
    reads only complete bars strictly earlier than each call date, so what it
    writes cannot depend on how any call turned out. Rows it cannot establish
    (a listing with fewer than STALE_SESSIONS complete bars) stay empty —
    honest ignorance, not a clean bill.

    An already-written flag is never touched. Back-editing a disclosure after
    the fact is the defect this column exists to prevent, so the code refuses
    to do it rather than trusting the operator to remember.
    """
    with open(ledger) as f:
        rows = list(csv.DictReader(f))
        header = list(rows[0].keys()) if rows else LEDGER_HEADER
    wrote = skipped = blocked = 0
    for r in rows:
        cur = (r.get("stale_quote") or "").strip()
        if cur:
            blocked += 1
            continue
        if (r.get("outcome") or "").strip():
            print(f"  REFUSED {r['date']} {r['ticker']}: already scored — a flag written "
                  f"after an outcome is visible is not a disclosure")
            skipped += 1
            continue
        flag, detail = flag_for(r["ticker"], r["date"])
        if not flag:
            skipped += 1
            continue
        r["stale_quote"] = flag
        wrote += 1
    _atomic_csv(ledger, header, rows)
    print(f"filled {wrote}; left {skipped} unestablished; {blocked} already declared "
          f"and untouched")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", metavar="TICKER",
                    help="print the stale_quote flag for a ticker")
    ap.add_argument("--asof", metavar="YYYY-MM-DD",
                    help="treat this as the call date (default: today)")
    ap.add_argument("--sessions", type=int, default=STALE_SESSIONS)
    ap.add_argument("--verify", action="store_true",
                    help="parse ledger.csv back and print the schema")
    ap.add_argument("--fill", action="store_true",
                    help="write the computed flag into rows that have none; never "
                         "overwrites, never writes to an already-scored row")
    ap.add_argument("--audit", action="store_true",
                    help="print (never write) the computed flag for every row")
    ap.add_argument("--fill-queued", action="store_true",
                    help="INS-020/REG-PP-002: fill open [QUEUED] rows from their owed official open")
    ap.add_argument("--dry", action="store_true", help="with --fill-queued: report, write nothing")
    a = ap.parse_args()
    if a.fill_queued:
        return fill_queued(dry=a.dry)
    if a.check:
        flag, detail = flag_for(a.check, a.asof, a.sessions)
        print(detail)
        print(flag)
        return 0
    if a.verify:
        return verify()
    if a.fill:
        return fill()
    if a.audit:
        return audit()
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

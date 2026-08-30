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

import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import date

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
    "price_at_check", "outcome", "stale_quote", "tags",
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


def append_call(row: dict, ledger: str = LEDGER, sessions: int = STALE_SESSIONS):
    """Append ONE call to the ledger with stale_quote already decided.

    This is the write path. Anything logging a call goes through here so the
    disclosure cannot be forgotten: if the caller does not supply stale_quote,
    it is computed from the pre-call series. `price_at_check` and `outcome` are
    always written empty — a call is never born scored.
    """
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
    if not str(row.get("price_at_call") or "").strip():
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
    scored = [r for r in rows if (r.get("outcome") or "").strip()]
    print(f"scored rows: {len(scored)} (this lab scores nothing before 2026-08-16)")
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
    with open(ledger, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
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
    a = ap.parse_args()
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

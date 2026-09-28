#!/usr/bin/env python3
"""INS-020 restatement — ruled by Anupam 2026-09-27 (delegated), option (a) "restate now + fix the checker".

    /opt/anaconda3/bin/python agent/restate_ins020.py            # dry run: prints before -> after, writes nothing
    /opt/anaconda3/bin/python agent/restate_ins020.py --apply    # writes, under the book lock (BOOK-001)

WHAT IS RESTATED. The 35 open rows the lab measured on 2026-09-22 (agent/lessons.md, "FIRM BRAIN S9
CHECK"): rows dated 2026-09-14..2026-09-21 whose price_at_call is a LIVE INTRADAY PRINT written by the
08:3x PT morning run while the session was trading, frozen as the 30-day reference. They are listed
below with the exact price each was written with, so the script refuses any row that has moved since.

TO WHAT. Not the call-day close. The lab's own written rule (AGENT.md SS INS-014) says a call written
before the day's bar is out is written EMPTY + [QUEUED] "and fill it from the next session's official
open"; REG-PP-002 (2026-08-31) says the same thing estate-wide: a queued row fills "from the FIRST
OFFICIAL OPEN after registration". Every one of these rows was registered after its call date's
06:30 PT open (first-commit times below, from git), so the owed price is the official open of the next
session - the first bar on/after it that actually traded (volume > 0; a zero-volume bar is a carry-
forward, INS-015 / Firm Brain S18).

BENCH-002. Each row is verified unscored (outcome and price_at_check empty) before it is touched; the
original price is kept on the row. A scored row is never restated - it is reported and left.
Idempotent: a row already carrying "[RESTATED 2026-09-27 (INS-020" is skipped.
A row whose owed open cannot be priced (no series) is NOT restated and is reported for /void-row.
"""
import csv
import os
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stale_quote as Q  # noqa: E402  (write-path helpers: owed_open, fill_session_for, fmt_px, atomic csv)

LEDGER = os.path.join(HERE, "ledger.csv")
MARK = "[RESTATED 2026-09-27 (INS-020"

# First commit that carried each call date's rows (git log -S on agent/ledger.csv) - the registration
# moment is no later than this, and the prices themselves are intraday prints, so the open had passed.
REGISTERED = {
    "2026-09-14": "2026-09-14T08:37", "2026-09-15": "2026-09-15T08:42", "2026-09-16": "2026-09-16T08:33",
    "2026-09-17": "2026-09-17T08:34", "2026-09-18": "2026-09-18T08:44", "2026-09-21": "2026-09-21T08:33",
}

# (date, ticker, price_at_call as written) - the ruled set, 35 rows.
RULED = [
    ("2026-09-14", "HELP", "13.33"), ("2026-09-14", "DOMH", "2.18"), ("2026-09-14", "FGBI", "8.11"),
    ("2026-09-14", "ANIX", "2.86"),
    ("2026-09-15", "PMTS", "24.69"), ("2026-09-15", "MAIA", "1.395"), ("2026-09-15", "NNOX", "0.6942"),
    ("2026-09-15", "OFLX", "26.28"), ("2026-09-15", "UAVS", "0.955"),
    ("2026-09-16", "HELP", "13.49"), ("2026-09-16", "CELH", "28.355"), ("2026-09-16", "RWT", "3.925"),
    ("2026-09-16", "SBLK", "31.17"), ("2026-09-16", "OXM", "29.97"), ("2026-09-16", "STI", "6.62"),
    ("2026-09-16", "TENX", "1.91"),
    ("2026-09-17", "ADC", "68.1175"), ("2026-09-17", "CROX", "124.0"), ("2026-09-17", "LMB", "50.24"),
    ("2026-09-17", "BUKS", "4.15"), ("2026-09-17", "MCFT", "20.21"), ("2026-09-17", "FLNT", "3.41"),
    ("2026-09-17", "BZUN", "2.825"), ("2026-09-17", "CTSO", "5.96"), ("2026-09-17", "KDOZF", "0.0924"),
    ("2026-09-17", "GREE", "2.84"),
    ("2026-09-18", "BWMX", "17.15"), ("2026-09-18", "SKIL", "6.71"), ("2026-09-18", "EML", "24.4"),
    ("2026-09-18", "BENF", "0.7331"), ("2026-09-18", "XBP", "3.68"),
    ("2026-09-21", "BORR", "4.435"), ("2026-09-21", "TH", "21.24"), ("2026-09-21", "RVSB", "5.92"),
    ("2026-09-21", "KWY", "9.75"),
]
assert len(RULED) == 35


def main(apply: bool) -> int:
    if apply and Q._ATOM:
        Q._ATOM.hold_book(LEDGER)
    rows = list(csv.DictReader(open(LEDGER)))
    header = Q.ledger_header(LEDGER)
    idx = {(r["date"], r["ticker"]): r for r in rows}
    today = date.today().isoformat()
    done, skipped, refused = [], [], []
    for d, t, orig in RULED:
        r = idx.get((d, t))
        if r is None:
            refused.append(f"{t} {d}: row not found"); continue
        th = r.get("thesis") or ""
        if MARK in th:
            skipped.append(f"{t} {d}: already restated ({r['price_at_call']})"); continue
        if (r.get("outcome") or "").strip() or (r.get("price_at_check") or "").strip():
            refused.append(f"{t} {d}: SCORED ({r.get('outcome')}) - BENCH-002, left as written"); continue
        if (r.get("check_date") or "") <= today:
            refused.append(f"{t} {d}: check_date {r.get('check_date')} already due - not restated"); continue
        if r["price_at_call"].strip() != orig:
            refused.append(f"{t} {d}: price_at_call {r['price_at_call']} != the measured {orig} - moved since, left"); continue
        reg = datetime.fromisoformat(REGISTERED[d])
        fs = Q.fill_session_for(d, reg)
        try:
            got = Q.owed_open(Q.daily_bars(t, fs), fs)
        except Exception as e:
            got = None; why = f"no series ({type(e).__name__})"
        else:
            why = "no traded bar on/after the owed session"
        if got is None:
            refused.append(f"{t} {d}: UNPRICEABLE - {why}; kept at {orig}, needs /void-row (INS-007)"); continue
        day, px = got
        new = Q.fmt_px(px)
        skip_note = "" if day == fs.isoformat() else (f" ({fs} and any bar before {day} printed zero volume - "
                                                      f"a carry-forward, not an open; INS-015/S18)")
        r["price_at_call"] = new
        r["thesis"] = (th + f" {MARK}, ruled 2026-09-27 option a): price_at_call {orig} was a LIVE intraday "
                            f"print, registered {REGISTERED[d]} PT while the {d} session was trading - not a "
                            f"settled price. AGENT.md SS INS-014 + REG-PP-002 owe the first official open after "
                            f"registration: the {day} official open {new}{skip_note}. Original {orig} kept here. "
                            f"Unscored at restatement - BENCH-002 holds.]").strip()
        chg = (float(new) / float(orig) - 1) * 100
        done.append(f"{t:6s} {d}  {orig:>9s} -> {new:>9s}  ({chg:+.1f}%)  {day} open")
    if done and apply:
        Q._atomic_csv(LEDGER, header, rows)
    print(f"INS-020 restatement {'APPLIED' if apply else 'DRY RUN'} - {len(done)} restated, "
          f"{len(skipped)} already done, {len(refused)} refused")
    for x in done:
        print("  RESTATED " + x)
    for x in skipped:
        print("  SKIPPED  " + x)
    for x in refused:
        print("  REFUSED  " + x)
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))

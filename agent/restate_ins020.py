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

# EXTENSION, 2026-09-27 ~23:40 PT: INS-020 (a) extended to the SAME defect class on Anupam's delegation
# ("Do what's necessary, fix everything"), relayed by the main session. These are the 51 further OPEN rows
# price_audit.py's reference test listed as REF_LEGACY: written by the morning run before the call-day
# close settled (a live print, or the prior session's close), so the rule owes the same thing - the first
# traded official open after registration. Ordered by check_date: the 10 rows graded Mon 09-28 13:40 PT first.
EXTENSION = [
    ("2026-08-27", "APCX", "0.369"),
    ("2026-08-27", "BXSY", "18.1"),
    ("2026-08-27", "NGL", "17.2"),
    ("2026-08-27", "SCOR", "5.24"),
    ("2026-08-27", "YORW", "34.19"),
    ("2026-08-28", "BMRA", "2.07"),
    ("2026-08-28", "MAIR", "26.39"),
    ("2026-08-28", "SLNH", "1.15"),
    ("2026-08-28", "UNB", "23.65"),
    ("2026-08-28", "VENU", "1.99"),
    ("2026-08-31", "BATL", "1.36"),
    ("2026-08-31", "BIVI", "2.37"),
    ("2026-08-31", "BLX", "54.54"),
    ("2026-08-31", "CBU", "63.16"),
    ("2026-08-31", "TNXP", "13.59"),
    ("2026-09-01", "BRID", "6.09"),
    ("2026-09-01", "HWKN", "120.27"),
    ("2026-09-01", "UAMY", "4.74"),
    ("2026-09-01", "VRXA", "1.35"),
    ("2026-09-02", "LUCK", "6.19"),
    ("2026-09-02", "QNRX", "6.51"),
    ("2026-09-02", "WIX", "88.38"),
    ("2026-09-03", "GPUS", "0.2"),
    ("2026-09-03", "GROV", "1.1"),
    ("2026-09-03", "OPAL", "1.99"),
    ("2026-09-04", "FRST", "16.11"),
    ("2026-09-04", "OVLY", "34.51"),
    ("2026-09-08", "ENOV", "18.84"),
    ("2026-09-08", "SHMD", "3.415"),
    ("2026-09-09", "BWFG", "66.97"),
    ("2026-09-09", "INBX", "122.86"),
    ("2026-09-09", "RGCO", "21.59"),
    ("2026-09-09", "TSM", "433.08"),
    ("2026-09-10", "ATLO", "31.96"),
    ("2026-09-10", "DY", "296.59"),
    ("2026-09-10", "GME", "20.155"),
    ("2026-09-11", "CZNC", "25.86"),
    ("2026-09-11", "KMT", "29.57"),
    ("2026-09-11", "RLMD", "4.355"),
    ("2026-09-11", "UBER", "71.29"),
    ("2026-09-17", "CBKM", "32.98"),
    ("2026-09-22", "BBD", "3.525"),
    ("2026-09-22", "CULP", "3.605"),
    ("2026-09-22", "EU", "1.19"),
    ("2026-09-22", "FBDT", "0.9258"),
    ("2026-09-22", "GRAB", "3.1301"),
    ("2026-09-22", "NTHI", "3.42"),
    ("2026-09-22", "UMH", "15.91"),
    ("2026-09-23", "BCBP", "8.7100"),
    ("2026-09-23", "BFRG", "0.7319"),
    ("2026-09-23", "VFF", "3.0550")
]
assert len(EXTENSION) == 51

# Registration moment per call date. Source: first git commit carrying the rows, unless a better one exists.
# 09-03: the brief says the sweep ran 08:30 PT (commit 18:53 was the session-end sweep). 09-01: time unknown;
# the rows anchor the PRIOR (08-31) settled close, so the 09-01 close had not settled when they were written ->
# registered during/before the 09-01 session; None = "after the call date's open", i.e. the next session.
REGISTERED_EXT = {
    "2026-08-27": "2026-08-27T08:45", "2026-08-28": "2026-08-28T08:46", "2026-08-31": "2026-08-31T08:50",
    "2026-09-01": None, "2026-09-02": "2026-09-02T08:47", "2026-09-03": "2026-09-03T08:30",
    "2026-09-04": "2026-09-04T08:55", "2026-09-08": "2026-09-08T08:44", "2026-09-09": "2026-09-09T08:32",
    "2026-09-10": "2026-09-10T08:38", "2026-09-11": "2026-09-11T08:41", "2026-09-17": "2026-09-17T08:34",
    "2026-09-22": "2026-09-22T08:50", "2026-09-23": "2026-09-23T08:36",
}
REGISTERED.update({k: v for k, v in REGISTERED_EXT.items() if k not in REGISTERED})


VOID_REASON = ("VOIDED 2026-09-27 under INS-020 (a), extended to the defect class by Anupam's 2026-09-27 "
               "delegation; INS-007 spirit: kept, reason on the row, EXCLUDED from every hit rate, never a third "
               "outcome. {why} The rule owes the first official open after registration and no such price exists "
               "for this ticker, so the row can never carry a fillable reference. Unscored at void time, so no "
               "recorded number is rewritten (BENCH-002); price_at_call {orig} left as written.")


def main(apply: bool) -> int:
    if apply and Q._ATOM:
        Q._ATOM.hold_book(LEDGER)
    rows = list(csv.DictReader(open(LEDGER)))
    header = Q.ledger_header(LEDGER)
    idx = {(r["date"], r["ticker"]): r for r in rows}
    today = date.today().isoformat()
    done, skipped, refused = [], [], []
    voided = []
    for d, t, orig in RULED + EXTENSION:
        ext_row = (d, t, orig) in EXTENSION
        r = idx.get((d, t))
        if r is None:
            refused.append(f"{t} {d}: row not found"); continue
        th = r.get("thesis") or ""
        if MARK in th:
            skipped.append(f"{t} {d}: already restated ({r['price_at_call']})"); continue
        if (r.get("outcome") or "").strip() == "void" and "INS-020" in (r.get("void_reason") or ""):
            skipped.append(f"{t} {d}: already voided under INS-020"); continue
        if (r.get("outcome") or "").strip() or (r.get("price_at_check") or "").strip():
            refused.append(f"{t} {d}: SCORED ({r.get('outcome')}) - BENCH-002, left as written"); continue
        if (r.get("check_date") or "") <= today:
            refused.append(f"{t} {d}: check_date {r.get('check_date')} already due - not restated"); continue
        if r["price_at_call"].strip() != orig:
            refused.append(f"{t} {d}: price_at_call {r['price_at_call']} != the measured {orig} - moved since, left"); continue
        reg = datetime.fromisoformat(REGISTERED[d]) if REGISTERED.get(d) else None
        fs = Q.fill_session_for(d, reg)
        noseries = False
        try:
            got = Q.owed_open(Q.daily_bars(t, fs), fs)
        except Exception as e:
            got = None; why = f"no series ({type(e).__name__}: {e})"; noseries = True
        else:
            why = "no traded bar on/after the owed session"
        if got is None:
            if noseries:
                # /void-row: match the book's convention exactly - outcome lowercase `void`, reason in void_reason.
                r["outcome"] = "void"
                r["void_reason"] = VOID_REASON.format(
                    why=(f"Yahoo returns {why} for {t} (endpoint verified alive on AAPL the same run; "
                         f"GREEL is a different instrument and no SEC-mapped alias exists, INS-016)."),
                    orig=orig)
                voided.append(f"{t} {d}: VOID - {why}")
            else:
                refused.append(f"{t} {d}: {why} - kept at {orig}, left open")
            continue
        day, px = got
        new = Q.fmt_px(px)
        skip_note = "" if day == fs.isoformat() else (f" ({fs} and any bar before {day} printed zero volume - "
                                                      f"a carry-forward, not an open; INS-015/S18)")
        r["price_at_call"] = new
        if ext_row:
            reg_txt = (f"registered {REGISTERED[d]} PT" if REGISTERED.get(d)
                       else f"registered on {d} before its close settled (it anchors the prior session's close)")
            r["thesis"] = (th + f" {MARK}, option a extended to the defect class by Anupam's 2026-09-27 "
                                f"delegation): price_at_call {orig} was not a settled call-day price - {reg_txt}, "
                                f"so it is a live print or the prior session's close. AGENT.md SS INS-014 + "
                                f"REG-PP-002 owe the first official open after registration: the {day} official "
                                f"open {new}{skip_note}. Original {orig} kept here. Unscored at restatement - "
                                f"BENCH-002 holds.]").strip()
        else:
            r["thesis"] = (th + f" {MARK}, ruled 2026-09-27 option a): price_at_call {orig} was a LIVE intraday "
                                f"print, registered {REGISTERED[d]} PT while the {d} session was trading - not a "
                                f"settled price. AGENT.md SS INS-014 + REG-PP-002 owe the first official open after "
                                f"registration: the {day} official open {new}{skip_note}. Original {orig} kept here. "
                                f"Unscored at restatement - BENCH-002 holds.]").strip()
        chg = (float(new) / float(orig) - 1) * 100
        done.append(f"{'EXT ' if ext_row else ''}{t:6s} {d} chk {r.get('check_date')}  {orig:>9s} -> {new:>9s}  ({chg:+.1f}%)  {day} open")
    if (done or voided) and apply:
        Q._atomic_csv(LEDGER, header, rows)
    print(f"INS-020 restatement {'APPLIED' if apply else 'DRY RUN'} - {len(done)} restated, "
          f"{len(voided)} voided (no series), {len(skipped)} already done, {len(refused)} refused")
    for x in voided:
        print("  VOIDED   " + x)
    for x in done:
        print("  RESTATED " + x)
    for x in skipped:
        print("  SKIPPED  " + x)
    for x in refused:
        print("  REFUSED  " + x)
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))

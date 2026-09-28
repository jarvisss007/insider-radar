#!/usr/bin/env python3
"""forecast_write.py — the insider desk's ONE write path for agent/forecasts.csv (INS-019).

INS-019, ruled 2026-09-27 (option a, "check date governs"): a forecast settles on its recorded
check_date - the estate grader (~/bin/resolve_forecasts.py) gates on it and, for this lab, reads the
close ON it - so the check_date must never disagree with the question. The fix is at WRITE time:
check_date is SET to the last date the question names. Two rows (SHMD, INBX, 2026-09-16) had
check_date 09-16 on questions about 09-15 closes, and ADC (09-17) asked about 09-24 with check 09-25;
the grader then either waited a day it did not need or would answer a different date than asked.

What this path enforces, every row:
  * the question names at least one YYYY-MM-DD date; check_date := the LAST (latest) date named,
    and a caller-supplied check_date that disagrees is overwritten and disclosed in `notes`;
  * that date is an NYSE session (SESSION-001) - a question about a non-session close is unresolvable;
  * the row's own `date` is a session (MORN-006: zero forecast rows dated a non-session);
  * 0 < p < 1; outcome is written empty (a forecast is never born scored);
  * the header is the file's own (INS-011); the write is atomic under the book lock (BOOK-001).

    /opt/anaconda3/bin/python agent/forecast_write.py --check   # audit: open rows whose check_date
                                                               # disagrees with the question (exit 1)
    /opt/anaconda3/bin/python agent/forecast_write.py --selftest
"""
import csv
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stale_quote as Q  # noqa: E402  (loads stock-radar/sessions.py and atomicio.py by path)

FORECASTS = os.path.join(HERE, "forecasts.csv")
_FALLBACK = ["date", "instrument", "horizon_days", "question", "p", "check_date", "outcome", "notes"]
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def question_date(question):
    """The LAST (latest) calendar date the question names, or None. Write-time only (INS-019)."""
    ds = []
    for m in _DATE.findall(str(question or "")):
        try:
            ds.append(date.fromisoformat(m))
        except ValueError:
            pass
    return max(ds).isoformat() if ds else None


def _is_session(d):
    return Q._is_session(date.fromisoformat(d))


def header(path=FORECASTS):
    try:
        with open(path) as f:
            h = next(csv.reader(f))
        return h or list(_FALLBACK)
    except (FileNotFoundError, StopIteration):
        return list(_FALLBACK)


def prepare(row):
    """Validate and normalise one forecast row in place (no I/O). Raises ValueError on refusal."""
    q = str(row.get("question") or "").strip()
    qd = question_date(q)
    if not qd:
        raise ValueError("INS-019: the question must name the date it resolves on (YYYY-MM-DD)")
    if not _is_session(qd):
        raise ValueError(f"INS-019: the question resolves on {qd}, which is not an NYSE session - "
                         "no official close exists to settle it (SESSION-001)")
    d = str(row.get("date") or "").strip()
    if not d or not _is_session(d):
        raise ValueError(f"MORN-006: a forecast row may not be dated a non-session ({d or 'blank'})")
    try:
        p = float(row.get("p"))
    except (TypeError, ValueError):
        raise ValueError("p must be a number strictly between 0 and 1")
    if not 0 < p < 1:
        raise ValueError("p must be strictly between 0 and 1 (never 0 or 1)")
    cd = str(row.get("check_date") or "").strip()
    if cd and cd != qd:
        row["notes"] = (str(row.get("notes") or "") +
                        f" [INS-019: check_date {cd} set to the question's date {qd} at write time]").strip()
    row["check_date"] = qd
    row["outcome"] = ""
    return row


def append_forecast(row, path=FORECASTS):
    prepare(row)
    h = header(path)
    missing = [k for k in h if k not in row and k not in ("outcome", "notes")]
    if missing:
        raise ValueError(f"forecast is missing fields: {missing}")
    if Q._ATOM:
        Q._ATOM.hold_book(path)
    rows = list(csv.DictReader(open(path))) if os.path.exists(path) and os.path.getsize(path) else []
    rows.append({k: row.get(k, "") for k in h})
    Q._atomic_csv(path, h, rows)
    return row


def check(path=FORECASTS):
    """Open rows whose check_date disagrees with the question's last date. Read-only."""
    bad = []
    for r in csv.DictReader(open(path)):
        if (r.get("outcome") or "").strip():
            continue
        qd = question_date(r.get("question"))
        if qd != (r.get("check_date") or "")[:10]:
            bad.append(f"{r.get('date')} {r.get('instrument')}: check_date {r.get('check_date')} vs question {qd}")
    for b in bad:
        print("  MISMATCH " + b)
    print(f"INS-019 forecast check: {len(bad)} open row(s) whose check_date disagrees with the question")
    return 1 if bad else 0


def _selftest():
    ok = 0
    r = prepare({"date": "2026-09-28", "instrument": "XBP", "horizon_days": "5", "p": "0.3",
                 "question": "Absolute XBP 5-session move from its 2026-09-28 close exceeds 20% on 2026-10-05",
                 "check_date": "2026-10-06"})
    ok += r["check_date"] == "2026-10-05" and "INS-019" in r["notes"]
    r = prepare({"date": "2026-09-28", "instrument": "CV", "horizon_days": "5", "p": "0.3",
                 "question": "abs(CV last on 2026-10-05 / 6.17 - 1) >= 0.10"})
    ok += r["check_date"] == "2026-10-05" and not r.get("notes")
    for bad in ({"date": "2026-09-28", "p": "0.5", "question": "CV closes higher next week"},       # no date
                {"date": "2026-09-28", "p": "0.5", "question": "CV closes above 6 on 2026-10-03"},  # Saturday
                {"date": "2026-09-27", "p": "0.5", "question": "CV closes above 6 on 2026-10-05"},  # dated Sunday
                {"date": "2026-09-28", "p": "1", "question": "CV closes above 6 on 2026-10-05"}):   # p = 1
        try:
            prepare(dict(bad))
        except ValueError:
            ok += 1
    print(f"selftest: {ok}/6 passed")
    return 0 if ok == 6 else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    if "--check" in sys.argv:
        sys.exit(check())
    print(__doc__)

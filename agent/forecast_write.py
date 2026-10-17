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
  * the header is the file's own (INS-011); the write is atomic under the book lock (BOOK-001);
  * CLAUSE B (REGISTRY.md, pre-registered 2026-09-04; tripped at n=40 on 2026-10-05, applied 2026-10-17): when
    `clause_b.json` sits beside the book, `p` is NOT the caller's - it is set to the running climatological base
    rate (the YES share of the book's resolved rows, the number score_forecasts.py calls climatology, 4 dp), the
    retired discretionary p is named in `notes`, and the stamp `[CLAUSE-B ... base=B k=K n=N]` is written so
    the resolver check can verify the row. Rows already filed are never touched (BENCH-002).

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
CLAUSE_B_FLAG = "clause_b.json"   # beside the book; its presence IS the verdict (REGISTRY.md Clause B, tripped n=40)
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


def _read_rows(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) and os.path.getsize(path) else []


def clause_b_flag(path=FORECASTS):
    """The Clause B verdict record beside the book, or None if the verdict has not been applied to this book.
    A flag file that is unreadable or incomplete raises: silently falling back to a discretionary p is the
    exact failure this clause exists to end."""
    import json
    fp = os.path.join(os.path.dirname(os.path.abspath(path)), CLAUSE_B_FLAG)
    if not os.path.exists(fp):
        return None
    try:
        flag = json.load(open(fp))
        for k in ("tripped_at_n", "tripped_on", "skill_at_trip"):
            flag[k]
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"CLAUSE-B: {fp} is unreadable or incomplete ({e!r}) - refusing to file a discretionary p")
    return flag


def running_base_rate(rows):
    """(k_yes, n_resolved) over the book's resolved rows - the climatology score_forecasts.py scores against.
    Same filters as its _read(): a non-empty `void` is out; outcome must be 1/0/yes/no/true/false; p a number in [0,1]."""
    k = n = 0
    for r in rows:
        if (r.get("void") or "").strip():
            continue
        out = (r.get("outcome") or "").strip().lower()
        if out not in ("1", "0", "yes", "no", "true", "false"):
            continue
        try:
            if not 0.0 <= float(r["p"]) <= 1.0:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        n += 1
        k += out in ("1", "yes", "true")
    return k, n


def apply_clause_b(row, rows, flag):
    """Clause B: p := the running climatological base rate (4 dp); the caller's p is retired and named in notes."""
    k, n = running_base_rate(rows)
    if n == 0 or k in (0, n):
        raise ValueError(f"CLAUSE-B: running base rate is {k}/{n} - not strictly inside (0,1); refusing to invent a p")
    base = round(k / n, 4)
    proposed = str(row.get("p") if row.get("p") not in (None, "") else "none supplied")
    row["p"] = base
    row["notes"] = (str(row.get("notes") or "") +
                    f" [CLAUSE-B: REGISTRY Clause B tripped at n={flag['tripped_at_n']} on {flag['tripped_on']} "
                    f"(skill {float(flag['skill_at_trip']):+.4f}); the discretionary p ({proposed}) is retired - filed at "
                    f"the running climatological base rate base={base:.4f} k={k} n={n} (YES share of resolved rows)]").strip()
    return row


def append_forecast(row, path=FORECASTS):
    flag = clause_b_flag(path)
    if flag:
        if Q._ATOM:
            Q._ATOM.hold_book(path)   # hold before reading, so the base rate and the append see the same book
        apply_clause_b(row, _read_rows(path), flag)
    prepare(row)
    h = header(path)
    missing = [k for k in h if k not in row and k not in ("outcome", "notes")]
    if missing:
        raise ValueError(f"forecast is missing fields: {missing}")
    if Q._ATOM:
        Q._ATOM.hold_book(path)
    rows = _read_rows(path)
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

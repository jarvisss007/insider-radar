#!/usr/bin/env python3
"""
Historical backfill of insider PURCHASE events for the event study.

Walks EDGAR's daily form indexes over a past window, deterministically samples K Form 4
filings per day (md5-ordered — reproducible, no cherry-picking), parses each, and appends
open-market purchases (code P) to docs/data/events.json.

Sampling is disclosed honestly: we don't need every filing for an event study, we need an
unbiased sample. Fetching everything (~2-3k Form 4s/day) would hammer SEC for no
statistical gain.

    python backfill_edgar.py --start 2026-03-02 --end 2026-07-02 --per-day 60
"""
import argparse, datetime, hashlib, json, re, time
from pathlib import Path

import requests

from collector_edgar import UA, PAUSE, form4_xml_url, parse_form4, get

HERE = Path(__file__).resolve().parent
EVENTS = HERE / "docs" / "data" / "events.json"


def qtr(d): return (d.month - 1) // 3 + 1


def day_index(d):
    url = (f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{qtr(d)}/"
           f"form.{d:%Y%m%d}.idx")
    try:
        txt = get(url).text
    except requests.HTTPError:
        return []          # weekend/holiday
    out = []
    for line in txt.splitlines():
        if not line.startswith("4 "):          # exactly Form 4 (not 4/A, 424B..)
            continue
        m = re.search(r"edgar/data/(\d+)/(\d{10}-\d{2}-\d{6})\.txt", line)
        if m:
            out.append((int(m.group(1)), m.group(2)))
    return out


def load_events():
    if EVENTS.exists():
        try:
            return json.loads(EVENTS.read_text())
        except json.JSONDecodeError:
            pass
    return {"events": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--per-day", type=int, default=60)
    a = ap.parse_args()
    d0 = datetime.date.fromisoformat(a.start)
    d1 = datetime.date.fromisoformat(a.end)

    doc = load_events()
    have = {e["acc"] for e in doc["events"]}
    n_new = n_seen = 0
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            filings = day_index(d)
            filings.sort(key=lambda x: hashlib.md5(x[1].encode()).hexdigest())
            sample = filings[:a.per_day]
            day_hits = 0
            for cik, acc in sample:
                n_seen += 1
                if acc in have:
                    continue
                have.add(acc)
                try:
                    url = form4_xml_url(cik, acc)
                    if not url:
                        continue
                    f = parse_form4(get(url).text)
                except Exception:
                    continue
                if not f or not f["ticker"]:
                    continue
                for tx in f["tx"]:
                    if tx["code"] != "P":
                        continue
                    doc["events"].append({
                        "ticker": f["ticker"], "company": f["company"],
                        "insider": f["insider"], "role": f["role"],
                        "date": tx["date"], "shares": tx["shares"],
                        "price": tx["price"], "value": tx["value"],
                        "acc": acc, "filed": d.isoformat(), "src": "backfill"})
                    n_new += 1
                    day_hits += 1
            print(f"{d} · sampled {len(sample):3d}/{len(filings):4d} form4s · "
                  f"+{day_hits} purchases (total {n_new})", flush=True)
            EVENTS.write_text(json.dumps(doc, indent=1))   # checkpoint per day
        d += datetime.timedelta(days=1)
    print(f"done: scanned {n_seen} filings, added {n_new} purchase events "
          f"→ {len(doc['events'])} total in {EVENTS}", flush=True)


if __name__ == "__main__":
    main()

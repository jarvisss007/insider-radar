#!/usr/bin/env python3
"""
Insider Radar collector — polls SEC EDGAR for fresh Form 4 filings, extracts open-market
insider PURCHASES (transaction code P), and writes docs/data/insiders.json for the hosted
viewer. Optionally commits+pushes when the data changes.

Why server-side: EDGAR's document archive doesn't send CORS headers, so a browser-only app
can't read transaction details. This collector does the reading; the web page just renders.

Fair-access: identifies itself via User-Agent and stays far below SEC's 10 req/s limit.

Usage:
    python collector_edgar.py                  # one pass, write JSON, no push
    python collector_edgar.py --push           # one pass + git commit/push if changed
    python collector_edgar.py --loop 15 --push # poll every 15 min, push on change
    python collector_edgar.py --loop 15 --push --max-hours 72
"""
import argparse, datetime, json, re, subprocess, sys, time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs" / "data" / "insiders.json"
UA = {"User-Agent": "Anupam Patil research anupam.p.patil@gmail.com"}
ATOM = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
        "&type=4&company=&dateb=&owner=include&count=100&output=atom")
KEEP = 400            # purchases retained in the feed
CLUSTER_DAYS = 14     # window for "multiple insiders buying" clusters
PAUSE = 0.25          # seconds between EDGAR requests (≈4 req/s worst case)


def get(url, **kw):
    time.sleep(PAUSE)
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r


def latest_form4_accessions():
    """The 'current events' atom feed → [(cik, accession), ...] newest first."""
    xml = get(ATOM).text
    seen, out = set(), []
    for entry in xml.split("<entry>")[1:]:
        m = re.search(r"edgar/data/(\d+)/(\d{18})", entry)
        if not m:
            continue
        cik, raw = int(m.group(1)), m.group(2)
        acc = f"{raw[:10]}-{raw[10:12]}-{raw[12:]}"
        if acc not in seen:
            seen.add(acc)
            out.append((cik, acc))
    return out


def form4_xml_url(cik, acc):
    """Find the ownership XML inside the filing directory."""
    idx = get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/index.json").json()
    for item in idx["directory"]["item"]:
        n = item["name"]
        if n.endswith(".xml") and not n.startswith("xsl"):
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{n}"
    return None


def t(el, path):
    x = el.find(path)
    return x.text.strip() if x is not None and x.text else ""


def parse_form4(xml_text):
    """Extract issuer, owner, and open-market purchase/sale transactions."""
    root = ET.fromstring(xml_text)
    issuer = root.find("issuer")
    owner = root.find("reportingOwner")
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    role = ""
    if rel is not None:
        if t(rel, "officerTitle"):
            role = t(rel, "officerTitle")
        elif t(rel, "isDirector") in ("1", "true"):
            role = "Director"
        elif t(rel, "isTenPercentOwner") in ("1", "true"):
            role = "10% owner"
    rows = []
    for tx in root.iter("nonDerivativeTransaction"):
        code = t(tx, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        try:
            shares = float(t(tx, "transactionAmounts/transactionShares/value") or 0)
            price = float(t(tx, "transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        if shares <= 0 or price <= 0:
            continue
        rows.append({
            "code": code,
            "date": t(tx, "transactionDate/value"),
            "shares": shares,
            "price": price,
            "value": round(shares * price, 2),
        })
    if not rows:
        return None
    return {
        "ticker": t(issuer, "issuerTradingSymbol").upper(),
        "company": t(issuer, "issuerName"),
        "insider": t(owner, "reportingOwnerId/rptOwnerName"),
        "role": role,
        "tx": rows,
    }


def load_existing():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text())
        except json.JSONDecodeError:
            pass
    return {"purchases": [], "seen": []}


def clusters(purchases):
    """Tickers where ≥2 distinct insiders bought within CLUSTER_DAYS."""
    cut = (datetime.date.today() - datetime.timedelta(days=CLUSTER_DAYS)).isoformat()
    by = {}
    for p in purchases:
        if p["date"] >= cut:
            by.setdefault(p["ticker"], set()).add(p["insider"])
    out = []
    for tick, insiders in by.items():
        if len(insiders) >= 2:
            tot = sum(p["value"] for p in purchases
                      if p["ticker"] == tick and p["date"] >= cut)
            out.append({"ticker": tick, "insiders": len(insiders),
                        "total_value": round(tot, 2)})
    return sorted(out, key=lambda x: -x["total_value"])


def one_pass():
    state = load_existing()
    seen = set(state.get("seen", []))
    purchases = state.get("purchases", [])
    new_p = new_s = 0
    for cik, acc in latest_form4_accessions():
        if acc in seen:
            continue
        seen.add(acc)
        try:
            url = form4_xml_url(cik, acc)
            if not url:
                continue
            f = parse_form4(get(url).text)
        except Exception as e:
            print(f"  skip {acc}: {e}", flush=True)
            continue
        if not f or not f["ticker"]:
            continue
        for tx in f["tx"]:
            row = {"ticker": f["ticker"], "company": f["company"],
                   "insider": f["insider"], "role": f["role"],
                   "date": tx["date"], "shares": tx["shares"],
                   "price": tx["price"], "value": tx["value"],
                   "acc": acc, "filed": datetime.date.today().isoformat()}
            if tx["code"] == "P":
                purchases.append(row)
                new_p += 1
            else:
                new_s += 1
    purchases = sorted(purchases, key=lambda x: (x["date"], x["value"]))[-KEEP:]
    doc = {
        "updated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "purchases": purchases,
        "clusters": clusters(purchases),
        "seen": sorted(seen)[-3000:],
        "note": "Open-market purchases (Form 4 code P) only. Educational; not advice.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1))
    print(f"[{datetime.datetime.now():%H:%M:%S}] pass done: +{new_p} purchases "
          f"(+{new_s} sales ignored) · feed {len(purchases)} · clusters {len(doc['clusters'])}",
          flush=True)
    return new_p > 0


def push():
    r = subprocess.run(["git", "-C", str(HERE), "status", "--porcelain", "docs/data"],
                       capture_output=True, text=True)
    if not r.stdout.strip():
        return
    subprocess.run(["git", "-C", str(HERE), "add", "docs/data"], check=True)
    subprocess.run(["git", "-C", str(HERE), "commit", "-q", "-m",
                    "data: insider feed update"], check=True)
    subprocess.run(["git", "-C", str(HERE), "push", "-q"], check=True)
    print("  pushed feed update", flush=True)


def run_study():
    """Refresh the before/after event study (prices via yfinance)."""
    r = subprocess.run([sys.executable, str(HERE / "event_study.py")],
                       capture_output=True, text=True, timeout=900)
    print("  study: " + (r.stdout.strip().splitlines() or ["?"])[-1], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=float, default=0, help="poll every N minutes")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--max-hours", type=float, default=0)
    a = ap.parse_args()
    start = time.time()
    last_study = 0.0
    while True:
        try:
            changed = one_pass()
            if time.time() - last_study > 6 * 3600:      # refresh before/after study ~4x/day
                try:
                    run_study()
                except Exception as e:
                    print(f"  study failed: {e}", flush=True)
                last_study = time.time()
                changed = True
            if a.push and changed:
                push()
        except Exception as e:
            print(f"pass failed: {e}", flush=True)
        if a.loop <= 0:
            break
        if a.max_hours and (time.time() - start) > a.max_hours * 3600:
            print("max-hours reached; stopping.", flush=True)
            break
        time.sleep(a.loop * 60)


if __name__ == "__main__":
    main()

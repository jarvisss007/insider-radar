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
# Placeholder strings filers put in issuerTradingSymbol for unlisted issuers.
# Compared AFTER norm_symbol() strips brackets/parens, so "[NONE]", "(none)", "N.A." etc. all match.
BAD_TICKERS = {"", "NONE", "N/A", "NA", "N.A.", "NULL", "NOT APPLICABLE", "NOT LISTED", "UNLISTED"}
PAUSE = 0.25          # seconds between EDGAR requests (≈4 req/s worst case)
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
TICKER_MAP_CACHE = HERE / "company_tickers_cache.json"
TICKER_MAP_MAX_AGE = 7 * 86400   # refresh weekly
# Form 4 transaction code P covers BOTH open-market buying and negotiated purchases
# (IPO allocations, private placements, buys directly from the issuer) — SEC's own
# definition. The code alone cannot tell them apart; the filer's transaction footnotes
# can. Conservative phrase list: flag a purchase as a placement/offering buy only when
# the footnote attached to THAT transaction plainly says the shares came from an
# offering or the issuer. Generic text ("open market transactions") must never match.
PLACEMENT_RE = re.compile(
    r"initial public offering|\bipo\b|public offering price|underwritten offering"
    r"|from (the )?underwriters?|private placement|securities purchase agreement"
    r"|subscription agreement|direct(ly)? from the (issuer|company)", re.I)


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


def norm_symbol(s):
    """'[NONE]' → 'NONE', ' aapl ' → 'AAPL'. Only strips wrapping brackets/parens,
    never characters inside a real symbol (BRK.B etc. survive)."""
    return (s or "").strip().strip("[]()").strip().upper()


def local_text(root, name):
    """Namespace/casing-agnostic: text of the first element whose local tag name matches."""
    want = name.lower()
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1].lower() == want and el.text and el.text.strip():
            return el.text.strip()
    return ""


_CIK_TICKERS = None


def cik_to_ticker(cik):
    """Official SEC CIK→ticker map (company_tickers.json), cached locally for a week."""
    global _CIK_TICKERS
    if _CIK_TICKERS is None:
        try:
            if (not TICKER_MAP_CACHE.exists()
                    or time.time() - TICKER_MAP_CACHE.stat().st_mtime > TICKER_MAP_MAX_AGE):
                TICKER_MAP_CACHE.write_text(get(TICKER_MAP_URL).text)
            raw = json.loads(TICKER_MAP_CACHE.read_text())
            _CIK_TICKERS = {int(v["cik_str"]): v["ticker"].upper() for v in raw.values()}
        except Exception as e:
            print(f"  ticker-map unavailable ({e}); using name+CIK fallback", flush=True)
            _CIK_TICKERS = {}
    return _CIK_TICKERS.get(int(cik)) if cik else None


def resolve_ticker(symbol_raw, cik, company):
    """Never returns a shared placeholder. Order: filing symbol → SEC CIK→ticker map →
    issuer name + CIK bucket (unique per issuer, never guessed)."""
    sym = norm_symbol(symbol_raw)
    if sym and sym not in BAD_TICKERS:
        return sym
    mapped = cik_to_ticker(cik)
    if mapped:
        return mapped
    name = (company or "UNKNOWN ISSUER").strip().upper()
    return f"{name} (CIK {int(cik)})" if cik else f"{name} (CIK unknown)"


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
    footnotes = {fn.get("id"): " ".join(fn.itertext()).strip()
                 for fn in root.iter("footnote")}
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
        # footnotes referenced by THIS transaction's trade facts only (security, date,
        # coding, amounts) — never the whole document, and never the holdings columns
        # (postTransactionAmounts / ownershipNature): those describe the owner's stake,
        # not the trade, and routinely mention the IPO for unrelated reasons. Verified
        # against SCTX 07-27/28 filings, which mix IPO-allocation and open-market lines.
        notes = " ".join(
            footnotes.get(f.get("id"), "")
            for part in ("securityTitle", "transactionDate", "transactionCoding",
                         "transactionTimeliness", "transactionAmounts")
            for el in tx.iter(part)
            for f in el.iter("footnoteId"))
        row = {
            "code": code,
            # some filers append a timezone ("2026-07-29-05:00"); keep the date part only
            "date": t(tx, "transactionDate/value")[:10],
            "shares": shares,
            "price": price,
            "value": round(shares * price, 2),
        }
        if code == "P" and PLACEMENT_RE.search(notes):
            row["placement"] = True
        rows.append(row)
    if not rows:
        return None
    # symbol: normal location first, then namespace/casing-agnostic scan of the whole doc
    symbol = t(issuer, "issuerTradingSymbol") if issuer is not None else ""
    if not symbol:
        symbol = local_text(root, "issuerTradingSymbol")
    cik_txt = (t(issuer, "issuerCik") if issuer is not None else "") or local_text(root, "issuerCik")
    try:
        cik = int(cik_txt)
    except ValueError:
        cik = None
    company = (t(issuer, "issuerName") if issuer is not None else "") or local_text(root, "issuerName")
    return {
        "ticker": resolve_ticker(symbol, cik, company),
        "cik": cik,
        "company": company,
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


def tx_key(p):
    """Identity of one reported transaction: (accession, insider, date, shares, price).
    Rows sharing this key are collector artifacts (the same filing re-emitted across
    passes), never two verifiable trades. Distinct lots inside one filing differ on at
    least one of date/shares/price and always survive."""
    return (p.get("acc"), p["insider"], p["date"], p["shares"], p["price"])


def clusters(purchases):
    """Tickers where ≥2 distinct insiders bought within CLUSTER_DAYS.

    Dollar figures are summed over DEDUPLICATED (accession, insider, transaction) keys —
    raw rows historically contained repeats (see agent/lessons.md 2026-08-05: SCTX 6.15x,
    XAIR 123x inflated) and must never be summed as-is. `total_value` is open-market
    buying only; purchases flagged as placement/offering buys are broken out into
    `other_value` (reported, never headline — the lab's thesis is open-market conviction).
    Insider COUNTS were always set-based and are unchanged."""
    cut = (datetime.date.today() - datetime.timedelta(days=CLUSTER_DAYS)).isoformat()
    by = {}
    for p in purchases:
        if p["date"] >= cut:
            by.setdefault(p["ticker"], set()).add(p["insider"])
    out = []
    for tick, insiders in by.items():
        if len(insiders) >= 2:
            uniq = {tx_key(p): p for p in purchases
                    if p["ticker"] == tick and p["date"] >= cut}
            open_v = sum(p["value"] for p in uniq.values() if not p.get("placement"))
            other_v = sum(p["value"] for p in uniq.values() if p.get("placement"))
            row = {"ticker": tick, "insiders": len(insiders),
                   "total_value": round(open_v, 2)}
            if other_v:
                row["other_value"] = round(other_v, 2)
            out.append(row)
    return sorted(out, key=lambda x: -x["total_value"])


def one_pass():
    state = load_existing()
    seen = set(state.get("seen", []))
    # collapse exact-duplicate rows left behind by past collector runs (same filing
    # re-emitted). Aggregation in clusters() dedupes independently, so totals are safe
    # either way; this keeps the displayed feed honest too.
    purchases, have_rows = [], set()
    for p in state.get("purchases", []):
        k = tx_key(p)
        if k not in have_rows:
            have_rows.add(k)
            purchases.append(p)
    # guard against re-processing an accession evicted from the trimmed `seen` list:
    # a filing already represented in the feed must never be appended twice
    have_acc = {p.get("acc") for p in purchases}
    new_p = new_s = 0
    for cik, acc in latest_form4_accessions():
        if acc in seen or acc in have_acc:
            seen.add(acc)
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
        if not f:
            continue
        for tx in f["tx"]:
            row = {"ticker": f["ticker"], "company": f["company"],
                   "insider": f["insider"], "role": f["role"],
                   "date": tx["date"], "shares": tx["shares"],
                   "price": tx["price"], "value": tx["value"],
                   "acc": acc, "filed": datetime.date.today().isoformat()}
            if tx.get("placement"):
                row["placement"] = True
            if tx["code"] == "P":
                if tx_key(row) in have_rows:      # never store the same transaction twice
                    continue
                have_rows.add(tx_key(row))
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

#!/opt/anaconda3/bin/python
"""random_twin.py - RANDOM-TWIN/v1: the insider desk judged against matched random twins (MEASUREMENT ONLY).

Spec: research/random_twin/PREREG_RANDOM_TWIN_v1.md (the page) and RULE below (the authority; if they disagree the code is
right and the page has a bug). Paper only. Nothing here buys, sizes, exits or refuses anything, writes no book, and does not
touch the IWM benchmark the insider desk is judged against (desk_review.BENCHMARK['insider'], DESK-001, INS-033); no desk
reader consumes its output (pinned by a test). It READS:
  ~/insider-radar/agent/ledger.csv            the desk's rows (the book; never written)
  ~/insider-radar/agent/strata.py             cluster_usd() for the INS-002 strata (shown, never judged)
  ~/insider-radar/docs/data/insiders.json     every daily git vintage -> the insider-purchase dates to keep twins away from
  ~/insider-radar/docs/data/events.json       the backfill sample (Jul 2025 - Jul 2026) -> more purchase dates
  research/random_twin/pool_universe_2026-10-17.csv   the frozen Twin B pool (a slim copy of spy-trading's scanner snapshot)
  ~/stock-radar/data/portfolio.js             which rows THE ACCOUNT held vs withheld (PORT-006), shown only
  Yahoo v8 daily chart                        the desk's own price source (grader, price_audit, stale_quote); settled bars only
and WRITES only research/random_twin/random_twin.json, random_twin_look.json, bars_read_<asof>.json.gz, and cache/ (gitignored).

Per desk row (long, outcome right|wrong, both prices on the ledger):
  desk return   (price_at_check - price_at_call) / price_at_call, from the ledger as it stands (BENCH-002)
  entry         OPEN of the session a note names ("[FILLED D official open" / "the D official open"), else the CLOSE of the call day
  exit          CLOSE of the first traded bar on or after check_date (the INS-012 roll); span S = check_date - entry bar, calendar days
  Twin A        SHOWN ONLY, NEVER JUDGED (C14 BLOCK, option a): same ticker, entered only AFTER the row's own blocked window (post-exit,
                up to 183 days later), same entry type and span, d_A = (desk - IWM) - mean(twin - IWM) at beta 1. The beta lean
                (1 - beta) x (IWM over the twin windows - IWM over the desk window) can read BEATS or TRAILS with zero skill.
  Twin B        same entry bar and exit target, K_B random names from a seeded 30-name panel of the desk ticker's
                (market-cap bucket x sector) cell in the frozen pool (bucket-only cell if the cell has < 10 names), same entry type;
                d_B = desk - mean twin (same dates, so no market adjustment is needed)
Judged cells (Twin B only): RETRO-B and FWD-B, K = 2. Pooled mean of d_B, CR1 t clustered by ISO week of the entry bar; bar t >=
max(2.67, two-sided Student-t at alpha_K = 1 - 0.95^(1/2), df = G-1); >= 10 weeks and >= 30 rows; same sign in both halves, in the
week-mean-of-means, and after dropping the best week; the replica reading must agree or the cell is DATA-SENSITIVE.

Run:  random_twin.py rule                 print RULE and RULE_SHA
      random_twin.py dry --limit 5        mechanics on <= 5 RETRO rows (Twin B only), writes nothing in the repo
      random_twin.py run                  THE registered one-shot: RETRO-B judged; Twin A shown (NOT JUDGED) where windows exist
      random_twin.py look                 counts only before RULE['look']; on/after it, the one-shot FWD-B (Twin A shown again)
"""
from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import gzip
import hashlib
import importlib.util as iu
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

HOME = Path.home()
IR_REPO = HOME / "insider-radar"                       # the lab whose book is read (data paths never follow this file's location)
CC_REPO = HOME / "command-center"
HERE = Path(__file__).resolve().parent                 # outputs sit beside this file
LEDGER = IR_REPO / "agent" / "ledger.csv"
STRATA = IR_REPO / "agent" / "strata.py"
FEED_PATH = "docs/data/insiders.json"
EVENTS = IR_REPO / "docs" / "data" / "events.json"
POOL_SOURCE = HOME / "spy-trading" / "data" / "saved_screens" / "universe.csv"
POOL = HERE / "pool_universe_2026-10-17.csv"
PORTFOLIO_JS = HOME / "stock-radar" / "data" / "portfolio.js"
EVO_REL = "council/evolution_ledger.json"
EVO = CC_REPO / EVO_REL
ISSUES = CC_REPO / "council" / "issues.json"
SESSIONS = HOME / "stock-radar" / "sessions.py"
OUT = HERE / "random_twin.json"
OUT_LOOK = HERE / "random_twin_look.json"
OUT_REL = "research/random_twin/random_twin.json"
CACHE = HERE / "cache" / "yahoo_bars.json"
PREREG_REL = "research/random_twin/PREREG_RANDOM_TWIN_v1.md"
SCRIPT_REL = "research/random_twin/random_twin.py"
TEST_REL = "tests/test_random_twin.py"
POOL_REL = "research/random_twin/pool_universe_2026-10-17.csv"
FROZEN = (PREREG_REL, SCRIPT_REL, TEST_REL, POOL_REL)
POOL_COLS = ["name", "exchange", "type", "typespecs", "is_primary", "market_cap_basic", "sector"]
NY = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0"}
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?period1={p1}&period2={p2}&interval=1d"

# ---------------------------------------------------------------------------------------------- THE RULE (frozen at registration)
RULE = {
    "id": "RANDOM-TWIN/v1",
    "registered": "2026-10-30",
    "seed": 20261030,
    "k_a": 20, "k_b": 20, "min_twins": 5,
    "twin_a": "SHOWN ONLY, never judged (C14 BLOCK option a): post-exit only, (end of the row's blocked window, +183 days]; IWM-adjusted "
              "at beta 1, so it carries the lean (1 - beta) x (IWM over the twin windows - IWM over the desk window)",
    "window_a_days": 183,
    "buffer_days": 14,
    "exit_roll_max_days": 10,
    "market": "IWM",
    "panel_size": 30, "min_cell": 10,
    "buckets": [["micro", 0, 3e8], ["small", 3e8, 2e9], ["mid", 2e9, 1e10], ["large", 1e10, None]],
    "pool_filter": {"type": "stock", "typespecs": "common", "is_primary": "True"},
    "pool_sha256": "81b6152d89baa4d2ca5583fcdb50e8bdc175957fd747211aa9ff88221956648f",
    "pool_source_sha256": "76fe81b7cd2acec680608eef1cf73ad7ad93442cc69bf7131eef548653033bcf",
    "retro_last_call": "2026-10-30",
    "forward_first_call": "2026-10-31", "forward_last_call": "2027-05-28", "look": "2027-09-30",
    "K": 2, "cells": ["RETRO-B", "FWD-B"], "t_floor": 2.67, "family_alpha": 0.05,
    "min_weeks": 10, "min_rows": 30,
    "replica_tol_pp": 1.0, "entry_range_eps": 0.001,
    "strata_floor_usd": 100000,
    "yahoo_from": "2025-12-01",
    "max_fetch_fail_share": 0.05,
}
RULE_SHA = hashlib.sha256(json.dumps(RULE, sort_keys=True).encode()).hexdigest()

_FILL = re.compile(r"(?:\[FILLED |the )(\d{4}-\d{2}-\d{2}) official open")
JUDGED = ("BEATS-TWIN", "TRAILS-TWIN")


# ---------------------------------------------------------------------------------------------- small helpers
def D(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


def plus(s: str, days: int) -> str:
    return (D(s) + dt.timedelta(days=days)).isoformat()


def iso_week(s: str) -> int:
    y, w, _ = D(s).isocalendar()
    return y * 100 + w


def fnum(x):
    try:
        v = float(str(x).strip())
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def rng_for(*parts) -> random.Random:
    h = hashlib.sha256("|".join([str(RULE["seed"])] + [str(p) for p in parts]).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha256_obj(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()


def ysym(t: str) -> str:
    """Ledger / TradingView ticker -> Yahoo symbol (class shares use '-')."""
    return t.strip().upper().replace(".", "-").replace("/", "-")


def r4(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 4)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ---------------------------------------------------------------------------------------------- the book
def load_ledger(path: Path | None = None) -> list[dict]:
    with open(path or LEDGER, newline="") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows):
        r["_i"] = i
    return rows


def entry_of(row: dict) -> tuple[str, str]:
    """(entry type, entry bar date): OPEN of the LAST session a note names as the official-open fill, else CLOSE of the call day."""
    m = list(_FILL.finditer(row.get("thesis") or ""))
    if m:
        return "open", m[-1].group(1)
    return "close", (row.get("date") or "")[:10]


def segment(row: dict) -> str:
    return "RETRO" if (row.get("date") or "")[:10] <= RULE["retro_last_call"] else "FORWARD"


def row_key(r: dict) -> str:
    return f"{ysym(r['ticker'])}|{r['date'][:10]}|{r['check_date'][:10]}"


def population(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Scored long rows -> (rows, excluded-with-reason). Allowlist: outcome exactly right|wrong. A scored-wrong row with no
    price_at_check is kept with ret -100 and delisted=True: out of every judged cell, in the -100% line only."""
    keep, excl = [], []
    for r in rows:
        oc = (r.get("outcome") or "").strip()
        base = {"i": r["_i"], "date": r.get("date"), "ticker": r.get("ticker"), "outcome": oc}
        if (r.get("call") or "").strip() != "long" or oc not in ("right", "wrong"):
            continue                                          # open, void (lowercase) or anything else: not a scored row
        p0, p1 = fnum(r.get("price_at_call")), fnum(r.get("price_at_check"))
        if not p0 or p0 <= 0:
            excl.append({**base, "why": "no price_at_call on the ledger"})
            continue
        delisted = p1 is None or p1 <= 0
        if delisted and oc != "wrong":
            excl.append({**base, "why": "scored right with no price_at_check: cannot be read"})
            continue
        if delisted:
            excl.append({**base, "why": "scored wrong with no price_at_check (delisted/unfetchable): out of the judged cells, "
                                        "counted at -100% in the sensitivity line only"})
        et, eb = entry_of(r)
        keep.append({"i": r["_i"], "ticker": r["ticker"].strip(), "date": r["date"][:10], "check_date": r["check_date"][:10],
                     "outcome": oc, "p_call": p0, "p_check": p1, "ret": -100.0 if delisted else (p1 / p0 - 1) * 100.0,
                     "delisted": delisted, "entry_type": et, "entry_bar": eb, "week": iso_week(eb), "segment": segment(r),
                     "thesis": r.get("thesis") or ""})
    return keep, excl


def blocked_end(r: dict) -> str:
    """The end of a ledger row's own blocked window: max(check_date, entry bar) + the 10-day exit roll."""
    d0, c = (r.get("date") or "")[:10], (r.get("check_date") or "")[:10]
    return plus(max(c or d0, entry_of(r)[1] or d0), RULE["exit_roll_max_days"])


def desk_windows(rows: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """Every ledger row (any outcome, open and void included) blocks [call - 14 days, blocked_end] in its ticker."""
    out: dict[str, list] = {}
    for r in rows:
        t, d0 = (r.get("ticker") or "").strip(), (r.get("date") or "")[:10]
        if not t or not d0:
            continue
        out.setdefault(ysym(t), []).append((plus(d0, -RULE["buffer_days"]), blocked_end(r)))
    return out


# ---------------------------------------------------------------------------------------------- insider purchase dates (the feed union)
def feed_union(repo: Path | None = None, events: Path | None = None, upto: str | None = None) -> tuple[dict, dict]:
    """{yahoo symbol: sorted purchase dates (transaction and filed)} from the last committed feed vintage of every calendar day
    (the feed is a rolling ~11-day window, so one vintage a day sees every purchase it ever held) plus the backfill sample."""
    repo, events = Path(repo or IR_REPO), Path(events or EVENTS)
    dates: dict[str, set] = {}
    meta = {"vintages": 0, "first_vintage": None, "last_vintage": None, "backfill_events": 0, "failed_vintages": 0}

    def add(t, *ds):
        if not t:
            return
        for d in ds:
            if d and re.match(r"\d{4}-\d{2}-\d{2}", str(d)):
                dates.setdefault(ysym(str(t)), set()).add(str(d)[:10])

    lg = subprocess.run(["git", "-C", str(repo), "log", "--format=%H %cd", "--date=format-local:%Y-%m-%d", "--", FEED_PATH],
                        capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "America/Los_Angeles"})
    if lg.returncode != 0:
        raise SystemExit(f"random_twin: refusing - cannot read the feed's git history ({lg.stderr.strip()[:200]})")
    log = lg.stdout
    last_of_day = {}
    for line in log.splitlines():                              # newest first: the first commit seen for a day is its last
        h, d = line.split()
        if upto and d > upto:
            continue
        last_of_day.setdefault(d, h)
    used = []
    for d in sorted(last_of_day):
        sh = subprocess.run(["git", "-C", str(repo), "show", f"{last_of_day[d]}:{FEED_PATH}"],
                            capture_output=True, text=True, timeout=60)
        raw = sh.stdout if sh.returncode == 0 else ""
        try:
            feed = json.loads(raw)
        except ValueError:
            meta["failed_vintages"] += 1
            continue
        used.append([d, last_of_day[d]])
        meta["vintages"] += 1
        meta["first_vintage"] = meta["first_vintage"] or d
        meta["last_vintage"] = d
        for p in feed.get("purchases", []):
            add(p.get("ticker"), p.get("date"), p.get("filed"))
    try:
        ev = json.loads(events.read_text()).get("events", [])
        meta["events_sha256"] = sha256_file(events)
    except (OSError, ValueError):
        ev = []
        meta["events_sha256"] = None
    for p in ev:
        add(p.get("ticker"), p.get("date"), p.get("filed"))
    meta["backfill_events"] = len(ev)
    meta["vintage_list_sha256"] = sha256_obj(used)
    out = {t: sorted(v) for t, v in dates.items()}
    meta["tickers"] = len(out)
    meta["dates"] = sum(len(v) for v in out.values())
    return out, meta


def has_purchase(pdates: list[str] | None, a: str, b: str) -> bool:
    return bool(pdates) and any(a <= d <= b for d in pdates)


def overlaps(a0: str, a1: str, wins) -> bool:
    return any(not (a1 < w0 or a0 > w1) for w0, w1 in (wins or ()))


# ---------------------------------------------------------------------------------------------- prices (the desk's own source)
def traded(bars: dict | None) -> list[tuple[str, float, float]]:
    """Sorted (date, open, close) of bars that TRADED: volume > 0 and both open and close printed. A zero-volume bar is a
    carry-forward (Firm Brain s18) and is dropped, never used as an entry, an exit or a roll target."""
    out = []
    for d, b in sorted((bars or {}).items()):
        o, c, v = b[2], b[3], b[4]
        if o is None or c is None or not v or v <= 0 or o <= 0 or c <= 0:
            continue
        out.append((d, float(o), float(c)))
    return out


def exit_bar(tb: list, target: str, asof: str):
    """First traded bar on or after `target`, within exit_roll_max_days and on/before asof -> (date, close) or None."""
    lim = min(plus(target, RULE["exit_roll_max_days"]), asof)
    k = bisect.bisect_left(tb, target, key=lambda b: b[0])
    if k >= len(tb) or tb[k][0] > lim:
        return None
    return tb[k][0], tb[k][2]


def bar_on(tb: list, day: str):
    k = bisect.bisect_left(tb, day, key=lambda b: b[0])
    return tb[k] if k < len(tb) and tb[k][0] == day else None


def entry_px(bar, et: str) -> float:
    return bar[1] if et == "open" else bar[2]


def mkt_ret(mtb: list, s: str, et: str, x: str):
    """IWM over the same bars: entry type on s, close on x; None if IWM has no traded bar on either day."""
    b0, b1 = bar_on(mtb, s), bar_on(mtb, x)
    if b0 is None or b1 is None:
        return None
    return (b1[2] / entry_px(b0, et) - 1) * 100


def settled_asof() -> str:
    sp = iu.spec_from_file_location("_rt_sessions", SESSIONS)
    m = iu.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m.settled_session().isoformat()


def _fetch(sym: str, asof: str):
    p1 = int(dt.datetime.fromisoformat(RULE["yahoo_from"]).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int((dt.datetime.fromisoformat(asof) + dt.timedelta(days=2)).replace(tzinfo=dt.timezone.utc).timestamp())
    url = CHART.format(s=urllib.parse.quote(sym), p1=p1, p2=p2)
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
    except urllib.error.HTTPError as e:
        return None, ("not_found" if e.code == 404 else "transient"), f"HTTP {e.code}"
    except Exception as e:                                      # URLError, timeout, TLS, not JSON
        return None, "transient", type(e).__name__
    try:
        res = (d.get("chart") or {}).get("result")
        if not res:
            code = str(((d.get("chart") or {}).get("error") or {}).get("code") or "")
            return None, ("not_found" if code.lower() == "not found" else "transient"), f"no result ({code})"
        res = res[0]
        if not res.get("timestamp"):
            return None, "not_found", "no bars in range"
        q = res["indicators"]["quote"][0]
        out = {}
        for i, ts in enumerate(res["timestamp"]):
            day = dt.datetime.fromtimestamp(ts, NY).date().isoformat()
            if day > asof:
                continue                                        # settled bars only: nothing after the settled session
            f = lambda k: None if q[k][i] is None else round(float(q[k][i]), 6)
            out[day] = [f("low"), f("high"), f("open"), f("close"), int(q["volume"][i] or 0)]
        return out, "ok", ""
    except (KeyError, IndexError, TypeError, ValueError) as e:
        return None, "transient", f"unexpected reply ({type(e).__name__})"


class Prices:
    """Yahoo daily bars, cached on disk per (symbol, asof). Transient failures are retried twice, never cached; 'not found' is
    cached for this asof only. offline=True never touches the network (tests). `read` keeps every series actually used."""

    def __init__(self, asof: str, cache_path: Path | None = None, offline: bool = False, fetcher=None, pause: float = 0.15):
        self.asof, self.path, self.offline, self.pause = asof, Path(cache_path or CACHE), offline, pause
        self.fetcher = fetcher or _fetch
        try:
            self.c = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.c = {}
        self.why: dict[str, str] = {}
        self.transient: set[str] = set()
        self.read: dict[str, dict | None] = {}
        self.dirty = False

    def get(self, sym: str):
        b = self._get(sym)
        self.read[sym] = b
        return b

    def prefetch(self, symbols) -> None:
        """R2: read every symbol ONCE, up front, then go offline - every row then sees the same fixed set, so network timing cannot
        change which twins a row is eligible for."""
        for k, sym in enumerate(sorted(symbols), 1):
            self._get(sym)
            if k % 100 == 0:
                self.save()
                print(f"  prefetched {k}/{len(symbols)}", file=sys.stderr)
        self.save()
        self.offline = True

    def _get(self, sym: str):
        if sym in self.transient:
            return None                                          # failed once this run: stays failed for every row (R2)
        e = self.c.get(sym)
        if e and e.get("asof") == self.asof:
            if e.get("nf"):
                self.why[sym] = f"no price series (source said not found: {e.get('why')})"
                return None
            return e["bars"]
        if self.offline:
            self.why[sym] = "not in the price cache (offline)"
            return None
        why = ""
        for attempt in range(3):
            bars, kind, why = self.fetcher(sym, self.asof)
            if self.pause:
                time.sleep(self.pause)
            if kind == "ok":
                self.c[sym] = {"asof": self.asof, "bars": bars}
                self.dirty = True
                return bars
            if kind == "not_found":
                self.c[sym] = {"asof": self.asof, "nf": True, "why": why}
                self.dirty = True
                self.why[sym] = f"no price series (source said not found: {why})"
                return None
            if attempt < 2:
                time.sleep(2 + 10 * attempt)
        self.transient.add(sym)
        self.why[sym] = f"price fetch failed (transient: {why}); blank, not zero"
        return None

    def save(self):
        if self.dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.c))
            os.replace(tmp, self.path)
            self.dirty = False

    def freeze_read(self, path: Path) -> str:
        """Write every series this run read (gzip, deterministic) and return its SHA-256 (C10)."""
        blob = gzip.compress(json.dumps(self.read, sort_keys=True).encode(), mtime=0)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, path)
        return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------------------------- the Twin B pool (frozen copy)
def bucket_of(mc) -> str | None:
    v = fnum(mc)
    if v is None or v <= 0:
        return None
    for name, lo, hi in RULE["buckets"]:
        if v >= lo and (hi is None or v < hi):
            return name
    return None


def freeze_pool(src: Path | None = None, dst: Path | None = None) -> str:
    """One-time: the slim copy of the scanner snapshot this study reads (C3). Returns its SHA-256."""
    src, dst = Path(src or POOL_SOURCE), Path(dst or POOL)
    with open(src, newline="") as f:
        rows = list(csv.DictReader(f))
    tmp = dst.with_suffix(".tmp")
    with open(tmp, "x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POOL_COLS, lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["name"]):
            w.writerow({k: r.get(k, "") for k in POOL_COLS})
    os.replace(tmp, dst)
    return sha256_file(dst)


def load_pool(path: Path | None = None, verify: bool = True) -> dict[str, tuple[str, str]]:
    """{yahoo symbol: (bucket, sector)} for common, primary-listed stocks that carry a market cap. Refuses a pool file whose
    SHA-256 is not RULE['pool_sha256'] (verify=False only for test fixtures)."""
    path = Path(path or POOL)
    if verify and sha256_file(path) != RULE["pool_sha256"]:
        raise SystemExit(f"random_twin: refusing - {path} is not the frozen pool (SHA-256 != RULE pool_sha256)")
    out = {}
    f = RULE["pool_filter"]
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("type") != f["type"] or r.get("typespecs") != f["typespecs"] or str(r.get("is_primary")) != f["is_primary"]:
                continue
            b = bucket_of(r.get("market_cap_basic"))
            if b is None or not r.get("name"):
                continue
            out[ysym(r["name"])] = (b, (r.get("sector") or "").strip() or "?")
    return out


def cell_of(sym: str, pool: dict) -> tuple | None:
    """The desk ticker's Twin B cell: (bucket, sector), or (bucket, '*') when that cell has fewer than min_cell pool names."""
    k = pool.get(ysym(sym))
    if k is None:
        return None
    n = sum(1 for v in pool.values() if v == k)
    return k if n >= RULE["min_cell"] else (k[0], "*")


def panel(cell: tuple, pool: dict) -> list[str]:
    members = sorted(s for s, v in pool.items() if v[0] == cell[0] and (cell[1] == "*" or v[1] == cell[1]))
    if len(members) <= RULE["panel_size"]:
        return members
    return sorted(rng_for("panel", cell[0], cell[1]).sample(members, RULE["panel_size"]))


# ---------------------------------------------------------------------------------------------- the twins
def twin_a(row: dict, tb: list, pdates: list | None, wins: list, asof: str, mtb: list) -> dict:
    """Post-exit only, market-adjusted (C1). Candidates start after the row's own blocked window, so a twin's return can never sit
    inside the decline that preceded the insiders' buy; each twin's return is net of IWM over its own bars."""
    eb, et = row["entry_bar"], row["entry_type"]
    span = (D(row["check_date"]) - D(eb)).days
    lo = blocked_end({"date": row["date"], "check_date": row["check_date"], "thesis": row.get("thesis", "")})
    hi = plus(lo, RULE["window_a_days"])
    elig = []
    cnt = {"overlaps_a_desk_window": 0, "insider_purchase_near": 0, "no_settled_exit": 0, "no_market_bar": 0}
    for bar in tb:
        s = bar[0]
        if s <= lo or s > hi:
            continue
        x = exit_bar(tb, plus(s, span), asof)
        if x is None:
            cnt["no_settled_exit"] += 1
            continue
        if overlaps(s, x[0], wins):
            cnt["overlaps_a_desk_window"] += 1
            continue
        if has_purchase(pdates, plus(s, -RULE["buffer_days"]), x[0]):
            cnt["insider_purchase_near"] += 1
            continue
        m = mkt_ret(mtb, s, et, x[0])
        if m is None:
            cnt["no_market_bar"] += 1
            continue
        p0 = entry_px(bar, et)
        elig.append((s, p0, x[0], x[1], m))
    out = {"window": [lo, hi], "n_eligible": len(elig), "excluded": cnt}
    if len(elig) < RULE["min_twins"]:
        out["why"] = f"fewer than {RULE['min_twins']} eligible post-exit same-stock twin days ({len(elig)})"
        return out
    pick = sorted(rng_for("A", ysym(row["ticker"]), row["date"]).sample(elig, min(RULE["k_a"], len(elig))))
    out["twins"] = [[s, r4(p0), x, r4(p1), r4((p1 / p0 - 1) * 100), r4(m)] for s, p0, x, p1, m in pick]
    out["mean_raw"] = mean([(p1 / p0 - 1) * 100 for _s, p0, _x, p1, _m in pick])
    out["mean"] = mean([(p1 / p0 - 1) * 100 - m for _s, p0, _x, p1, m in pick])      # market-adjusted
    out["pre_entry_share"] = sum(1 for t in pick if t[0] < eb) / len(pick)
    return out


def twin_b(row: dict, cell: tuple | None, members: list[str], prices: "Prices", feed: dict, wins: dict, asof: str) -> dict:
    if cell is None:
        return {"why": "ticker not in the pool snapshot (delisted, a fund or an ADR outside both pulls, OTC, a secondary listing, "
                       "a large-float micro cap, or no market cap)"}
    eb, et, me = row["entry_bar"], row["entry_type"], ysym(row["ticker"])
    elig, cnt = [], {"desk_ticker": 0, "no_price_series": 0, "panel_fetch_failed": 0, "no_trade_on_entry_bar": 0,
                     "no_settled_exit": 0, "insider_purchase_near": 0, "overlaps_a_desk_window": 0}
    for s in members:
        if s == me:
            cnt["desk_ticker"] += 1
            continue
        tb = traded(prices.get(s))
        if not tb:
            cnt["panel_fetch_failed" if s in getattr(prices, "transient", ()) else "no_price_series"] += 1
            continue
        bar = bar_on(tb, eb)
        if bar is None:
            cnt["no_trade_on_entry_bar"] += 1
            continue
        x = exit_bar(tb, row["check_date"], asof)
        if x is None:
            cnt["no_settled_exit"] += 1
            continue
        if has_purchase(feed.get(s), plus(eb, -RULE["buffer_days"]), x[0]):
            cnt["insider_purchase_near"] += 1
            continue
        if overlaps(eb, x[0], wins.get(s)):
            cnt["overlaps_a_desk_window"] += 1
            continue
        elig.append((s, entry_px(bar, et), x[0], x[1]))
    out = {"cell": list(cell), "panel": len(members), "n_eligible": len(elig), "excluded": cnt}
    if len(elig) < RULE["min_twins"]:
        out["why"] = f"fewer than {RULE['min_twins']} eligible same-day twins in cell {cell} ({len(elig)})"
        return out
    pick = sorted(rng_for("B", me, row["date"]).sample(elig, min(RULE["k_b"], len(elig))))
    out["twins"] = [[s, r4(p0), x, r4(p1), r4((p1 / p0 - 1) * 100)] for s, p0, x, p1 in pick]
    out["mean"] = mean([(p1 / p0 - 1) * 100 for _s, p0, _x, p1 in pick])
    return out


def replica(row: dict, tb: list, asof: str):
    """The desk row re-priced from the same bars as its twins (data audit) -> (return, exit bar date) or (None, why)."""
    bar = bar_on(tb, row["entry_bar"])
    x = exit_bar(tb, row["check_date"], asof)
    if bar is None or x is None:
        return None, ("no traded entry bar" if bar is None else "no settled exit bar")
    return (x[1] / entry_px(bar, row["entry_type"]) - 1) * 100, x[0]


def build_row(row, prices, feed, wins, pool, asof, mtb, build_a: bool = True):
    sym = ysym(row["ticker"])
    bars = prices.get(sym)
    tb = traded(bars)
    rec = {k: row[k] for k in ("i", "ticker", "date", "check_date", "outcome", "entry_type", "entry_bar", "week", "segment",
                               "delisted")}
    rec["key"] = row_key(row)
    rec["desk_ret"] = r4(row["ret"])
    rec["cluster_usd"] = cluster_usd(row.get("thesis", ""))
    exit_d = None
    if not tb:
        rec["replica_ret"], rec["replica_why"] = None, prices.why.get(sym) or "no traded bars in the desk ticker's series"
    else:
        rp, rx = replica(row, tb, asof)
        rec["replica_ret"] = r4(rp)
        if rp is None:
            rec["replica_why"] = rx
        else:
            rec["replica_exit_bar"] = exit_d = rx
        eb = (bars or {}).get(row["entry_bar"])
        if eb and eb[0] is not None and eb[1] is not None:
            eps = RULE["entry_range_eps"]
            rec["entry_in_bar_range"] = bool(eb[0] * (1 - eps) <= row["p_call"] <= eb[1] * (1 + eps))
    # the desk's own window against IWM: Twin A's market adjustment, and a context line (never the IWM ruling)
    if exit_d is None and mtb:
        x = exit_bar(mtb, row["check_date"], asof)
        exit_d = x[0] if x else None
    m_desk = mkt_ret(mtb, row["entry_bar"], row["entry_type"], exit_d) if (mtb and exit_d) else None
    rec["context_iwm_same_bars_ret"] = r4(m_desk)
    if build_a:
        if not tb:
            rec["twin_a"] = {"why": prices.why.get(sym) or "no traded bars in the desk ticker's series"}
        else:
            rec["twin_a"] = twin_a(row, tb, feed.get(sym), wins.get(sym), asof, mtb)
    else:
        rec["twin_a"] = {"deferred": f"Twin A is built once, at the {RULE['look']} look (post-exit windows); counts only now"}
    cell = cell_of(row["ticker"], pool)
    rec["twin_b"] = twin_b(row, cell, panel(cell, pool) if cell else [], prices, feed, wins, asof)
    ta, tbb = rec["twin_a"], rec["twin_b"]
    desk_abn = (row["ret"] - m_desk) if m_desk is not None else None
    rep_abn = (rec["replica_ret"] - m_desk) if (m_desk is not None and rec["replica_ret"] is not None) else None
    rec["d_a"] = r4(desk_abn - ta["mean"]) if ("mean" in ta and desk_abn is not None) else None
    rec["d_a_replica"] = r4(rep_abn - ta["mean"]) if ("mean" in ta and rep_abn is not None) else None
    rec["d_b"] = r4(row["ret"] - tbb["mean"]) if "mean" in tbb else None
    rec["d_b_replica"] = r4(rec["replica_ret"] - tbb["mean"]) if ("mean" in tbb and rec["replica_ret"] is not None) else None
    if "mean" in ta and desk_abn is None:
        ta["why_no_d"] = "IWM has no bar on the desk's entry or exit day"
    for t in (ta, tbb):
        for k in ("mean", "mean_raw", "pre_entry_share"):
            if k in t:
                t[k] = r4(t[k])
    return rec


_STRATA = []


def cluster_usd(thesis: str):
    """INS-002's own parser (agent/strata.py), loaded read-only; None when it does not parse (UNKNOWN, never sub-floor)."""
    if not _STRATA:
        try:
            sp = iu.spec_from_file_location("_rt_strata", STRATA)
            m = iu.module_from_spec(sp)
            sp.loader.exec_module(m)
            _STRATA.append(m.cluster_usd)
        except Exception:
            _STRATA.append(None)
    fn = _STRATA[0]
    return fn(thesis) if fn else None


# ---------------------------------------------------------------------------------------------- inference (house style)
def cr1_t(vals, wk):
    """Cluster-robust (CR1) t of the pooled mean of `vals`, clusters = `wk` (spy-trading/src/pattern_engine_run.cr1_t)."""
    import numpy as np
    v = np.asarray(vals, float)
    n = len(v)
    if n < 3:
        return float("nan")
    uniq, inv = np.unique(np.asarray(wk), return_inverse=True)
    G = len(uniq)
    if G < 3:
        return float("nan")
    s = np.bincount(inv, weights=v - v.mean())
    var = (G / (G - 1)) * float((s ** 2).sum()) / n ** 2
    return float(v.mean() / math.sqrt(var)) if var > 0 else float("nan")


def alpha_k() -> float:
    return 1 - (1 - RULE["family_alpha"]) ** (1 / RULE["K"])


def t_bar(G: int) -> float | None:
    if G < 2:
        return None
    from scipy.stats import t as student
    return max(RULE["t_floor"], float(student.ppf(1 - alpha_k() / 2, G - 1)))


def judge(recs: list[dict], key: str) -> dict:
    vals = [(r["week"], r[key]) for r in recs if r.get(key) is not None]
    n = len(vals)
    weeks = sorted({w for w, _ in vals})
    G = len(weeks)
    out = {"n_rows": n, "n_weeks": G, "clustered_by": "ISO week of the entry bar", "blank_rows": sum(1 for r in recs if r.get(key) is None)}
    if n == 0:
        out["verdict"] = "UNREADABLE"
        out["why"] = "no row has a reading"
        return out
    mu = sum(v for _, v in vals) / n
    t = cr1_t([v for _, v in vals], [w for w, _ in vals])
    tb = t_bar(G)
    h1w, h2w = set(weeks[: G // 2]), set(weeks[G // 2:])
    h1, h2 = mean([v for w, v in vals if w in h1w]), mean([v for w, v in vals if w in h2w])
    wsum, per_week = {}, {}
    for w, v in vals:
        wsum[w] = wsum.get(w, 0.0) + v
        per_week.setdefault(w, []).append(v)
    best, worst = max(wsum, key=wsum.get), min(wsum, key=wsum.get)
    drop_best = mean([v for w, v in vals if w != best])
    drop_worst = mean([v for w, v in vals if w != worst])
    wmm = sum(sum(v) / len(v) for v in per_week.values()) / len(per_week)
    srt = sorted(v for _, v in vals)
    med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    out.update({"mean_d_pp": r4(mu), "median_d_pp": r4(med), "share_d_positive": r4(sum(1 for _, v in vals if v > 0) / n),
                "t_cr1": r4(t), "t_bar": r4(tb), "df": G - 1,
                "halves": {"first": {"weeks": sorted(h1w), "mean_d_pp": r4(h1)}, "second": {"weeks": sorted(h2w), "mean_d_pp": r4(h2)}},
                "drop_best_week": {"week": best, "mean_d_pp": r4(drop_best)}, "drop_worst_week": {"week": worst, "mean_d_pp": r4(drop_worst)},
                "week_mean_of_means_pp": r4(wmm)})
    readable = G >= RULE["min_weeks"] and n >= RULE["min_rows"] and math.isfinite(t)
    if not readable:
        out["verdict"] = "UNREADABLE"
        out["why"] = f"needs >= {RULE['min_weeks']} entry weeks and >= {RULE['min_rows']} rows with a reading (has {G} and {n})"
    elif mu > 0 and t >= tb and (h1 or 0) > 0 and (h2 or 0) > 0 and (drop_best or 0) > 0 and wmm > 0:
        out["verdict"] = "BEATS-TWIN"
    elif mu < 0 and t <= -tb and (h1 or 0) < 0 and (h2 or 0) < 0 and (drop_worst or 0) < 0 and wmm < 0:
        out["verdict"] = "TRAILS-TWIN"
    else:
        out["verdict"] = "NO-DIFFERENCE"
    return out


def gated(primary: dict, rep: dict) -> dict:
    """C2: BEATS/TRAILS needs the ledger and replica readings to agree; otherwise the cell reads DATA-SENSITIVE (not a pass)."""
    out = dict(primary)
    out["replica_verdict"] = rep["verdict"]
    out["replica_t_cr1"] = rep.get("t_cr1")
    out["replica_mean_d_pp"] = rep.get("mean_d_pp")
    out["ledger_verdict"] = primary["verdict"]
    if primary["verdict"] in JUDGED and rep["verdict"] != primary["verdict"]:
        out["verdict"] = "DATA-SENSITIVE"
    out["data_sensitive"] = rep["verdict"] != primary["verdict"]
    return out


def overall_b(cell: dict, retro: bool) -> str:
    """One judged twin (Twin B). RETRO is retrospective: it never routes anywhere (R4)."""
    v = cell.get("verdict")
    if retro:
        return (f"RETROSPECTIVE ({v}): rows seen before registration; whatever the verdict, this changes nothing and routes nowhere - "
                "only the FORWARD reading can")
    if v == "BEATS-TWIN":
        return ("BEATS SAME-DAY SIMILAR STOCKS: the desk beat same-size, same-sector stocks bought the same day (goes to /edge-refute "
                "and Anupam, beaten-down state first; changes nothing the desk does)")
    if v == "UNREADABLE":
        return "UNREADABLE: below the minimum n"
    return f"NOT SEPARATED ({v}): the desk did not beat same-size, same-sector stocks bought the same day at the bar"


def strata_block(recs: list[dict]) -> dict:
    """C5 / INS-002: >= $100k, under $100k and unknown, never blended without this beside it. Shown, never judged."""
    fl = RULE["strata_floor_usd"]
    out = {}
    for name, test in (("ge_100k", lambda u: u is not None and u >= fl), ("lt_100k", lambda u: u is not None and u < fl),
                       ("unknown", lambda u: u is None)):
        sub = [r for r in recs if test(r.get("cluster_usd"))]
        blk = {"rows": len(sub)}
        for k in ("d_a", "d_b"):
            xs = [r[k] for r in sub if r.get(k) is not None]
            blk[k] = {"n": len(xs), "mean_pp": r4(mean(xs)), "share_positive": r4(sum(1 for x in xs if x > 0) / len(xs)) if xs else None}
        out[name] = blk
    return out


def shown(recs: list[dict], account_keys: set | None) -> dict:
    """Shown, never judged."""
    def m(k, sub=None):
        xs = [((r.get(k) or {}).get(sub) if sub else r.get(k)) for r in recs]
        xs = [x for x in xs if x is not None]
        return {"mean": r4(mean(xs)), "n": len(xs)}
    with_cell = [r for r in recs if "cell" in r["twin_b"]]
    no_cell = [r for r in recs if "cell" not in r["twin_b"]]
    mism = [{"key": r["key"], "ledger": r["desk_ret"], "replica": r["replica_ret"]}
            for r in recs if r.get("replica_ret") is not None and abs(r["desk_ret"] - r["replica_ret"]) > RULE["replica_tol_pp"]]
    out_rng = [r["key"] for r in recs if r.get("entry_in_bar_range") is False]
    pre = [r["twin_a"].get("pre_entry_share") for r in recs if r["twin_a"].get("pre_entry_share") is not None]
    out = {"desk_ret_pct": m("desk_ret"), "twin_a_raw_ret_pct": m("twin_a", "mean_raw"), "twin_a_mkt_adj_ret_pct": m("twin_a", "mean"),
           "twin_b_ret_pct": m("twin_b", "mean"),
           "context_iwm_same_bars_ret_pct": m("context_iwm_same_bars_ret"),
           "twin_b_rows_with_cell_vs_without": {"with_cell": {"rows": len(with_cell), "desk_ret_mean": r4(mean([r["desk_ret"] for r in with_cell]))},
                                               "without_cell": {"rows": len(no_cell), "desk_ret_mean": r4(mean([r["desk_ret"] for r in no_cell]))}},
           "twin_a_pre_entry_share": {"rows": len(pre), "max": r4(max(pre)) if pre else None},
           "replica_vs_ledger": {"rows_compared": sum(1 for r in recs if r.get("replica_ret") is not None),
                                 f"over_{RULE['replica_tol_pp']}pp": len(mism), "rows": mism},
           "price_at_call_outside_entry_bar_range": {"rows": len(out_rng), "keys": out_rng},
           "entry_types": {t: sum(1 for r in recs if r["entry_type"] == t) for t in ("open", "close")},
           "twin_b_cells_bucket_only": sum(1 for r in recs if (r["twin_b"].get("cell") or [None, None])[1] == "*"),
           "strata_ins002": strata_block(recs),
           "note": "Shown, never judged. The context IWM line uses the twins' own bars; the desk review's IWM figure (close-to-close "
                   "from the call date, DESK-001) is the standing judgement and is untouched."}
    if account_keys is not None:
        held = sum(1 for r in recs if acct_key(r) in account_keys)
        out["account_held_vs_withheld_port006"] = {"held_by_the_account": held, "not_in_the_account": len(recs) - held,
                                                   "note": "the lab's ledger is measured; desk_review's n follows THE ACCOUNT (Brain s6)"}
    return out


A_CAVEAT = ("SHOWN ONLY, NEVER JUDGED (C14 BLOCK, option a). Twin A is IWM-adjusted at beta 1, so it carries the lean "
            "(1 - beta) x (IWM over the twin windows - IWM over the desk window), shared by every row. On zero-skill prices the reviewer "
            "read d_A +1.76 pp (t +3.60) at beta 0.5 and -2.72 pp (t -2.42) at beta 1.5; real betas are far from 1 (dry-cache panel "
            "median 0.70, desk names ~1.5). Its sign here is not known in advance. It can neither pass nor fail anything.")


def reading(recs_all: list[dict], excluded: list[dict], account_keys=None, judged: bool = True, retro: bool = False) -> dict:
    """Twin B is the judged cell (unless judged=False: NOT JUDGED, no verdict, no overall sentence - C7). Twin A is ALWAYS shown
    through the NOT JUDGED path with its beta caveat."""
    recs = [r for r in recs_all if not r.get("delisted")]
    b = gated(judge(recs, "d_b"), judge(recs, "d_b_replica"))
    a = gated(judge(recs, "d_a"), judge(recs, "d_a_replica"))
    for blk in ((a, b) if not judged else (a,)):
        for f in ("verdict", "replica_verdict", "ledger_verdict", "why"):
            blk.pop(f, None)
        blk["status"] = "NOT JUDGED"
    a["caveat"] = A_CAVEAT
    pre = [r["twin_a"].get("pre_entry_share") for r in recs if r["twin_a"].get("pre_entry_share") is not None]
    a["pre_entry_share_max"] = r4(max(pre)) if pre else None
    out = {"cells": {"B_same_day_similar_stock": b, "A_same_stock_post_exit_shown_only": a}}
    if judged:
        out["overall"] = overall_b(b, retro)
    else:
        out["status"] = "NOT JUDGED - shown only"
    dl = [r for r in recs_all if r.get("delisted")]
    db = judge(recs_all, "d_b")
    out["delisted_at_minus_100"] = {"rows": len(dl), "B_mean_d_pp": db.get("mean_d_pp"), "B_t": db.get("t_cr1"),
                                    "note": "shown, never judged: scored-wrong rows with no price_at_check at -100%"}
    out["excluded"] = excluded
    out["shown"] = shown(recs, account_keys)
    out["blank_reasons"] = {"B": _reasons(recs, "twin_b"), "A": _reasons(recs, "twin_a")}
    return out


def _reasons(recs, k):
    out = {}
    for r in recs:
        w = r[k].get("why") or r[k].get("why_no_d")
        if w:
            w = re.sub(r"\(\d+\)$", "(n)", re.sub(r"in cell \(.*?\) ", "in its cell ", w))
            out[w] = out.get(w, 0) + 1
    return out


def account_keys(path: Path | None = None) -> set | None:
    """'TICKER|check_date' of the insider rows THE ACCOUNT carries in portfolio.js (PORT-006 withholds the rest). One open row per
    ticker means ticker + check_date names a ledger row. Read-only; None (not an empty set) when the file cannot be read."""
    try:
        t = Path(path or PORTFOLIO_JS).read_text()
        rows = json.loads(t[t.index("{"): t.rindex("}") + 1])["rows"]
    except (OSError, ValueError, KeyError):
        return None
    return {f"{ysym(r['ticker'])}|{(r.get('exit_planned') or '')[:10]}" for r in rows if r.get("desk") == "insider"}


def acct_key(r: dict) -> str:
    return f"{ysym(r['ticker'])}|{r['check_date'][:10]}"


# ---------------------------------------------------------------------------------------------- the registered runs
def git(*a, repo: Path | None = None) -> str:
    """git stdout; ANY git error refuses (R3 of the C14 BLOCK: a silent empty stdout passed the dirty-ledger check)."""
    p = subprocess.run(["git", "-C", str(repo or IR_REPO), *a], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise SystemExit(f"random_twin: refusing - git {' '.join(a[:2])} failed in {repo or IR_REPO}: {p.stderr.strip()[:200]}")
    return p.stdout.strip()


def registration_check(me: Path | None = None, repo: Path | None = None, evo: Path | None = None, cc_repo: Path | None = None,
                       issues: Path | None = None, result_id: str = "RANDOM-TWIN/v1 result") -> dict:
    """The run refuses unless (C8):
      1. this file IS the repo copy;
      2. the prereg, this script, its test and the frozen pool are committed and clean (any git error refuses);
      3. evolution_ledger.json has no uncommitted change;
      4. a generation with id exactly RANDOM-TWIN/v1, trials_charged == K and variant ids exactly {RANDOM-TWIN/v1/<cell>} (any status),
         freezes the current SHA-256 of all four - or a 0-trial 'RANDOM-TWIN/v1 amendment' does, citing an issues.json row whose own
         text names RANDOM-TWIN/v1;
      5. no generation with id `result_id` exists yet (the result is one-shot in the ledger, not just on disk)."""
    me = Path(me or __file__).resolve()
    repo, evo = Path(repo or IR_REPO), Path(evo or EVO)
    cc_repo, issues = Path(cc_repo or CC_REPO), Path(issues or ISSUES)
    if me != (repo / SCRIPT_REL).resolve():
        raise SystemExit(f"random_twin: refusing - run the committed repo copy {repo / SCRIPT_REL}, not {me}")
    dirty = git("status", "--porcelain", "--", *FROZEN, repo=repo)
    tracked = git("ls-files", "--", *FROZEN, repo=repo).split()
    if dirty or len(tracked) != len(FROZEN):
        raise SystemExit(f"random_twin: refusing - prereg/script/test/pool must be committed and clean (status: {dirty or 'untracked'})")
    if git("status", "--porcelain", "--", EVO_REL, repo=cc_repo):
        raise SystemExit("random_twin: refusing - the evolution ledger has uncommitted changes")
    shas = {f"insider-radar/{rel}": sha256_file(repo / rel) for rel in FROZEN}
    try:
        gens = json.loads(evo.read_text()).get("generations", [])
    except (OSError, ValueError) as e:
        raise SystemExit(f"random_twin: refusing - cannot read the evolution ledger ({type(e).__name__})")
    if any(str(g.get("id", "")) == result_id for g in gens):
        raise SystemExit(f"random_twin: refusing - the evolution ledger already holds '{result_id}' (one-shot)")
    reg = [g for g in gens if str(g.get("id", "")) == RULE["id"]]
    if not reg:
        raise SystemExit("random_twin: refusing - no evolution-ledger generation with id exactly RANDOM-TWIN/v1")
    g = reg[0]
    want = {f"{RULE['id']}/{c}" for c in RULE["cells"]}
    have = {str(v.get("id", "")) for v in g.get("variants", [])}
    if g.get("trials_charged") != RULE["K"] or have != want:
        raise SystemExit(f"random_twin: refusing - RANDOM-TWIN/v1 must charge K={RULE['K']} trials with variants exactly {sorted(want)}")
    ok = [g] if all((g.get("frozen_sha256") or {}).get(k) == v for k, v in shas.items()) else []
    if not ok:
        try:
            rows = [v for v in json.loads(issues.read_text()).values() if isinstance(v, list)][0]
        except (OSError, ValueError, IndexError):
            rows = []
        named = {r.get("id") for r in rows if isinstance(r, dict) and RULE["id"] in json.dumps(r)}
        for a in gens:
            if (str(a.get("id", "")) == RULE["id"] + " amendment" and a.get("trials_charged") == 0 and a.get("issue") in named
                    and all((a.get("frozen_sha256") or {}).get(k) == v for k, v in shas.items())):
                ok = [a]
    if not ok:
        raise SystemExit("random_twin: refusing - no RANDOM-TWIN/v1 registration (or cited 0-trial amendment) freezes these "
                         "SHA-256s: " + json.dumps(shas))
    return {"commit": git("log", "-1", "--format=%H", "--", *FROZEN, repo=repo), "frozen_sha256": shas,
            "ledger_gen": ok[0].get("gen"), "ledger_id": ok[0].get("id")}


def retro_result_check(out: Path | None = None, evo: Path | None = None) -> dict:
    """The look reads RETRO's rows only from a random_twin.json that the ledger's 'RANDOM-TWIN/v1 result' generation froze."""
    out, evo = Path(out or OUT), Path(evo or EVO)
    try:
        gens = json.loads(evo.read_text()).get("generations", [])
    except (OSError, ValueError) as e:
        raise SystemExit(f"random_twin: refusing - cannot read the evolution ledger ({type(e).__name__})")
    res = [g for g in gens if str(g.get("id", "")) == "RANDOM-TWIN/v1 result"]
    if not res:
        raise SystemExit("random_twin: refusing - no 'RANDOM-TWIN/v1 result' generation; the look reads only a frozen RETRO result")
    want = (res[0].get("frozen_sha256") or {}).get(f"insider-radar/{OUT_REL}")
    if not out.exists() or sha256_file(out) != want:
        raise SystemExit("random_twin: refusing - random_twin.json is missing or is not the file the result generation froze")
    return json.loads(out.read_text())


def needed_symbols(rows: list[dict], pool: dict) -> tuple[set, set]:
    desk = {RULE["market"]} | {ysym(r["ticker"]) for r in rows}
    pan = set()
    for r in rows:
        c = cell_of(r["ticker"], pool)
        if c:
            pan |= set(panel(c, pool))
    return desk, pan - desk


def compute(rows_in, all_rows, asof, prices, feed, pool, build_a):
    wins = desk_windows(all_rows)
    mtb = traded(prices.get(RULE["market"]))
    out = []
    for k, row in enumerate(rows_in, 1):
        out.append(build_row(row, prices, feed, wins, pool, asof, mtb, build_a=build_a))
        if k % 20 == 0:
            prices.save()
            print(f"  {k}/{len(rows_in)} rows", file=sys.stderr)
    prices.save()
    return out


def fetch_gate(prices: Prices, desk_syms: set, panel_syms: set):
    """C9: any transient failure on a desk ticker or IWM refuses; panel failures refuse above 5% of all symbols."""
    bad_desk = sorted(prices.transient & desk_syms)
    if bad_desk:
        raise SystemExit(f"random_twin: refusing to write - desk ticker / market fetch failed transiently: {bad_desk}")
    need = len(desk_syms | panel_syms)
    bad = sorted(prices.transient)
    if need and len(bad) / need > RULE["max_fetch_fail_share"]:
        raise SystemExit(f"random_twin: refusing to write - {len(bad)} of {need} symbols failed transiently "
                         f"(> {RULE['max_fetch_fail_share']:.0%}): {bad}")


def meta_block(asof, feed_meta, prices, desk_syms, panel_syms, reg, bars_sha) -> dict:
    return {"id": RULE["id"], "rule": RULE, "rule_sha": RULE_SHA, "asof_settled_session": asof,
            "run_at": dt.datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M PT"),
            "registration": reg,
            "inputs_sha256": {"ledger.csv": sha256_file(LEDGER), "pool": sha256_file(POOL), "events.json": feed_meta.get("events_sha256"),
                              "feed_vintage_list": feed_meta.get("vintage_list_sha256"), "bars_read_gz": bars_sha},
            "feed_union": feed_meta, "symbols": {"desk_and_market": len(desk_syms), "panel": len(panel_syms)},
            "transient_fetch_failures": sorted(prices.transient),
            "paper_only": "Measurement only: nothing the insider desk buys, sizes or exits changes, the IWM ruling (DESK-001) is "
                          "untouched, and no desk reader consumes this file."}


def cmd_run(args):
    reg = registration_check()
    if OUT.exists():
        raise SystemExit(f"random_twin: refusing - {OUT} already exists (one-shot: a defect found after the run is RANDOM-TWIN/v2, and "
                         "this v1 result stays primary)")
    asof = settled_asof()
    rows = load_ledger()
    pop, excl = population(rows)
    retro = [r for r in pop if r["segment"] == "RETRO"]
    pool = load_pool()
    feed, fmeta = feed_union(upto=asof)
    prices = Prices(asof)
    desk_syms, panel_syms = needed_symbols(retro, pool)
    prices.prefetch(desk_syms | panel_syms)                       # R2: one fixed set, then offline
    fetch_gate(prices, desk_syms, panel_syms)
    recs = compute(retro, rows, asof, prices, feed, pool, build_a=True)
    bars_name = f"bars_read_{asof}.json.gz"
    bars_sha = prices.freeze_read(HERE / bars_name)               # R5: beside the result, committed with it
    blk = reading(recs, [e for e in excl if (e["date"] or "") <= RULE["retro_last_call"]], account_keys(), retro=True)
    out = {"meta": {**meta_block(asof, fmeta, prices, desk_syms, panel_syms, reg, bars_sha), "bars_read_file": bars_name},
           "retro_closed": {"definition": f"call date <= {RULE['retro_last_call']} and scored right|wrong by {asof}; outcomes were "
                                          "SEEN before registration - a retrospective reading, never pooled with FORWARD; it changes "
                                          "nothing whatever its verdict",
                            **blk, "rows": recs}}
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=1))
    os.replace(tmp, OUT)
    _print(out["retro_closed"], "RETRO (closed rows, seen before registration)")


def cmd_look(args):
    asof = settled_asof()
    rows = load_ledger()
    pop, excl = population(rows)
    fwd = [r for r in pop if r["segment"] == "FORWARD" and r["date"] <= RULE["forward_last_call"]]
    if asof < RULE["look"]:
        print(f"LOOK counts only until {RULE['look']} (asof {asof}): FORWARD {len(fwd)} scored rows, "
              f"{len({r['week'] for r in fwd})} entry weeks; minimum {RULE['min_weeks']} weeks / {RULE['min_rows']} rows. "
              "No twin is built and no difference is computed before the look.")
        return
    reg = registration_check(result_id="RANDOM-TWIN/v1 look result")
    if OUT_LOOK.exists():
        raise SystemExit(f"random_twin: refusing - {OUT_LOOK} already holds the one-shot look")
    prior = retro_result_check()
    retro_keys = {x["key"] for x in prior["retro_closed"]["rows"]}
    retro_all = [r for r in pop if r["segment"] == "RETRO"]
    late = [r for r in retro_all if row_key(r) not in retro_keys]
    seen = [r for r in retro_all if row_key(r) in retro_keys]
    pool = load_pool()
    feed, fmeta = feed_union(upto=asof)
    prices = Prices(asof)
    desk_syms, panel_syms = needed_symbols(fwd + retro_all, pool)
    prices.prefetch(desk_syms | panel_syms)
    fetch_gate(prices, desk_syms, panel_syms)
    recs = compute(fwd, rows, asof, prices, feed, pool, build_a=True)
    recs_seen = compute(seen, rows, asof, prices, feed, pool, build_a=True)
    recs_late = compute(late, rows, asof, prices, feed, pool, build_a=True)
    bars_name = f"bars_read_{asof}.json.gz"
    bars_sha = prices.freeze_read(HERE / bars_name)
    acct = account_keys()
    out = {"meta": {**meta_block(asof, fmeta, prices, desk_syms, panel_syms, reg, bars_sha), "bars_read_file": bars_name},
           "forward": {"definition": f"call date {RULE['forward_first_call']}..{RULE['forward_last_call']}, scored by {asof}",
                       **reading(recs, [e for e in excl if (e["date"] or "") >= RULE["forward_first_call"]], acct), "rows": recs},
           "retro_rows_twin_a_shown": {"definition": "the RETRO rows of random_twin.json again, for Twin A (shown only) now that their "
                                                     "post-exit windows exist; RETRO-B's verdict stays the one in random_twin.json",
                                       **reading(recs_seen, [], acct, judged=False), "rows": recs_seen},
           "retro_scored_after_registration": {**reading(recs_late, [], acct, judged=False), "rows": recs_late}}
    tmp = OUT_LOOK.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=1))
    os.replace(tmp, OUT_LOOK)
    _print(out["forward"], "FORWARD")


def cmd_dry(args):
    """Mechanics on <= 5 RETRO rows (Twin B only; Twin A is never built for RETRO before the look). Writes only to dry/."""
    if args.limit > 5:
        raise SystemExit("random_twin: the dry run is capped at 5 rows")
    asof = settled_asof()
    rows = load_ledger()
    pop, _ = population(rows)
    pool = load_pool()
    retro = [r for r in pop if r["segment"] == "RETRO"]
    picks, seen = [], set()
    for kind, test in (("close", lambda r: r["entry_type"] == "close"),
                       ("open-restated", lambda r: r["entry_type"] == "open" and "[FILLED " not in r["thesis"]),
                       ("open-filled", lambda r: "[FILLED " in r["thesis"]),
                       ("ins012-roll", lambda r: "[INS-012: no bar on" in r["thesis"]),
                       ("not-in-pool", lambda r: cell_of(r["ticker"], pool) is None)):
        for r in retro:
            if r["i"] not in seen and test(r):
                picks.append((kind, r))
                seen.add(r["i"])
                break
    picks = picks[: args.limit]
    feed, fmeta = feed_union(upto=asof)
    prices = Prices(asof, cache_path=HERE / "dry" / "yahoo_bars.json")
    print(f"asof {asof}; feed union {fmeta}")
    recs = compute([r for _, r in picks], rows, asof, prices, feed, pool, build_a=False)
    for (kind, _), rec in zip(picks, recs):
        b = rec["twin_b"]
        print(f"\n[{kind}] row {rec['i']} {rec['ticker']} call {rec['date']} entry {rec['entry_type']} {rec['entry_bar']} "
              f"check {rec['check_date']} week {rec['week']}")
        print(f"  desk {rec['desk_ret']} | replica {rec['replica_ret']} (exit bar {rec.get('replica_exit_bar')}) | in bar range "
              f"{rec.get('entry_in_bar_range')}")
        print(f"  B: cell {b.get('cell')} panel {b.get('panel')} eligible {b.get('n_eligible')} excluded {b.get('excluded')} "
              f"why {b.get('why')} mean {b.get('mean')}  d_B {rec['d_b']}")
    (HERE / "dry").mkdir(exist_ok=True)
    (HERE / "dry" / "dry_run_v2.json").write_text(json.dumps({"asof": asof, "rule_sha": RULE_SHA, "rows": recs}, indent=1))


def _print(block, title):
    print(f"== RANDOM-TWIN/v1 {title} ==")
    for k, c in block["cells"].items():
        if "n_rows" not in c:
            print(f"  {k}: {c.get('status')} - {c.get('why')}")
            continue
        print(f"  {k}: n {c['n_rows']} rows / {c['n_weeks']} weeks, mean d {c.get('mean_d_pp')} pp, t {c.get('t_cr1')} "
              f"(bar {c.get('t_bar')}), halves {c.get('halves', {}).get('first', {}).get('mean_d_pp')} / "
              f"{c.get('halves', {}).get('second', {}).get('mean_d_pp')}, drop-best {c.get('drop_best_week', {}).get('mean_d_pp')}, "
              f"week-mean-of-means {c.get('week_mean_of_means_pp')}, replica {c.get('replica_verdict')} -> "
              f"{c.get('verdict') or c.get('status')}")
    print("  " + str(block.get("overall") or block.get("status")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rule")
    d = sub.add_parser("dry")
    d.add_argument("--limit", type=int, default=5)
    sub.add_parser("run")
    sub.add_parser("look")
    a = ap.parse_args(argv)
    if a.cmd == "rule":
        print(json.dumps(RULE, indent=1, sort_keys=True))
        print("RULE_SHA", RULE_SHA)
    elif a.cmd == "dry":
        cmd_dry(a)
    elif a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "look":
        cmd_look(a)


if __name__ == "__main__":
    main()

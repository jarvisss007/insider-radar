#!/usr/bin/env python3
"""
Event study: what actually happens BEFORE and AFTER insider purchases?

Merges purchase events (live feed + backfill), fetches daily prices (yfinance) for every
event ticker + SPY, and computes market-adjusted (abnormal) returns around each event:

  BEFORE  — the stock's excess return over the 10 trading days into the buy
            (are insiders buying dips?)
  AFTER   — excess return at +1, +3, +5, +10, +20 trading days from the day you could
            realistically FOLLOW (the filing date close, not the insider's trade date),
            plus the full day-by-day CAR path out to +20 for the exit question.

Honest choices:
  * entry = filing-date CLOSE → measures what a follower could capture, not the insider.
  * abnormal = stock return − SPY return → strips market drift.
  * events too recent for a horizon are excluded from that horizon (no peeking).
  * per-horizon t-stats; small N reported as small N, not hidden.

Writes docs/data/event_study.json for the viewer.
"""
import datetime, json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
DATA = HERE / "docs" / "data"
HORIZONS = [1, 3, 5, 10, 20]
PRE_DAYS = 10
MAX_H = 20


def load_purchase_events():
    events = []
    f = DATA / "insiders.json"
    if f.exists():
        events += [dict(e, src="live") for e in json.loads(f.read_text())["purchases"]]
    f = DATA / "events.json"
    if f.exists():
        events += json.loads(f.read_text())["events"]
    # dedupe by accession+date+ticker (live and backfill can overlap)
    seen, out = set(), []
    for e in events:
        k = (e["acc"], e["ticker"], e["date"])
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def fetch_prices(tickers, start):
    """Daily adjusted closes for tickers + SPY; SPY's index is the trading calendar."""
    got = {}
    for chunk in [tickers[i:i + 80] for i in range(0, len(tickers), 80)]:
        try:
            df = yf.download(chunk + ["SPY"], start=start, progress=False,
                             auto_adjust=True, threads=True)["Close"]
            if isinstance(df, pd.Series):
                df = df.to_frame(chunk[0])
            for c in df.columns:
                s = df[c].dropna()
                if len(s) > 5 and (c not in got or len(s) > len(got[c])):
                    got[c] = s
        except Exception as e:
            print(f"  price chunk failed: {e}", file=sys.stderr)
    return got


def study():
    events = load_purchase_events()
    if not events:
        print("no events yet"); return
    tickers = sorted({e["ticker"] for e in events if e["ticker"].isalpha()})
    start = (min(datetime.date.fromisoformat(e["date"][:10]) for e in events)
             - datetime.timedelta(days=40)).isoformat()
    print(f"{len(events)} purchase events · {len(tickers)} tickers · prices from {start}")
    px = fetch_prices(tickers, start)
    spy = px.get("SPY")
    if spy is None:
        print("SPY prices missing — abort"); return
    cal = spy.index

    per_event, car_paths = [], []
    for e in events:
        p = px.get(e["ticker"])
        if p is None:
            continue
        entry_date = pd.Timestamp(e.get("filed", e["date"])[:10])
        pos = cal.searchsorted(entry_date)          # first trading day ≥ filing
        if pos >= len(cal):
            continue
        d0 = cal[pos]
        if d0 not in p.index:
            continue
        i_t, i_s = p.index.get_loc(d0), spy.index.get_loc(d0)
        # BEFORE: 10 trading days into the event
        pre = None
        if i_t >= PRE_DAYS and i_s >= PRE_DAYS:
            pre = float((p.iloc[i_t] / p.iloc[i_t - PRE_DAYS] - 1)
                        - (spy.iloc[i_s] / spy.iloc[i_s - PRE_DAYS] - 1)) * 100
        # AFTER: abnormal return at each horizon (only if matured)
        after, path = {}, []
        for h in range(1, MAX_H + 1):
            if i_t + h < len(p) and i_s + h < len(spy):
                ar = float((p.iloc[i_t + h] / p.iloc[i_t] - 1)
                           - (spy.iloc[i_s + h] / spy.iloc[i_s] - 1)) * 100
                path.append(ar)
                if h in HORIZONS:
                    after[str(h)] = round(ar, 3)
            else:
                break
        car_paths.append(path)
        days_live = len(path)
        per_event.append({
            "ticker": e["ticker"], "insider": e["insider"], "role": e.get("role", ""),
            "date": e["date"][:10], "filed": e.get("filed", "")[:10],
            "value": e["value"], "src": e.get("src", "?"),
            "pre10": None if pre is None else round(pre, 2),
            "after": after,
            "days": days_live,
            "running": round(path[-1], 2) if path else None,
            "mature": days_live >= MAX_H,
        })

    # aggregates per horizon
    agg = {}
    for h in HORIZONS:
        v = np.array([ev["after"][str(h)] for ev in per_event if str(h) in ev["after"]])
        if len(v) < 3:
            agg[str(h)] = {"n": int(len(v))}
            continue
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if v.std() > 0 else 0.0
        agg[str(h)] = {"n": int(len(v)), "mean": round(float(v.mean()), 3),
                       "median": round(float(np.median(v)), 3),
                       "win": round(float((v > 0).mean() * 100), 1),
                       "t": round(float(t), 2)}
    # average CAR curve day 0..20 (varying N disclosed per day)
    curve = []
    for h in range(1, MAX_H + 1):
        v = [pth[h - 1] for pth in car_paths if len(pth) >= h]
        if len(v) >= 3:
            curve.append({"day": h, "car": round(float(np.mean(v)), 3), "n": len(v)})
    pre_all = np.array([ev["pre10"] for ev in per_event if ev["pre10"] is not None])

    # honest verdict
    m = [agg[str(h)] for h in HORIZONS if agg[str(h)].get("n", 0) >= 30]
    sig = [a for a in m if abs(a.get("t", 0)) >= 2]
    if not m:
        verdict = "TOO EARLY — not enough matured events yet; conclusions need N ≥ 30 per horizon."
    elif sig and all(a["mean"] > 0 for a in sig):
        best = max(sig, key=lambda a: a["mean"])
        verdict = (f"SIGNAL DETECTED so far: positive abnormal returns with |t|≥2; "
                   f"strongest at +{HORIZONS[[agg[str(h)] for h in HORIZONS].index(best)]}d. "
                   f"Still a statistical tendency — validate before any real use.")
    elif sig:
        verdict = "Significant but NEGATIVE/mixed — following these buys did not pay after market adjustment."
    else:
        verdict = "NO significant edge at any horizon after market adjustment (all |t|<2) — the honest null."

    out = {
        "updated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_events": len(per_event),
        "n_mature": sum(1 for ev in per_event if ev["mature"]),
        "pre10_mean": round(float(pre_all.mean()), 2) if len(pre_all) else None,
        "pre10_n": int(len(pre_all)),
        "agg": agg, "curve": curve,
        "events": sorted(per_event, key=lambda x: x["filed"] or x["date"])[-250:],
        "verdict": verdict,
        "method": ("Entry = filing-date close (what a follower gets). Abnormal = stock − SPY. "
                   "Horizons in trading days. Immature events excluded per-horizon."),
    }
    (DATA / "event_study.json").write_text(json.dumps(out, indent=1))
    print(f"study written: {len(per_event)} events ({out['n_mature']} mature) · verdict: {verdict}")


if __name__ == "__main__":
    study()

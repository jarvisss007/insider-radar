#!/usr/bin/env python3
"""
Honest validation of the event-study "SIGNAL DETECTED" verdict (+5d, |t|>=2).

event_study.py reports positive abnormal returns on ~725 insider-purchase events,
strongest at +5d (t ~ 2.3). That t-stat assumes 725 INDEPENDENT observations.
They are not independent: events cluster in calendar weeks (up to 85 in one week),
repeat on the same tickers (ONMD x22, CPIX x21), and share the same market factor.

Checks run here (event-level; the portfolio-level DSR/PBO gate already lives in
research/validate_signal.py):

  1. Reproduce the per-event abnormal returns EXACTLY as event_study.py computes
     them (entry = next-day OPEN after filing, AR = stock - SPY, same hygiene).
  2. Clustered inference: cluster-robust t by entry week, by ticker, and a
     week-block bootstrap. This is the honest replacement for the naive t.
  3. Placebo test: same tickers, same event count, random pseudo filing dates
     inside the same sample window -> distribution of mean +5d "abnormal" return.
     Where does the real number sit?
  4. Subperiod split: first half vs second half of events by filing date.
  5. Outlier sensitivity: 1% trim each side, median, win rate.
  6. Cost realism: entry-price profile of the sample and net mean at 20/40/80 bps
     round-trip, with the clustered t on the 40 bps net series.

Writes research/validate_event_study_results.json and prints a report.
Does NOT touch event_study.py or the collector.
"""
import datetime, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from event_study import load_purchase_events, fetch_prices, PRE_DAYS, MAX_H  # noqa: E402

RNG = np.random.default_rng(7)
N_PLACEBO = 500
N_BOOT = 4000
HOR = 5                      # the horizon the headline verdict rests on
COSTS_BPS = [20, 40, 80]     # round-trip cost scenarios


# ---------------------------------------------------------------- data prep
def build_arrays(px, pxo):
    """Per-ticker numpy arrays (dates int64, close, open) for fast lookups."""
    arr = {}
    for t in px:
        if t == "SPY" or t not in pxo:
            continue
        p, po = px[t], pxo[t]
        idx = p.index.intersection(po.index)
        if len(idx) < MAX_H + PRE_DAYS + 2:
            continue
        arr[t] = (idx.values.astype("datetime64[D]").astype(np.int64),
                  p.reindex(idx).to_numpy(float), po.reindex(idx).to_numpy(float))
    return arr


def ar_h(tick_arr, spy_arr, filed_day, h=HOR):
    """Replicates event_study.py: filing day located by searchsorted, entry at the
    NEXT trading day's open, AR(h) = stock close[i+h]/entry - SPY same. Applies the
    same sub-$1 and >75% single-day-move hygiene. Returns AR in % or None."""
    dts, cl, op = tick_arr
    sdts, scl, sop = spy_arr
    i_t = int(np.searchsorted(dts, filed_day))
    i_s = int(np.searchsorted(sdts, filed_day))
    if i_t + 1 >= len(dts) or i_s + 1 >= len(sdts):
        return None
    # event_study requires d0/d1 (SPY-calendar days) to exist in the ticker index;
    # approximate faithfully: ticker's own next rows must match SPY's d0/d1 dates
    if dts[i_t] != sdts[i_s] or dts[i_t + 1] != sdts[i_s + 1]:
        return None
    entry, entry_spy = op[i_t + 1], sop[i_s + 1]
    if not np.isfinite(entry) or entry < 1.0:
        return None
    lo, hi = max(0, i_t - PRE_DAYS), min(len(cl), i_t + MAX_H + 1)
    w = cl[lo:hi]
    with np.errstate(invalid="ignore", divide="ignore"):
        if np.nanmax(np.abs(w[1:] / w[:-1] - 1)) > 0.75:
            return None
    if i_t + h >= len(cl) or i_s + h >= len(scl):
        return None
    return ((cl[i_t + h] / entry - 1) - (scl[i_s + h] / entry_spy - 1)) * 100, dts[i_t + 1]


def cluster_t(x, groups):
    """Cluster-robust t for the mean (Liang-Zeger, CR0)."""
    x = np.asarray(x, float)
    m = x.mean()
    e = x - m
    s = pd.Series(e).groupby(pd.Series(list(groups))).sum().to_numpy()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m / se if se > 0 else 0.0, len(s)


def naive_t(x):
    x = np.asarray(x, float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0


def main():
    events = load_purchase_events()
    tickers = sorted({e["ticker"] for e in events if e["ticker"].isalpha()})
    start = (min(datetime.date.fromisoformat(e["date"][:10]) for e in events)
             - datetime.timedelta(days=40)).isoformat()
    print(f"{len(events)} raw events, {len(tickers)} tickers, prices from {start}")
    px, pxo = fetch_prices(tickers, start)
    if "SPY" not in px:
        sys.exit("SPY missing - abort")
    arr = build_arrays(px, pxo)
    spy_arr = (px["SPY"].index.values.astype("datetime64[D]").astype(np.int64),
               px["SPY"].to_numpy(float), pxo["SPY"].reindex(px["SPY"].index).to_numpy(float))

    # ---- real per-event ARs at +5d (mirroring event_study.py) ----------------
    rows, n_nopx = [], 0
    for e in events:
        t = e["ticker"]
        if t not in arr:
            n_nopx += 1
            continue
        filed = np.datetime64(e.get("filed", e["date"])[:10], "D").astype(np.int64)
        r = ar_h(arr[t], spy_arr, filed, HOR)
        if r is None:
            continue
        ar, entry_day = r
        rows.append({"ticker": t, "ar": ar, "entry_day": int(entry_day),
                     "entry_px": float(arr[t][2][int(np.searchsorted(arr[t][0], filed)) + 1])})
    df = pd.DataFrame(rows)
    dts = pd.to_datetime(df["entry_day"], unit="D")
    iso = dts.dt.isocalendar()
    df["week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    x = df["ar"].to_numpy()
    print(f"\n{len(df)} clean +{HOR}d observations "
          f"({n_nopx} events dropped: no usable prices from yfinance — note the "
          f"survivorship angle: delisted tickers vanish from yfinance)")

    res = {"n": int(len(df)), "n_dropped_no_prices": int(n_nopx),
           "mean": float(x.mean()), "median": float(np.median(x)),
           "win_rate": float((x > 0).mean() * 100)}

    # ---- 1) naive vs clustered t ---------------------------------------------
    res["t_naive"] = float(naive_t(x))
    t_wk, n_wk = cluster_t(x, df["week"])
    t_tk, n_tk = cluster_t(x, df["ticker"])
    res["t_cluster_week"], res["n_weeks"] = float(t_wk), int(n_wk)
    res["t_cluster_ticker"], res["n_ticker_clusters"] = float(t_tk), int(n_tk)
    # week-block bootstrap of the mean
    wk_groups = [g.to_numpy() for _, g in df.groupby("week")["ar"]]
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        pick = RNG.integers(0, len(wk_groups), len(wk_groups))
        boot[b] = np.concatenate([wk_groups[i] for i in pick]).mean()
    res["boot_p_le_0"] = float((boot <= 0).mean())
    res["boot_ci95"] = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    print(f"mean +{HOR}d AR {x.mean():+.3f}%  median {np.median(x):+.3f}%  "
          f"win {res['win_rate']:.1f}%")
    print(f"t naive {res['t_naive']:+.2f} | t week-clustered {t_wk:+.2f} ({n_wk} wks) | "
          f"t ticker-clustered {t_tk:+.2f} ({n_tk} clusters)")
    print(f"week-block bootstrap: P(mean<=0) = {res['boot_p_le_0']:.3f}, "
          f"95% CI [{res['boot_ci95'][0]:+.3f}, {res['boot_ci95'][1]:+.3f}]")

    # ---- 2) placebo -----------------------------------------------------------
    lo_day, hi_day = int(df["entry_day"].min()), int(df["entry_day"].max())
    ticker_counts = df["ticker"].value_counts()
    valid_pos = {}
    for t, cnt in ticker_counts.items():
        dts_t = arr[t][0]
        ok = np.where((dts_t >= lo_day) & (dts_t <= hi_day))[0]
        ok = ok[ok + HOR + 1 < len(dts_t)]
        if len(ok):
            valid_pos[t] = ok
    pmeans = []
    for b in range(N_PLACEBO):
        vals = []
        for t, cnt in ticker_counts.items():
            if t not in valid_pos:
                continue
            for i in RNG.choice(valid_pos[t], cnt):
                r = ar_h(arr[t], spy_arr, arr[t][0][int(i)], HOR)
                if r is not None:
                    vals.append(r[0])
        if vals:
            pmeans.append(np.mean(vals))
    pmeans = np.array(pmeans)
    res["placebo_reps"] = int(len(pmeans))
    res["placebo_mean_of_means"] = float(pmeans.mean())
    res["placebo_sd"] = float(pmeans.std(ddof=1))
    res["placebo_pctile_of_real"] = float((pmeans < x.mean()).mean() * 100)
    print(f"placebo ({len(pmeans)} reps, same tickers/counts, random dates): "
          f"mean of means {pmeans.mean():+.3f}%  sd {pmeans.std(ddof=1):.3f}%")
    print(f"real mean sits at the {res['placebo_pctile_of_real']:.1f}th percentile "
          f"of the placebo distribution")

    # ---- 3) subperiod split ---------------------------------------------------
    order = df.sort_values("entry_day")
    half = len(order) // 2
    subs = {}
    for name, part in (("first_half", order.iloc[:half]), ("second_half", order.iloc[half:])):
        v = part["ar"].to_numpy()
        tw, nw = cluster_t(v, part["week"])
        subs[name] = {"n": int(len(v)), "mean": float(v.mean()),
                      "t_naive": float(naive_t(v)), "t_week": float(tw),
                      "from": str(pd.to_datetime(int(part['entry_day'].min()), unit='D').date()),
                      "to": str(pd.to_datetime(int(part['entry_day'].max()), unit='D').date())}
        print(f"{name}: n={len(v)} [{subs[name]['from']}..{subs[name]['to']}] "
              f"mean {v.mean():+.3f}%  t_naive {naive_t(v):+.2f}  t_week {tw:+.2f}")
    res["subperiods"] = subs

    # ---- 4) outlier sensitivity ----------------------------------------------
    q1, q99 = np.percentile(x, [1, 99])
    xt = x[(x > q1) & (x < q99)]
    res["trimmed_1pct"] = {"n": int(len(xt)), "mean": float(xt.mean()),
                           "t_naive": float(naive_t(xt))}
    print(f"1%-trimmed: mean {xt.mean():+.3f}%  t_naive {naive_t(xt):+.2f} "
          f"(untrimmed mean {x.mean():+.3f}%)")

    # ---- 5) cost realism ------------------------------------------------------
    px_med = float(df["entry_px"].median())
    res["entry_price"] = {"median": px_med,
                          "pct_under_5": float((df['entry_px'] < 5).mean() * 100),
                          "pct_under_10": float((df['entry_px'] < 10).mean() * 100)}
    print(f"entry price: median ${px_med:.2f}, {res['entry_price']['pct_under_5']:.0f}% "
          f"under $5, {res['entry_price']['pct_under_10']:.0f}% under $10")
    res["net_of_cost"] = {}
    for c in COSTS_BPS:
        net = x - c / 100.0
        tw, _ = cluster_t(net, df["week"])
        res["net_of_cost"][str(c)] = {"mean": float(net.mean()),
                                      "t_naive": float(naive_t(net)),
                                      "t_week": float(tw)}
        print(f"net of {c} bps round-trip: mean {net.mean():+.3f}%  "
              f"t_naive {naive_t(net):+.2f}  t_week {tw:+.2f}")

    out = HERE / "validate_event_study_results.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
The validation gate for the insider-purchase signal.

The event study found positive abnormal returns through ~day 10. That is a FINDING, not a
strategy. This script asks the strategy question honestly:

  Build a calendar-time portfolio — each day, hold every stock whose insider purchase was
  filed within the last H trading days (equal weight) — hedge with SPY, charge round-trip
  costs, and run the daily return series of all H-variants through the backtest-overfitting
  toolkit (Deflated Sharpe, PBO/CSCV, minimum backtest length).

Choosing the best H after looking at results is a 5-trial selection — exactly what DSR/PBO
exist to police.

Costs: 40 bps round-trip (these skew small-cap; tighter than that is dreaming).
"""
import datetime, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # insider-radar/
sys.path.insert(0, str(Path.home() / "backtest-overfitting"))
import overfit                                 # noqa: E402
from event_study import load_purchase_events, fetch_prices, PRE_DAYS, MAX_H  # noqa: E402

HOLDS = [1, 3, 5, 10, 20]
COST = 0.004                                   # 40 bps round trip, charged on entry day


def clean_events(events, px, cal, spy):
    out = []
    for e in events:
        p = px.get(e["ticker"])
        if p is None:
            continue
        pos = cal.searchsorted(pd.Timestamp(e.get("filed", e["date"])[:10]))
        if pos >= len(cal):
            continue
        d0 = cal[pos]
        if d0 not in p.index:
            continue
        i_t = p.index.get_loc(d0)
        if p.iloc[i_t] < 1.0:                  # same hygiene as the event study
            continue
        win = p.iloc[max(0, i_t - PRE_DAYS):min(len(p), i_t + MAX_H + 1)]
        if win.pct_change().abs().max() > 0.75:
            continue
        out.append((e["ticker"], d0))
    return out


def main():
    events = load_purchase_events()
    tickers = sorted({e["ticker"] for e in events if e["ticker"].isalpha()})
    start = (min(datetime.date.fromisoformat(e["date"][:10]) for e in events)
             - datetime.timedelta(days=40)).isoformat()
    px = fetch_prices(tickers, start)
    spy = px["SPY"]
    cal = spy.index
    ev = clean_events(events, px, cal, spy)
    print(f"{len(ev)} clean events across {len({t for t, _ in ev})} tickers")

    # daily simple returns per ticker, aligned to SPY calendar
    rets = {t: px[t].reindex(cal).pct_change() for t, _ in dict(ev).items()}
    spy_ret = spy.pct_change()

    # calendar-time portfolios: entry at filing-day close → held days e+1 .. e+H
    t0 = min(cal.get_loc(d) for _, d in ev)
    days = cal[t0 + 1:]
    M = np.zeros((len(days), len(HOLDS)))
    for j, H in enumerate(HOLDS):
        for k, day in enumerate(days):
            i = cal.get_loc(day)
            legs = []
            for tick, d0 in ev:
                e_i = cal.get_loc(d0)
                if e_i < i <= e_i + H:
                    r = rets[tick].iloc[i]
                    if np.isfinite(r):
                        ar = r - spy_ret.iloc[i]
                        if i == e_i + 1:       # charge round-trip cost on first held day
                            ar -= COST
                        legs.append(ar)
            M[k, j] = np.mean(legs) if legs else 0.0

    active = (M != 0).any(axis=1)
    M = M[active]
    print(f"portfolio series: {M.shape[0]} trading days × {len(HOLDS)} hold-variants "
          f"(cost {COST*1e4:.0f} bps round-trip)\n")

    ann = np.sqrt(252)
    for j, H in enumerate(HOLDS):
        s = M[:, j]
        sr = ann * s.mean() / s.std(ddof=1) if s.std() > 0 else 0.0
        print(f"  hold {H:>2d}d: net Sharpe {sr:+.2f} · ann.return {252*s.mean()*100:+.1f}% "
              f"· worst day {s.min()*100:+.1f}%")

    rep = overfit.analyze(M, periods_per_year=252, n_splits=8)
    print()
    print(overfit.format_report(rep))
    out = HERE / "validation_report.txt"
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print(f"Insider-purchase signal validation — {datetime.date.today()}")
        print(f"{M.shape[0]} days × {len(HOLDS)} hold-variants, {len(ev)} events, "
              f"{COST*1e4:.0f} bps costs")
        print(overfit.format_report(rep))
    out.write_text(buf.getvalue())
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()

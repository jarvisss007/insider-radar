# Event-Study Validation — does "SIGNAL DETECTED" survive the honest bar?

**Date:** 2026-07-25 · **Code:** `research/validate_event_study.py` · **Numbers:** `research/validate_event_study_results.json`

`event_study.py` reports: *"SIGNAL DETECTED: positive abnormal returns with |t|≥2; strongest at +5d"*
on ~725 events. This document subjects that claim to the same bar used in `~/backtest-overfitting`,
`~/spy-trading`, and `~/strategy-lab`: no signal is believed until it survives honest validation.

**Bottom line first: the +5d "signal" does not clear the bar. The headline t≥2 is an artifact of
treating clustered events as independent. Week-clustered t = 1.31. After realistic costs it is dead
outright.**

---

## 1. What the event study actually computes (and what it does right)

- Event = deduped Form 4 open-market purchase (live feed + backfill), 881 raw events, 2025-07-01 → 2026-07-24.
- Entry = **next trading day's OPEN after the filing date** — this is the correct tradeable convention
  (no look-ahead; the insider's own trade date is not used for entry). Good.
- Abnormal return = stock − SPY (market-adjusted, no beta). Horizons = closes N days after filing.
- Hygiene: sub-$1 entries and >75% single-day moves excluded. Good.
- Per-horizon t = mean / (sd/√N), i.e. **assumes all N events are independent**. This is where it breaks.

## 2. Methodology critique — the pitfalls before any new numbers

1. **Cross-sectional dependence.** 669 clean +5d observations sit in only **55 calendar weeks**, and
   the weeks are lumpy: 85 events in the heaviest week, several weeks >20. Same-week events share the
   same market/sector shocks. Ticker repetition compounds it: ONMD appears 22 times, CPIX 21 — near-
   duplicate observations. Naive √N inference overstates precision badly.
2. **Benchmark quality.** SPY-adjustment only. These are mostly small caps (median entry price $12.15,
   33% under $5); their beta to SPY is not 1 and their factor exposure is small-cap/illiquidity, not
   the S&P 500. "Abnormal" here still contains small-cap factor return.
3. **Illiquidity / bid-ask bounce.** Entry at the yfinance OPEN of thin small caps is the auction print,
   often inside a wide spread. The +1d t of 3.59 (open→close of a single day) is exactly the horizon
   most contaminated by this. Mid-quote reality is worse than the printed open.
4. **Selection / survivorship.** 76 of 881 events (8.6%) were dropped because yfinance has **no usable
   prices** — largely delisted or defunct tickers (CXNU, EMBY, OCTO, KFS, …). Stocks that died after
   insider buys vanish from the sample. This biases the measured "abnormal return" **up**.
5. **One year, one regime.** The whole sample is Jul-2025 → Jul-2026. No cross-regime evidence exists.
6. **Distribution shape.** Median +5d AR is **−0.01%** and the win rate is **49.6%**. The positive mean
   is entirely a right-tail phenomenon: the typical follow-the-insider trade loses to SPY.

## 3. Robustness checks (all run on the exact per-event ARs, replicated from `event_study.py`)

### a. Naive vs clustered inference — the headline killer

| Inference | t-stat | Verdict at |t|≥2 |
|---|---|---|
| Naive (assumes 669 independent events) | **+2.31** | "significant" |
| Cluster-robust by entry week (55 clusters) | **+1.31** | not significant |
| Cluster-robust by ticker (372 clusters) | **+1.17** | not significant |
| Week-block bootstrap, 4000 reps | P(mean≤0) = 0.090 · 95% CI **[−0.36%, +1.90%]** | CI straddles zero |

The t≥2 exists only under the independence assumption the data visibly violates.

### b. Placebo test — the one check it passes

500 reps: same tickers, same per-ticker event counts, random pseudo filing dates inside the same
window. Placebo mean-of-means −0.065% (sd 0.351%). The real mean (+0.784%) sits at the
**99.2th percentile** of the placebo distribution.

Honest read: the real event dates do look special relative to random dates on the same tickers —
this is genuine, and it is the friendliest check here. Caveat: placebo dates spread evenly across
55 weeks, so the placebo sd *understates* the null variance for a sample as week-clustered as the
real one. Pass, with an asterisk.

### c. Subperiod split — positive in both halves, significant in neither

| Half | N | Period | Mean +5d AR | t naive | t week-clustered |
|---|---|---|---|---|---|
| First | 334 | 2025-07-02 → 2025-11-28 | +0.51% | +1.08 | **+0.52** |
| Second | 335 | 2025-11-28 → 2026-07-20 | +1.06% | +2.15 | **+1.81** |

Same sign both halves (mildly encouraging), but the first half is statistical noise and even the
stronger second half misses |t|≥2 once clustered.

### d. Outlier sensitivity

1%-trimmed mean +0.62% (t naive +2.19): the mean is not driven by one or two moonshots — it is
driven by the broader right tail (consistent with median ≈ 0, win rate <50%).

### e. Cost realism — where it dies outright

Entry-price profile: median $12.15, 33% of entries under $5, 45% under $10. For that profile a
20 bps round trip is optimistic, 40 bps is the standard used in `validate_signal.py`, 80 bps is
realistic for the sub-$5 third of the book.

| Round-trip cost | Net mean +5d | t naive | t week-clustered |
|---|---|---|---|
| 20 bps | +0.58% | +1.72 | +0.97 |
| 40 bps | +0.38% | +1.13 | +0.64 |
| 80 bps | −0.02% | −0.05 | −0.03 |

At the house-standard 40 bps the clustered t is 0.64. At the cost level appropriate for a third of
these names, the edge is exactly zero.

### f. Prior portfolio-level gate (already on file)

`research/validate_signal.py` (2026-07-07) ran the calendar-time portfolio version through the
backtest-overfitting toolkit: best-of-5 hold variants, Deflated Sharpe 0.411, **PBO 0.914**, verdict
**OVERFIT**. This event-level analysis and that portfolio-level analysis agree.

## 4. Verdict

**Signal survives the placebo test and outlier trimming, but dies at clustered inference and dies
again at costs.** Specifically:

- The +5d t≥2 in `event_study.json` is a naive-independence artifact: week-clustered t = **1.31**,
  ticker-clustered t = **1.17**, bootstrap CI includes zero.
- The median event **loses** to SPY (median −0.01%, win rate 49.6%); the mean is a right-tail story.
- Net of 40 bps the clustered t is **0.64**; net of 80 bps the mean is **negative**.
- Survivorship (8.6% of events unpriceable, skewed to dead tickers) biases even these numbers up.
- One year of data, one regime, and the portfolio-level DSR/PBO gate already said OVERFIT.

What would change this verdict: 2–3 more years of events (more independent weeks), a small-cap
benchmark instead of SPY, and the clustered +5d t holding above 2 net of 40 bps out-of-sample.
Until then: **interesting tendency, not a signal, and absolutely not a trade.** The viewer's
"SIGNAL DETECTED" banner should be read as "naive t≥2", nothing more.

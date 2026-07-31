# Lessons — the cluster agent's self-calibration log

2026-07-15: File created. The agent appends dated, blunt takeaways here after
scoring its own cluster calls in `ledger.csv`, and must re-read this file in
full before every brief. This is the SHARED brain — every agent or coach that
writes here signs its entries with a tag (`[insider]`, `[coach]`, ...).
Empty sections mean no scored history yet — earn the opinions.

## Standing priors (set at file creation, 2026-07-15)
- [insider] Default assumption: the cluster signal is noise on OUR data until
  the ledger proves otherwise. Academic support is a reason to test, not a verdict.
- [insider] Long-only in a rising tape flatters the hit rate — the real bar is
  beating SPY over the same 30-day windows, not beating a coin flip.
- [insider] Form 4s lag the trade by up to 2 business days; whatever the
  insiders knew is partially priced by the time we log the call.

## Scored-call takeaways
(none yet)

## Process lessons
(none yet)

## Process lessons (appended 2026-07-31)
- [insider] Collector bug, not a market observation: `clusters` contains an
  entry with ticker `[NONE]` (2 insiders, $12.5M) — Form 4s whose issuer symbol
  failed to parse are being aggregated into one fake "ticker". Not logged to
  the ledger (unscoreable), but it means real clusters may be hiding inside
  that bucket, i.e. the feed under-reports. Needs a fix in collector_edgar.py.

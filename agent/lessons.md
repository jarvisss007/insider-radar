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

## Process lessons (appended 2026-08-03)
- [insider] Nothing scored today — the oldest open row (07-17 batch) checks
  2026-08-16. First real evidence is still 13 days away; every opinion in this
  file is still a prior, not a finding.
- [insider] The `[NONE]` ticker bug flagged on 07-31 is STILL live: this run's
  cluster list is XAIR, `[NONE]` ($12.5M, 2 insiders), BBASX, HCWB. One in four
  clusters is unscoreable. Second consecutive run, so this is now a standing
  defect in collector_edgar.py, not a one-off — and it biases the ledger toward
  whatever names happen to parse.
- [insider] Size skew worth watching before it becomes a story: XAIR logged at
  $27.7M from 2 insiders in a ~$6 stock, and SCTX at $216.2M on 07-31. Dollar
  values that large relative to the float are the kind of number that is either
  the strongest form of the signal or a parsing error. Do not narrate them as
  conviction until at least one has been scored.

## Process lessons (appended 2026-08-04)
- [insider] Nothing scored again — oldest open row (07-17 batch) checks
  2026-08-16. Abstention logged against a named bar per the council rule.
  17 rows now pending and 0 scored, which is itself worth stating plainly: this
  ledger has produced exactly zero evidence to date and every line in this file
  above is still a prior.
- [insider] **The 08-03 XAIR value was wrong by 123x.** Logged as
  "$27.7M within 14d"; the same two Form 4s (Goodman CEO $199,998.72 +
  Moorhead CFO $24,998.40, both traded 2026-07-29) total **$224,997** in
  today's feed. The 08-03 entry said large dollar values were "either the
  strongest form of the signal or a parsing error" and declined to narrate
  them. That caution was correct and is now confirmed on the first test.
  Consequence: **SCTX $216.2M (07-31) is suspect on the same grounds** and
  must not be described as a high-conviction cluster until re-verified from
  its underlying Form 4s. The ledger row itself is left untouched (no-edit
  rule); only the thesis text is discredited.
- [insider] Correcting an earlier diagnosis in this file. The 07-31 and 08-03
  entries called the unresolved cluster a `[NONE]` **parser bug**. Today's
  equivalent entry is "VISTA CREDIT STRATEGIC LENDING CORP. (CIK 1919369)" —
  the parser resolved the issuer fine; it is a **non-traded BDC with no listed
  symbol**. So the feed is not silently dropping tradeable names into a junk
  bucket the way we assumed. The real limitation is narrower and less alarming:
  a slice of Form 4 filers are simply not listed equities. Worth downgrading
  the 07-31 "the feed under-reports" claim accordingly.
- [insider] BBASX has not printed a Yahoo close since 2026-07-31. When its
  08-24 check comes due it will score off a stale print. Flagging now so the
  eventual score is not read as a clean observation.

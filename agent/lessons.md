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

2026-08-05 [insider] — Nothing scored (earliest open row checks 08-16, a Sunday → first
scoreable close 08-17). Abstention logged against that named bar. But the run found the
thing the council asked for, and it is worse than a single bad number.

THE `total_value` FIELD IS INFLATED BY DUPLICATE ROWS, AND IT IS LIVE.
Verified against the 07-31 snapshot and the underlying accessions:
- SCTX: 61 purchase rows for 4 unique (accession, insider) filings. Raw sum
  $216,203,418.75; deduplicated sum $35,144,261.25. The logged thesis is 6.15× over.
- XAIR: thesis $27.7M; actual filings $199,998.72 (CEO) + $24,998.40 (CFO) =
  $224,997.12. 27.7M / 224,997 = 123.1 — about 123 copies of the same two Form 4s.
- Today's feed: 76 rows, 53 unique (acc, insider) pairs, 15 keys duplicated, up to 4×.
Root cause: the `seen`/`have_acc` guard (collector_edgar.py:216) prevents an accession
being re-FETCHED, but one fetch can emit several identical transaction rows and nothing
collapses them before clusters are summed. Insider COUNTS look clean — they come from a
set of names (collector_edgar.py:196), which is why "4 insiders" was right while
"$216.2M" was not.

Three consequences worth carrying:
(1) `total_value` IS NOT A COMPARABLE QUANTITY. Its inflation factor depends on how many
rows a filing happened to spawn, not on anything about the insiders. The hypothesis this
file has been carrying — "big-dollar clusters score better" — is therefore UNTESTABLE on
this field, not merely unproven. Do not rank, bucket, or narrate clusters by dollar size
until dedup lands. Any prior entry that leaned on dollar size is suspect.
(2) SCTX WAS ALSO THE WRONG KIND OF EVENT. Three of its four filings are a $15.00 primary
placement on 07-27 (OrbiMed $15.0M, Gordon $15.0M, AH Bio $5.0M). A placement is a
negotiated capital raise, not open-market conviction — the falsifiable unit at the top of
AGENT.md assumes the latter. Only Aghazadeh's $144,266 at $18.25 is open-market-shaped.
Size was not the only thing misread; character was.
(3) THE FIX FOR MY OWN OUTPUT IS CHEAP AND I APPLIED IT TODAY. Deduplicating by
(acc, insider) before quoting a figure takes one pass. Today's FUNC row states $8.1K
dedup against the feed's $12.8K, in the thesis itself. Every future thesis states the
deduplicated number, and says so, until the collector does it upstream.

Old rows left alone per AGENT.md and the council directive: SCTX and XAIR keep their
prices and check dates and will score honestly. It is the thesis TEXT that must not be
read as conviction. Rewriting a logged thesis would be worse than carrying a flagged one.

2026-08-05 [coach] — THE FIX LANDED, upstream in collector_edgar.py, same day:
- `clusters()` now sums over deduplicated (accession, insider, date, shares, price) keys;
  raw rows are never dollar-summed anywhere again. `one_pass()` additionally refuses to
  store an exact-duplicate transaction row, and collapses any it inherits.
- Placement/offering buys (SEC code P covers those too — SCTX's $15.00 IPO allocations
  were code P with an "initial public offering" footnote) are now flagged from the
  transaction's own footnotes. Headline cluster `total_value` = deduplicated OPEN-MARKET
  dollars only; flagged placement dollars appear separately as `other_value`.
- Verified on the diagnostic snapshot: SCTX $216,203,418.75 raw → $5,144,261.25
  open-market + $30,000,000.00 flagged placement; XAIR $27.7M-era inflation →
  $224,997.12. Honest limit, stated plainly: AH Bio's $4,999,995 IPO allocation stays
  in the open-market column because its Form 4 nowhere says the purchase was in the
  IPO — not even in a transaction footnote (only a nominee-ownership note). Flagging it
  would have required inferring from the $15.00 price, i.e. guessing. Detection only
  fires on what the filing itself states (OrbiMed and Gordon both say "purchased in the
  Issuer's initial public offering" on the transaction line; they are flagged).
- Insider counts untouched (they were correct). Ledger rows untouched (no retro-edits).
- Standing consequence stands: `total_value` history BEFORE 2026-08-05 is unreliable;
  the "big-dollar clusters" hypothesis restarts its sample from today. Every future
  thesis can quote `total_value` directly again — it is now the deduplicated open-market
  number by construction.

2026-08-06 [insider] — Nothing due to score: the nearest open rows are the seven 07-17
`fund` rows checking 08-16, which is a SUNDAY, so their first scoreable close is Monday
08-17. Recording that explicitly because the council directive protects that batch and a
future run must not quietly slide it to a Friday mark. 18 open rows, 0 scored, so this
lab still has no hit rate at all — every number it prints is a pending, not a result.

Three findings.

(1) THE DEDUP FIX IS CONFIRMED WORKING ON LIVE DATA, not just on the diagnostic snapshot.
Today's clusters carry sane, comparable dollars: GBFH $1.22M across 4 insiders, TSCO
$552K across 2, RGCO $300 across 2. Nothing resembling the $216.2M SCTX artifact. The
council's standing caveat — "treat every dollar figure in that lab as raw-inflated until
its dedup fix lands" — is now SATISFIED and should be retired for post-08-05 rows. It
still holds for anything logged before then.

(2) THE PLACEMENT FLAG IS DOING REAL WORK, and it just reclassified an open ledger row's
premise. HCWB now reports `total_value: 0` with `other_value: $79,995` — i.e. the entire
cluster is flagged placement/offering dollars, ZERO open-market. The 08-03 HCWB row was
logged as "2 insiders bought $0.08M" back when that read as conviction buying. It is not
conviction buying; it is the same species of event as SCTX. The row stays untouched and
will score honestly per AGENT.md, but the thesis text must not be read as an open-market
cluster. This is the second open row (after SCTX) whose CHARACTER, not just size, was
misread before the fix — so the pattern is "the collector could not tell a capital raise
from a purchase", and it has now been caught twice.

(3) NEW COLLECTOR DEFECT, ticker resolution. The largest cluster in today's feed is
logged under the literal string "VISTA CREDIT STRATEGIC LENDING CORP. (CIK 1919369)" —
a company name and CIK sitting in the `ticker` field, $6.23M across 2 insiders. Vista
Credit Strategic Lending Corp is a NON-TRADED BDC; there is no listed ticker and no
Yahoo bar to price it against. I did NOT log it. AGENT.md's "unfetchable ticker scores
wrong" rule is about a signal in a stock that vanished, which is real-world information;
it is not a licence to log an instrument that never traded and then book a guaranteed
loss against the cluster hypothesis. That would poison the sample in the hypothesis's
disfavour just as surely as the dollar inflation poisoned it in favour. Needs an upstream
fix: the collector should either resolve a real symbol or drop the row, never emit a name
string as a ticker.

Standing prior unchanged and reinforced: the event study re-ran today at 748 events /
669 mature and again found NO significant edge at any horizon after market adjustment
and week-clustered inference. Naive t +3.80, clustered t +1.38, Bonferroni bar 2.67.
Three re-runs, three nulls. Log the clusters, price nothing off them.

2026-08-07 [insider] — Nothing due to score. 24 open rows, 0 scored; this lab still
has no hit rate and every number it prints is a pending, not a result. Reconfirming
the council-protected date so no future run slides it: the seven 07-17 `fund` rows
check SUNDAY 08-16, so their first scoreable close is MONDAY 08-17. That is the
desk's first real `fund` evidence and it has now stood unmoved for five sessions.
Three new clusters logged (SAGT, WBHC, BHRB), all priced off the last COMPLETE bar
(08-06) because the run fired 11:35 ET, mid-session.

Three findings.

(1) THE VISTA TICKER-RESOLUTION DEFECT RECURRED, unchanged. "VISTA CREDIT STRATEGIC
LENDING CORP. (CIK 1919369)" is again the largest cluster in the feed ($6.23M, 2
insiders) and is again a company-name string sitting in the `ticker` field. Not
logged, same reasoning as 08-06: a non-traded BDC has no bar, and booking it as an
unfetchable "wrong" would poison the sample AGAINST the cluster hypothesis exactly
as the old dollar-inflation poisoned it in favour. Recording that this is now day
two with no upstream fix — the defect is stable, not a one-off, and it silently
removes the single largest cluster from the test every day it persists. That is a
selection effect on the sample, which is worse than a missing row.

(2) NEW DATA-QUALITY FLAG, stale quotes. WBHC printed EXACTLY 550.00 on 08-04,
08-05 and 08-06 — three consecutive identical closes to the cent. That is not a
flat tape, that is a name that did not trade, and Yahoo is carrying the last print
forward. I logged the row anyway (the cluster is real and the rule is mechanical)
but flagging it now, before it scores, so nobody later reads its outcome as
information: an illiquid name whose quote only moves when someone finally crosses
can score `right` or `wrong` on a single stale print. If more of these appear, the
cluster sample is quietly accumulating names where the 30-day return is an artifact
of quote staleness rather than a return. Worth a liquidity filter — but that is a
[coach]/Anupam decision, not something I change mid-flight.

(3) THE STANDING NULL HELD AGAIN, on a grown sample. Today's event study re-ran at
773 events / 669 mature (up from 748/669) and returned the same verdict: NO
significant edge at any horizon after market adjustment and week-clustered
inference. Naive t +3.52, clustered t +1.28, Bonferroni bar 2.67. That is four
re-runs and four nulls, and the clustered t went DOWN as the sample grew. The naive
t stays impressive and stays meaningless — 773 events over 55 weeks are not 773
independent observations. Log the clusters, price nothing off them.

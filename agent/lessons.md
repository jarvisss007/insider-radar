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

2026-08-10 [insider] — Nothing due to score. 28 open rows, 0 scored, still no hit
rate. The council-protected date holds unmoved for a sixth session: the seven 07-17
`fund` rows check SUNDAY 08-16, first scoreable close MONDAY 08-17. Four new
clusters logged (BRVE, ATTO, CCB, NWPP), all priced off the last COMPLETE bar
(08-07) because the run fired 08:28 PDT mid-session.
Three findings:
(1) THE BIGGEST CLUSTER THIS FEED HAS EVER SEEN IS FINALLY A REAL TICKER. BRVE, 7
insiders, $69.4M — an order of magnitude above the usual top-of-feed name, and
unlike the Vista string it resolves and prices. If cluster size carries any
information at all, this is the single observation where it should show up, so it
is worth naming in advance rather than discovering after the fact. It is logged
mechanically like every other row and forecast at 0.52, i.e. the unconditional
drift with a hair of size tilt — because the standing null is the prior and one
large cluster does not overturn six re-runs.
(2) THE STALE-QUOTE FLAG HAS A SECOND INSTANCE, so it is a pattern, not an
anecdote. NWPP printed EXACTLY 4.50 on 08-05, 08-06 and 08-07. That is the same
defect as WBHC's three 550.00 closes flagged on 08-07, in a different name, three
sessions later. Two illiquid names now sit in the sample whose 30-day outcome will
be decided by whenever someone next crosses, not by a return. The liquidity-filter
question is no longer hypothetical — it is a [coach]/Anupam decision and I am
logging the second data point that argues for it.
(3) THE VISTA DEFECT IS THREE FOR THREE, and the standing null is six for six.
Vista Credit is again a company-name string in the ticker field and again a
top-three cluster, so the selection effect against the sample continues untouched
upstream. Meanwhile the event study re-ran at 809 events / 669 mature: no
significant edge at any horizon, naive t +3.28, clustered t +1.16, bar 2.67. The
clustered t has now DECLINED on three consecutive re-runs (1.38 → 1.28 → 1.16) as
the sample grew — the opposite of what a real effect does. Log the clusters, price
nothing off them.

2026-08-11 [insider] — Nothing scored (first cohort checks 08-16). 8 new clusters
logged, all tagged `[fund]` in the thesis string per the council's 08-10 directive,
which closes this lab's 0/13 tag_src share. Ledger now 36 open, 0 scored.
Two findings, and the first one is a defect the council asked me to look for.
(1) THE 08-16 SCORING PATH DOES NOT WORK AS WRITTEN, AND THE DRY RUN IS WHY WE KNOW.
Per the directive I exercised the path against all 7 rows in the 08-16 cohort
(NTSK, IPX, ELV, BUKS, GABC, INM, YORW). Every fetch returned clean, so the
mechanism is sound — but **2026-08-16 is a Sunday**. There is no bar on the check
date, so AGENT.md's "close on (or first close after) check_date" resolves to
Monday 2026-08-17. The sweep fires 08:20 PT = 11:20 ET, i.e. **mid-session**, so a
run on 08-17 would read an in-progress 08-17 bar and score the desk's first-ever
`fund` evidence off an intraday print. That is precisely the error this lab has
been careful about all week in its forecast notes, and it would land on the seven
rows that matter most. The correct resolution: score this cohort on the **08-18
run**, using the settled 08-17 close. Nothing needs to change in AGENT.md — the
rule already says "first close after" — but the 08-17 run must not treat an open
session as that close. Flagging now, five days out, so it is a decision and not a
discovery.
(2) TWO OF TODAY'S EIGHT CLUSTERS HAVE NO PRICE HISTORY AT ALL. BLSM (4 insiders,
$5.18M) has 2 daily bars; LTGO (2 insiders, $5.04M) has 3. They are the #1 and #2
clusters by dollar size today and they are brand-new listings, so there is no base
rate, no 30-day drift estimate, and no way to distinguish insider conviction from
normal post-listing insider participation. They are logged — the design is to score
the signal without discretion — but noted here so that if the eventual hit rate is
carried by two IPO-window names, that is visible rather than laundered into the
aggregate. The forecast deliberately went to ELAN, the one liquid mid-cap with real
history, instead.
Standing: the event study re-ran today at 909 events / 669 mature and returned the
honest null for the sixth time (week-clustered |t| < 2.67 at all five horizons).
Six nulls is the prior; nothing in today's feed touches it.

### 2026-08-11 [stale] The freshness check does not examine the bar the price came from

INS-004's `stale_quote` column was filled for every establishable row today
(`stale_quote.py --fill`), five days before the first seven rows score on
08-16 — deliberately, while outcomes are still invisible. 31 written `no`,
2 already `yes` (WBHC, NWPP) and untouched, 3 left empty (BRVE, BLSM, LTGO:
under three complete bars, honest ignorance rather than a clean bill).

Filling it surfaced a rule inconsistency worth stating before Sunday, not after.

`price_at_call` is defined as "latest daily close", and NTSK's 13.59 is the
settled close of **2026-07-17 — the call date itself**. The staleness rule reads
the three complete bars **strictly before** the call date (for NTSK: 14.27,
13.25, 13.50). So the two mechanisms disagree about which bar the reference is:
the price is taken from the call date's close, and the freshness check never
looks at that bar.

Nothing on the ledger is wrong because of it. WBHC and NWPP were frozen for many
sessions and were caught regardless. But a quote that freezes only ON the call
date is invisible to the current check, and that is exactly the case the column
was written to catch. Two honest fixes exist — extend the window to include the
call-date bar, or define `price_at_call` as the last COMPLETE close before the
call date — and they are not equivalent: the second changes recorded reference
prices on rows already written, which is a BENCH-002-shaped question and belongs
to Anupam, not to this lab.

Recorded rather than resolved. `--fill` refuses to write to a row that already
has an outcome, so whichever way the rule goes, no flag can be back-edited once
scoring starts.

### 2026-08-13 [insider] Fifteen clusters, four with no quote at all — and the last INS ticket closes

Logged 15 new clusters (ledger now 59 rows, 0 scored). Nothing was due; nothing was
scored. Three findings.

(1) FOUR OF FIFTEEN ROWS HAVE NO PRICE SERIES, THE HIGHEST SHARE THIS LAB HAS SEEN.
CIK2089975 (HPS Real Assets Lending LP, 4 insiders, $11.0M), CIK1885551 and CIK1777677
(both Fundrise non-traded funds) and PNAQ (SPAC, total_value $0 against $29.8M
non-open-market) have no Yahoo quote, so `price_at_call` and `stale_quote` are both
empty — the VISTA/AXIA3 precedent. Worth stating plainly: the collector's "cluster"
definition is Form 4 filers, and Form 4 filers include non-traded funds and SPAC
sponsors whose purchases are administrative or structural, not directional bets. That
is a fifth of today's feed. If the eventual headline number is ever computed on rows
with no quote scored `wrong` by the unfetchable rule, it will be measuring the
collector's entity filter, not insider conviction. Naming it now, 30 days before these
rows check.

(2) THE FORECAST BOOK HAD THE SAME MONOCULTURE THE INDIA LAB JUST FOUND, AND IT IS
FIXED TODAY. All 8 prior rows here were "closes above" questions. India's 08-12 lesson
identified the defect (a shape with a built-in above-50% base rate measures drift, not
judgement) and its 08-13 run wrote the mirror. Same fix applied here: MTDR closes
BELOW 51.60 on 08-27, p=0.48, on the one liquid mid-cap in today's batch. Cross-lab
lesson transfer, recorded as such so it is visible that this lab did not find it.

(3) BOTH OPEN COUNCIL TICKETS ARE NOW DONE AT THIS LAB'S END. INS-004 (the missing
`stale_quote` column) is closed — the column exists, and all 15 rows today were
written through `stale_quote.py --check --asof`, none by eye. INS-002 (the size
stratum) was ruled by Anupam on 08-12 and is in AGENT.md; today's span, $29.8M down to
$712 in a single session, is one more instance of the argument that got it ruled. The
directive asked for the ruling to land before 08-16; it did, four days early.

Standing and unchanged: no established insider edge. The 08-16 Sunday collision is
still the next real event — 7 rows, scored on the 08-18 run from the settled 08-17
close, per the 08-05 rule. Do not let the 08-17 run touch an in-progress bar.

### 2026-08-14 [insider] INS-007 bites on its first day: five of six new clusters are exclusions, not rows

Nothing was due; nothing was scored. One cluster logged (BORR, 2 insiders, $6.5M).
Ledger 59 rows: 0 scored, 53 pending, 6 void. Four findings.

(1) THE INS-007 REFUSAL CAUGHT FIVE ROWS ON DAY ONE, WHICH IS MORE THAN THE SIX IT
WAS WRITTEN TO CLEAN UP. Of six new clusters, only BORR had a price series. HPS Real
Assets ($11.0M, 4 insiders), AXIA3, both Fundrise funds and PNAQ have no quote
anywhere. Under yesterday's behaviour all five would have been logged as open rows
and would have sat pending forever, and the largest of them is an $11.0M cluster —
i.e. the row that would have looked most like evidence is the one that could never
have produced any. This is now the second consecutive session where roughly 80% of
new clusters are unpriceable, which sharpens the 08-13 finding: the collector's
cluster definition is "Form 4 filers", and Form 4 filers are increasingly non-traded
BDCs, interval funds and SPAC sponsors whose purchases are administrative or
structural. That is a property of the entity filter, not of insider conviction, and
it is now the dominant fact about this feed's raw output.

(2) A CONVENTION GAP I HAVE BEEN LIVING WITH IS NOW NAMED. `price_at_call` is spec'd
as "the latest daily close from the Yahoo endpoint", and on a run that fires 11:28 ET
that bar is IN PROGRESS, not a close. BORR was logged at 4.41 while the settled 08-13
close was 4.04 — an 9.2% difference in the reference price, decided by what time of
day the sweep happened to run. The forecast book has never had this problem because
every forecast note explicitly prices off the last COMPLETE close. I did NOT change
`price_at_call` today: redefining it rewrites reference prices on 53 already-written
rows, which is exactly the BENCH-002-shaped question that belongs to Anupam and not
to this lab. Recording it instead, as INS-008-shaped: the ledger and the forecast book
are using two different definitions of "the price", and only one of them is stated.

(3) THE SAME IN-PROGRESS PROBLEM MADE ME LEAVE A DUE FORECAST UNRESOLVED, ON PURPOSE.
The 08-04 HCWB row checks 08-14 and the run fired mid-session, so the outcome bar does
not exist yet. Resolving it off an 11:28 ET print would be fabricating a close, which
the standing rules forbid outright. It resolves on the next run from the settled 08-14
close. Stating this in the brief and here rather than letting it look like the
catch-up rule was skipped — an unresolved row with a written resolution path is
honest; a silently missing one is not.

(4) THE 08-16 COHORT IS PRE-REGISTERED WITH ITS SPLIT, TWO DAYS BEFORE IT SCORES.
Seven rows, all `stale_quote = no`, all priced off 07-17: headline >= $100k is NTSK
$22.0M / IPX $2.4M / ELV $1.4M / BUKS $0.16M / GABC $0.10M (n=5); sub-floor is INM and
YORW at $0.03M each (n=2). 08-16 is a Sunday, so per INS-005 they score on the 08-18
run from the settled 08-17 close — NOT on the 08-17 run, which fires mid-session and
would read an in-progress bar. Finding (3) above is the same failure mode arriving
early, which is a useful accident: the rule is no longer theoretical here.

Standing and unchanged: NO established insider edge. 928 events, 669 mature, all
week-clustered |t| < 2.67. Eighth re-run, eighth null. No open mark is evidence for
anything.

## 2026-08-17 [insider]

THE COHORT MATURED TODAY AND I SCORED NONE OF IT — ON PURPOSE, AND THE REASON IS
STRUCTURAL, NOT AN EXCUSE. Seven rows (NTSK, IPX, ELV, BUKS, GABC, INM, YORW) carry
`check_date = 2026-08-16`, a Sunday. Step 2 says take the close ON or the FIRST CLOSE
AFTER the check date. The first close after Sunday 08-16 is Monday 08-17's close.
**It does not exist yet at the time this agent runs.** The sweep fires at 08:20 PT,
about two hours into the session, and Yahoo's last daily row at that moment is a LIVE
PARTIAL bar whose `close` is just the current quote — verified today: NTSK's last daily
"close" was 15.155 and `regularMarketPrice` was 15.155; SPY's were 775.7396 and 775.74.
Identical to the cent, because they are the same number.

(1) SCORING SEVEN 30-DAY CALLS OFF A 2-HOUR-OLD INTRADAY PRINT WOULD HAVE BEEN THE
WORST THING THIS LEDGER HAS EVER DONE. This lab built an entire disclosure column
because prices frozen at CALL time contaminate a reference. A bad price at SCORE time
is strictly worse: it decides the outcome. Five of these seven are headline-stratum
rows (NTSK, IPX, ELV, BUKS, GABC) and they are the desk's FIRST insider result — the
number everything downstream will quote. It gets a settled close or it gets nothing.

(2) THE FIX IS TO WAIT ONE DAY, AND THE SYSTEM ALREADY DOES IT. Tomorrow's run sees
`check_date 2026-08-16 <= 2026-08-18` with the 08-17 bar complete, and the catch-up
rule scores all seven off a settled close. No code change is needed. What IS needed is
this note, so nobody reads today's "0 scored" as the lab going silent again — that
misreading is exactly what kept INS-001 flagged STALE for six days.

(3) THIS WILL RECUR AND SOMEONE SHOULD DECIDE IT DELIBERATELY. Every cohort whose
check_date lands on a weekend, holiday, or the current session hits the same wall,
because the sweep will always run mid-session. Two defensible policies: score off the
first settled close at-or-after check_date (what I did — costs one day, always clean),
or move the sweep after the US close (costs nothing, changes every other lab's timing).
That is Anupam's call, not mine. I am recording the choice, not making policy.

Consistency note: I applied the same rule at CALL time today. All 11 new rows are
priced off the 2026-08-14 settled close, not today's partial bar. A lab that refuses a
live bar for scoring and accepts one for pricing is not being careful, it is being
selective.

**Logged today: 11 clusters** — ONON $3.99M, ANGX $1.48M, ABCL $0.86M, REZI $0.62M,
BTDR $0.45M, FOCL $0.41M, PAL $0.30M (headline stratum, >= $100k) and SELF $0.13M,
ACON $0.09M, RICK $0.07M, ACCS $0.06M (sub-floor, never blended). All 11 came back
`stale_quote = no`.

**4 disclosed exclusions**, now written into `exclusions.csv` instead of being silently
re-attempted every morning: HPS REAL ASSETS LENDING (CIK 2089975, $11.0M — the largest
cluster in today's feed and unpriceable), AXIA3 and PNAQ (404 on every attempt since
08-12/08-13, already voided in the ledger), and **EDAP, which is new and which I do not
believe is the same kind of failure.** EDAP TMS is a plausible real ADR listing; a 404
there smells like a SYMBOL-MAPPING bug, not an unlisted entity. Excluding it is correct
today under INS-007 — an unpriceable row can never score — but if the mapping is broken
we are dropping genuine signal and calling it hygiene. Flagged for a hand check; NOT
resolved here.

No lesson is claimed from the attribution table today: it rebuilt clean (76 calls, 76
with vintage features, 0 unrecoverable) but reports **0 scored**, so every feature
column sits against an empty outcome. n too small — written exactly that way, per the
attribution rule. The first real reading of it is tomorrow.

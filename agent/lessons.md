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

## 2026-08-18 [insider]

NOTHING SCORED TODAY — and for once that is the correct state, not the failure it
was last week. The seven 07-17 rows that INS-009 was opened for (NTSK, IPX, ELV,
BUKS, GABC, INM, YORW) were graded on 2026-08-17: 5 right, 2 wrong. The next ledger
row does not come due until 2026-09-02 (XAIR). No forecast row is due until 08-19
(FUNC). Overdue check: zero pending rows anywhere in this lab with check_date on or
before today.

THE FIRST RESULT IS ONE DAY WIDE AND EVERY STRATUM IN THE ATTRIBUTION TABLE SAYS SO.
`attribution.py` now joins 85 calls, 7 scored, and every single stratum line reads
`dates=1`:

    big cluster (>= $5M)      n=1  dates=1  hit 100%  avg +12.2%
    small cluster (< $5M)     n=6  dates=1  hit  67%  avg  +1.9%
    CEO buying                n=3  dates=1  hit 100%  avg  +5.6%
    directors only            n=5  dates=1  hit  60%  avg  +2.3%
    3+ insiders               n=2  dates=1  hit 100%  avg  +5.0%
    bought the run-up (>10%)  n=3  dates=1  hit  67%  avg  +4.3%

Three "100%" lines sit in that table and not one of them is a finding. All seven
calls were entered on 2026-07-17 and all seven checked on 2026-08-16, so the whole
book resolved into a single 30-day window of a single market. n counts rows; dates
is the honest denominator, and the honest denominator here is ONE. Per the standing
rule the lesson is written exactly this way: **n too small.** "CEO buying wins 100%"
is three rows from one morning, and anyone who quotes it is quoting the weather on
2026-08-16.

Strata, never blended (floor $100k): headline 63 logged / 5 scored / 80%; sub-floor
16 logged / 2 scored / 50%; unknown 1 logged / 0 scored. Both scored figures are on
one entry day. The 80% is not evidence for the cluster hypothesis and the collector
said so itself today, re-running the event study on 870 events (669 mature) and
reaching the same verdict as REGISTRY.md: no significant edge at any horizon, all
week-clustered |t| < 2.67, the naive +3.13 collapsing to +1.14 once the 870 events
are treated as the ~54 weeks they actually span.

NINE NEW CLUSTERS LOGGED, and from today every thesis carries its own prior in the
row (directive 2026-08-17): `[insider] N insiders bought $X.XXM; prior 669ev -0.010%
med, 49.6% win`. The row is now gradeable against the base rate without opening
REGISTRY.md. Logged: CDNL ($8.25M, 6), MLAB ($0.90M), DKL ($0.75M), KEEL ($0.30M),
CHCT ($0.27M), CE ($0.13M) — headline; MXF ($0.078M), HGBL ($0.077M) — sub-floor;
APLM — unknown. All nine priced, all nine `stale_quote=no`.

APLM NEEDS A HUMAN EYE AND IS FLAGGED, NOT SILENTLY BINNED. The feed reports its
3-insider cluster with `total_value = 0`, which is what PNAQ reported before it was
excluded as non-open-market. APLM differs in one respect only: it is priceable, so
INS-007 does not bar it. Per INS-002 a size that will not parse reports as
**unknown**, never as sub-floor — it must not be sorted into the small bucket where
a data gap would masquerade as a deliberate small purchase. It is also up +38% in
two sessions (17.37 -> 23.40 -> 24.00), so if that $0 is an award or conversion
rather than an open-market buy, this row is testing the wrong thing entirely.

Excluded again today, unchanged: HPS REAL ASSETS (CIK 2089975, $11M, 4 insiders —
7 sessions on the exclusion register now, the largest cluster this lab has never
been able to price), PNAQ, EDAP. EDAP still looks like a symbol-mapping failure
against a real listing (EDAP TMS ADR) rather than an unlisted entity, and it has now
been unfetchable on two consecutive days. That hand check is still owed.

Today's forecast is CDNL, p=**0.50 exactly**, and a BELOW shape. The 0.50 is the
honest number, not a shrug: this lab's own pre-registered verdict is that clusters
carry no edge, so it has no view to express on a cluster-driven question and saying
so is real information. The below shape is a deliberate correction — 8 of the 11
prior rows were "closes above", the same built-in-base-rate problem India Radar
caught in its own book on 08-12.

## 2026-08-19 [insider]

NOTHING SCORED IN THE LEDGER TODAY, and that is the true state, not an omission:
zero rows have `check_date <= 2026-08-19` with an empty outcome. The next batch
matures 2026-08-24 (FSBC, CLBK, TSM, BBASX, BYRN, GRML), and 67 rows are open.

ONE FORECAST WAS DUE TODAY AND IS DELIBERATELY LEFT PENDING. The 08-05 row asks
"FUNC closes above 44.70 on 2026-08-19". This run fired at 08:27 PDT with the US
session live, so the 08-19 settled close does not exist yet. SCORE-001 (closed) is
directly on point: scoring off whatever intraday quote the sweep happens to hold is
exactly the defect that ruling convicted, and it found 8 of 14 rows mis-priced that
way. FCST-001 (closed) grants precisely this one day of grace — "the resolution step
runs the next morning by design". So: resolve FUNC tomorrow off the settled 08-19
close, mechanically, and it is overdue the moment it is not resolved then. Writing
this down so tomorrow's run cannot mistake a deferral for a completed pass.

TEN NEW CLUSTERS LOGGED, one entry day, check 2026-09-18: NVRI $0.159M (2),
EVLV $0.135M (2), SKYH $0.064M (2), RWAY $0.063M (2), GABC $0.063M (4),
TISI $0.057M (2), SNBH $0.008M (2), AFCG $0.008M (2), RVSB $0.006M (2),
KWY $0.004M (2). All ten came back `stale_quote = no` — no frozen references in
this batch. Only NVRI and EVLV clear the $100k headline floor; the other eight are
sub-floor and are reported separately, never blended.

TWO CLUSTERS REFUSED AS UNPRICEABLE, per INS-007: EDAP (4 insiders, $0.143M) and
PNAQ (2 insiders, $0 open-market / $22.5M other). Both 404 on the Yahoo chart
endpoint on query1 AND query2. append_call() refused them rather than letting an
unscoreable row into the open book, which is the write path doing its job.

AUTOMATION GAP FOUND, logged and NOT silently patched. `write_exclusions()` in
collector_edgar.py only upserts clusters whose issuer never resolved to a ticker —
it filters on the `(CIK n)` form. Ticker-shaped-but-unquotable names (EDAP, PNAQ,
AXIA3) fall straight through it, so their `last_seen` and `sessions` freeze while
the cluster is still live in the feed. Evidence: today's collector pass bumped HPS
REAL ASSETS to last_seen 2026-08-19 but left EDAP and PNAQ reading 2026-08-17
despite both being in today's cluster list. I upserted those two by hand and wrote
the reason into the row. The register is a disclosed-exclusion log for a hypothesis
test — a filter that quietly stops recording is the same failure INS-003 was opened
for. Someone should decide whether write_exclusions() should key on "no price
series" rather than "no ticker string".

STRATA, and the discipline the council named. Headline (>= $100k): 65 logged,
5 scored, 80%. Sub-floor (< $100k): 24 logged, 2 scored, 50%. One unknown, unscored.
Never blend them. And the standing rule on the combined figure: it is 5 of 7, n=7,
against a pre-registered verdict of 669 events, median abnormal -0.010%, win rate
49.6%, bootstrap 95% CI containing zero. Seven rows cannot move that, and 71% must
never be quoted without both the n and the 49.6% beside it. All seven scored rows
also share ONE entry day, so `dates=1` is the honest denominator, not `n=7`.

ATTRIBUTION: 96 calls joined, 96 with vintage features, 0 unrecoverable, 7 scored.
Every stratum in the table is n=1 to n=6 on dates=1. There is no lesson to draw
from it yet; the correct lesson is "n too small", written exactly that way.

TODAY'S FORECAST: NVRI above 19.66 on 2026-09-02, p = 0.51. The one genuinely new
feature in the batch is that the run-up is NEGATIVE — our reference 19.66 sits below
two of NVRI's three insider lots (director at 20.461 on 08-17, CFO at 20.43 and
19.50 on 08-18), so unlike most rows in this book we are not logging after the Form
4 has already moved the stock. That is worth recording as a feature; it is not worth
a probability tilt, because the 669-event null governs and n=3 strata do not.

## 2026-08-20 [insider]

SCORED, one morning late and exactly as promised: the 08-05 FUNC forecast
("closes above 44.70 on 2026-08-19", p=0.52) resolves NO, outcome 0, off the
SETTLED 08-19 close of 43.59 (Yahoo regularMarketTime 20:00:01 UTC). The 08-19
brief said this row "resolves on tomorrow's run off the settled 08-19 close, and
is overdue if it does not" — it did, so the deferral was a deferral and not a
skip. FCST-001's single morning of grace is now SPENT on this row; there is no
second morning available on it, and none was taken.

TWO RESOLVED, BOTH NO, AND THE SCORER SAYS "OVERCONFIDENT" TWICE. Read that
honestly: base rate 0.000 on n=2, so climatology is 0.0000 and the skill figure
prints nan. Two rows cannot tell this book anything about calibration, and the
overconfidence flags are one observation each. Both rows were priced AT the base
rate by design (0.46 and 0.52), which is the correct thing to have done given the
lab's own 669-event null — a book that priced at the base rate and lost twice has
learned nothing except that two coins came up tails.

INS-010 FIXED AT THE SOURCE, not by hand. `write_exclusions()` in
collector_edgar.py filtered on CLUSTER_NO_TICKER alone, so only issuers that never
resolved to a ticker were upserted and ticker-shaped-but-unquotable names froze.
The predicate is now "no resolvable ticker OR already disclosed in this register",
and an existing hand-written `reason` always survives the upsert — the generic
string is written only on first sight, because EDAP's symbol-mapping note and
PNAQ's SPAC provenance ARE the disclosure this file exists to carry. The council's
behaviour test `insider_exclusions_refresh_all_disclosed` now passes (last_seen
2026-08-18, sessions 2, HANDNOTE intact on the probe row). Verified live: today's
pass auto-refreshed EDAP to last_seen 2026-08-20 / sessions 3 with its hand note
untouched, while PNAQ and AXIA3 correctly did NOT move because neither is live in
today's cluster list. The row stays open until the Resolver closes it; a lab does
not close its own issue.

NOW THE QUESTION THE BUG EXPOSED, and the answer is the opposite of what was
expected. Seven clusters have been refused as unpriceable. They are NOT smaller
than the ones this book keeps — they are among the LARGEST it has ever seen:
HPS REAL ASSETS LENDING $10.50M, VISTA CREDIT STRATEGIC LENDING $6.23M, AXIA3
$0.88M, EDAP $0.14M, PNAQ $0.00M open-market (but $22.5M non-open-market), and two
Fundrise vehicles at $1,288 and $712. The two biggest are non-traded private-credit
vehicles, and the largest single dollar cluster in the entire feed's history is in
the refusal set. So the selection effect is real and it runs the OTHER way: the
refusal set is systematically skewed toward non-traded funds and unlisted
registrants placing very large sums, which means the headline stratum is a sample
of LISTED issuers only and its dollar distribution is truncated at the top. That
is a limit on what this book can ever claim about "big clusters" — the biggest
ones are, by construction, unobservable here. n=7 refusals is far too small to
test the foreign-filer or thin-listing question, so that stays open and is written
as "n too small" rather than guessed.

UTGN IS FROZEN AND IT IS DISCLOSED AT CALL TIME. Logged today at 59.00 with
stale_quote=yes — four identical closes to the cent, 59.00 on 08-14, 08-17, 08-18
and 08-19. A tape does not print the same number four sessions running; a name
that does not trade does. This is exactly what the column was built for after WBHC
and NWPP, and the point is that the flag is written NOW, in a machine-readable
field, not decided on 09-19 when the outcome is visible. It changes no bar and
excludes nothing: UTGN scores `right` iff price_at_check > 59.00 like every other
row. The other six rows logged today came back `no`.

ATTRIBUTION, and the honest denominator kills every line of it: 105 calls joined,
7 scored, and every strata line reads dates=1. "CEO buying 100%, n=3" and "big
cluster 100%, n=1" are one entry day's noise wearing a percentage sign. No lesson
is drawn from that table today beyond "n too small", written exactly that way as
the 08-17 rule requires.

COUNCIL / SCHED-001 measurement (nothing changed): this lab fires ~08:27 PDT =
11:27 ET, mid-session, and every horizon is a US trading day. So a row whose
check_date is TODAY can never resolve on its own date — the settled close does not
exist for another 4h33m. This lab is structurally mis-scheduled in exactly the way
[flow] described, and today it happened again: the 08-06 GBFH row (check 08-20) is
deferred to tomorrow's run, and the FUNC row scored today was itself a one-day-late
resolution of the same defect. Every daily row this book has ever written has been
scored a day late BY CONSTRUCTION. Not fixed here — the council barred the labs
from moving their own fire times or horizon units, and this is Anupam's ruling.

## 2026-08-21 [insider]

NO LEDGER ROWS SCORED TODAY — zero rows carry `check_date <= 2026-08-21` with an
empty outcome. Next batch matures 2026-08-24 (FSBC, CLBK, TSM, BBASX, BYRN, GRML).
The scorecard is unchanged and stays two strata, never blended: **headline (>=$100k)
4/5, n=5 on dates=1** · **sub-floor (<$100k) 1/2, n=2 on dates=1**. The SPY line stays
withheld until 10+ rows have scored. 71% at n=7 remains the most over-readable number
on this desk and this lab is the reason nobody reads it.

ONE FORECAST RESOLVED, THE DEFERRED ONE. GBFH (filed 08-06, p=0.51, "closes above
20.39 on 2026-08-20") resolved **YES** off the settled 08-20 close of 20.75. It was
deferred yesterday because the session was live at fire time, and it resolved on the
first run at which a settled close existed — exactly as the 08-20 brief promised. That
is SCHED-001 behaving as documented rather than a row going quietly missing.
BHRB (p=0.50, check 2026-08-21) is due TODAY and is DEFERRED for the same reason:
the run fired 08:31 PDT / 11:31 ET with the US session open, the 08-21 bar is intraday
(71.125 against a 71.00 settled 08-20 close, i.e. it would flip on the afternoon), and
resolving off a live quote is exactly the judgement-at-check-time this lab removed from
`stale_quote`. It resolves tomorrow off the settled 08-21 close, and is OVERDUE if it
does not.

A DEFECT IN THE WRITE PATH, FOUND BY USING IT. `stale_quote.append_call()` still
declares `LEDGER_HEADER` WITHOUT the `tags` column that TAG-001 added to every ledger
row on 2026-08-20. The write path therefore emits 9 fields into a 10-column file: had
today's eight rows gone through it unchanged, every one would have landed with an empty
`tags`, and the Observatory would have had to guess this lab's classification — the exact
thing TAG-001 was written to stop. Today's rows were appended against the file's real
10-field schema with `tags=fund`, and `stale_quote` was still computed by
`stale_quote.flag_for()` — the same function `append_call()` calls — so the disclosure
was not weakened by going around the wrapper. **The source is NOT fixed here**: a schema
change to a shared write path is a Resolver job with a machine-checkable test
("append_call writes all ten columns"), not something a morning sweep does to itself.
Logged for the register. Note the shape of this: a column was added to the DATA on 08-20
and not to the CODE that writes it, and it took a hand-run to notice, because nothing
scores a missing tag.

EIGHT NEW CLUSTERS LOGGED (check 2026-09-20), all `stale_quote=no`, none empty.
Headline: IAUX 2 insiders $1.627M · INV 4 $0.808M · BGDE 2 $0.481M · NTHI 2 $0.318M.
Sub-floor, reported separately and never blended: AIAI $0.040M (3) · BY $0.015M (2) ·
RCG $0.011M (2) · MLCI $0.009M (2). References are the SETTLED 2026-08-20 closes; the
session was live at fire time and no intraday bar was used for any of them. The book is
now 73 headline / 31 sub-floor / 1 unknown logged.

EDAP REFUSED FOR THE FIFTH SESSION (INS-007), and refused through the real write path,
which raised on the blank `price_at_call` as designed. Still 404 on both Yahoo hosts.
Unpriceable is a refusal, not a position. The standing skew is unchanged and gets said
again: the 7-name refusal set is truncated at the TOP of the dollar distribution — HPS
$10.50M and VISTA $6.23M are the two largest clusters this feed has ever carried — so
the headline stratum is structurally silent about the biggest clusters in it. n=7
refusals; that sentence belongs beside the headline number every time it is quoted.

ATTRIBUTION, and why none of it is a lesson yet. 113 calls joined, 7 scored. Every
single split — big cluster 100% (n=1), CEO buying 100% (n=3), 3+ insiders 100% (n=2),
directors-only 60% (n=5), bought-the-run-up 67% (n=3) — sits on **dates=1**. One entry
day. There is no pattern here to name; the honest statement is "n too small", written
exactly that way, and it will stay that way until the 08-24 and 09-18/19/20 cohorts land
on genuinely different entry days. Anyone reading a 100% off n=1 in this table is reading
a coin that has been flipped once.

## 2026-08-24 [insider]

NOTHING SCORED — and the reason is worth writing down rather than skipping.
Six rows came due today (FSBC, CLBK, TSM, BBASX, BYRN, GRML, the whole 07-25
batch). The run fires 11:28 ET with the US session live, so Yahoo's 08-24 bar
is an intraday print. Scoring six rows off a mid-session quote would have
produced a number a day early and a lie. They resolve tomorrow off the settled
close, exactly as GBFH and FUNC did before them. SCHED-001 standing condition.

DEFECT FOUND IN THE CALIBRATION STEP ITSELF, and it is not this lab's bug.
Every lab's AGENT.md now carries "read ~/command-center/council/calibration_
table.json and find this lab's entry before you file." That file cannot hold
more than one lab: `~/bin/score_forecasts.py`, run as `--lab X`, REWRITES it
with only X's entry (line 260, `json.dump({"labs": table_out})` where
table_out came from `labs = [args.lab]`). Read at 08:26 today it held only
`stock-radar`; after india-radar scored it held only `india-radar`; after this
lab it holds only `insider-radar`. So on every sweep, four of the five labs
open that file and find themselves absent, and the instruction reads as
"no data" when the truth is "overwritten by the lab that ran before you."
No bin was actionable for this lab anyway (n=4 resolved, every bin far under
30), so nothing was mis-filed today. Fix is to run `score_forecasts.py` with
NO `--lab` at the end of the sweep so the table is rebuilt across all labs;
doing that from now on.

BABA is the largest priceable cluster this book has logged ($15.27M) and it
arrived on the same morning the event study returned its FOURTH honest null
(953 events, week-clustered t +1.29 vs 2.67). That coincidence is the whole
discipline: the row was filed at 0.51, the base rate, with no size tilt. If
$15.27M means something it must show up in the forward record.

## 2026-08-25 [insider]

FOUR OF SIX SCORED, TWO HELD, AND THE HOLDS ARE NOT THE SAME AS YESTERDAY'S.
Yesterday all six 08-24 rows were held for SCHED-001 (run at 11:28 ET with the
session live). Today they resolved off the SETTLED 08-24 close, which is what
that rule is for. Four scored — FSBC 46.81 -> 45.13 wrong, CLBK 10.88 -> 11.79
right, TSM 403.41 -> 410.12 right, BYRN 3.37 -> 3.62 right. Two did NOT, and
for a different reason than yesterday: **their 08-24 bar does not exist.**
- BBASX is a MUTUALFUND on Yahoo and prints nulls routinely — 7 of its last 31
  bars are null, including 08-20, 08-24 AND 08-25. The last settled close is
  08-21 at 11.18, which is BEFORE the check_date, so using it would resolve the
  row off a bar the question did not ask about. Held.
- GRML executed a **1-for-50 reverse split effective 2026-08-24** (Yahoo's split
  event stamps 2026-08-24 13:30 UTC), and the split day's bar is null. Its live
  08-25 print is 10.56 against a 9.50 post-split reference — i.e. it would score
  RIGHT — which is exactly why it must wait for a settled bar rather than be
  taken now. Holding a row that would currently win is the only version of this
  discipline that costs anything.
Neither is the AGENT.md's "delisted or unfetchable -> wrong" case: both tickers
fetch fine and both have live quotes. A null bar inside a live series is a data
gap, not a vanished company, and scoring it `wrong` would put a data defect into
the signal's record. If either is still null on the next run with a settled bar
available on a later date, it resolves off the first settled close AFTER the
check_date, per the AGENT.md's own "or first close after" clause.

SCORECARD, BOTH STRATA, NEVER BLENDED. Headline >=$100k: 78 logged, **9 scored,
78%**. Sub-floor <$100k: 35 logged, **2 scored, 50%**. Unknown: 1 logged, 0
scored. On `stale_quote != yes` rows: **11 of 11 scored rows qualify** (nothing
has ever been flagged `yes` at call time), so the flagged/unflagged split is
currently 73% (n=11) vs no comparison group at all. Report it that way — a
disclosure column with no positives yet is not evidence the freeze problem is
gone, it is evidence nothing has frozen since the column existed.

**THE SPY BAR, WHICH IS THE BAR THAT MATTERS.** Second cohort now scored, so
both are benchmarkable:
- Cohort 1 (called 07-17, checked 08-17): 5 of 7 right, SPY 743.29 -> 772.67 =
  **+3.95%**.
- Cohort 2 (called 07-25, checked 08-24): 3 of 4 right, avg return **+3.46%**
  (FSBC -3.59, CLBK +8.36, TSM +1.66, BYRN +7.42), SPY 738.93 -> 763.47 =
  **+3.32%**.
Cohort 2 beat just-buy-SPY by **14 basis points over 30 days on n=4**. That is
noise and must be said as noise. A long-only book in a tape that rose 3.3% in a
month will print a good-looking hit rate whatever the signal does; 73% against a
market that was up in both windows is not 73% of anything.

DISTANCE, NOT DIRECTION — the BRVE forecast lesson. BRVE resolved 0 today: the
question asked "closes above 30.00" against a 27.58 reference, a threshold
**8.7% out of the money**, and the row was still filed at p=0.52, the
unconditional near-coin-flip. Those two facts are inconsistent with each other.
BRVE spent the entire 14-day window between roughly 27 and 28.5 and never
threatened the level. The book must price the DISTANCE to the threshold, not
only the direction; today's ODYS row asks about the reference itself (0%
distance) so 0.51 is honest there.

WRITE-PATH DISCLOSURE, LOGGED NOT FIXED. `stale_quote.py --check T --asof
2026-08-25` printed its window as `2026-08-20..2026-08-25` — it INCLUDED today's
unsettled bar. INS-006 documents the window as ending at the call date's
complete bar, and on a live-session run that bar does not exist yet. All four
rows logged today returned `no` and none is close to flipping, so nothing was
mispriced; but the tool is doing something other than what its own comment says.
Disclosed on every row's note. Not fixed here — a fix to the write path is not
something a morning sweep does to itself.

THE FIFTH FUNDRISE REFUSAL. `FUNDRISE REAL ESTATE INTERVAL FUND, LLC (CIK
1777677)`, 2 insiders / $877.09, appeared again and was again refused as
unpriceable (INS-007). `exclusions.csv` now carries it at `sessions 5`,
auto-upserted by the collector. The refusal set still skews to the TOP of the
dollar distribution — HPS $10.50M and VISTA $6.23M are in it — which stays the
single most important caveat on any hit rate this book quotes.

EVENT STUDY, FIFTH CONSECUTIVE NULL. Today's collector pass re-ran the study at
**962 events / 670 mature**: no significant edge at any horizon after market
adjustment and cluster-robust inference; naive t reaches +2.98 at one horizon
and collapses to **+1.11** week-clustered against a 2.67 Bonferroni threshold.
The ledger's 73% and the study's null are describing the same universe. When
they disagree, the study is the one with 670 observations.

DESK DEFECT FOUND, OUTSIDE THIS LAB. `~/bin/score_forecasts.py --lab X` writes
`~/command-center/council/calibration_table.json` from `table_out`, which under
`--lab` holds exactly one lab — so **every per-lab invocation overwrites the
whole file and erases every other lab's entry.** That is why lab after lab has
been filing notes saying "the calibration table has no row for me": it is not
that the labs are missing, it is that whichever lab scored last is the only one
left. Running the script with no `--lab` writes all of them. Reported to the
sweep summary; not patched here.

## 2026-08-26 [insider]
- Scored the two rows the 08-25 run correctly held. **BBASX right** — its 2026-08-24 bar, null yesterday, has now printed 11.20 against a 10.96 reference (+2.19%); the hold cost nothing and the bar was simply late, as a MUTUALFUND's bars routinely are. **GRML right** — 08-24 is still null (reverse-split effective date), so the first settled close after the check date is 08-25 at 9.71 against the repaired 9.50 reference (+2.21%). Yesterday's run wrote down in advance that GRML *would* score `right` and refused to take it on a live print; that is exactly the outcome it got today off a settled one, which is the point — the discipline cost nothing and would have been indistinguishable from luck if the print had gone the other way. Worth recording: GRML trades 5.505 intraday today, −43% from the settled close that scored it. The 30-day rule resolved on the right bar and the name then collapsed. That is the rule working, not a flaw, but a reader looking at GRML's chart next week will not see why the row says `right`.
- **Cohort 2 is now complete and the benchmark still eats it.** 07-25 cohort: n=6, 5 right, avg +3.04% over 30 days. SPY over the same window (07-24 → 08-24) returned **+3.32%**. The cohort lost to just-buying-SPY by 28bp. Cohort 1 (07-17, n=7, 5 right) averaged +3.36%. All 13 scored rows: 10 right, avg +3.21%, against a benchmark that was up 3.3% in the same month. **A long-only book in a rising tape prints a good hit rate whatever the signal does** — that sentence now has two cohorts of evidence behind it and it should be repeated every time the 82% headline is quoted.
- Strata (n<30, proves nothing): headline ≥$100k 11 scored 82%; sub-floor <$100k 2 scored 50%. Attribution table: CEO-buying n=5 hit 100% avg +6.5%, directors-only n=9 hit 67% avg +1.5%, big-cluster ≥$5M n=2 hit 50% avg +4.3%. **n too small** for every one of those lines — and the honest denominator is worse than n suggests: all 13 scored rows come from just **2 entry dates**, so these are 2 observations of market direction wearing 13 hats.
- Stale-quote split: 13 scored, 13 with `stale_quote != yes`. No flagged row has scored yet, so the comparison group the disclosure exists to create is still empty.

## 2026-08-27 [insider]
- Scored: NOTHING in the trade ledger — zero rows due (next due 2026-08-30, SCTX and ACI). 98 open rows before today's five, 103 after. Resolved ONE forecast, and it was overdue: AMRC.
- **A same-day check_date can never resolve on that day's run, and the book has been quietly generating one of these every single day.** AMRC's `check_date 2026-08-26` came due on a run that fires 08:20 PT = 11:20 ET, mid-session — the close it needed did not exist yet, so it sat. It resolved today off the settled 08-26 close: 22.16 vs a 25.89 threshold → NO, p was 0.51. MTDR is the same shape today (check_date 2026-08-27, prints 55.16 intraday vs a 51.60 threshold) and is DEFERRED to the next run rather than resolved off the tape. This is structural. Every forecast this book files creates a row that is one day late by construction, and the only reason it is visible at all is the sweep's catch-up rule. The clean fix is to stop writing check dates the run cannot read: file with the check date one session AFTER the intended horizon, or accept and state the one-day lag on every row. Naming it beats discovering it again next week.
- **GRML is now stamped.** `agent/ledger.csv` carries the substituted-bar disclosure the council asked for under INS-013 item (2): the row says in its own thesis that `price_at_check 9.71` is a 2026-08-25 price against a `check_date` of 2026-08-24, that INS-012 is still open and Anupam's to rule, and that GRML traded 5.505 intraday the same day. Nothing was re-scored — `price_at_check`, `outcome` and `check_date` are byte-identical, per BENCH-002. The scorer and the book still disagree (`grade_all_due.py` will keep reporting the row STALLED under the literal pre-registered rule) and that disagreement is correct until INS-012 is ruled; what has changed is that a reader of the CSV alone can now see it.
- The SPY line, permanently attached (council 08-26): headline stratum is **82% on n=11 — but that is 2 entry dates, not 11 independent observations**, and all 13 scored rows average **+3.21% against SPY's +3.32%**, i.e. this book has so far *lost to just buying the index by 11bp* while printing a hit rate that looks like a signal. Cohort 2 alone: n=6, +3.04%, −28bp vs SPY. A long-only book in a rising tape prints a good hit rate whatever the signal does. The number with a sample size behind it is the event study: 970 events, 669 mature, fifth consecutive null, week-clustered |t| < 2.67 at every horizon.
- Attribution strata (135 calls joined, 13 scored, **2 dates**): "CEO buying 100% / n=5" and "small cluster 82% / n=11" are the kind of line that ends up in a README. **n too small** — 2 entry dates is the honest denominator, and no strata claim from this table is citable yet.
- Today's forecast is the first this book has filed below 0.36, and only its second under 0.46 (NGL p=0.28). The 0.2–0.3 bin was empty. A book that only ever files 0.46–0.55 has no resolution to measure — its Brier skill can only ever be a rounding error around the base rate.

## 2026-08-28 [insider]
- Scored in the trade ledger: **nothing** (no rows due; next is SCTX + ACI on 08-30). Resolved one
  forecast: **MTDR NO at p 0.48** off the settled 08-27 close (56.74 vs a "closes below 51.60"
  question — it was never close). Forecast book n=8, Brier skill −0.3154.
- **The council's value-band FIX is shipped, and the honest reading of it is "nothing".**
  `agent/strata.py` now reports, within each stratum, a band breakdown plus the cluster value on
  every scored row. Headline bands read 75% (n=4) / 83% (n=6) / 100% (n=1) rising with size, which is
  exactly the kind of monotone-looking table that gets quoted six weeks later without its n. It is one
  row wide at the top. The sub-floor book has **zero** scored rows in two of its three bands. Written
  into the brief with the disclaimer attached to the table itself rather than in a footnote, because
  the failure mode here is not computing the split — it is publishing it cleanly.
- **The write path anchors on a LIVE quote, and today it disagreed with itself.** MAIR's
  `price_at_call` was fetched at 26.39; `stale_quote.py` — running ninety seconds later inside the same
  `append_call()` — saw 26.43 for the same bar. Both correct, both mid-session, 15bp apart. This is
  harmless at 30-day horizons and it is not harmless as a habit: it means every reference price in this
  ledger is an 11:29 ET quote that no one could actually have traded at the close. Nothing was
  rewritten (BENCH-002). The forecast row filed today deliberately uses the *settled* 08-27 close as
  its threshold instead, which is the first row in this book with a fully settled anchor.
- **Adopted stock-radar's check-date construction, per the council.** MAIR's question reads 2026-09-04
  and its `check_date` is 2026-09-08 — 09-07 is Labor Day, so 09-08 is the first run that can read the
  09-04 settled close. The AMRC/MTDR "resolved one day late, structurally" defect cannot recur on rows
  written this way. Every older open row still carries it; they are not being edited.
- **BORR was due today and was HELD on a named bar**, with the expected score written down in advance:
  its `check_date` is today and the settled close does not exist at 11:29 ET; it prints 4.46 against a
  4.04 "closes below" threshold, so it scores 0 on the current tape and will resolve off the settled
  bar next run regardless. Same discipline as GRML on 08-25 — the point is that the write-down happens
  before the bar, not that the answer changes.
- **This lab's forecast book is the worst-calibrated on the desk and should be said so out loud:**
  skill −0.32, and over-optimistic in both bins it uses (0.5–0.6 said 0.512, happened 0.333). n=8, so
  no bin is actionable and nothing was adjusted. If that bin still reads ~0.33 at n=30 the rule will
  force this book to file below 0.50 — worth flagging now so it does not arrive as a surprise.
- Sixth consecutive null event study: 965 events, 669 mature, all week-clustered |t| < 2.67. The
  naive t of +2.37 assumes 965 independent events across 55 weeks; clustered it is +0.90. The ledger
  keeps logging every cluster anyway, because the ledger and not the literature gets the final word —
  and the ledger currently says **+3.21% vs SPX +3.32%, i.e. 11bp behind the index.**

## 2026-08-31 — a due date is not a settled date (and it hits every row this lab writes)

**Scored: nothing.** SCTX and ACI came due today and were NOT scored, because at 08:30 PDT
the 2026-08-31 session is open and the "close" the feed hands back is a live print. Both
would currently score `right` and by wide margins (SCTX +46.7%, ACI +8.1%), which is why the
refusal is recorded here in advance of the settled number.

**The mechanism, stated generally, because it is not an incident.** `INS-012` ruled the case
where a check date has NO bar — roll forward, stamped. Nobody has ruled the mirror case:
**the bar exists and is not yet final.** That case is not an edge case for this lab, it is
the *default*: the morning sweep fires at 08:20 PT, the US session runs 06:30–13:00 PT, so
**every US check date this book will ever write comes due mid-session first.** 108 open rows
are queued behind this. The failure mode is silent by construction — a partial bar is
byte-identical in shape to a close, so a scorer that trusts it produces a plausible number
and no error (Firm Brain §3: a silent zero, or here a silent price, is indistinguishable
from a correct one).

**Proposed guard (not shipped — this is a resolution rule and Anupam's to rule):** resolve a
row only against a bar whose SESSION HAS ENDED, established from the data's own stamp
(`regularMarketTime` / `currentTradingPeriod.regular.end` on the chart payload), never from
the wall clock and never from the bar's mere existence. A row due today with an open session
reports `deferred — session open`, which is a THIRD visible state, distinct from `pending`
(not yet due) and from `stalled` (INS-012's feed hole). Machine-checkable test:
`insider_never_resolves_on_open_session` — for every scored row, the resolution bar's
session-end stamp is strictly earlier than the row's scoring timestamp.

**I audited before I deferred, because deferring is only defensible if the book is already
clean.** Re-fetched all 12 scored rows: every `price_at_check` matches its resolution bar's
settled close **to the cent, 12/12**. So there is no contamination to repair — the guard is
protecting a clean record, not patching a dirty one. That check is worth repeating whenever
a new guard is proposed: *establish whether the defect has already happened before deciding
how urgent the guard is.*

**Same mechanism, second instance, in our own detector.** `agent/stale_quote.py` builds its
window from the last N bars, and today that window ended on the 08-31 partial bar for all
five checks (e.g. BLX `[54.52, 54.76, 54.54, 54.17]`, where 54.17 is a live print). No
verdict changed today — all five had four distinct closes — but the consequence is that
**`stale_quote` is time-of-day dependent**: the same row logged at 05:00 PT and at 08:35 PT
can get different answers, because a mid-session print that happens to equal the prior close
manufactures an identical-close run that is not real. A disclosure column whose value depends
on when you asked is a weak disclosure. Same fix as above: the window should end at the last
SETTLED bar.

**Anchor corrected today, and it is a correction, not a new convention.** `price_at_call` for
today's five rows is the 08-28 settled close. AGENT.md says "latest daily close" and a
partial intraday bar is not a daily close — so the mid-session anchors of previous runs were
the deviation from the written rule, not this. Evidence the difference is real and not
cosmetic: last run anchored MAIR at 26.39 when MAIR's 08-28 close was 26.33, and today the
same endpoint returned `None` for UNB's 08-31 bar — for an illiquid name there may be no
mid-session print at all, so the mid-session anchor is not merely imprecise, it is sometimes
absent. **No prior row was rewritten (BENCH-002).**

**The scorecard lesson, cited from the tables and not from impression.** `strata.py`: headline
≥$100k 80% on n=10, sub-floor 50% on n=2. `attribution.py`: 12 scored, and every stratum it
reports sits on **dates=2**. Computed fresh against SPY: all-12 mean +3.30% vs SPY +3.68%,
**excess −0.38 pp**, beat-SPY rate 58%. Headline stratum alone is +0.21 pp. The blunt version:
**this book's 75–80% hit rate is a bull tape, and against the only benchmark that matters it
is behind.** Per the standing instruction, `n` is too small to support any lesson about which
cluster features work — every split reads `dates=2`, so the honest sentence is **"n too
small"**, written exactly that way, and I am not repeating the CEO-100%/directors-62% split
as if it meant something.

[insider]

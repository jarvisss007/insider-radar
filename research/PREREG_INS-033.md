# INS-033/v1: does a $5 entry-price floor help the insider desk? Pre-registered forward test

Registered 2026-10-14 (Pacific), before the first cohort call is written (2026-10-15 morning run). Ruled by Anupam on 2026-10-14, about 20:30 PT, in reply to Claude's four-item proposal (register row INS-033). Paper only. Nothing in this file places, sizes or advises a trade.

`RULE_SHA` (SHA-256 of `json.dumps(RULE, sort_keys=True)` in `ins033_floor_test.py`; the evolution ledger entry INS-033/v1 carries it as `spec_sha256`):

```
ee0cbe2552899b062ec5eee6d051594fbe1a3a38c68de54d0e08c3d54642051b
```

`RULE` in `ins033_floor_test.py` is the authority. This page is the same rule in words. If the two ever disagree, the code is right and this page has a bug. The rule is frozen: a change is a NEW variant in the evolution ledger, never an edit.

## What this decides

1. The desk keeps trading exactly as it does. Nothing is bought, sized, exited or refused differently. This is a measurement of the desk's own forward rows.
2. The question: do the desk's longs priced at $5.00 or more beat small caps (IWM) by more than its longs under $5.00 do?
3. The idea came from this same desk's data. In the audit of 2026-10-13/14, the 48 insider longs under $5 lost $7,772 (45 of them, $7,258, in the audit's snapshot), while the 66 at $20 and up made $331. That is a cut found after looking at many cuts. It counts as a mined hypothesis and carries a luck tax (K = 20, below). Only rows called from 2026-10-15 on count. The in-sample rows are never evidence.
4. The answer comes on two dates only, 2026-12-31 and 2027-03-31. Before the first, the scorer prints counts and nothing else.
5. The likeliest answer at the first look is CONTINUE (not enough, or not clear enough). That is not a refutation and not a result. About 8 entry weeks per bucket gives this bar little power (table below).
6. A PASS only proposes a $5 floor to Anupam. Adopting it also needs 30 entry days in each bucket. A FAIL retires the idea for good, with no re-cut at $3 or $10.

## The hypothesis

Among insider-desk longs, **D** = (mean excess vs IWM of rows with entry price at or above $5.00) minus (mean excess vs IWM of rows with entry price under $5.00) is greater than 0.

## Population (the cohort)

- Rows of `insider-radar/agent/ledger.csv` with `call = long` and call `date` from **2026-10-15 to 2026-12-01 inclusive**.
- Calendar rule: the desk's exit clock is 30 days, so a call dated after 2026-12-01 cannot close by 2026-12-31. The window ends there so every row can be in the first look.
- Calls dated 2026-10-14 or earlier are in-sample, even if they fill at the 2026-10-15 open. They are never in the cohort. The first rows of the cohort are written by the morning run of 2026-10-15 and fill later.
- Scored means `outcome` is exactly `right` or `wrong`, as written by the 13:40 PT grader (INS-018). Blank means still open. A lowercase `void` is excluded. Voids and unfilled rows are printed per bucket.
- A pause of the insider desk ends the cohort on the pause date (see Pause).

## Bucket

- The bucket is set by `price_at_call` as **first written non-blank** by the INS-020 / INS-026 fill. Queued rows have a blank price until their fill session settles.
- The stamper (`ins033_floor_test.py stamp`) copies each newly filled cohort row into `agent/ins033_cohort.csv` ONCE, with `stamped_at`, the price as written, the bucket, and the fill session and price named in the fill note. A row already stamped is never touched again.
- A later restatement never moves a row between buckets. (This is what keeps a reverse-split basis repair, which can turn $0.19 into $9.50, from flipping a row.) The return still follows the ledger as it stands, so the row's return stays internally consistent; the scorer prints how many cohort rows were restated.
- Exactly **5.00 is in the at-or-above bucket (GE5)**. Under 5.00 is LT5. The comparison is decimal, never float.
- The stamp runs weekdays at 14:50 PT from `views-rebuild.sh`, after the morning fill, so "first written" is "first seen by the stamper, hours after it was written". If a price were restated within those hours, the restated price would be the one stamped. No such restatement is known; the stamp time is on every row so it can be checked.

## Metric (unchanged from the weekly desk review)

- The function is `desk_review.summarize('insider', rows, week_end)`, called as the desk review calls it, with the benchmark `desk_review.BENCHMARK['insider']` = IWM. A fixture test pins its outputs, and its source's SHA-256 is pinned in RULE, so a later edit to it turns a test red.
- Row return = `round((price_at_check - price_at_call) / price_at_call * 100, 2)` from the ledger. Dollars = the $2,000 lot (SIZE-001) times the return.
- Excess = row return minus IWM close-to-close from entry to exit, the IWM close on or before each date.
- Entry date is the date the desk review's own feed gives the row: the call date, unless a restated thesis names a fill session as "the YYYY-MM-DD official open". Exit is `check_date`. (A queued row actually fills at the next settled open, one session after its entry date; the IWM base is therefore the close on the call date. The desk review has always done this, and doing it identically in both buckets is the point.) A test pins the scorer's rows to the desk blotter's (`portfolio.js`) rows, return and dollars, for every closed insider row there (157 on 2026-10-14).
- A delisted or unfetchable `wrong` row, with no usable `price_at_check`, counts as a return of **-100%** (and -$2,000), in its bucket and per bucket in the printout. The desk's own blotter leaves such a row without a return; this test does not.

## Statistic

- Primary clustering is the **entry week** (ISO week of the entry date). A week's value is the mean excess of its rows. A bucket's value is the equal-weighted mean of its weeks. D is GE5's bucket value minus LT5's.
- The t statistic is a one-sided Welch t on the two buckets' entry-week values (sample variances).
- Printed beside it: D with rows pooled, and D with entry days as clusters (summarize's own mean of per-day means).

## Minimum n, in EACH bucket

At least **15 entry days**, at least **6 entry weeks**, and at least **30 rows**, counting scored rows that have a return and an IWM reading. Voids, open and unfilled rows never count toward n.

## Decision

- **PASS** needs all of: the minimum n met in both buckets; D > 0; Welch t at or above `max(2.67, Sidak z for K)` = **2.7992**; D still above 0 after dropping the best entry week of the GE5 bucket; and D still above 0 after dropping the best entry week of the LT5 bucket. "Best" means the week that does most for the floor: GE5's highest week, LT5's lowest week. PASS only proposes a floor to Anupam; adoption also needs 30 entry days in each bucket.
- **FAIL** is the minimum n met in both buckets and D at or below 0. The idea is retired permanently; there is no re-cut at $3 or $10.
- **CONTINUE** is everything else. At the final look (2027-03-31) CONTINUE closes the test undecided: there is no third look.

## Looks

2026-12-31 and 2027-03-31 only, at the same bar. The cohort is closed on 2026-12-01, so the second look reads the same rows plus any that closed late (an INS-012 roll or a stalled grading); it is a second reading of nearly the same data, not a new sample, and the bar is not loosened or tightened for it. Two looks at one bar slightly raise the chance of a lucky PASS; the late rows are few, so the rise is small.

## Counts only before a look

Before a look date `ins033_floor_test.py score` prints counts and the minimum-n progress. It does not fetch IWM, call `summarize`, or print D, t, hit rate, dollars or excess. A test enforces this by making the evaluator raise if it is reached.

## Shown, never judged

Hit rate vs IWM (the share of rows that beat it), "made money", dollars, and each bucket's own excess. They appear at a look beside the decision and are not part of it (Firm Brain section 20).

## Luck tax: K = 20

K counts the cells the audit looked at. The audit's own cut table was never saved (`council/audits/AUDIT_2026-10-14.md` has none), so the cells were rebuilt from the code of the deep dive that produced the audit and re-run on the in-sample insider ledger. The output is `research/INS-033_cuts_looked_at.txt`, and it reproduces the audit's headline numbers exactly (152 rows, -$9,589; 45 under $5, -$7,258; 66 at $20+, +$331).

| family | cells | note |
|---|---|---|
| price | 9 | seven bins from the cutoffs $1, $2, $5, $10, $20, $50, plus the two unions the audit text names (under $5, $20+) |
| side | 1 | degenerate: the desk logs longs only |
| desk | 1 | degenerate: this ledger is the insider desk |
| exit month | 3 | August, September, October |
| structure | 1 | degenerate: common stock, long |
| tenor | 2 | one real level (the 30-day clock); a second bin appears only because INS-020 moved 11 rows' entry dates |
| entry month | 3 | not one of the six named families, but the audit's same table printed it; counted, because an undercounted tax flatters the next idea |

K = 17 + 3 = **20**. The Sidak z is the one-sided normal critical value at the per-test level `1 - 0.95^(1/K)`, which is 2.7992 for K = 20 (it would be 2.3862 for the minimum K = 6 and 2.7464 for K = 17). The bar is `max(2.67, 2.7992)` = **2.7992**. The lab's usual floor of 2.67 is the week-clustered bar from `REGIME_SPLIT_2026-09-10.md`.

K is a lower bound. The audit also cut the whole account by desk, side, option structure and tenor, and those cuts are what pointed at the insider desk in the first place; they are not counted. On the insider ledger alone, desk, side and structure have one level each.

For reference, in-sample and mined, the table in the cuts file shows the $5 cut at D = +6.91 pp with Welch t +1.88 over 16.5 df (not significant even in-sample), and the $2 cut with a higher in-sample t (+2.89). The ruling fixed $5. INS-033 tests $5 only.

## Prior: what to expect

`research/ins033_power_sim.py` applies the frozen rule to simulated entry-week values: 8 weeks a bucket, spreads taken from the in-sample weeks (9.14 and 6.80 pp), 40,000 trials, minimum n assumed met. The real weekly values are fat-tailed and share market moves, so this is an upper bound on power.

| true weekly gap D | PASS | FAIL | CONTINUE |
|---|---|---|---|
| 0 pp | 0.7% | 50.2% | 49.0% |
| 3 pp | 4.0% | 23.0% | 73.1% |
| 6.9 pp (the in-sample size) | 18.2% | 4.4% | 77.4% |
| 10 pp | 40.9% | 0.6% | 58.4% |
| 15 pp | 80.4% | 0.0% | 19.6% |

Reading it: CONTINUE is the likeliest result for any real gap up to about 10 pp, and it is not a refutation. Two properties of the frozen rule are worth knowing now. If there is no gap at all, FAIL is a coin flip. And a real but modest gap of 3 pp would still be retired by a FAIL about one time in four. The rule was frozen as ruled; this is disclosed so a FAIL is read for what it is.

At the pace of the last 22 weekdays (about 3.5 calls a weekday, 38% under $5), the window yields roughly 120 calls over 8 ISO weeks, about 45 of them under $5. The minimum n is therefore likely to be met, but not certainly, in the LT5 bucket.

The lab's standing verdict is that the insider signal has no established edge (669 events, week-clustered t 1.31; `EVENT_STUDY_VALIDATION.md`), and the desk's own weekly review of the week ending 2026-10-09 reads it at t -0.08 against IWM over 29 entry days. A PASS here would still owe an edge-refute panel before anyone acts.

## Frozen through 2026-12-31

Cluster detection and any price or size filter; the INS-020 queued fill; the INS-026 settled fill; the 30-day clock and the INS-012 roll; the grader (INS-018); the $2,000 lot (SIZE-001); IWM as `desk_review.BENCHMARK['insider']`.

## Pause

A pause of the insider desk ends the cohort on the pause date. Rows called before that date count; rows called on or after it do not. Two things count as a pause: an `insider` key in `stock-radar/agent/HALTS.json` (the date is its `since=`), and a `PROPOSE-PAUSE` for insider (t at or below -2.0) in any weekly desk review dated on or after 2026-10-15 (the date is that review's week end). `stamp` writes the end date once to `agent/ins033_state.json`, so lifting the halt later does not reopen the cohort. A PROPOSE-PAUSE ends the cohort even if Anupam later declines the pause; that is the literal reading of the ruling.

## Implementation

| file | role |
|---|---|
| `ins033_floor_test.py` | RULE, RULE_SHA, `stamp`, `score`, `rule` |
| `agent/ins033_cohort.csv` | the stamped cohort; written only through `atomicio` under the book's lock |
| `agent/ins033_state.json` | the cohort end date, if a pause ever occurs |
| `research/INS-033_cuts_looked_at.txt` | the cut table and K; rebuilt by `research/ins033_cuts_looked_at.py` |
| `research/ins033_power_sim.py` | the prior table above |
| `tests/test_ins033_floor_test.py` | the pins: RULE_SHA, summarize, the 5.00 boundary, stamp idempotency and restatement, counts-only, the decision rule, pause, no truncating writes |

Run `/opt/anaconda3/bin/python ins033_floor_test.py score` any time; before 2026-12-31 it prints counts only. `stamp` is wired into `~/bin/views-rebuild.sh` by Anupam's session, not here.

## Disclosed at registration

- **Ledger drift.** `evolution_ledger.json` has `trials_total` 54 against the guard's 14 seeded + 39 variant entries = 53. The drift of 1 has stood since gen 16 and gen 20 and 21 recorded it. `hypothesis_miner.py` refuses to register while it stands, so INS-033/v1 is registered by hand as generation 22: `trials_total` 54 to 55, guard 14 + 40 = 54 against 55, the same drift of 1. It is not fixed here.
- **Choices the ruling left open, made in the build and frozen above:** D is computed on entry-week values; "best week" is the week that favours the floor, per bucket; the entry date is the desk's own convention (the call date for queued rows); a PROPOSE-PAUSE ends the cohort; CONTINUE at the final look closes the test undecided; K counts one-level families as 1 and includes entry month.
- **What would void this pre-registration:** a registered edit to RULE, to `desk_review.summarize`, or to anything in "Frozen through 2026-12-31" before that date. The tests are the tripwire for the first two.

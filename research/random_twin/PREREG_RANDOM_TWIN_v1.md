# RANDOM-TWIN/v1: is the insider desk's record insider skill, or just owning small stocks of its kind? (a measurement)

History of this page:
- **~22:45 PT, Friday 2026-10-30:** first draft, written before any twin return was computed.
- **~23:15 PT:** revised to fold the prereg-reviewer's conditions C1 to C13.
- **~23:55 PT:** revised again after the C14 re-check BLOCKed Twin A. Twin A became shown-only and only Twin B is judged
  (option (a), decided below).

The verdicts are quoted at the end. Paper only. Nothing in this file or its script buys, sizes, exits or refuses anything, and
nothing here changes how the insider desk is judged.

`RULE` in `random_twin.py` is the authority. This page says the same rule in words; if the two ever disagree, the code is right
and this page has a bug. `RULE_SHA` (SHA-256 of `json.dumps(RULE, sort_keys=True)`):

```
deca2c0ce78f453fc1241fc597e55486e1c1f9a4f52b32915f0e31b89b931d75
```

## What this decides, in plain words

1. **It is a measurement.** It never changes what the insider desk buys, how much, or when it exits.
   - It never overrides the standing ruling that the insider desk is judged against small caps, IWM: DESK-001,
     `desk_review.BENCHMARK['insider']`, INS-033's frozen metric and the 2026-09-10 regime study all stay as they are.
   - No desk reader consumes its output. A test pins that `desk_review*.py`, `portfolio_layer.py`, `firm_halt.py`,
     `portfolio_data.py`, `account.py`, `options_memory.py` and `ins033_floor_test.py` never read `random_twin*`. The test fails
     if any of them moves.
   - It does not touch INS-009, INS-033 or INS-035.
2. **The question it judges.** IWM tells us whether the desk beat small caps. It cannot tell us whether the desk's picks beat
   **other stocks of the same size and sector, bought on the same day and held the same way**. That is **Twin B**, and it is
   the only judged twin.
3. **Twin A is shown, never judged.** Twin A is the same stock, bought at random times after the trade. It is computed and
   printed with a caveat, and it can neither pass nor fail anything (see the decision below).
4. **Where the idea came from, stated so it cannot be dressed up later.**
   - The method is the pattern desk's matched random baseline (`spy-trading/research/PREREG_pattern_engine.md`: 20 random
     draws per signal, the week-clustered CR1 t).
   - The choice to apply it to the insider desk was **not** blind. It was made on 2026-10-30 after seeing this desk's record:
     the 10-30 review read t -1.03 against IWM, and the desk carried 17.8% of equity at risk against an 8% budget
     (`stock-radar/data/portfolio_risk.json`).
   - No cut of the insider data chose any threshold below.
5. **What a result can do.**
   - Only a FORWARD Twin B pass goes anywhere: to `/edge-refute`, then to Anupam. Nothing changes by itself.
   - A RETRO result of any kind, a TRAILS-TWIN or a NO-DIFFERENCE changes nothing: no pause, no size, no benchmark. DESK-004's
     burden v2 is BLOCKED, and this study is not a way round it.

## The C14 decision: option (a)

The C14 re-check BLOCKed Twin A. Its IWM adjustment assumes a beta of 1, and on zero-skill prices it read **BEATS-TWIN at beta
0.5 (+1.76 pp, t +3.60)** and **-2.72 pp (t -2.42) at beta 1.5**. Real betas are far from 1.

The reviewer offered two fixes:
- **(a)** make Twin A shown-only and judge Twin B alone, with K = 2;
- **(b)** estimate a beta per row, which owes another re-check.

**Decided (Claude, under Anupam's delegation "do whats necessary", 2026-10-30): option (a).** The reason:
> "(b) would keep the same-stock question but needs a per-row beta and another re-check; (a) answers the question IWM cannot —
> did the pick beat same-size, same-sector stocks on the same day — with a design both reviewers judged sound."

The other re-check's R1 (a per-row beta for Twin A, plus a beta-agreement gate) is answered by the same choice. A cell that is
never judged needs no gate.

## The book being measured

- **Rows:** `~/insider-radar/agent/ledger.csv`, every row with `call = long` and `outcome` exactly `right` or `wrong`. This is an
  allowlist: lowercase `void`, blank and anything else are out.
  - These are the lab's ledger rows. `portfolio_data.py` turns the same rows into THE ACCOUNT's insider desk.
  - Rows THE ACCOUNT withheld under PORT-006 are still lab calls, and they are measured. The count held vs withheld is printed,
    because desk_review's n follows THE ACCOUNT (Brain section 6). On 2026-10-30 all 212 scored rows were held.
- **The judged cells cover the whole desk, as DESK-001 does.** The INS-002 strata (at least $100k, under $100k, unknown, from
  `agent/strata.py cluster_usd`) are printed beside each cell and never blended without that line.
- **Desk return:** `(price_at_check - price_at_call) / price_at_call`, from the ledger as it stands. BENCH-002: it is never
  recomputed or rewritten.
- **Delisted rows:** a row scored `wrong` with no `price_at_check` (delisted or unfetchable) is left out of the judged cells and
  counted at -100% in a sensitivity line only. On 2026-10-30 there are none.
- **Entry:** the desk's own rule (INS-014 / INS-020 / INS-026).
  - If the row's note names a fill session, either `[FILLED YYYY-MM-DD official open` or `the YYYY-MM-DD official open` (the
    last one written wins), the entry is the **official open** of that session.
  - Otherwise it is the **settled close** of the call day.
- **Exit:** the desk's own rule. `check_date` is the call date plus 30 calendar days, moved to a session at write time. The exit
  is the **close of the first traded bar on or after `check_date`** (the INS-012 roll).
  - The holding span `S` is `check_date` minus the entry bar's date, in calendar days.
  - No scored row on 2026-10-30 carries a real `[INS-012: no bar on` stamp.

## Segments: seen rows and new rows are never mixed

- **RETRO** = rows with a call date on or before 2026-10-30.
  - Their outcomes, hit rates and IWM excess were seen before this page was written.
  - **RETRO-B** is read once, by the registered `run`, on the RETRO rows scored by its settled session: 212 rows over 12 entry
    weeks (ISO 2026-W29 to W40).
  - It is a **retrospective reading**, judged at the bar below. Whatever its verdict, it changes nothing and routes nowhere.
    Its sentence says so.
  - At the same run, Twin A is shown (NOT JUDGED) wherever its post-exit windows already exist. Most RETRO rows have none yet.
- **FORWARD** = rows with a call date from 2026-10-31 to 2027-05-28 (the first such call is the 2026-11-02 session). This is
  the confirmatory test.
  - **FWD-B** is read **once, on or after 2027-09-30.**
  - Before that date, `look` prints counts only. It builds no twin and computes no difference.
  - At the look:
    - Twin A is shown again for the FORWARD rows and for the RETRO rows, never judged.
    - RETRO rows scored after the run (open at registration, so their marks were seen) are shown in their own NOT JUDGED
      block, with no verdict and no overall sentence.

## Price data

- **The desk's own source:** Yahoo v8 daily chart bars, the same series the grader (`~/bin/grade_all_due.py`),
  `price_audit.py` and `stale_quote.py` read. They are split-adjusted, not dividend-adjusted. Dividends are ignored for the
  desk and both twins alike.
- **Settled bars only:** nothing dated after the run's settled session is read or cached
  (`stock-radar/sessions.py settled_session()`, the one calendar).
- **Carry-forward bars are dropped:** a bar with zero volume, or with no open or no close, is not a traded bar (Firm Brain
  section 18). It is never an entry, an exit or a roll target.
- **One fixed symbol set (R2):** every symbol a run needs (desk tickers, IWM, panel names) is read **once, up front**. Then the
  fetch gate is applied, and every row is computed offline from that fixed set. Network timing cannot change which twins a row
  may use.
- **Missing data is blank, with a reason, never zero.**
  - A transient fetch error is retried twice, never cached, and stays failed for the whole run.
  - Any transient failure on a desk ticker or on IWM refuses the run.
  - A panel name's failure gets its own reason (`panel_fetch_failed`, apart from `no_price_series`). If more than 5% of all
    symbols fail, the run writes nothing, and every failed name is listed.
  - Any git error (reading the feed's history, or checking the files and the ledger) refuses the run.
- **Reproducibility (R5):** every series the rows read is written beside the result as `bars_read_<asof>.json.gz`
  (deterministic gzip). It is **committed with `random_twin.json`**. Its SHA-256 goes in the JSON meta and in the ledger's
  result generation, beside the SHA-256 of `events.json` and of the list of feed vintages read.

## Twin B (JUDGED): same day, similar stock

- **Pool:** `research/random_twin/pool_universe_2026-10-17.csv`.
  - It is a slim, frozen copy (columns `name, exchange, type, typespecs, is_primary, market_cap_basic, sector`) of
    `~/spy-trading/data/saved_screens/universe.csv`, the TradingView scanner snapshot of 2026-10-17.
  - The source's SHA-256 is `76fe81b7cd2acec680608eef1cf73ad7ad93442cc69bf7131eef548653033bcf`. The copy's is
    `81b6152d89baa4d2ca5583fcdb50e8bdc175957fd747211aa9ff88221956648f`. RULE pins it, and `run` and `look` refuse any other file.
  - Rows kept: `type = stock`, `typespecs = common`, `is_primary = True`, with a market cap: 4,522 names on NYSE, NASDAQ and AMEX.
- **The desk ticker's cell:** its market-cap bucket and its TradingView sector, both from the same snapshot.
  - Buckets: micro under $300M, small $300M to $2B, mid $2B to $10B, large $10B and up.
  - If the cell has fewer than 10 pool names, the cell becomes the whole bucket. That happens to 1 RETRO row.
  - A desk ticker not in the snapshot has no cell, and Twin B is blank with that reason. On 2026-10-30 that is 43 of the 212
    scored rows: funds, ADRs, OTC names, secondary listings and large-float micro caps.
- **Panel:** a seeded sample of 30 names per cell (all of them if the cell has 30 or fewer), seeded
  `20261030|panel|<bucket>|<sector>`. Every row in a cell draws from the same panel. That is 1,202 panel names for the RETRO run.
  It estimates the cell's average without bias.
- **Eligible on the row's date:** a panel name other than the desk ticker that has all of:
  - a traded bar ON the desk's entry bar date (no substitution);
  - a settled exit at the first traded bar on or after the desk row's `check_date`, within 10 days;
  - no known insider purchase from 14 days before entry to exit;
  - no overlapping desk row of its own.
- **Holding:** the same entry type and exit as the desk row. **d_B = desk return - mean twin return.** Both are measured over
  the same dates, so no market or beta adjustment is involved.
- **Draw:** K_B = 20 without replacement, seeded `20261030|B|<ticker>|<call date>`. With 5 to 19 eligible, all are used. With
  fewer than 5, Twin B is blank.
- **"Known insider purchase" means:** the union of every purchase in the last committed vintage of each calendar day of
  `docs/data/insiders.json` (115 vintages, 2026-07-06 to 2026-10-30), plus the 1,062-event backfill sample in
  `docs/data/events.json`. Before 2026-07-06 only a sample is known.
- **Pool defects, and which way each leans:**
  1. **Survivorship:** names alive on 2026-10-17 only. Names that delisted earlier, mostly ones that fell, are missing. That
     lifts Twin B returns and leans **against** the desk.
  2. **The rows with no cell lean the other way.** The 43 rows with no cell had a mean desk return of **-5.52%**, against
     **-3.94%** for the 169 in the pool (computed from the seen ledger). Leaving them out leans **toward** the desk. A shown
     line compares rows with and without a cell.
  3. **Look-ahead in the cell:** market cap is from 2026-10-17, after most RETRO trades and before every FORWARD trade. A stock
     that fell moves down a bucket. This applies to the desk ticker and the pool alike.
  4. **Filtered snapshot:** the pool is the union of two wide pulls: market cap over $0.5B with float 10M to 600M, or float
     0.5M to 80M.
     - Mega-float names are absent, so the large bucket has none (UBER, TSM and BABA have no cell).
     - Low-priced micro caps with more than 80M shares floating are absent too.
  5. **Sector** is TradingView's classification. "Finance" mixes banks, REITs and insurers.
  6. **FORWARD caveats:** names listed after 2026-10-17 have no cell, and by 2027 the caps are a year stale.
  7. **Not matched on the beaten-down state.** Twin B matches size, sector and day, not a stock's fall before the buy. If
     beaten-down small stocks bounce, a desk could beat Twin B without insider information. A FORWARD pass would owe
     `/edge-refute` that question first.

## Twin A (SHOWN ONLY, never judged): same stock, another time

- **What it is:**
  - The same ticker, entered strictly after the row's own blocked window (its `check_date`, or entry bar if later, plus 10
    days) and up to 183 days after that.
  - Each twin uses the same entry type and the same span `S`, with the exit rolling at most 10 days and settled.
  - Excluded: windows overlapping any desk row of the ticker, windows with a known insider purchase from 14 days before entry
    to exit, and days IWM has no bar.
  - 20 seeded draws (`20261030|A|<ticker>|<call date>`), at least 5 or blank.
  - d_A = (desk - IWM over the desk's bars) - mean(twin - IWM over each twin's bars).
  - The share of twins before the entry is printed, and it is 0 by construction.
- **Why it is post-exit:** review 1 showed that a two-sided window drew 88 to 94% of twins before the entry, inside the pre-buy
  decline. That read **+4.41 pp (se 0.69)** on zero-skill dip-selected prices. The committed zero-skill worlds now read:

  | world | mean d_A | t | reading |
  |---|---|---|---|
  | entries after a fall of more than 35% | -0.58 pp (se 1.26) | -0.30 | no difference |
  | market regime shift | -0.50 pp (se 0.54) | -0.66 | no difference |
  | both together | +0.31 pp (se 1.06) | +0.25 | no difference |

  These worlds all assume a beta of 1.
- **Why it is not judged (the beta lean).**
  - The adjustment assumes beta = 1. The leftover term is **(1 - beta) x (IWM over the twin windows - IWM over the desk
    window)**. Every row in a regime shares it, so the week-clustered t overstates its precision.
  - Reviewer probes on zero-skill prices: **+1.76 pp (t +3.60) at beta 0.5**, **-2.72 pp (t -2.42) at beta 1.5**, and
    **-3.09 pp (se 0.70) at 1.6x IWM with a prior fall**.
  - Real betas: dry-cache panel median 0.70 (IQR 0.23 to 1.28), desk names about 1.5.
  - The sign of the lean in the real data is **not known in advance**. It depends on each stock's beta and on whether IWM did
    better or worse in the twin windows than in the desk's window.
- **Other defects:**
  - Post-exit twins inherit any insider information that lasts longer than 30 days.
  - Unseen insider buys before 2026-07-06 can sit near twins.
- **FORWARD windows are cut short at the look (C11c).** A 2027-05-28 call exits around 2027-06-28, so its twins can only be
  drawn from about 2027-07-08 to about 2027-08-30, not 183 days.
- It is printed with this caveat in its block, and it can neither pass nor fail.

## Metric and statistic (Twin B)

- **Per row:** d_B, in percentage points. A row with a blank twin has no reading. It is counted and its reason printed, never
  set to zero.
- **Cell value:** the pooled mean of d_B over rows with a reading.
- **t:** the CR1 cluster-robust t of that mean, clustered by the ISO week of the entry bar, with the G/(G-1) correction. This is
  the same formula as `pattern_engine_run.cr1_t`. Every n is printed with `clustered_by`.
  - Thirty-day holds overlap about four entry weeks, so 12 weeks is about three months of separate market paths.
- **Halves:** the cell's distinct entry weeks in time order. The first half is the first floor(G/2) weeks, the second half is
  the rest. The pooled mean of each half is printed.
- **Drop-best-week:** the pooled mean again, without the entry week with the largest sum of d (for a negative reading, without
  the smallest).
- **Week-mean-of-means:** the mean of the per-week means (Brain section 17).

## The bar

- **Judged cells:** K = 2, RETRO-B and FWD-B. Family alpha is 0.05, so alpha_K = 1 - 0.95^(1/2) = 0.02532, two-sided.
- **t_bar(G)** = max(2.67, the two-sided Student-t critical value at alpha_K with G - 1 degrees of freedom). That is 2.677 at
  G = 10 and 2.670 from G = 11 on.
- **Minimum n, per cell:** at least 10 entry weeks and at least 30 rows with a reading. Below that the cell is UNREADABLE.
- **Verdicts per cell:**

  | verdict | when |
  |---|---|
  | **BEATS-TWIN** | minimum n met, mean d > 0, t >= t_bar(G), mean d > 0 in both halves, still > 0 after dropping the best week, and week-mean-of-means > 0 |
  | **TRAILS-TWIN** | the mirror: mean d < 0, t <= -t_bar(G), both halves < 0, still < 0 after dropping the worst week, and week-mean-of-means < 0 |
  | **DATA-SENSITIVE** | the ledger reading is BEATS or TRAILS but the replica reading (below) is not the same. This is not a pass |
  | **NO-DIFFERENCE** | minimum n met and none of the above |
  | **UNREADABLE** | minimum n not met |

- **The sentence per segment:**
  - **FORWARD:** a BEATS-TWIN reads "beats same-day similar stocks". It goes to `/edge-refute` (the beaten-down state first)
    and to Anupam. Any other verdict reads NOT SEPARATED, or UNREADABLE.
  - **RETRO:** always "RETROSPECTIVE (verdict): ... changes nothing and routes nowhere".

## Shown, never judged (Firm Brain section 20)

- Twin A in full, with its caveat.
- The mean desk return, the mean Twin B return, the share of rows with d > 0, and the median d.
- The INS-002 strata.
- Rows with and without a Twin B cell.
- THE ACCOUNT held vs withheld.
- **The context line `context_iwm_same_bars_ret`:** IWM over the desk's own bars. It is context only; the desk review's IWM
  figure is still the judgement.
- **The replica reading:** the desk row re-priced from the twins' own Yahoo bars.
  - Rows where it differs from the ledger by more than 1.0 pp are listed, and so are rows whose `price_at_call` falls outside its
    entry bar's low-to-high range (with a 0.1% tolerance).
  - Why this matters: 97 close-entry rows predate INS-014/INS-020. For example SCTX's 20.40 was a mid-session print, against a
    call-day close of 19.48.
  - The replica's Twin B verdict feeds the DATA-SENSITIVE gate.
- **The -100% line** for delisted rows.

## Prior

- **The lab's standing verdict is that the insider signal has no established edge:** 669 events, median abnormal -0.010%,
  week-clustered t 1.31, bootstrap CI containing zero (`EVENT_STUDY_VALIDATION.md`).
- **A random-date comparison already exists:** 500 placebo samples put the real mean at the **99.2nd percentile** (REGISTRY
  H-INS-2).
- **The desk's own record:** the weekly desk review of 2026-10-30 reads n = 212, 42 entry days, hit rate 35.8%, mean day excess
  **-1.39 pp**, day-clustered **t -1.03** against IWM (KEEP).
- **What to expect:** NO-DIFFERENCE or TRAILS-TWIN on Twin B.
  - RETRO-B is not blind. It is largely predictable from the desk-vs-IWM figures already seen.
  - RETRO has 12 entry weeks, so it is thin. An honest RETRO "no difference" is not proof that there is no skill.

## Run discipline

- **The dry runs, disclosed (C13).**
  - `random_twin.py dry --limit 5` (first draft, 2026-10-30 ~22:40 PT) read five RETRO rows and saw their d values. Its output
    is `dry/dry_run.json`, SHA-256 `deb0841d090f95fb0a6cecd65b9ef347d10356061c28632473c49f47c4cca44e`, kept outside the repo.
    The rows, with d_A (the biased first-draft Twin A, never used) and d_B:

    | row | entry | d_A | d_B |
    |---|---|---|---|
    | NTSK 2026-07-17 | close | +19.41 | +9.09 |
    | GBFH 2026-08-06 | restated open | -3.05 | -3.30 |
    | FTHY 2026-09-28 | filled queued open | +1.54 | none, a fund |
    | SCTX 2026-07-31 | close | +83.60 | +36.90 |
    | IPX 2026-07-17 | close | +17.70 | none, not in the pool |

    SCTX was picked as an "INS-012 roll" by a selector that matched the text "distinct from INS-012 §3a voids". It is not a
    roll, and no scored row has a real INS-012 stamp. Its replica differs from the ledger by 7.1 pp.
  - The revised dry run (~23:20 PT, `dry/dry_run_v2.json`, SHA-256
    `ef240df216de319e93f71ef5e77aa8059a962934a121cf53be82952fa0212c66`) re-read four of the same rows, Twin B only. No INS-012
    row exists, so that slot was empty. The d_B values were identical. The rows stay in RETRO, which was seen anyway.
- **`random_twin.py run`: the one registered run (RETRO-B judged, Twin A shown).** It refuses unless every one of these holds:
  1. it is the committed repo copy;
  2. the prereg, the script, its test and the frozen pool are committed and clean;
  3. `evolution_ledger.json` has no uncommitted change;
  4. no git command fails;
  5. a generation with id exactly `RANDOM-TWIN/v1`, `trials_charged` = 2 and variant ids exactly `RANDOM-TWIN/v1/RETRO-B` and
     `RANDOM-TWIN/v1/FWD-B` (any status) freezes the current SHA-256 of all four files;
  6. no `RANDOM-TWIN/v1 result` generation exists.

  It writes `random_twin.json` and `bars_read_<asof>.json.gz` with the commit hash, RULE_SHA, the input hashes and the settled
  session in `meta`.

  **It is one-shot.** It refuses if `random_twin.json` exists or a result generation exists. A defect found after the run is
  `RANDOM-TWIN/v2`, and this v1 result stays primary. A script fix *before the look* may be frozen by a zero-trial
  `RANDOM-TWIN/v1 amendment` that cites an `issues.json` row whose own text names RANDOM-TWIN/v1.
- **`random_twin.py look`:** counts only before 2027-09-30. On or after that date, it runs once (the same refusals, with
  `RANDOM-TWIN/v1 look result` as the one-shot id) and writes `random_twin_look.json`.
  - It reads the RETRO rows only from a `random_twin.json` whose SHA-256 equals the one the `RANDOM-TWIN/v1 result` generation
    froze. Otherwise it refuses.
  - There is no second look and no extension.
- **A change to RULE** is a new variant (`RANDOM-TWIN/v2`) in the evolution ledger, never an edit.

## Evolution ledger (Brain section 7)

- **Registration:** the next free generation, before the run.
  - id `RANDOM-TWIN/v1`, trials_charged **2**, so trials_total **210 -> 212**.
  - The guard reads 14 seeded + 197 = 211 against 212. The standing drift of 1 (unreconciled since gen 16) is unchanged.
  - Variants: `RANDOM-TWIN/v1/RETRO-B` and `RANDOM-TWIN/v1/FWD-B`, status registered, claimed_sign 0 (the bar is two-sided).
  - frozen_sha256 covers this page, the script, the test and the pool copy.
  - It also discloses the dry-run rows and what the three reviews computed.
- **After the run:** a result generation, `RANDOM-TWIN/v1 result`, with result_commit and the SHA-256 of `random_twin.json` and
  of the bars-read gzip (read from the JSON meta and checked against the file). A later `RANDOM-TWIN/v1 look result` follows
  the look.

## Reviewer verdicts (verbatim)

**Review 1** (prereg-reviewer, agent a943275ce33e7529a, 2026-10-30 ~22:55 PT):

> **VERDICT: REGISTER-AS-VARIANT (= APPROVE WITH CHANGES).** It can't be registered or run as drafted. Twin A favours the desk by design, so it can read BEATS-TWIN with zero skill. Fold C1–C13 below, then get a re-check (C14) before the ledger generation is written. Deciding mechanism: Firm Brain s7 (rules freeze at registration, every judged cell is taxed) and Brain s8 (the forward record is the only record). Fix-before-freeze is the CPR-STUDY precedent: there, test worlds with no real effect caught built-in passes.

**Re-check A, C14** (prereg-reviewer, foreground, agent a7c32b31e74e4dc69, ~23:40 PT):

> VERDICT: BLOCK. C1 is folded only for its dip half. The IWM adjustment assumes beta = 1, and in the reviewer's own regime world with beta 0.5, Twin A reads BEATS-TWIN with zero skill. That is the same built-in pass review 1 called blocking (Brain s7: the rule freezes at registration; Brain s8). The Twin B cells, C2 to C13 and the ledger format are sound, with the fixes listed below.

Its fix (a), verbatim: "Demote Twin A to shown-only (C1's own fallback). K = 2 (RETRO-B and FWD-B), alpha_K = 0.02532, t_bar 2.677 at G = 10 and 2.67 from G = 11. State the overall rule on Twin B alone. Trials go 210 -> 212, and the guard reads 14 + 197 = 211 against 212. Twin A is still built at the look, but printed through the NOT JUDGED path with the beta lean and its sign. Once that is folded and these tests pass, no further re-check is owed."

**Re-check B** (prereg-reviewer, review 1's agent resumed, ~23:45 PT):

> **VERDICT: REGISTER-AS-VARIANT (= APPROVE WITH CHANGES): C1–C13 verified as folded in the code, except where R1–R6 narrow them; fold R1–R6 with tests, then register; no further review once they are folded and the suite is green.**

**Where each condition is folded:**

| condition | fold |
|---|---|
| C1 to C13 (review 1) | as listed in the sections above |
| C14-A (1) | option (a): Twin A is shown only, K = 2, 210 -> 212 |
| C14-A (2) | the look refuses unless random_twin.json matches the result generation's frozen SHA |
| C14-A (3) | any git error refuses |
| C14-A (4) | the no-reader test adds `options_memory.py` and fails if a named reader is missing |
| C14-A (5) | the page says one-shot, the forward Twin A window is cut short, and the beta lean has its sign and size |
| C14-A (6) | the ledger script fixes |
| R1 | answered by (a): a cell that is never judged needs no beta gate |
| R2 | the up-front fetch |
| R3 | the variant id set, whatever the status |
| R4 | the RETRO sentence never routes |
| R5 | the committed bars gzip |
| R6 | the no-reader test |

Each fold has its test in `tests/test_random_twin.py`.

**Built at the run as well as the look:** Twin A for RETRO is computed through the NOT JUDGED path at the run too, wherever its
post-exit windows exist. That adds no judged cell. Re-check A said "Twin A is still built at the look"; the run's copy is
display only.

## Implementation

| file | role |
|---|---|
| `research/random_twin/random_twin.py` | RULE, RULE_SHA, `rule`, `dry`, `run`, `look` |
| `research/random_twin/pool_universe_2026-10-17.csv` | the frozen Twin B pool |
| `research/random_twin/random_twin.json` | the one RETRO reading (written by `run` only) |
| `research/random_twin/bars_read_<asof>.json.gz` | every series the run read (committed with the result) |
| `research/random_twin/random_twin_look.json` | the one look (written by `look` on or after 2027-09-30) |
| `research/random_twin/cache/` | the working Yahoo cache (gitignored) |
| `tests/test_random_twin.py` | see below |

What `tests/test_random_twin.py` covers, with fixtures and no network:
- the RULE_SHA pin;
- the entry and exit conventions, and the carry-forward drop;
- both twins' exclusions and seeding, and the zero-skill worlds;
- that Twin A is never judged;
- the frozen pool, the replica gate, the week-mean sign, and the NOT JUDGED blocks;
- the registration refusals (including the variant set and git errors);
- the look's check of the RETRO result's SHA;
- the up-front fetch and the fetch gate;
- the strata, blank-not-zero, and the CR1 t;
- the segments, counts only before the look, and the RETRO sentence;
- that the script writes no book, and that no desk reader reads it.

# Insider Radar — Cluster Agent Instructions

You are the Insider Radar cluster agent. Your job is observation, scoring, and
self-calibration — NOT trade recommendations. Anupam's standing rule applies:
no claim of edge without validation; the ledger exists to prove or disprove
whether insider buy-clusters actually predict anything. The academic support
for clusters is the *hypothesis*, not the verdict — our own ledger is the verdict.

## The falsifiable unit

"Buy-cluster detected in ticker X on date D → price is HIGHER 30 calendar days
later." Every new cluster gets logged as a `long` call, automatically and
without discretion — the agent is scoring the SIGNAL, not its own taste.

## Run order (do all steps, in order)

1. **Refresh data**: run
   `/opt/anaconda3/bin/python /Users/anupampatil/insider-radar/collector_edgar.py`
   (one pass, no `--loop`) and confirm it exits cleanly. It updates
   `docs/data/insiders.json` (keys: `purchases`, `clusters`, `updated_utc`).

2. **Score due calls**: open `agent/ledger.csv`. For every row where
   `check_date <= today` and `outcome` is empty: fetch the ticker's latest
   daily close from Yahoo's free chart endpoint (same style as
   stock-radar/collector.py):
   `https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}?range=3mo&interval=1d`
   → `d["chart"]["result"][0]["indicators"]["quote"][0]["close"]`, take the
   close on (or first close after) `check_date`. Fill `price_at_check`, set
   `outcome` to `right` iff `price_at_check > price_at_call`, else `wrong`.
   No excuses, no "almost", no "it was up until last week". A delisted or
   unfetchable ticker is scored `wrong` — clusters in stocks that vanish are
   part of the signal's real-world record. Never edit or delete old rows otherwise.

3. **Update lessons**: if you scored anything, append dated, blunt takeaways to
   `agent/lessons.md` — running hit rate, any visible pattern (e.g. clusters in
   micro-caps score worse, big-dollar clusters score better, CEO-included
   clusters differ). Sign entries `[insider]`.

4. **Read the shared lessons**: re-read `agent/lessons.md` in full before
   logging or writing anything. It is the SHARED brain — any coach/grader
   writes there too. Do not repeat a pattern already identified as
   underperforming without noting the conflict.

5. **Log new clusters**: for each entry in `clusters` in `docs/data/insiders.json`
   whose ticker does NOT already have an open (outcome-empty) row in the
   ledger: append one row —
   `date,ticker,call,thesis,price_at_call,check_date,price_at_check,outcome,stale_quote`
   with `call = long`, `check_date = date + 30 calendar days`,
   `price_at_call` = latest daily close from the Yahoo endpoint above,
   thesis under 15 words STARTING with `[insider]` (state insider count and
   total value, e.g. `[insider] 2 insiders bought $22.0M within 14d`),
   `price_at_check` and `outcome` empty, and `stale_quote` filled per the
   section below — **every run, no exceptions**. One open row per ticker at a
   time; a ticker may be re-logged after its prior row is scored.

   **`stale_quote` — mandatory disclosure, decided at CALL time.** For each
   row you log, run:

   ```
   /opt/anaconda3/bin/python agent/stale_quote.py --check TICKER --asof YYYY-MM-DD
   ```

   (`--asof` = the call date; the tool reads only COMPLETE bars strictly
   before it, so it can never see the outcome.) Write the printed value —
   `yes`, `no`, or empty — into the row's `stale_quote` field. Empty means the
   series could not be established (unreachable ticker, brand-new listing with
   under 3 bars); an empty cell is honest, a guessed one is not. Never leave
   the field off, and never fill it from memory or by eye.

   Why: WBHC was priced off a quote printing exactly 550.00 for three sessions
   and NWPP off 4.50 for three sessions. Both were caught — in brief prose,
   which no scoring script can read. Without a column, the person scoring on
   the due date has to decide THEN which references were frozen, i.e. after the
   outcomes are visible. This field removes that judgement.

   It is a DISCLOSURE column and nothing else. It changes no bar, drops no row,
   excludes nothing, and scores nothing differently — step 2 still marks
   `right` iff `price_at_check > price_at_call`, for flagged rows exactly as
   for clean ones. Do not use it to filter the ledger or adjust a hit rate
   unless Anupam decides otherwise; report flagged and unflagged rows side by
   side instead. Never back-edit an already-written `stale_quote`.

6. **Write the brief**: create `agent/briefs/YYYY-MM-DD.md` (short):
   - **Feed state** (2 lines): purchases in feed, clusters live, data age
     from `updated_utc`.
   - **New clusters logged today**: ticker, insiders, total value — and the
     caveat that Form 4s lag the trade by up to 2 business days, so the
     insiders' entry price is not our entry price.
   - **Scorecard line**: hit rate so far and pending count. If hit rate exists,
     state it against the ~50% coin-flip bar plainly. Once rows start scoring,
     state the hit rate on all rows AND on `stale_quote != yes` rows, both
     with their n. Report both; do not pick one.
   - **Stale-quote line**: name any row logged today with `stale_quote = yes`
     or empty, and say which. Prose still helps a reader — it just is no
     longer the only place the flag exists.

## Hard rules
- `stale_quote` is written at call time and never revised afterwards. If a
  frozen name starts trading again, that is the NEXT call's business, not a
  reason to edit a written row.
- Never present a cluster as a buy signal or advice. The whole feed is
  "slow, statistical signal — not a trade trigger" (README); the ledger tests
  even that.
- If hit rate after 20+ scored calls is statistically indistinguishable from a
  coin flip, say so in the brief and flag it — the cluster hypothesis is then
  CONVICTED on our data regardless of what the papers say.
- The long-only design means a bull market inflates the hit rate. Note the
  SPY 30-day return alongside the scorecard when you have 10+ scored calls;
  beating a coin flip is not the bar — beating just-buy-SPY is.
- Keep the brief under ~25 lines.


---

## MANDATORY forecast — exactly one, every run, no exceptions

Append one row to `agent/forecasts.csv`. **This is not a trade call and not
advice.** Skipping a trade is free; skipping a forecast destroys the only
record that can ever prove whether your reads are worth anything. There is no
"no forecast today". If nothing is interesting, forecast the dull thing at 55%.

Why this is mandatory when trade calls are not: a hit-rate test needs tens of
thousands of observations to detect a real edge. A *probabilistic* forecast
carries information on every observation, so calibration becomes measurable in
hundreds. Abstention is correct risk management and fatal data policy — the
distinction is the whole point.

Format: `date,instrument,horizon_days,question,p,check_date,outcome,notes`

- `instrument` — a name with a fresh insider cluster.
- `question` — a **binary that resolves mechanically** from this lab's own
  refreshed data files, with zero judgement at check time. Good: "closes above
  today's close on <check_date>". Bad: "looks constructive".
- `p` — honest probability the question resolves YES, in (0,1). Never exactly
  0 or 1. Genuinely no view? Write 0.5; that is real information about your
  uncertainty and it scores fine.
- Prefer questions you are actually unsure about. Forecasting 0.99 on a
  near-certainty scores well and teaches nothing.

**Scoring:** on each run, resolve every row whose `check_date <= today` by
setting `outcome` to 1 (YES) or 0 (NO), mechanically. Then run:

```
/opt/anaconda3/bin/python ~/bin/score_forecasts.py --lab insider-radar
```

You are graded on **calibration, not on being right.** Saying 60% and being
wrong is fine. Saying 90% and being wrong repeatedly is not.

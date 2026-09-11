# Does insider buying stop working when the market falls?

Asked by Anupam on 2026-09-10, after a week in which the insider book went from +$4,233 to −$6,187 in open marks while small caps fell. Claim tested: *"insider doesn't work when the whole market is going down."* **Verdict: not supported.** In a falling small-cap market most insider picks lose money, as any long does, but they still beat small caps on average. When small caps rise, the picks lag them. Nothing clears the lab's significance bar against the benchmark this book actually tracks.

## Two claims, separated before testing
1. *Insider longs lose money when the market falls.* True of almost any long book; not the signal failing.
2. *Insider picks stop beating the market when the market falls.* The claim that would matter.

## Design, fixed before any result was seen
- 711 clean insider purchase events, 2025-07-02 → 2026-09-03, 55 entry weeks (1,095 on file after excluding 15 dated before 2024-06; 85 no prices, 48 calendar mismatch, 69 hygiene drops).
- Entry and hygiene rules identical to `validate_event_study.py`: next trading day's OPEN after the filing; sub-$1 entries and any >75% single-day move dropped.
- Horizons +5 / +10 / +20 trading days. **Judged on +20**, which matches the desk's ~30-calendar-day hold.
- Returns: raw; minus SPY (the lab's definition); minus IWM (small caps, the benchmark this book behaves like). IWM is taken from the same adjusted download as the stocks.
- Split A, **hindsight**: did IWM fall over the event's own window? Explains outcomes; can never be a filter.
- Split B, **knowable at entry**: was IWM's close below its 50-day mean on the filing day? The only split that could become a rule.
- Significance = week-clustered t. The lab's bar is |t| ≥ 2.67 (Bonferroni, 5 horizons). This table runs 24 comparisons, so the honest bar is higher still.

## +20 trading days
| cell | events | weeks | went up | small caps | vs small caps, mean | median | t (week) | beat small caps | vs SPY, mean | t (week) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 655 | 54 | 55% | +3.04% | −0.23 | −1.11 | −0.22 | 44% | +1.05 | +0.95 |
| A: small caps fell | 153 | 24 | **42%** | −2.29% | **+5.39** | +0.85 | +2.32 | 55% | +3.83 | +1.55 |
| A: small caps rose | 502 | 44 | 59% | +4.67% | −1.94 | −1.46 | −1.82 | 40% | +0.21 | +0.17 |
| B: entered below 50-day | 100 | **11** | 73% | +7.45% | +1.78 | +2.52 | +1.44 | 54% | +4.95 | **+3.81** |
| B: entered above 50-day | 555 | 49 | 52% | +2.25% | −0.59 | −1.11 | −0.48 | 42% | +0.35 | +0.27 |

## +10 trading days
| cell | events | weeks | went up | small caps | vs small caps, mean | median | t (week) | beat small caps | vs SPY, mean | t (week) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 655 | 54 | 57% | +1.64% | +0.19 | −0.11 | +0.29 | 49% | +0.88 | +1.32 |
| A: small caps fell | 202 | 32 | 50% | −1.95% | +2.44 | +2.10 | +2.64 | 65% | +0.96 | +1.02 |
| A: small caps rose | 453 | 42 | 60% | +3.24% | −0.81 | −1.65 | −1.00 | 42% | +0.85 | +1.00 |
| B: entered below 50-day | 100 | 11 | 71% | +3.67% | +2.23 | +0.39 | +1.70 | 52% | +4.05 | +3.27 |
| B: entered above 50-day | 555 | 49 | 54% | +1.27% | −0.18 | −0.22 | −0.25 | 48% | +0.31 | +0.43 |

+5 days is in `regime_split_results.json`; same shape, weaker.

## Reading it
- **In falling small caps, most picks lose money.** Only 42% went up over 20 days. Sense 1 of the claim is true, and it is true of any long book.
- **They still beat small caps.** The mean edge is +5.39 points and the median +0.85; 55% beat. Sense 2 of the claim is false in this sample. The mean far above the median says a few big winners carry it.
- **When small caps rise, the picks lag them** by a median 1.46 points. Falling less and rising less is what a book that is less sensitive to small caps looks like, with or without skill. A per-event beta is not yet estimated; until it is, do not read the down-market edge as skill.
- **The one cell over the bar is a benchmark artifact.** Entries made with small caps below their 50-day show +4.95 vs SPY with t 3.81 at +20. Those windows were sharp small-cap rebounds (+7.45%). Against small caps the edge is +1.78 with t 1.44, from only 11 weeks. Do not cite the SPY number.
- **The desk's own forward calls agree in direction.** Of 35 scored calls over 9 entry days, the 21 whose window saw small caps fall returned −0.19% but beat small caps by +2.72 points (76% beat). The 14 in rising windows beat by +4.21. Far too few to weigh.
- **This does not rescue the signal.** The lab's standing verdict stands: no significant edge after market adjustment and clustered inference, and it dies after realistic costs (`EVENT_STUDY_VALIDATION.md`). This study only says a falling market is not where it breaks.

## What to learn, and what not to
- **Learn:** insider longs are still longs. In a falling small-cap tape the book loses money even when its picks beat the market. That is exposure, not a broken signal. Judge the desk against small caps, not against zero or the S&P.
- **Do not learn:** "stop buying insider clusters when the market is falling." The evidence points the other way, and any such filter would be a pre-registration change (REG-PP-001) needing Anupam's ruling and a forward test.
- **What would change this:** a per-event beta near 1 with the down-market edge intact would make it look like skill; more independent down-market weeks, well beyond 24, would make it readable; a forward entry-time filter frozen through the Saturday evolution loop would test split B honestly.

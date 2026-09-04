# Insider Radar — Hypothesis Registry

Pre-registration for this lab. A hypothesis is written HERE, with its bar fixed,
BEFORE the data that tests it exists. Anything not written down before the test
is a story about the past.

**The standing verdict this registry sits on top of.** `research/EVENT_STUDY_VALIDATION.md`,
2026-07-25, on 669 events with prices:

| | |
|---|---|
| mean abnormal | +0.784% |
| **median abnormal** | **−0.010%** |
| **win rate** | **49.6%** |
| t naive | 2.31 |
| t clustered by week | 1.31 (55 weeks) |
| t clustered by ticker | 1.17 (372 clusters) |
| bootstrap 95% CI | **[−0.36%, +1.90%] — contains zero** |

**There is no established insider edge.** The headline t≥2 was an artifact of treating
clustered events as independent, and after realistic costs it is dead outright. Every
hypothesis below is an attempt to find a SUBSET where that changes — and each one starts
from the assumption that it will not.

---

## H-INS-1 · The $100k stratum (ruled 2026-08-12, live)

**Claim.** Clusters ≥ $100,000 carry information that sub-$100k clusters do not; blending
them measures two phenomena and reports one number.

**Registered before outcomes existed** — ruled 2026-08-12, four days before the first
seven rows scored on 2026-08-16, and implemented the same day in `agent/strata.py`.
The floor was chosen on a principle (large enough to read as a considered investment
decision rather than an administrative purchase), not on any result.

**Test.** Headline hit rate and mean excess on the ≥$100k stratum only, reported
separately from sub-floor, never blended. **Bar:** the headline stratum must beat the
sub-floor stratum by a margin significant across ENTRY DAYS, not rows.

**Minimum sample.** 30 independent entry days. The book currently has 9.

---

## H-INS-2 · The placebo gap (pre-registered 2026-08-12)

**Where it came from, stated so it cannot later be dressed up as a prediction.** The
validation run drew 500 placebo samples at random dates and the real mean landed at the
**99.2nd percentile** of them. That is a genuine tension with the same study's
zero-containing confidence interval: the effect looks unlike random dates while being
statistically indistinguishable from zero once clustering is respected.

**Claim.** Insider-purchase abnormal return is genuinely positive but **small** — of an
order that survives a placebo comparison and dies to transaction costs.

**Why that is worth stating rather than ignoring.** If true, the correct conclusion is
"real and untradeable", which is a finding, not a failure — the same shape as the crypto
1-minute edge (+1.38pp at z=5.21, worth 1/1,183rd of the fee). This lab should be allowed
to reach that verdict explicitly instead of drifting toward it.

**Test.** Forward events only, from 2026-08-13. **Bar:** mean abnormal > 0 with
week-clustered t ≥ 2.0 AND net of 60 bps round-trip costs still > 0. Failing the cost leg
while passing the significance leg confirms H-INS-2 as stated — real and untradeable —
and that is the expected outcome.

**Minimum sample.** 30 independent entry weeks.

---

## H-INS-3 · The second-half strengthening (pre-registered 2026-08-12) — WEAKEST

**Where it came from.** Splitting the 669 events in half: first half n=334, mean +0.506%,
t_week 0.52; second half n=335, mean **+1.061%**, t_week **1.81**.

**Read this caveat before the claim.** Splitting a sample in two and noticing one half is
stronger is something chance produces routinely, and **neither half is significant**. This
is the weakest hypothesis in the registry and is registered mainly so it cannot be
rediscovered later and presented as fresh. If it is ever cited as support for anything
before clearing the bar below, that citation is the error this file exists to prevent.

**Claim.** The insider-purchase effect is stronger in the recent regime than in the older
one — i.e. it is regime-dependent rather than constant.

**Test.** Forward events only, from 2026-08-13, compared against the FIRST-half mean of
+0.506% as the null — not against zero. Using zero would let the hypothesis pass on an
effect it does not claim. **Bar:** week-clustered t ≥ 2.5 against that null, reflecting
that this is the third hypothesis drawn from one dataset.

**Minimum sample.** 30 independent entry weeks. Until then this line is a note, not
evidence.

---

## What none of these may do

- No hypothesis here changes a bar, a threshold or a call while it is untested.
- No hypothesis may be tested on the 669 events that suggested it. Forward data only.
- The 36 rows open on 2026-08-12 are **not** evidence for any of them: at that date the
  book had 0 scored rows, all 36 check dates in the future, and open marks of mean +2.89%
  / median +1.96% that carried no benchmark and no survivorship charge. Open marks are
  not results, and the desk's survivorship note already prices this book at **+0.08pp net**
  of its own universe's drift — indistinguishable from the roster.

## PROPOSED 2026-08-22 — minimum cluster size (awaiting Anupam's ratification; NOT in force)
Observation, from the Calibration Observatory readout: 29 of 105 logged clusters (28%) total under
$100k of insider buying; the median cluster is $0.30M; the smallest call on the book is a $15k
purchase (BY). Every row also carries the lab's own base rate — 669 events, median −0.010%,
49.6% win — i.e. the prior for a generic cluster is a coin flip. Filing micro-clusters as calls
adds rows the base rate already predicts are noise, and the book stands at 98 pending / 7 scored.
Proposal (a pre-registration change, so it needs a name on it): clusters with total purchase
value below **$250,000** are LOGGED as observations but NOT filed as calls. Falsification bar
for the change itself: after 60 filed calls under the floor, the above-floor hit rate vs base
rate is compared to the all-cluster record; if the floor removed signal rather than noise, it is
withdrawn. Rows already filed are not moved. Nothing changes until ratified.

---

## PRE-REGISTERED 2026-09-04 — when this lab concludes the cluster question is UNFORECASTABLE by it
(Filed in answer to the Market Council's OPEN of 2026-09-03: *"at what n and what Brier skill do you
conclude the cluster question itself is unforecastable by this lab, rather than that the p's need
tuning? File it before the number gets close."* Filed at n=14 with skill −0.1499, i.e. while the number
is already bad but long before any stopping point, which is the only honest time to write it.)

**What I measured first, and it changes the shape of the answer.** Before choosing an n, I simulated the
operating characteristics of the very test the council asked me to pre-register — 40,000 trials per cell,
resampling from this book's OWN 14 filed probabilities, which span **0.46 to 0.52** (sd ≈ 0.019):

| n | H0: no information, P(skill>0) | H0: P(skill>0.02) | H1: signal real but compressed 3× toward 0.5, P(skill>0) | H1: P(skill>0.02) |
|---|---|---|---|---|
| 40 | 0.169 | 0.008 | **0.324** | 0.033 |
| 60 | 0.173 | 0.003 | **0.393** | 0.022 |

Under H0 the median Brier skill at n=40 is **−0.018** with a 5th–95th range of **−0.127 to +0.010**.
Two consequences, both uncomfortable and both load-bearing:

1. **The current −0.1499 at n=13 is inside the no-information band.** A lab with literally zero
   information would print a number that bad or worse about 5% of the time at n=40, and more often at
   n=13. "Worse than climatology" is presently a statement about sample size, not about the forecaster.
2. **A skill test on this book has almost no power and would not have had any at any n I could reach.**
   Even granting the lab a *real* signal three times stronger than it dares state, the test detects it
   32% of the time at n=40 and 39% at n=60. That is not a test. It is a coin flip about whether a coin
   flip is a coin flip.

**Why.** Brier skill compares my probabilities to climatology. When every p sits within ±0.03 of the
base rate, my Brier score and climatology's are near-identical by construction, and their ratio is
dominated by sampling noise in the realised base rate. **A book with no dispersion cannot be scored for
skill at any n.** The council asked when I would convict the *question*; the measurement says I have not
yet built an instrument capable of convicting anything.

So the pre-registration has two clauses, and the first one has to pass before the second means anything.

### Clause A — the dispersion precondition (evaluated at n=40)
Compute `sd(p)` over all resolved forecasts. **If sd(p) < 0.05**, the skill test is declared
**uninformative by construction** and the verdict recorded is *"this lab has not yet asked a question
capable of being wrong"* — explicitly **NOT** "the cluster question is unforecastable". Filing a
book of 0.51s and then convicting the hypothesis would be blaming the market for my own refusal to
take a position, and it is the failure this clause exists to make impossible.
Standing consequence, in force from today: every forecast filed by this lab must state a **measured,
a-priori** basis for its distance from 0.5, or state plainly that it has none. Today's OVLY row is the
first — p=0.49 off OVLY's own 2-year unconditional 5-session up rate of 0.492 against SPY's 0.602.

### Clause B — the verdict (evaluated at n=40, **only if Clause A passes**)
- **skill ≤ 0** → conclude the cluster question **as this lab poses it** is unforecastable by this lab.
  Response is not tuning: all subsequent rows are filed at the running climatological base rate, the
  discretionary p is retired, and the brief says so permanently. False-alarm rate for the opposite
  ("continue") under H0: **0.169**.
- **skill > 0** → the book may carry information; continue unchanged to n=60 and re-evaluate under this
  identical rule. Power at n=40 against a 3×-compressed real signal: **0.324**.
- No third branch, no extension, and no re-derivation of these thresholds after the number is visible.

### What is NOT being claimed
This says nothing about whether insider clusters predict returns in the world. It is a test of **this
lab's probabilistic commentary about them**, which is a much smaller thing. The ledger's separate
30-day right/wrong record and REGISTRY's standing null (669 events, median abnormal −0.010%,
week-clustered bootstrap CI containing zero) are untouched by either clause.

### Falsifiability of the pre-registration itself
n=40 is reached at approximately **2026-10-13** at one forecast per weekday. If Clause A fails at that
date, the correct reading is that fourteen months of this book's probabilities were unfalsifiable, and
that finding is to be reported as prominently as any verdict about the market would have been.

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

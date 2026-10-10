# insider-radar — a lab of Leo's Trading Firm

## Cloud sessions: pull requests only (rule set 2026-10-10)

The firm runs on Anupam's Mac; the cloud only sends pull requests. If this session is running in the cloud (claude.ai/code, a fresh
checkout with no `~/command-center` or `~/stock-radar` beside this repo):

- Work on a branch and open a pull request. Never push to `main`.
- Never run this repo's writers, scheduled jobs or agents, and never edit books, ledgers, forecasts, journals, state JSON or data files:
  their real state lives only on the Mac (much of it is gitignored), so a cloud copy is stale and partial.
- Never edit `command-center/council/issues.json` and never run `resolver.py`: the register is written on the Mac only.
- Code, tests and docs only. In the pull request, say what you could not verify without the Mac's data.
- A Mac session reviews every cloud pull request before it is merged.

**Paper only, always.** Sim-only until the Rule 7 gate; nothing here places, sizes or
advises a real trade. Rule 4 bars live short-dated options regardless.

**Before acting, read `~/command-center/THE_FIRM_BRAIN.md`** — the cross-lab canon of
paid-for mechanisms — and ask whether an entry names a defect this lab has not checked
itself for.

**The law of this repo:**
- Pre-registration is sacred: a rule is frozen when registered; improving it is a NEW
  registered variant (log it in `~/command-center/council/evolution_ledger.json` — an
  unlogged tweak is a mining violation), never an edit to a live rule.
- BENCH-002: a scored number is never rewritten. Disposals go through /void-row —
  match the book's existing void convention exactly, and prove the row left every
  hit-rate (allowlists, never denylists).
- n is counted in independent days/events, never rows, and every published n carries
  `clustered_by`. A mid is not a fill; a mark is not a result.
- Freshness is judged by the DATA'S own stamp (last_trade_time, book timestamp, file
  vintage) — never the wall clock, never a CDN rebuild time.
- Every zero states its reason. A monitor aimed at a missing file reports BROKEN, not
  a clean age. Empty books exist with headers.
- Benchmark: the lab's own base rate (669 events: median −0.010%, 49.6% win) — never a naive zero
- $100k stratum reported separately, never blended; voids are lowercase `void`; ledger header is derived from the file, never a literal (INS-011).
**Standing rulings live in `~/command-center/council/issues.json` — grep it before
rewriting any recorded row.** Commit this repo at session end (push if it has a remote).

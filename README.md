# Insider Radar

Live feed of **US corporate insider open-market purchases** (SEC Form 4, transaction code P),
with cluster detection — several insiders buying the same stock within 14 days, the variant of
the signal with the strongest academic support.

**Live viewer:** https://jarvisss007.github.io/insider-radar/

## How it works

- `collector_edgar.py` polls EDGAR's latest-filings feed, reads each Form 4's XML, and keeps
  only **open-market purchases** — the rare, deliberate act of an insider spending their own
  cash. Sales are ignored (mostly diversification/compensation noise).
- It writes `docs/data/insiders.json`; with `--push` it commits the update so the GitHub
  Pages viewer refreshes for everyone.
- The viewer (`docs/index.html`) is a static page: stats, buy-cluster panel, filterable feed.

Run it:

```
python collector_edgar.py                    # one pass
python collector_edgar.py --loop 15 --push   # poll every 15 min, push updates
python collector_edgar.py --loop 15 --push --max-hours 24   # auto-stop after a day
```

Server-side collection is required by design: EDGAR's document archive doesn't send CORS
headers, so a browser-only app can't read the transaction details.

## Data honesty — 2026-08-05 correction (read before using dollar history)

Two defects, found by the council audit and fixed on 2026-08-05:

1. **Duplicate-row inflation.** Cluster `total_value` used to sum raw feed rows, and the
   feed could carry the same (accession, insider, transaction) row many times — observed
   inflation 6.15x (SCTX, $216.2M shown vs $35.1M real) and 123x (XAIR, $27.7M shown vs
   $225.0k real). Dollar sums are now computed over deduplicated
   (accession, insider, date, shares, price) keys, and the feed refuses to store the same
   transaction twice.
2. **Placements counted as conviction.** Form 4 code P covers both open-market buying and
   negotiated offering/placement purchases (e.g. three of SCTX's four 07-27 filings were
   $15.00 IPO allocations totaling $35.0M). The transaction's own footnotes are the only
   machine-readable marker; flagged placement buys are now excluded from the headline
   `total_value` and reported separately as `other_value`. Detection is deliberately
   conservative — it fires only when the filing itself says so on the transaction line
   (a filer who omits the disclosure, as one SCTX holder did, will still land in
   `total_value`), so treat the split as a floor on placement dollars, not a ceiling.

**Consequence:** every `total_value` recorded before 2026-08-05 is unreliable, and the
"big-dollar clusters" hypothesis restarts its sample from 2026-08-05. Ledger rows logged
before then are left untouched (no retro-editing of scored history) — their thesis text
is simply not to be trusted on dollar size. Insider *counts* were always set-based and
were never affected.

## Fair access & honesty

- Identifies itself to the SEC via User-Agent and stays far below the 10 req/s guideline.
- Form 4s lag the actual trade by up to 2 business days; the feed lags by the push cadence
  (timestamp shown in the viewer). This is a **slow, statistical signal — not a trade
  trigger**. Educational only; not investment advice.

## Self-learning agent

`agent/` holds a self-calibrating cluster agent (same pattern as `~/stock-radar`):
every new buy-cluster is auto-logged to `agent/ledger.csv` as a falsifiable `long`
call and scored strictly at +30 calendar days from free Yahoo daily closes; blunt
takeaways accumulate in `agent/lessons.md`. **Honesty note:** this is calibration,
not advice — no claim of edge; the ledger exists to prove or disprove the cluster
hypothesis on our own data. Procedure: `agent/AGENT.md`.

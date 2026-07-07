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

## Fair access & honesty

- Identifies itself to the SEC via User-Agent and stays far below the 10 req/s guideline.
- Form 4s lag the actual trade by up to 2 business days; the feed lags by the push cadence
  (timestamp shown in the viewer). This is a **slow, statistical signal — not a trade
  trigger**. Educational only; not investment advice.

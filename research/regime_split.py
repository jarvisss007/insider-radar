"""Does insider buying stop working when the market falls? (Anupam, 2026-09-10)

Research only: reads insider-radar's events with the lab's own loaders and price fetch; writes only
research/regime_split_results.json. Rules mirror research/validate_event_study.py exactly: entry = the NEXT
trading day's OPEN after the filing date; sub-$1 entries and any >75% single-day move in the
window dropped; significance judged on the week-clustered t, never the naive t.
Pre-declared before any result was seen:
  horizons +5/+10/+20 trading days (judge on +20: the desk holds ~30 calendar days)
  returns: raw · minus SPY (the lab's definition) · minus IWM (small caps, what the book tracks)
  split A (HINDSIGHT, explains, cannot filter): IWM fell over the event's own window
  split B (KNOWABLE AT ENTRY, the only possible rule): IWM close below its 50-day mean on filing day
"""
import sys, json, datetime as dt
import numpy as np, pandas as pd
sys.path.insert(0, "/Users/anupampatil/insider-radar")
sys.path.insert(0, "/Users/anupampatil/insider-radar/research")
from event_study import load_purchase_events, fetch_prices, PRE_DAYS, MAX_H
from validate_event_study import build_arrays, cluster_t

FLOOR = "2024-06-01"
ev_all = load_purchase_events()
ev = [e for e in ev_all if str(e.get("date", ""))[:10] >= FLOOR]
tickers = sorted({e["ticker"] for e in ev if e["ticker"].isalpha()} | {"IWM"})
start = (dt.date.fromisoformat(min(e["date"][:10] for e in ev)) - dt.timedelta(days=100)).isoformat()
print(f"{len(ev_all)} events on file · {len(ev_all)-len(ev)} dated before {FLOOR} excluded · {len(ev)} kept · {len(tickers)} tickers · prices from {start}", flush=True)
px, pxo = fetch_prices(tickers, start)
if "SPY" not in px or "IWM" not in px: sys.exit("SPY or IWM missing — abort")
arr = build_arrays(px, pxo)
def asarr(t):
    s, so = px[t], pxo[t]
    return (s.index.values.astype("datetime64[D]").astype(np.int64), s.to_numpy(float), so.reindex(s.index).to_numpy(float))
sd, sc, so = asarr("SPY")
iw_close = dict(zip(asarr("IWM")[0], asarr("IWM")[1])); iw_open = dict(zip(asarr("IWM")[0], asarr("IWM")[2]))
iw_d, iw_c = asarr("IWM")[0], asarr("IWM")[1]

rows, skipped = [], {"no_prices": 0, "calendar": 0, "hygiene": 0, "no_iwm": 0}
for e in ev:
    t = e["ticker"]
    if t not in arr: skipped["no_prices"] += 1; continue
    dts, cl, op = arr[t]
    filed = np.datetime64(e.get("filed", e["date"])[:10], "D").astype(np.int64)
    i_t = int(np.searchsorted(dts, filed)); i_s = int(np.searchsorted(sd, filed))
    if i_t + 1 >= len(dts) or i_s + 1 >= len(sd) or dts[i_t] != sd[i_s] or dts[i_t + 1] != sd[i_s + 1]:
        skipped["calendar"] += 1; continue
    entry, entry_spy = op[i_t + 1], so[i_s + 1]
    if not np.isfinite(entry) or entry < 1.0: skipped["hygiene"] += 1; continue
    lo, hi = max(0, i_t - PRE_DAYS), min(len(cl), i_t + MAX_H + 1); w = cl[lo:hi]
    with np.errstate(invalid="ignore", divide="ignore"):
        if np.nanmax(np.abs(w[1:] / w[:-1] - 1)) > 0.75: skipped["hygiene"] += 1; continue
    d_entry, d_file = sd[i_s + 1], sd[i_s]
    iwe = iw_open.get(d_entry)
    j = int(np.searchsorted(iw_d, d_file))
    below50 = None
    if j < len(iw_d) and iw_d[j] == d_file and j >= 50:
        below50 = bool(iw_c[j] < np.mean(iw_c[j - 49:j + 1]))
    rec = {"ticker": t, "entry_day": int(d_entry), "below50": below50}
    for h in (5, 10, 20):
        if i_t + h < len(cl) and i_s + h < len(sc):
            raw = (cl[i_t + h] / entry - 1) * 100
            spy = (sc[i_s + h] / entry_spy - 1) * 100
            iwx = iw_close.get(sd[i_s + h])
            iwm = (iwx / iwe - 1) * 100 if (iwe and iwx) else None
            rec[f"raw{h}"], rec[f"spy{h}"], rec[f"iwm{h}"] = raw, spy, iwm
    if rec.get("raw5") is None: continue
    if rec.get("iwm5") is None: skipped["no_iwm"] += 1
    rows.append(rec)
df = pd.DataFrame(rows)
wk = pd.to_datetime(df["entry_day"], unit="D").dt.isocalendar(); df["week"] = wk["year"].astype(str) + "-W" + wk["week"].astype(str).str.zfill(2)
print(f"clean events {len(df)} · skipped {skipped} · entry weeks {df['week'].nunique()} · {pd.to_datetime(df['entry_day'].min(), unit='D').date()} → {pd.to_datetime(df['entry_day'].max(), unit='D').date()}", flush=True)

def cell(label, sub, h):
    sub = sub.dropna(subset=[f"raw{h}", f"iwm{h}"])
    if len(sub) < 5: return {"label": label, "n": int(len(sub))}
    ex_spy = sub[f"raw{h}"] - sub[f"spy{h}"]; ex_iwm = sub[f"raw{h}"] - sub[f"iwm{h}"]
    t_spy, nw = cluster_t(ex_spy.to_numpy(), sub["week"]); t_iwm, _ = cluster_t(ex_iwm.to_numpy(), sub["week"])
    return {"label": label, "n": int(len(sub)), "weeks": int(nw),
            "raw_mean": round(float(sub[f"raw{h}"].mean()), 2), "raw_win": round(float((sub[f"raw{h}"] > 0).mean() * 100), 1),
            "mkt_iwm_mean": round(float(sub[f"iwm{h}"].mean()), 2),
            "vs_spy_mean": round(float(ex_spy.mean()), 2), "vs_spy_median": round(float(ex_spy.median()), 2), "t_spy_week": round(float(t_spy), 2),
            "vs_iwm_mean": round(float(ex_iwm.mean()), 2), "vs_iwm_median": round(float(ex_iwm.median()), 2), "t_iwm_week": round(float(t_iwm), 2),
            "beat_iwm_pct": round(float((ex_iwm > 0).mean() * 100), 1)}
out = {"built": dt.datetime.now().isoformat(timespec="minutes"), "n_clean": int(len(df)), "weeks": int(df["week"].nunique()), "skipped": skipped, "horizons": {}}
for h in (5, 10, 20):
    have = df.dropna(subset=[f"raw{h}", f"iwm{h}"])
    res = [cell("all", have, h),
           cell("A: small caps FELL over the window", have[have[f"iwm{h}"] < 0], h),
           cell("A: small caps ROSE over the window", have[have[f"iwm{h}"] >= 0], h),
           cell("B: entered with small caps BELOW 50-day", have[have["below50"] == True], h),
           cell("B: entered with small caps ABOVE 50-day", have[have["below50"] == False], h)]
    out["horizons"][str(h)] = res
    print(f"\n+{h} trading days")
    print(f"   {'cell':42} {'n':>4} {'wks':>4} {'raw':>7} {'win':>5} {'IWM':>6} {'vsSPY':>6} {'t':>5} {'vsIWM':>6} {'med':>6} {'t':>5} {'beat':>5}")
    for c in res:
        if "raw_mean" not in c: print(f"   {c['label']:42} {c['n']:>4}  (too few)"); continue
        print(f"   {c['label']:42} {c['n']:>4} {c['weeks']:>4} {c['raw_mean']:>+7.2f} {c['raw_win']:>5.0f} {c['mkt_iwm_mean']:>+6.2f} {c['vs_spy_mean']:>+6.2f} {c['t_spy_week']:>+5.2f} {c['vs_iwm_mean']:>+6.2f} {c['vs_iwm_median']:>+6.2f} {c['t_iwm_week']:>+5.2f} {c['beat_iwm_pct']:>5.0f}")
json.dump(out, open("regime_split_results.json", "w"), indent=1)
print("\nwritten: regime_split_results.json (scratch only)")

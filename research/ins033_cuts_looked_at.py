#!/usr/bin/env python3
"""INS-033: re-run the audit's cut families on the IN-SAMPLE insider ledger and count K, the luck tax.

Writes research/INS-033_cuts_looked_at.txt (read-only on every book). The audit of 2026-10-13/14 cut the firm's closed rows
by several families and found "insider longs under $5 lost $7,258" in one of those cuts. This file is that cut table, rebuilt,
because the audit's own table was never saved (command-center/council/audits/AUDIT_2026-10-14.md has none).

In-sample = scored (right/wrong) insider longs called on or before 2026-10-14. Nothing here is evidence for INS-033: the cohort
starts 2026-10-15 and these rows suggested the hypothesis.

Run:  /opt/anaconda3/bin/python research/ins033_cuts_looked_at.py [--asof YYYY-MM-DD]   (fetches IWM through desk_review.bench_closes)
"""
import datetime as dt
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IR = os.path.dirname(HERE)
sys.path.insert(0, IR)
import ins033_floor_test as F  # noqa: E402

IN_SAMPLE_LAST = "2026-10-14"
OUT = os.path.join(HERE, "INS-033_cuts_looked_at.txt")
AUDIT_SNAPSHOT_EXIT_LAST = "2026-10-13"
AUDIT_NUMBERS = {"rows": 152, "net": -9589, "lt5_rows": 45, "lt5_net": -7258, "ge20_rows": 66, "ge20_net": 331}
GRID = [0, 1, 2, 5, 10, 20, 50, float("inf")]
GRID_LABELS = ["<1", "1-2", "2-5", "5-10", "10-20", "20-50", "50+"]
TENOR_BINS = [(0, 7, "<=7d"), (8, 14, "8-14d"), (15, 21, "15-21d"), (22, 28, "22-28d"), (29, 10 ** 6, ">28d")]
CUTOFFS = [1, 2, 5, 10, 20, 50]


def build(asof):
    ledger = F.read_ledger()
    rows = []
    for r in ledger:
        if (r.get("call") or "").strip() != "long" or (r.get("date") or "") > IN_SAMPLE_LAST:
            continue
        b = F.blotter_row(r)
        if b is None:
            continue
        b["px"] = F.fnum(r.get("price_at_call"))
        b["call_date"] = r["date"]
        rows.append(b)
    dr = F.load_desk_review()
    dr.summarize("insider", rows, asof)            # sets r["exc"] on every row, exactly as the desk review does
    for b in rows:
        b["xm"], b["em"] = (b["exit"] or "")[:7], b["entry"][:7]
        b["tenor"] = (dt.date.fromisoformat(b["exit"]) - dt.date.fromisoformat(b["entry"])).days
    return rows, dr


def cell(rows):
    ex = [r["exc"] for r in rows if r.get("exc") is not None]
    wk = F.week_values(rows)
    return dict(n=len(rows), net=round(sum(r["usd"] for r in rows)), ret=st.mean(r["ret"] for r in rows) if rows else None,
                exc=st.mean(ex) if ex else None, beat=(sum(1 for e in ex if e > 0) / len(ex) * 100) if ex else None,
                weeks=len(wk), wexc=st.mean(wk.values()) if wk else None)


def line(label, c):
    f = lambda x, nd=2: "  n/a" if x is None else f"{x:+.{nd}f}"
    return (f"  {label:<22} n {c['n']:>4}   net ${c['net']:>7,}   mean ret {f(c['ret'])}%   mean excess vs IWM {f(c['exc'])} pp"
            f"   beat IWM {('n/a' if c['beat'] is None else format(c['beat'], '.0f') + '%'):>4}   weeks {c['weeks']:>2}   week-clustered excess {f(c['wexc'])} pp")


def main():
    asof = IN_SAMPLE_LAST
    if "--asof" in sys.argv:
        asof = sys.argv[sys.argv.index("--asof") + 1]
    rows, dr = build(asof)
    L = []
    P = L.append
    P("INS-033 - the cuts looked at (in-sample, the insider ledger through 2026-10-14)")
    P("=" * 100)
    P(f"Rebuilt {dt.datetime.now(F.PT).strftime('%Y-%m-%d %H:%M %Z')} by research/ins033_cuts_looked_at.py. In-sample = scored insider longs called on or before {IN_SAMPLE_LAST}: {len(rows)} rows.")
    P("Metric = desk_review.summarize('insider') (row return minus IWM close-to-close, entry to exit), IWM closes fetched live by desk_review.bench_closes.")
    P("NOT EVIDENCE for INS-033: these rows suggested the hypothesis. The cohort (calls 2026-10-15..2026-12-01) is the only evidence.")
    P("")
    P("PROVENANCE. The audit's own cut table was never saved. The cells below are rebuilt from the code of the 2026-10-13 deep dive that produced the")
    P("audit (session 26c6cdd5, subagent abebb9fc84830820d): price grid pd.cut(entry_px,[0,1,2,5,10,20,50,inf]) (its call 117); groupby side / desk / exit month /")
    P("entry month (its call 66); tenor bins [0,7,14,21,28,100] (its call 105); and the two unions the audit text names, 'under $5' and '$20+'.")
    P("")
    snap = [r for r in rows if r["exit"] and r["exit"] <= AUDIT_SNAPSHOT_EXIT_LAST]
    s = lambda sel: (len(sel), round(sum(r["usd"] for r in sel)))
    got = dict(zip(("rows", "net"), s(snap)))
    got.update(zip(("lt5_rows", "lt5_net"), s([r for r in snap if r["px"] < 5])))
    got.update(zip(("ge20_rows", "ge20_net"), s([r for r in snap if r["px"] >= 20])))
    P(f"REPRODUCTION CHECK against the audit's numbers (rows exited on or before {AUDIT_SNAPSHOT_EXIT_LAST}):")
    for k, lab in (("rows", "closed insider longs"), ("net", "net dollars"), ("lt5_rows", "rows under $5"), ("lt5_net", "net under $5"),
                   ("ge20_rows", "rows at $20+"), ("ge20_net", "net at $20+")):
        P(f"  {lab:<24} audit {AUDIT_NUMBERS[k]:>7}   rebuilt {got[k]:>7}   {'MATCH' if got[k] == AUDIT_NUMBERS[k] else 'DIFFERS'}")
    P(f"  (the rebuilt table below uses all {len(rows)} in-sample rows, i.e. {len(rows) - len(snap)} more that closed on {IN_SAMPLE_LAST})")
    P("")

    cells = {}                                                                 # family -> [(label, rows)]
    def lab_price(r):
        for i in range(len(GRID_LABELS)):
            if GRID[i] <= r["px"] < GRID[i + 1]:
                return GRID_LABELS[i]
    price_bins = [(l, [r for r in rows if lab_price(r) == l]) for l in GRID_LABELS]
    unions = [("UNION <$5", [r for r in rows if r["px"] < 5]), ("UNION $20+", [r for r in rows if r["px"] >= 20])]
    cells["price"] = [c for c in price_bins + unions if c[1]]
    cells["side"] = [("long", rows)]
    cells["desk"] = [("insider", rows)]
    cells["exit month"] = [(m, [r for r in rows if r["xm"] == m]) for m in sorted({r["xm"] for r in rows})]
    cells["structure"] = [("equity long, common stock", rows)]
    cells["tenor"] = [(l, [r for r in rows if lo <= r["tenor"] <= hi]) for lo, hi, l in TENOR_BINS]
    cells["tenor"] = [c for c in cells["tenor"] if c[1]]
    extra = {"entry month (seventh cut, printed in the same audit table)": [(m, [r for r in rows if r["em"] == m]) for m in sorted({r["em"] for r in rows})]}

    num = 0
    for fam, cs in list(cells.items()) + list(extra.items()):
        deg = " - DEGENERATE: a single level, nothing to cut" if len(cs) == 1 else ""
        P(f"FAMILY: {fam}{deg}")
        for l, rs in cs:
            P(line(l, cell(rs)))
        if fam == "tenor" and len(cs) > 1:
            P("  note: the desk's clock is one fixed length (30 calendar days from the call). The short bin holds the rows INS-020 restated to a fill session")
            P("  a few days after the call date: their entry date moves, their check_date does not. Two non-empty cells, one real level; counted as 2.")
        P("")
    P("PRICE CUTOFFS as binary floors (each cutoff tried: rows at or above vs rows below; the same 7 bins, regrouped - not counted again in K)")
    P(f"  {'cutoff':<8}{'n >=':>6}{'n <':>6}{'excess >=':>12}{'excess <':>11}{'D (week-clust.)':>17}{'Welch t':>9}{'df':>6}")
    for c in CUTOFFS:
        hi, lo = [r for r in rows if r["px"] >= c], [r for r in rows if r["px"] < c]
        a, b = list(F.week_values(hi).values()), list(F.week_values(lo).values())
        t, df = F.welch(a, b)
        D = st.mean(a) - st.mean(b)
        P(f"  ${c:<7}{len(hi):>6}{len(lo):>6}{st.mean(r['exc'] for r in hi):>+12.2f}{st.mean(r['exc'] for r in lo):>+11.2f}{D:>+17.2f}{('n/a' if t is None else format(t, '+.2f')):>9}{('n/a' if df is None else format(df, '.1f')):>6}")
    ge5, lt5 = list(F.week_values([r for r in rows if r["px"] >= 5]).values()), list(F.week_values([r for r in rows if r["px"] < 5]).values())
    P(f"  At $5, entry-week values of excess: GE5 {len(ge5)} weeks, mean {st.mean(ge5):+.2f}, sd {st.stdev(ge5):.2f}; LT5 {len(lt5)} weeks, mean {st.mean(lt5):+.2f}, sd {st.stdev(lt5):.2f}  (inputs of research/ins033_power_sim.py)")
    P("  In-sample and mined: $5 is the cut the audit headlined, chosen after seeing the table. These are not tests.")
    P("  Note the order: by in-sample t the $2 cut is higher than $5. The ruling fixed $5 before the build; INS-033 tests $5 only and never re-cuts at $3 or $10.")
    P("")

    P("K - THE LUCK TAX")
    P("  Definition: K = the number of cells (levels) of the cut families looked at on the in-sample insider ledger, a family with one level counting 1.")
    kk = {}
    for fam in ("price", "side", "desk", "exit month", "structure", "tenor"):
        kk[fam] = len(cells[fam])
        P(f"  {fam:<12} {kk[fam]:>2} cell(s)" + ("   (degenerate on an equity desk: one level)" if fam in ("side", "desk", "structure") else ""))
    six = sum(kk.values())
    em = len(list(extra.values())[0])
    P(f"  six specified families: {six}")
    P(f"  entry month (the audit's same table also printed it; not one of the six named families, counted anyway because an undercounted tax flatters the next idea): {em}")
    K = six + em
    P(f"  K = {six} + {em} = {K}")
    P(f"  Sidak z (one-sided, family-wise alpha 0.05): K=6 (one cell per family, the floor) {F.sidak_z(6):.4f}; K={six} {F.sidak_z(six):.4f}; K={K} {F.sidak_z(K):.4f}")
    P(f"  pass_t_min = max(lab floor 2.67, Sidak z for K) = {max(2.67, F.sidak_z(K)):.4f}")
    P("  NOT COUNTED, so K is a lower bound: the audit's account-wide cuts (many desks, long/short, option structures and tenors) that led the eye to the insider")
    P("  desk in the first place. On the insider ledger alone desk, side and structure are single-level, and tenor is one real level (see its note), as they must be for an equity-only, long-only, 30-day desk.")
    print("\n".join(L))
    F.atomicio.atomic_write_text(OUT, "\n".join(L) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

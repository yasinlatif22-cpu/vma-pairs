"""Historical valuation reconstruction using currently available Compustat data, filtered by report date.

This is NOT a point-in-time (vintage) dataset: Compustat rows reflect the values held today, which can include later revisions or
restatements, and the report date (rdq) has no time of day. To avoid counting a release that came after the signal close, only
quarters reported strictly BEFORE the signal date are used. Figures quoted in the case studies are checked against the original
earnings releases where noted (docs/CASE_STUDIES.md); otherwise they carry the reconstruction label.

  python diagnostics/case_valuation.py [results_dir]     (needs data/raw/earnings.csv from extract_aux.py, data/processed/market.csv)

For each trade and company: trailing-four-quarter diluted EPS (reported, i.e. GAAP as stored by Compustat), sales and operating
margin using ONLY quarters whose report date (rdq) is before the signal date; trailing P/E at the signal-date close; sales growth (TTM vs the prior TTM);
and where today's V/MA P/E ratio sits against that ratio over the prior three years (same point-in-time rule).
EPS is divided by the Compustat adjustment factor (ajexq) so it is on the same split basis as the adjusted CRSP close.
No analyst estimates are used (not pulled); this is trailing, not forward, valuation. Check the printed quarters against
the companies' earnings releases before quoting a number."""
import sys

import numpy as np
import pandas as pd


def ttm_asof(fq, t, back=0):
    """Latest four quarters reported strictly before t (skipping `back` quarters). fq: one company's quarterly rows."""
    r = fq[fq.rdq < t].sort_values("datadate")
    r = r.iloc[: len(r) - back] if back else r
    q = r.tail(4)
    if len(q) < 4:
        return None
    return dict(eps=float((q.epsfxq / q.ajexq).sum()), sales=float(q.saleq.sum()), opinc=float(q.oiadpq.sum()),
                last_report=q.rdq.max(), last_quarter=q.datadate.max())


def pe_asof(fq, close, t):
    m = ttm_asof(fq, t)
    return close / m["eps"] if m and m["eps"] > 0 else np.nan


def describe(fq, close, t):
    m, p = ttm_asof(fq, t), ttm_asof(fq, t, back=4)
    if not m:
        return None
    return dict(ttm_eps=m["eps"], pe=pe_asof(fq, close, t), ttm_sales=m["sales"], sales_growth=(m["sales"] / p["sales"] - 1) if p else np.nan,
                op_margin=m["opinc"] / m["sales"], last_quarter=m["last_quarter"].date(), last_report=m["last_report"].date())


def main(res="results_rerun"):
    e = pd.read_csv("data/raw/earnings.csv", parse_dates=["datadate", "rdq"])
    need = {"epsfxq", "ajexq", "saleq", "oiadpq"}
    if not need <= set(e.columns):
        raise SystemExit(f"earnings.csv lacks {need - set(e.columns)}; re-run extract_aux.py")
    e = e.dropna(subset=["rdq", "epsfxq", "ajexq", "saleq"])
    mk = pd.read_csv("data/processed/market.csv", parse_dates=["date"]).pivot(index="date", columns="ticker", values="close")
    val = pd.read_csv(f"{res}/val_none_open_next/trades.csv", parse_dates=["signal_date"])
    hold = pd.read_csv(f"{res}/holdout_none_open_next/trades.csv", parse_dates=["signal_date"])
    picks = {"largest validation winner": val.loc[val.net_pnl.idxmax()], "largest validation loser": val.loc[val.net_pnl.idxmin()],
             "worst holdout trade": hold.loc[hold.net_pnl.idxmin()]}
    fq = {tk: g for tk, g in e.groupby("ticker")}
    for label, r in picks.items():
        t = r.signal_date
        print(f"\n=== {label}: signal {t.date()}, side {int(r.side)} ({'long V / short MA' if r.side == 1 else 'short V / long MA'}), net {r.net_pnl:,.0f}")
        d = {tk: describe(fq[tk], mk.at[t, tk], t) for tk in ("V", "MA")}
        for tk, x in d.items():
            print(f"  {tk}: close {mk.at[t, tk]:.2f}  TTM EPS {x['ttm_eps']:.2f}  trailing P/E {x['pe']:.1f}  sales growth {x['sales_growth']:.1%}  "
                  f"op margin {x['op_margin']:.1%}  (last quarter {x['last_quarter']}, reported {x['last_report']})")
        ratio = d["V"]["pe"] / d["MA"]["pe"]
        hist = []
        for s in mk.loc[t - pd.Timedelta(days=3 * 365):t].index[::5]:
            a, b = pe_asof(fq["V"], mk.at[s, "V"], s), pe_asof(fq["MA"], mk.at[s, "MA"], s)
            if np.isfinite(a) and np.isfinite(b):
                hist.append(a / b)
        if len(hist) > 20:
            print(f"  V/MA trailing P/E ratio {ratio:.2f}; prior-3-year (report-date filtered, every 5th day, n={len(hist)}) median {np.median(hist):.2f}, "
                  f"percentile {np.mean(np.array(hist) <= ratio):.0%}")
        print("  quarters used (reported before the signal date):")
        for tk in ("V", "MA"):
            q = fq[tk][fq[tk].rdq < t].sort_values("datadate").tail(4)
            print("   ", tk, [(str(a.date()), round(float(b / c), 2), str(f.date())) for a, b, c, f in zip(q.datadate, q.epsfxq, q.ajexq, q.rdq)], "(quarter end, EPS/adj, reported)")


if __name__ == "__main__":
    main(*sys.argv[1:2])

"""Why does fill=open_next differ from fill=close_next?  Descriptive diagnostic; changes no strategy rule.
Reads results/<period>_none_{open,close}_next/trades.csv and data/processed/market.csv (local, not committed).
Per-trade identity (open-fill quantities q): G_open - G_close = sum_legs q*[(C_e-O_e) - (C_x-O_x)] + quantity term,
i.e. the entry-day open->close move minus the exit-day open->close move."""
import sys
import numpy as np
import pandas as pd

mk = pd.read_csv("data/processed/market.csv", parse_dates=["date"])
O = mk.pivot(index="date", columns="ticker", values="open")
C = mk.pivot(index="date", columns="ticker", values="close")
D = ["signal_date", "entry_date", "exit_signal_date", "exit_date"]


def load(p, f):
    return pd.read_csv(f"results/{p}_none_{f}_next/trades.csv", parse_dates=D)


def analyse(p):
    a, b = load(p, "open"), load(p, "close")
    m = a.merge(b, on=["signal_date", "side"], suffixes=("_o", "_c"), how="outer", indicator=True)
    print(f"\n=== {p}: open trades {len(a)}, close trades {len(b)}; matched on signal_date+side: {(m._merge=='both').sum()}")
    m = m[m._merge == "both"].copy()
    print(f"identical fill dates: {((m.entry_date_o==m.entry_date_c)&(m.exit_date_o==m.exit_date_c)).mean():.0%}; same exit reason: {(m.exit_reason_o==m.exit_reason_c).mean():.0%}")
    rows = []
    for _, r in m.iterrows():
        e, x, qy, qx = r.entry_date_o, r.exit_date_o, r.qty_y_o, r.qty_x_o
        ent = qy*(C.at[e, "V"]-O.at[e, "V"]) + qx*(C.at[e, "MA"]-O.at[e, "MA"])
        ex = qy*(C.at[x, "V"]-O.at[x, "V"]) + qx*(C.at[x, "MA"]-O.at[x, "MA"])
        diff = r.gross_pnl_o - r.gross_pnl_c
        rows.append(dict(signal=r.signal_date.date(), side=r.side, reason=r.exit_reason_o, gross_open=r.gross_pnl_o, gross_close=r.gross_pnl_c,
                         diff=diff, entry_intraday=ent, exit_intraday=-ex, qty_term=diff-(ent-ex)))
    d = pd.DataFrame(rows)
    print("sums ($):\n", d[["gross_open", "gross_close", "diff", "entry_intraday", "exit_intraday", "qty_term"]].sum().round(0).to_string())
    top = d.reindex(d["diff"].abs().sort_values(ascending=False).index).head(6)
    print("largest |diff| trades:\n", top.round(0).to_string(index=False))
    print(f"top-3 |diff| trades sum {top.head(3)['diff'].sum():,.0f}; top-5 {top.head(5)['diff'].sum():,.0f}; all {d['diff'].sum():,.0f}")
    print(f"open beat close in {(d['diff']>0).mean():.0%} of trades; median diff {d['diff'].median():,.0f}, mean {d['diff'].mean():,.0f}, "
          f"t(mean) {d['diff'].mean()/(d['diff'].std()/np.sqrt(len(d))):.2f}")
    idx = C.index[(C.index >= pd.Timestamp(d.signal.min())) & (C.index <= pd.Timestamp(d.signal.max()))]
    ov = np.log(O.loc[idx]/C.shift(1).loc[idx]); it = np.log(C.loc[idx]/O.loc[idx])
    print("mean daily overnight / intraday log return, bps (V, MA):", (ov.mean()*1e4).round(1).tolist(), (it.mean()*1e4).round(1).tolist())


for p in sys.argv[1:] or ["dev", "val"]:
    analyse(p)

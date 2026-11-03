"""Pre-registered earnings-window diagnostic (docs/PREREG_EARNINGS.md).  Exploratory; changes no strategy rule."""
import numpy as np
import pandas as pd

ev = pd.read_csv("data/raw/earnings.csv", parse_dates=["datadate", "rdq"])
print("report dates per ticker:\n", ev.groupby("ticker").rdq.agg(["count", "min", "max"]).to_string(), "\nmissing rdq:", int(ev.rdq.isna().sum()))
cal = pd.read_csv("data/processed/market.csv", parse_dates=["date"]).date.drop_duplicates().sort_values().reset_index(drop=True)
exp = set()
for r in ev.rdq.dropna():
    i = cal.searchsorted(r)                       # first trading day on/after r
    exp.update(cal.iloc[i:i + 2])                 # r and r+1
T = {p: pd.read_csv(f"results/{p}_none_open_next/trades.csv", parse_dates=["entry_date", "exit_date"]) for p in ("dev", "val", "holdout")}
D = {p: pd.read_csv(f"results/{p}_none_open_next/daily.csv", parse_dates=["date"]).set_index("date") for p in T}
rng = np.random.default_rng(7)


def flag(t):
    return t.apply(lambda r: any(d in exp for d in cal[(cal >= r.entry_date) & (cal <= r.exit_date)]), axis=1)


rows, trades = [], []
for p, t in T.items():
    t = t.assign(period=p, exposed=flag(t)); trades.append(t)
al = pd.concat(trades)
for name, g in list(al.groupby("period")) + [("all", al)]:
    for ex, h in g.groupby("exposed"):
        rows.append(dict(period=name, exposed=ex, n=len(h), mean_net=h.net_pnl.mean(), median_net=h.net_pnl.median(), win=(h.net_pnl > 0).mean(),
                         z_stop=(h.exit_reason == "z_stop").mean(), total=h.net_pnl.sum()))
print("\nTRADES (exposed = any day entry..exit is an earnings day for V or MA)\n", pd.DataFrame(rows).round(2).to_string(index=False))
a, b = al[al.exposed].net_pnl.values, al[~al.exposed].net_pnl.values
if len(a) and len(b):
    bs = [rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(10000)]
    print(f"\nall periods: mean(exposed)-mean(unexposed) = {a.mean()-b.mean():,.0f}  bootstrap 95% [{np.percentile(bs,2.5):,.0f}, {np.percentile(bs,97.5):,.0f}]  n={len(a)} vs {len(b)}")
dr = []
for p, d in D.items():
    d = d.assign(pnl=d.equity.diff().fillna(0), period=p, exp=[i in exp for i in d.index])
    dr.append(d[d.in_trade > 0])
dd = pd.concat(dr)
print("\nIN-TRADE DAYS ($ daily P&L)\n", dd.groupby("exp").pnl.agg(n="count", mean="mean", std="std").round(1).to_string())

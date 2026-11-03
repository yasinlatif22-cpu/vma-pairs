"""Statistics from the ACTUAL daily return series (replaces hand-pooled Sharpe/t figures).
Each run (dev, val, holdout) is an independent evaluation: capital resets to $1M, positions are flat at the start
and end of each run, and the 252-day formation window may use data from before the run's start.  Stitching just
concatenates the daily returns; it does not describe one continuous account.  Reported:
 - total-equity Sharpe (primary; return on $1M equity, zero cash interest, as in the runs)
 - excess-of-rf versions if data/raw/rf.csv exists (columns date, rf as daily decimal); otherwise constant-rate grid
 - cash scenarios: S1 interest on idle cash = max(0, equity - long_mv) at rf; S2 additionally credits short proceeds
 - utilisation reported separately
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

RUNS = {"dev": "dev_none_open_next", "val": "val_none_open_next", "holdout": "holdout_none_open_next"}
d = {k: pd.read_csv(f"results/{v}/daily.csv", parse_dates=["date"]).set_index("date") for k, v in RUNS.items()}
rf_path = Path("data/raw/rf.csv")
rf = pd.read_csv(rf_path, parse_dates=["date"]).set_index("date").rf if rf_path.exists() else None


def sharpe(r, rf_=None):
    x = r - (rf_.reindex(r.index).fillna(0) if rf_ is not None else 0)
    return x.mean() / x.std(ddof=1) * np.sqrt(252) if x.std() > 0 else np.nan


def nw_t(r, lags=10):
    x = r.values - r.mean(); n = len(x); s = (x @ x) / n
    for l in range(1, lags + 1):
        s += 2 * (1 - l / (lags + 1)) * (x[l:] @ x[:-l]) / n
    return r.mean() / np.sqrt(s / n)


def boot_ci(r, block=21, B=4000, seed=7):
    rng = np.random.default_rng(seed); x = r.values; n = len(x); k = int(np.ceil(n / block)); out = []
    for _ in range(B):
        st = rng.integers(0, n, k); idx = (st[:, None] + np.arange(block)).ravel()[:n] % n
        out.append(x[idx].mean() / x[idx].std(ddof=1) * np.sqrt(252))
    return np.percentile(out, [2.5, 97.5])


def scen(df, rate, which):
    """add daily interest at annual `rate` (scalar or daily Series, decimal) to the net return"""
    r = rate.reindex(df.index).ffill().fillna(0) if hasattr(rate, "reindex") else rate
    base = df.equity.shift(1).fillna(df.equity.iloc[0])
    idle = (base - df.long_mv.shift(1).fillna(0)).clip(lower=0) if which == "S1" else (base - df.long_mv.shift(1).fillna(0) - df.short_mv.shift(1).fillna(0)).clip(lower=0)
    return df.ret + idle * r / 252 / base


def report(name, r, parts=None):
    lo, hi = boot_ci(r)
    print(f"{name:34s} n={len(r):5d} ann.ret {r.mean()*252:6.2%} vol {r.std()*np.sqrt(252):6.2%} Sharpe {sharpe(r):5.2f} "
          f"NW-t {nw_t(r):5.2f}  boot95(21d) [{lo:5.2f},{hi:5.2f}]" + (f"  excess-Sharpe {sharpe(r, rf):5.2f}" if rf is not None else ""))


print("(stitched independent runs; capital/positions/formation reset per run)")
for k in d: report(k, d[k].ret)
vh = pd.concat([d["val"].ret, d["holdout"].ret]); report("val+holdout (2018-2025)", vh)
report("dev+val+holdout (dev-inclusive)", pd.concat([d["dev"].ret, vh]))
print("\nutilisation (mean over run days):")
for k, x in d.items():
    print(f"  {k:8s} in-trade days {x.in_trade.mean():.0%}, mean gross {x.gross_pct[x.in_trade>0].mean():.2f}x, mean long_mv/equity {(x.long_mv/x.equity).mean():.2f}, mean |short_mv|/equity {(x.short_mv.abs()/x.equity).mean():.2f}")
print("\ncash scenarios on val+holdout (return on total equity; rate = annual rf applied to idle cash). 'excess' subtracts the same rf,")
print("because a scenario that credits interest on cash raises raw Sharpe mechanically; the question is whether the strategy beats cash.")
rates = {"2% flat": 0.02, "4% flat": 0.04} if rf is None else {"actual rf": rf * 252}   # rf.csv is a daily decimal; scenarios take an annual rate
vh_d = {k: d[k] for k in ("val", "holdout")}
for nm, rate in rates.items():
    rd = rate / 252
    for which in ("S0", "S1", "S2"):
        s = pd.concat([(d[k].ret if which == "S0" else scen(d[k], rate, which)) for k in vh_d])
        rr = rd if not hasattr(rd, "reindex") else rd.reindex(s.index).ffill().fillna(0)
        ex = s - rr
        print(f"  {which} {nm:10s} ann.ret {s.mean()*252:6.2%}  excess-of-rf ann.ret {ex.mean()*252:6.2%}  excess Sharpe {ex.mean()/ex.std(ddof=1)*np.sqrt(252):5.2f}")
print("  S0 = as run (cash earns 0); S1 = idle cash (equity - long MV) earns rf; S2 = S1 plus short proceeds earn rf (optimistic).")
if rf is None:
    print("  (data/raw/rf.csv not found: flat rates are illustrative sensitivities, not the historical series)")

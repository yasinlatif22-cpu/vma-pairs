"""Descriptive concentration of trade P&L.  Sensitivity diagnostics, NOT alternative strategies.

  python diagnostics/concentration.py [results_dir]      (default results_rerun; primary open-fill runs)

For each period: net P&L of all trades, then excluding the k largest winners, the k largest losers, and the k largest
by absolute size (k = 1, 3), with trade counts and a trade-resampling bootstrap 95% interval for mean trade P&L."""
import sys

import numpy as np
import pandas as pd


def boot_mean(x, B=10000, seed=7):
    rng = np.random.default_rng(seed)
    m = [rng.choice(x, len(x)).mean() for _ in range(B)]
    return np.percentile(m, [2.5, 97.5])


def main(res="results_rerun"):
    T = {p: pd.read_csv(f"{res}/{p}_none_open_next/trades.csv") for p in ("dev", "val", "holdout")}
    T["all"] = pd.concat(T.values(), ignore_index=True)
    for p, t in T.items():
        x = t.net_pnl.sort_values()
        pos = t.net_pnl[t.net_pnl > 0].sum()
        print(f"\n== {p}: {len(t)} trades, net {t.net_pnl.sum():,.0f}, mean {t.net_pnl.mean():,.0f}, "
              f"95% CI of mean [{boot_mean(t.net_pnl.values)[0]:,.0f}, {boot_mean(t.net_pnl.values)[1]:,.0f}]; "
              f"largest winner = {x.iloc[-1] / pos:.0%} of gross wins, top-3 winners = {x.iloc[-3:].sum() / pos:.0%}")
        for k in (1, 3):
            if len(t) <= k + 2:
                continue
            ex = {"excluding top-%d winners" % k: x.iloc[:-k], "excluding top-%d losers" % k: x.iloc[k:],
                  "excluding top-%d by |P&L|" % k: t.net_pnl.loc[t.net_pnl.abs().sort_values().index[:-k]]}
            for name, s in ex.items():
                print(f"   {name:28s} n={len(s):3d} net {s.sum():>10,.0f}  mean {s.mean():>8,.0f}")


if __name__ == "__main__":
    main(*sys.argv[1:2])

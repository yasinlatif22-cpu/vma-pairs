"""Statistics from the ACTUAL daily return series, utilisation, and explicit financing scenarios.

  python diagnostics/pooled_stats.py [results_dir]        (default results_rerun; needs data/raw/rf.csv for financing)

Each run (dev, val, holdout) is an independent evaluation: capital resets to $1M, positions start and end flat, the
252-day formation window may use pre-run data, and risk-control state (peak, halt, loss locks) restarts. Stitching only
concatenates daily returns; it does not describe one continuous account.

Return on total equity ($1M, cash earning nothing) is the principal measure. Financing scenarios: diagnostics/financing.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from financing import DEBIT_SPREAD, MARGIN, REBATE_SPREAD, account, load_rf, tbill

PERIODS = {"dev": "dev_none_open_next", "val": "val_none_open_next", "holdout": "holdout_none_open_next"}


def sharpe(r):
    return r.mean() / r.std(ddof=1) * np.sqrt(252) if r.std() > 0 else np.nan


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


def line(name, r):
    lo, hi = boot_ci(r)
    print(f"{name:34s} n={len(r):5d} ann.ret {r.mean()*252:6.2%} vol {r.std()*np.sqrt(252):6.2%} Sharpe {sharpe(r):5.2f} "
          f"NW-t {nw_t(r):5.2f}  boot95(21d) [{lo:5.2f},{hi:5.2f}]")


def main(res="results_rerun"):
    d = {k: pd.read_csv(f"{res}/{v}/daily.csv", parse_dates=["date"]).set_index("date") for k, v in PERIODS.items()}
    print("(stitched independent runs; capital, positions, formation and risk-control state reset per run)")
    for k in d:
        line(k, d[k].ret)
    vh = pd.concat([d["val"].ret, d["holdout"].ret])
    line("val+holdout (2018-2025)", vh)
    line("dev+val+holdout (dev-inclusive)", pd.concat([d["dev"].ret, vh]))
    print("\nutilisation (mean over run days):")
    for k, x in d.items():
        inn = x.in_trade > 0
        print(f"  {k:8s} in-trade days {x.in_trade.mean():.0%}; while in trade: gross {x.gross_pct[inn].mean():.2f}x, long {(x.long_mv/x.equity)[inn].mean():.2f}x, "
              f"short {(x.short_mv.abs()/x.equity)[inn].mean():.2f}x; all days: long {(x.long_mv/x.equity).mean():.2f}x, short {(x.short_mv.abs()/x.equity).mean():.2f}x")
    rf_path = Path("data/raw/rf.csv")
    if not rf_path.exists():
        print("\n(data/raw/rf.csv not found: run extract_aux.py for the financing section)")
        return
    rf, rf_label = load_rf()
    print(f"\nrisk-free source: {rf_label}")
    print(f"FINANCING: one account per run, holdings fixed as run (financing does not resize positions); margin {MARGIN:.0%} of short "
          f"value, rebate rf-{REBATE_SPREAD:.1%}, debit rf+{DEBIT_SPREAD:.1%}. $ totals; returns use (E+F) as the daily denominator.")
    print(f"{'period':8s} {'trading $':>11s} {'borrow $':>9s} {'interest $':>11s} {'rebate $':>9s} {'debit $':>8s} {'T-bill $':>10s} | "
          f"CAGR S0 / S1 / S2 / T-bill | excess-of-rf mean ann. S0 / S1 / S2 | excess Sharpe S0 / S1 / S2")
    tr = {p: pd.read_csv(f"{res}/{v}/trades.csv") for p, v in PERIODS.items()}
    ex_all = {n: {} for n in ("S0", "S1", "S2")}
    for k, x in d.items():
        acc = {n: account(x, rf, n) for n in ("S0", "S1", "S2")}
        assert abs(acc["S0"].trading_pnl.sum() - tr[k].net_pnl.sum()) < 0.01, "daily $ P&L must equal the sum of trade P&L"
        tb = tbill(x.index, rf)
        yrs = len(x) / 252
        cagr = {n: (a.equity_fin.iloc[-1] / 1e6) ** (1 / yrs) - 1 for n, a in acc.items()}
        cagr_tb = (tb.iloc[-1] / 1e6) ** (1 / yrs) - 1
        for n, a in acc.items():
            ex_all[n][k] = a.ret - a.rf
        a1, a2 = acc["S1"], acc["S2"]
        print(f"{k:8s} {a1.trading_pnl.sum():11,.0f} {tr[k].borrow.sum():9,.0f} {a1.interest.sum():11,.0f} {a2.rebate.sum():9,.0f} "
              f"{a2.debit.sum():8,.0f} {tb.iloc[-1] - 1e6:10,.0f} | {cagr['S0']:.2%} / {cagr['S1']:.2%} / {cagr['S2']:.2%} / {cagr_tb:.2%} | "
              + " / ".join(f"{ex_all[n][k].mean()*252:.2%}" for n in ("S0", "S1", "S2")) + " | "
              + " / ".join(f"{sharpe(ex_all[n][k]):.2f}" for n in ("S0", "S1", "S2")))
    print("val+holdout excess of rf (each run its own account): " + "; ".join(
        f"{n} mean ann. {pd.concat([ex_all[n]['val'], ex_all[n]['holdout']]).mean()*252:.2%}, Sharpe {sharpe(pd.concat([ex_all[n]['val'], ex_all[n]['holdout']])):.2f}"
        for n in ("S0", "S1", "S2")))
    print("\nFinancing lines are scenarios about a brokerage account, not trading results. Interest on cash does not by itself\n"
          "establish or refute trading skill; the benchmark question is whether trading P&L plus feasible financing beats T-bills.")


if __name__ == "__main__":
    main(*sys.argv[1:2])

"""Statistics from the ACTUAL daily return series, utilisation, and explicit financing scenarios.

  python diagnostics/pooled_stats.py [results_dir]        (default results_rerun; needs data/raw/rf.csv for financing)

Each run (dev, val, holdout) is an independent evaluation: capital resets to $1M, positions start and end flat, the
252-day formation window may use pre-run data, and risk-control state (peak, halt, loss locks) restarts. Stitching only
concatenates daily returns; it does not describe one continuous account.

Return on total equity ($1M, cash earning nothing) is the principal measure. Financing is shown separately:
  trading P&L  = gross price P&L + dividends - transaction costs - borrow fees   (what the engine books)
  S1 interest  = rf on cash not needed to fund longs or collateralise shorts at 100% of short value
  S2 rebate    = S1 plus a short-sale rebate of max(0, rf - REBATE_SPREAD) on short market value (illustrative; real rebates
                 depend on the lender and the name, and not all proceeds are investable)
  benchmark    = rf on the full $1M (a feasible cash alternative)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PERIODS = {"dev": "dev_none_open_next", "val": "val_none_open_next", "holdout": "holdout_none_open_next"}
REBATE_SPREAD = 0.005      # annual; illustrative


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


def financing(df, rf):
    """daily $ interest under S1 and S2 for one run; positions and equity are those held overnight (prior close)."""
    e, L, S = (df[c].shift(1).fillna(df.equity.iloc[0] if c == "equity" else 0.0) for c in ("equity", "long_mv", "short_mv"))
    r = rf.reindex(df.index).ffill().fillna(0.0)
    s1 = r * (e - L - S.abs()).clip(lower=0)
    s2 = s1 + (r - REBATE_SPREAD / 252).clip(lower=0) * S.abs()
    return s1, s2, r * df.equity.iloc[0]


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
    rf = pd.read_csv(rf_path, parse_dates=["date"]).set_index("date").rf          # daily decimal
    print(f"\nFINANCING (first four columns: $ per year as % of the initial $1M; excess columns: mean daily return based; rf = Fama-French daily rf; rebate spread {REBATE_SPREAD:.1%}):")
    print(f"{'period':8s} {'trading':>8s} {'S1 int':>7s} {'S2 rebate':>9s} {'T-bill':>7s} | excess of T-bill: {'S0':>6s} {'S1':>6s} {'S2':>6s} | excess Sharpe S0/S1/S2")
    tr = {p: pd.read_csv(f"{res}/{v}/trades.csv") for p, v in PERIODS.items()}
    for k, x in d.items():
        s1, s2, bench = financing(x, rf)
        yrs = len(x) / 252
        trading = x.ret * x.equity.shift(1).fillna(1e6)                           # $ per day, equals trade P&L in total
        assert abs(trading.sum() - tr[k].net_pnl.sum()) < 0.01, "daily $ P&L must equal the sum of trade P&L"
        t_ann, s1_ann, s2_ann, b_ann = (v.sum() / 1e6 / yrs for v in (trading, s1, s2 - s1, bench))
        ex = {n: x.ret - rf.reindex(x.index).ffill().fillna(0) + add / 1e6 for n, add in (("S0", 0 * s1), ("S1", s1), ("S2", s2))}
        sh = [sharpe(ex[n]) for n in ("S0", "S1", "S2")]
        print(f"{k:8s} {t_ann:8.2%} {s1_ann:7.2%} {s2_ann:9.2%} {b_ann:7.2%} | {'':18s}{ex['S0'].mean()*252:6.2%} {ex['S1'].mean()*252:6.2%} {ex['S2'].mean()*252:6.2%} | "
              f"{sh[0]:5.2f} / {sh[1]:5.2f} / {sh[2]:5.2f}")
    vh_ex = {}
    for n in ("S0", "S1", "S2"):
        parts = []
        for k, x in d.items():
            if k == "dev":
                continue
            s1, s2, _ = financing(x, rf)
            add = {"S0": 0 * s1, "S1": s1, "S2": s2}[n]
            parts.append(x.ret - rf.reindex(x.index).ffill().fillna(0) + add / 1e6)
        vh_ex[n] = pd.concat(parts)
    print("val+holdout excess of T-bill: " + "; ".join(f"{n} ann {v.mean()*252:.2%}, Sharpe {sharpe(v):.2f}" for n, v in vh_ex.items()))
    print("\nThese financing lines are scenarios about a brokerage account, not trading results. Interest on cash does not by itself\n"
          "establish or refute trading skill; the benchmark question is whether trading P&L plus feasible financing beats T-bills.")


if __name__ == "__main__":
    main(*sys.argv[1:2])

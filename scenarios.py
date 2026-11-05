"""Exploratory post-evaluation scenario grid: every cell is a full engine rerun on the licensed data.

  python scenarios.py [--out results_rerun/scenarios.csv]

Varied: transaction cost (bps per leg per fill), borrow fee (bps a year on short value), and execution timing (fill at the open or
close of the session `lag` sessions after the signal close; lag 1 at the open is the frozen specification). Everything else is the
frozen specification. Because each cell reruns the engine, cost and timing changes flow through equity, position sizing, the
5% trade loss limit and the 20% drawdown halt; nothing is a P&L haircut.
Financing scenarios S1 and S2 are then applied to each run as a fixed-holdings account (diagnostics/financing.py): interest does not
change sizing.
This grid was computed after every period had been evaluated. It is descriptive sensitivity, not a search: no cell is selected,
and the best-looking cell is not a validated optimum. The baseline cell must reproduce the published runs exactly."""
import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "diagnostics")
from config import DEFAULT  # noqa: E402
from data_io import load_market  # noqa: E402
from engine import reconcile, run_engine  # noqa: E402
from financing import account, load_rf  # noqa: E402
from metrics import perf  # noqa: E402
from signals import build_signals  # noqa: E402

COSTS = [0.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0]
BORROWS = [0.0, 30.0, 100.0, 300.0]
TIMINGS = [(1, "open_next"), (1, "close_next"), (2, "open_next"), (2, "close_next"), (3, "open_next"), (3, "close_next")]
TIMING_LABEL = {(1, "open_next"): "t+1 open", (1, "close_next"): "t+1 close", (2, "open_next"): "t+2 open",
                (2, "close_next"): "t+2 close", (3, "open_next"): "t+3 open", (3, "close_next"): "t+3 close"}
SAMPLES = {"dev": ["dev"], "val": ["val"], "holdout": ["holdout"], "val+holdout": ["val", "holdout"]}


def metrics(parts, rf):
    """parts: list of (daily, trades) for one sample; independent runs are concatenated, never merged into one account."""
    r = pd.concat([d.ret for d, _ in parts])
    p = perf(r)
    out = dict(trades=sum(len(t) for _, t in parts), net_pnl=sum(t.net_pnl.sum() for _, t in parts if len(t)),
               mean_ann_ret=p["mean_ann_ret"], cagr=p["cagr"], ann_vol=p["ann_vol"], sharpe=p["sharpe"], max_dd=p["max_dd"],
               utilization=pd.concat([d.in_trade for d, _ in parts]).mean(),
               costs=sum(t.costs.sum() for _, t in parts if len(t)), borrow_paid=sum(t.borrow.sum() for _, t in parts if len(t)))
    for sc in ("S0", "S1", "S2"):
        acc = [account(d, rf, sc) for d, _ in parts]
        ex = pd.concat([a.ret - a.rf for a in acc])
        out[f"excess_sharpe_{sc}"] = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan
        out[f"excess_ann_{sc}"] = ex.mean() * 252
        out[f"cagr_{sc}"] = perf(pd.concat([a.ret for a in acc]))["cagr"]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results_rerun/scenarios.csv")
    ap.add_argument("--market", default="data/processed/market.csv")
    a = ap.parse_args(argv)
    o, c, d = load_market(a.market, [DEFAULT.y, DEFAULT.x])
    rf, rf_label = load_rf()
    sig = {}
    for p in ("dev", "val", "holdout"):
        f, l = getattr(DEFAULT, p)
        s, _ = build_signals(c.loc[:l], DEFAULT, c.index.searchsorted(pd.Timestamp(f)))
        sig[p] = (f, l, s.loc[f:l])
    rows, n = [], 0
    for cost in COSTS:
        for bor in BORROWS:
            for lag, fill in TIMINGS:
                spec = replace(DEFAULT, cost_bps=cost, borrow_bps=bor, fill=fill)
                runs = {}
                for p, (f, l, s) in sig.items():
                    daily, trades = run_engine(o.loc[f:l], c.loc[f:l], d.loc[f:l], s, spec, fill_lag=lag)
                    reconcile(daily, trades, spec)
                    runs[p] = (daily, trades)
                    n += 1
                for sample, ps in SAMPLES.items():
                    rows.append(dict(sample=sample, cost_bps=cost, borrow_bps=bor, fill_lag=lag, fill=fill,
                                     timing=TIMING_LABEL[(lag, fill)], baseline=(cost == 5.0 and bor == 30.0 and lag == 1 and fill == "open_next"),
                                     **metrics([runs[p] for p in ps], rf)))
    df = pd.DataFrame(rows)
    # the baseline cells must reproduce the published runs to the cent
    for p in ("dev", "val", "holdout"):
        pub = pd.read_csv(f"results_rerun/{p}_none_open_next/trades.csv").net_pnl.sum()
        got = df[(df["sample"] == p) & df.baseline].net_pnl.iloc[0]
        assert abs(pub - got) < 0.01, (p, pub, got)
    for p in ("dev", "val"):
        pub = pd.read_csv(f"results_rerun/{p}_none_close_next/trades.csv").net_pnl.sum()
        got = df[(df["sample"] == p) & (df.cost_bps == 5) & (df.borrow_bps == 30) & (df.fill_lag == 1) & (df.fill == "close_next")].net_pnl.iloc[0]
        assert abs(pub - got) < 0.01, (p, pub, got)
    df["rf_source"] = rf_label
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"{n} engine runs; {len(df)} sample rows -> {a.out}; baseline and published close-fill variant reproduced to the cent")
    print(f"risk-free source: {rf_label}")
    b = df[(df.borrow_bps == 30)].pivot_table(index="cost_bps", columns="timing", values="sharpe", aggfunc="first")
    print("\nval+holdout total-equity Sharpe, borrow 30 bps (rows cost bps, columns timing):")
    print(df[(df["sample"] == "val+holdout") & (df.borrow_bps == 30)].pivot_table(index="cost_bps", columns="timing", values="sharpe")
          [[TIMING_LABEL[t] for t in TIMINGS]].round(2).to_string())
    return df


if __name__ == "__main__":
    main()

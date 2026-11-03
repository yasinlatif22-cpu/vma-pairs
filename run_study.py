"""Run one evaluation period.

  python run_study.py --period dev
  python run_study.py --period val
  python run_study.py --period holdout --confirm <spec hash>      # allowed once
  python run_study.py --period synthetic                          # engine demo only, not evidence
  python run_study.py --period holdout --reproduce --out results_rerun   # re-run of a spent holdout; NOT a fresh test

Every run is appended to EXPERIMENTS.md. Pass --gate coint / --fill close_next for the pre-declared variants.
"""
import argparse
import datetime as dt
from dataclasses import replace
from pathlib import Path

import pandas as pd

from config import DEFAULT
from data_io import load_market, synthetic_market
from engine import reconcile, run_engine
from metrics import bootstrap_sharpe, deflated_sharpe, exposure_report, market_regression, past_only_vol_regimes, perf
from signals import build_signals


def run(spec, o, c, d, first_date, last_date):
    first_idx = c.index.searchsorted(pd.Timestamp(first_date))
    sig, wins = build_signals(c.loc[:last_date], spec, first_idx)
    sig = sig.loc[first_date:last_date]
    sl = slice(first_date, last_date)
    daily, trades = run_engine(o.loc[sl], c.loc[sl], d.loc[sl], sig, spec)
    return daily, trades, wins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, choices=["dev", "val", "holdout", "synthetic"])
    ap.add_argument("--market", default="data/processed/market.csv")
    ap.add_argument("--mkt", default="data/processed/mkt.csv")
    ap.add_argument("--gate", default=DEFAULT.gate)
    ap.add_argument("--fill", default=DEFAULT.fill)
    ap.add_argument("--confirm", default="")
    ap.add_argument("--out", default="results")
    ap.add_argument("--reproduce", action="store_true",
                    help="re-run an already-evaluated period (e.g. after a code correction). Allowed for the holdout; "
                         "output and log rows are labelled as reproductions, never as fresh evaluations.")
    a = ap.parse_args()
    if a.reproduce and a.out == "results":
        raise SystemExit("Use a separate --out directory (e.g. results_rerun) for reproduction runs.")
    spec = replace(DEFAULT, gate=a.gate, fill=a.fill)
    out = Path(a.out) / f"{a.period}_{a.gate}_{a.fill}"
    out.mkdir(parents=True, exist_ok=True)

    if a.period == "synthetic":
        long, mkt = synthetic_market(seed=1)
        Path("data/processed").mkdir(parents=True, exist_ok=True)
        long.to_csv("data/processed/synthetic_market.csv", index=False)
        o, c, d = load_market("data/processed/synthetic_market.csv", [spec.y, spec.x])
        first, last = c.index[spec.formation], c.index[-1]
    else:
        if a.period == "holdout" and a.reproduce:
            if a.out == "results":
                raise SystemExit("Use a separate --out directory (e.g. results_rerun) for reproduction runs.")
            if not (Path("results") / "HOLDOUT_USED").exists():
                raise SystemExit("No record that the holdout was evaluated; run it normally first.")
            (out).mkdir(parents=True, exist_ok=True)
            (out / "REPRODUCTION_OF_SPENT_HOLDOUT").write_text(
                f"{dt.datetime.now().isoformat()} spec {spec.hash()}: re-run of an already-evaluated period, not a fresh test\n")
        elif a.period == "holdout":
            lock = Path(a.out) / "HOLDOUT_USED"
            if a.confirm != spec.hash():
                raise SystemExit(f"Holdout needs --confirm {spec.hash()} (the frozen spec hash).")
            if lock.exists():
                raise SystemExit("Holdout was already run. Re-running it would make it a development set.")
            lock.write_text(f"{dt.datetime.now().isoformat()} spec {spec.hash()}\n")
        o, c, d = load_market(a.market, [spec.y, spec.x])
        first, last = getattr(spec, a.period)
        mkt = pd.read_csv(a.mkt, parse_dates=["date"], index_col="date").mkt_ret if Path(a.mkt).exists() else None

    daily, trades, wins = run(spec, o, c, d, first, last)
    err = reconcile(daily, trades, spec)
    perf_all = perf(daily.ret)
    active = daily.ret[daily.in_trade.eq(1)]
    expo = exposure_report(daily, c, mkt, spec)
    lines = [f"# {a.period}{' (REPRODUCTION, not a fresh evaluation)' if a.reproduce else ''} | gate={a.gate} fill={a.fill} | spec {spec.hash()}",
             f"window {daily.index[0].date()} to {daily.index[-1].date()}, {len(wins)} windows, {len(trades)} trades",
             f"net: ann ret {perf_all['ann_ret']:.2%}, vol {perf_all['ann_vol']:.2%}, Sharpe {perf_all['sharpe']:.2f}, max DD {perf_all['max_dd']:.2%}",
             f"time in market {daily.in_trade.mean():.0%}; mean gross {expo.gross_pct[daily.in_trade == 1].mean():.2f}x, "
             f"mean net {expo.net_pct[daily.in_trade == 1].mean():+.2f}x",
             f"reconciliation (equity change - sum of trade P&L): {err:.6f}"]
    if len(trades):
        lines += [f"trade totals: gross {trades.gross_pnl.sum():,.0f}  dividends {trades.dividends.sum():,.0f}  "
                  f"costs {trades.costs.sum():,.0f}  borrow {trades.borrow.sum():,.0f}  net {trades.net_pnl.sum():,.0f}",
                  f"win rate {(trades.net_pnl > 0).mean():.0%}; exit reasons: {trades.exit_reason.value_counts().to_dict()}"]
    if mkt is not None and len(daily) > 60:
        mr = market_regression(daily.ret, mkt)
        lines.append(f"market regression: beta {mr['beta']:.3f} (t {mr['beta_t']:.1f}), alpha {mr['alpha_ann']:.2%}/yr (t {mr['alpha_t']:.1f})")
        lines.append("vol regimes (cut-offs from past data only):\n" + past_only_vol_regimes(daily.ret, mkt).round(3).to_string())
    if len(daily) > 100:
        bs = bootstrap_sharpe(daily.ret, spec.bootstrap_runs, seed=spec.seed)
        lines.append("Sharpe 95% block-bootstrap by block length: " +
                     ", ".join(f"{b}d [{lo:.2f}, {hi:.2f}]" for b, (lo, hi) in bs.items()))
        n_trials = 0 if a.reproduce else sum(1 for ln in Path("EXPERIMENTS.md").read_text().splitlines() if ln.startswith("|") and "---" not in ln) - 1 \
            if Path("EXPERIMENTS.md").exists() else 1
        if not a.reproduce:
            lines.append(f"deflated Sharpe vs {max(n_trials,1)} logged runs (independence assumed; see METHODOLOGY): "
                         f"{deflated_sharpe(daily.ret, max(n_trials, 1)):.2f}")
    text = "\n".join(lines)
    (out / "summary.txt").write_text(text)
    daily.join(expo.drop(columns=["gross_pct", "net_pct"])).to_csv(out / "daily.csv")
    trades.to_csv(out / "trades.csv", index=False)
    wins.to_csv(out / "windows.csv", index=False)
    print(text)
    if a.period != "synthetic" and Path("EXPERIMENTS.md").exists():
        with open("EXPERIMENTS.md", "a") as f:
            tag = "reproduction (after engine correction)" if a.reproduce else a.period
            f.write(f"| {dt.date.today()} | {tag if a.reproduce else a.period} | {spec.hash()} | gate={a.gate}, fill={a.fill} | "
                    f"Sharpe {perf_all['sharpe']:.2f}, {len(trades)} trades | "
                    f"{'re-run of ' + a.period + ' in ' + str(out) + '; not a fresh evaluation' if a.reproduce else ''} |\n")


if __name__ == "__main__":
    main()

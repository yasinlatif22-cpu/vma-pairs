"""Descriptive figures from completed runs (no strategy logic, no new tests). Written to figures/ (git-ignored: they use
CRSP-derived prices, so check your data licence before publishing them).

  python make_figures.py [results_dir]        (default results_rerun; needs data/raw files and data/processed/market.csv)
"""
import sys
from dataclasses import replace
from pathlib import Path

import matplotlib
import matplotlib.ticker
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from config import DEFAULT  # noqa: E402
from data_io import load_market  # noqa: E402
from signals import build_signals  # noqa: E402

BLUE, ORANGE, GREEN, RED, GREY = "#1f77b4", "#e07b00", "#2a9d4b", "#c0392b", "#777777"
REASON_COLOR = {"target": GREEN, "z_stop": RED, "max_hold": ORANGE, "window_end": GREY, "end_of_data": GREY, "loss_limit": RED}
PERIODS = {"dev": DEFAULT.dev, "val": DEFAULT.val, "holdout": DEFAULT.holdout}


def trades_of(res, period):
    t = pd.read_csv(Path(res) / f"{period}_none_open_next" / "trades.csv", parse_dates=["signal_date", "entry_date", "exit_signal_date", "exit_date"])
    t["period"] = period
    return t


def fig_spread(c, trades, out, period="val"):
    first, last = PERIODS[period]
    first_idx = c.index.searchsorted(pd.Timestamp(first))
    sig, _ = build_signals(c.loc[:last], DEFAULT, first_idx)
    z = sig.loc[first:last, "z"]
    t = trades[trades.period == period]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(z.index, z, color=GREY, lw=0.8)
    for y, ls in [(DEFAULT.entry_z, "--"), (-DEFAULT.entry_z, "--"), (DEFAULT.stop_z, ":"), (-DEFAULT.stop_z, ":"), (0, "-")]:
        ax.axhline(y, color="k", lw=0.5, ls=ls, alpha=0.5)
    for _, r in t.iterrows():
        zs = z.get(r.signal_date, np.nan)
        ax.scatter(r.signal_date, zs, marker="^" if r.side == 1 else "v", color=BLUE, s=36, zorder=3)
        ze = z.get(r.exit_signal_date, np.nan)
        ax.scatter(r.exit_signal_date, ze, marker="o", color=REASON_COLOR.get(r.exit_reason, GREY), s=30, zorder=3, edgecolor="k", lw=0.4)
    ax.set_ylabel("z-score of V/MA log spread (60-day)")
    ax.set_title(f"Spread z-score and trade signals, {period} {first[:4]}-{last[:4]} (open-fill run, {len(t)} trades)")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="^", color=BLUE, ls="", label="entry: long V / short MA"),
                       Line2D([], [], marker="v", color=BLUE, ls="", label="entry: short V / long MA")] +
                      [Line2D([], [], marker="o", color=col, ls="", markeredgecolor="k", label=f"exit: {k}") for k, col in
                       [("target", GREEN), ("z_stop", RED), ("max_hold", ORANGE), ("window_end", GREY)]], loc="upper left", ncol=2, fontsize=8)
    ax.set_ylim(-5, 5)
    fig.tight_layout()
    fig.savefig(out / "fig1_spread_zscore.png", dpi=160)
    plt.close(fig)


def fig_cases(c, trades, earnings, out):
    cases = [("2019-01-28", "Validation loser (long V / short MA)"), ("2021-03-19", "Validation winner (long V / short MA)"),
             ("2024-11-06", "Holdout worst (short V / long MA)")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, (sd, title) in zip(axes, cases):
        sd = pd.Timestamp(sd)
        r = trades[trades.signal_date == sd].iloc[0]
        i0 = c.index.get_loc(sd)
        i1 = c.index.get_loc(r.exit_date) if r.exit_date in c.index else len(c) - 1
        w = c.iloc[max(i0 - 20, 0): min(i1 + 6, len(c))]
        idx = w / c.loc[sd] * 100
        ax.plot(idx.index, idx["V"], color=BLUE, label="V")
        ax.plot(idx.index, idx["MA"], color=ORANGE, label="MA")
        ax.axvspan(r.entry_date, r.exit_date, color=GREY, alpha=0.15, label="position held")
        for tk, col in [("V", BLUE), ("MA", ORANGE)]:
            e = earnings[(earnings.tic == tk) & (earnings.rdq >= w.index[0]) & (earnings.rdq <= w.index[-1])].rdq
            for k, d in enumerate(e):
                ax.axvline(d, color=col, ls=":", lw=1.2, label=f"{tk} report date" if k == 0 else None)
        ax.set_title(f"{title}\nsignal {sd.date()}, {r.exit_reason}, net \\${r.net_pnl:,.0f}", fontsize=9)
        ax.set_ylabel("close, indexed to 100 at signal date")
        ax.tick_params(axis="x", rotation=30, labelsize=8)
        ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    fig.savefig(out / "fig2_case_studies.png", dpi=160)
    plt.close(fig)


def fig_pnl(trades, out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.4, 1]})
    bins = np.linspace(trades.net_pnl.min(), trades.net_pnl.max(), 24)
    a.hist([trades[trades.period == p].net_pnl for p in PERIODS], bins=bins, stacked=True, color=[BLUE, ORANGE, GREEN],
           label=[f"{p} (n={int((trades.period == p).sum())})" for p in PERIODS])
    a.axvline(0, color="k", lw=0.6)
    a.set_xlabel("net P&L per trade (US\\$, \\$1M account)")
    a.set_ylabel("number of trades")
    a.set_title(f"Trade P&L distribution, all periods (n={len(trades)}; mean \\${trades.net_pnl.mean():,.0f})")
    a.legend(fontsize=8)
    g = trades.groupby("exit_reason").net_pnl.agg(["sum", "count"]).sort_values("sum")
    b.barh([f"{k} (n={int(n)})" for k, n in zip(g.index, g["count"])], g["sum"], color=[REASON_COLOR.get(k, GREY) for k in g.index])
    b.axvline(0, color="k", lw=0.6)
    b.set_xlabel("total net P&L (US\\$ thousands)")
    b.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:,.0f}"))
    b.set_title("Net P&L by exit reason")
    fig.tight_layout()
    fig.savefig(out / "fig3_trade_pnl.png", dpi=160)
    plt.close(fig)


def main(res="results_rerun"):
    out = Path("figures")
    out.mkdir(exist_ok=True)
    o, c, d = load_market("data/processed/market.csv", [DEFAULT.y, DEFAULT.x])
    c = c.rename(columns={DEFAULT.y: "V", DEFAULT.x: "MA"}) if DEFAULT.y != "V" else c
    trades = pd.concat([trades_of(res, p) for p in PERIODS], ignore_index=True)
    e = pd.read_csv("data/raw/earnings.csv", parse_dates=["rdq"])
    e["tic"] = e.gvkey.map({179534: "V", 160225: "MA"})
    fig_spread(c.rename(columns={"V": DEFAULT.y, "MA": DEFAULT.x}) if DEFAULT.y != "V" else c, trades, out)
    fig_cases(c, trades, e, out)
    fig_pnl(trades, out)
    print("wrote", sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    main(*sys.argv[1:])

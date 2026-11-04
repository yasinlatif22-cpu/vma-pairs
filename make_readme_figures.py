"""Strategy-level figures for the README (no security prices, no price-level trade data): equity vs T-bills and drawdown,
execution sensitivity, trade P&L and concentration. Reads completed runs; adds no strategy logic.

  python make_readme_figures.py [results_dir]        (default results_rerun; needs data/raw/rf.csv) -> docs/img/*.png
"""
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker as mt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BG, GRID, TXT = "#000000", "#2a2a2a", "#d9d9d9"
AMBER, GREEN, RED, CYAN, GREY = "#ffa028", "#00d26a", "#ff3b30", "#2bc4ff", "#8a8a8a"
REASON = {"target": GREEN, "z_stop": RED, "max_hold": AMBER, "window_end": GREY, "end_of_data": CYAN}
PERIODS = ["dev", "val", "holdout"]
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "axes.edgecolor": "#555", "axes.labelcolor": TXT,
                     "xtick.color": TXT, "ytick.color": TXT, "text.color": TXT, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "font.family": "monospace", "font.size": 9, "axes.titlecolor": AMBER, "axes.titlesize": 10, "axes.titlelocation": "left"})
usd = mt.FuncFormatter(lambda v, _: f"{'-' if v < 0 else ''}${abs(v):,.0f}")
usdk = mt.FuncFormatter(lambda v, _: f"{'-' if v < 0 else ''}${abs(v) / 1000:,.0f}k")


def load(res, p, fill="open_next"):
    d = Path(res) / f"{p}_none_{fill}"
    daily = pd.read_csv(d / "daily.csv", parse_dates=["date"], index_col="date")
    tr = pd.read_csv(d / "trades.csv", parse_dates=["signal_date", "entry_date", "exit_date"])
    tr["period"] = p
    return daily, tr


def equity(res, out, rf):
    ret = pd.concat([load(res, p)[0].ret for p in PERIODS])
    eq = 1e6 * (1 + ret).cumprod()
    bm = 1e6 * (1 + rf.reindex(ret.index).ffill().fillna(0)).cumprod()
    dd = (eq / eq.cummax() - 1) * 100
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    a.plot(eq.index, eq, color=AMBER, lw=1.5, label="strategy, total equity (cash earns 0)")
    a.plot(bm.index, bm, color=CYAN, lw=1.2, ls=":", label="T-bills on $1M (Fama-French rf)")
    for x, t in (("2018-01-01", "VAL 2018-22"), ("2023-01-01", "HOLDOUT 2023-25 (spent)")):
        a.axvline(pd.Timestamp(x), color=AMBER, lw=0.8, ls="--")
        a.text(pd.Timestamp(x), a.get_ylim()[1], " " + t, color=AMBER, va="top", fontsize=8)
    a.text(pd.Timestamp("2009-02-01"), a.get_ylim()[1], " DEV 2009-17", color=AMBER, va="top", fontsize=8)
    a.yaxis.set_major_formatter(usd)
    a.set_title("EQUITY vs T-BILLS AND DRAWDOWN. Three independent $1M runs stitched by compounding; corrected-engine reproduction")
    a.legend(loc="upper left", bbox_to_anchor=(0.0, 0.88), facecolor=BG, edgecolor="#333", fontsize=8)
    b.fill_between(dd.index, dd, 0, color=RED, alpha=0.45, lw=0)
    b.plot(dd.index, dd, color=RED, lw=0.8)
    b.set_ylabel("drawdown %")
    fig.tight_layout()
    fig.savefig(out / "equity_drawdown.png", dpi=150)
    plt.close(fig)


def fills(res, out):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4), sharey=False)
    for a, p, lab in zip(ax, ("val", "dev"), ("VALIDATION 2018-22", "DEVELOPMENT 2009-17")):
        _, o = load(res, p)
        _, c = load(res, p, "close_next")
        m = o.merge(c, on="signal_date", suffixes=("_o", "_c")).sort_values("exit_date_o")
        assert len(m) == len(o) == len(c)
        a.step(m.exit_date_o, m.gross_pnl_o.cumsum(), where="post", color=AMBER, lw=1.5, label="open fill (primary)")
        a.step(m.exit_date_o, m.gross_pnl_c.cumsum(), where="post", color=CYAN, lw=1.5, label="close fill")
        d = (m.gross_pnl_o - m.gross_pnl_c).cumsum()
        a.fill_between(m.exit_date_o, d, 0, step="post", color=GREEN, alpha=0.25, lw=0, label="open minus close")
        a.yaxis.set_major_formatter(usdk)
        a.set_title(f"{lab}: CUMULATIVE GROSS P&L, SAME TRADES")
        a.legend(fontsize=8, facecolor=BG, edgecolor="#333", loc="upper left")
        if p == "val":
            _, v = load(res, "val")
            s = v[v.signal_date.isin(pd.to_datetime(["2020-03-16", "2020-03-20", "2020-03-25"]))]
            a.axvspan(s.entry_date.min(), s.exit_date.max(), color=RED, alpha=0.25, lw=0)
            a.annotate("3 March-2020 trades", (s.entry_date.min(), d.max() * 0.1), color=RED, fontsize=8, xytext=(-110, 40), textcoords="offset points",
                       arrowprops=dict(arrowstyle="-", color=RED))
    fig.tight_layout()
    fig.savefig(out / "execution_sensitivity.png", dpi=150)
    plt.close(fig)


def pnl(res, out):
    t = pd.concat([load(res, p)[1] for p in PERIODS], ignore_index=True)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4), gridspec_kw={"width_ratios": [1.3, 1, 1.3]})
    bins = np.linspace(t.net_pnl.min(), t.net_pnl.max(), 24)
    ax[0].hist([t[t.period == p].net_pnl for p in PERIODS], bins=bins, stacked=True, color=[CYAN, AMBER, GREEN],
               label=[f"{p} (n={int((t.period == p).sum())})" for p in PERIODS])
    ax[0].axvline(0, color="#777", lw=0.8)
    ax[0].xaxis.set_major_formatter(usdk)
    ax[0].set_title(f"NET P&L PER TRADE (n={len(t)}, mean ${t.net_pnl.mean():,.0f})")
    ax[0].legend(fontsize=8, facecolor=BG, edgecolor="#333")
    g = t.groupby("exit_reason").net_pnl.agg(["sum", "count"]).sort_values("sum")
    ax[1].barh([f"{k} (n={int(n)})" for k, n in zip(g.index, g["count"])], g["sum"], color=[REASON.get(k, GREY) for k in g.index])
    ax[1].axvline(0, color="#777", lw=0.8)
    ax[1].xaxis.set_major_formatter(usdk)
    ax[1].set_title("TOTAL NET P&L BY EXIT")
    r = t.sort_values("net_pnl", ascending=False).reset_index(drop=True)
    ax[2].bar(r.index + 1, r.net_pnl, color=[{"dev": CYAN, "val": AMBER, "holdout": GREEN}[p] for p in r.period], width=0.9)
    ax[2].axvspan(0.5, 3.5, color=AMBER, alpha=0.15, lw=0)
    ax[2].yaxis.set_major_formatter(usdk)
    ax[2].set_xlabel("trade rank (shaded = top 3)")
    ax[2].set_title("TRADES RANKED BY NET P&L")
    fig.tight_layout()
    fig.savefig(out / "trade_pnl.png", dpi=150)
    plt.close(fig)


def main(res="results_rerun"):
    out = Path("docs/img")
    out.mkdir(parents=True, exist_ok=True)
    rf = pd.read_csv("data/raw/rf.csv", parse_dates=["date"]).set_index("date").rf
    equity(res, out, rf)
    fills(res, out)
    pnl(res, out)
    print("wrote", sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    main(*sys.argv[1:])

"""Build public_results/: aggregate tables, captured diagnostic output and two figures from a results directory.

  python make_public_results.py [results_dir]        (default results_rerun)

Publishes only aggregates (no prices, no daily or trade-level files): licensed CRSP inputs and granular outputs derived
from them stay local. The figures show strategy equity and drawdown, not security prices."""
import contextlib
import io
import sys
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, "diagnostics")
import attribution, concentration, earnings_analysis, pooled_stats, trade_audit  # noqa: E402

from metrics import perf  # noqa: E402

RUNS = [("dev", "none", "open_next", "primary (fill at next open)"), ("dev", "none", "close_next", "fill at next close"),
        ("dev", "coint", "open_next", "cointegration gate"), ("val", "none", "open_next", "primary (fill at next open)"),
        ("val", "none", "close_next", "fill at next close"), ("val", "coint", "open_next", "cointegration gate"),
        ("holdout", "none", "open_next", "primary (run once; re-run here is a reproduction)")]


def capture(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a)
    return buf.getvalue()


def main(res="results_rerun"):
    out = Path("public_results")
    out.mkdir(exist_ok=True)
    rows = []
    for p, g, f, label in RUNS:
        d = pd.read_csv(f"{res}/{p}_{g}_{f}/daily.csv", parse_dates=["date"]).set_index("date")
        t = pd.read_csv(f"{res}/{p}_{g}_{f}/trades.csv")
        m = perf(d.ret)
        rows.append(f"| {p} | {label} | {len(t)} | {m['ann_ret']:.2%} | {m['ann_vol']:.2%} | {m['sharpe']:.2f} | {m['max_dd']:.1%} | "
                    f"{t.gross_pnl.sum():,.0f} | {t.costs.sum():,.0f} | {t.net_pnl.sum():,.0f} |")
    table = ("| period | variant | trades | ann. return | vol | Sharpe | max DD | gross P&L $ | costs $ | net P&L $ |\n"
             "|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
    (out / "runs.md").write_text(table)
    text = "".join(f"\n##### {n}\n{capture(fn, res)}" for n, fn in
                   (("pooled_stats", pooled_stats.main), ("attribution (open vs close fills)", attribution.main),
                    ("concentration", concentration.main), ("independent trade audit", trade_audit.main),
                    ("earnings diagnostic (exploratory)", earnings_analysis.main)))
    (out / "diagnostics_output.txt").write_text(text)

    fig, ax = plt.subplots(2, 3, figsize=(12, 5.5), sharey="row")
    for j, (p, title) in enumerate((("dev", "development 2009-17"), ("val", "validation 2018-22"), ("holdout", "holdout 2023-25")) ):
        d = pd.read_csv(f"{res}/{p}_none_open_next/daily.csv", parse_dates=["date"]).set_index("date")
        eq = (1 + d.ret).cumprod()
        ax[0, j].plot(eq.index, eq.values - 1, lw=1.2); ax[0, j].set_title(title); ax[0, j].axhline(0, color="grey", lw=.5)
        ax[1, j].fill_between(eq.index, (eq / eq.cummax() - 1).values, 0, color="tab:red", alpha=.5)
    for a in ax.ravel():
        a.xaxis.set_major_locator(mdates.YearLocator()); a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        a.tick_params(axis="x", labelsize=8)
    ax[0, 0].set_ylabel("cumulative net return"); ax[1, 0].set_ylabel("drawdown")
    fig.suptitle("V/MA pairs study: net return on $1M equity, fill at next open (each period an independent run; cash earns 0)", fontsize=10)
    fig.tight_layout(); fig.savefig(out / "equity_drawdown.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for a, p in zip(ax, ("dev", "val")):
        for f, lab in (("open_next", "fill next open"), ("close_next", "fill next close")):
            d = pd.read_csv(f"{res}/{p}_none_{f}/daily.csv", parse_dates=["date"]).set_index("date")
            a.plot(d.index, (d.equity / 1e6 - 1).values, lw=1.1, label=lab)
        a.set_title({"dev": "development 2009-17", "val": "validation 2018-22"}[p]); a.axhline(0, color="grey", lw=.5); a.legend()
    for a in ax:
        a.xaxis.set_major_locator(mdates.YearLocator()); a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax[0].set_ylabel("cumulative net P&L / initial equity")
    fig.suptitle("Execution sensitivity: identical trades, different fill price", fontsize=10)
    fig.tight_layout(); fig.savefig(out / "fill_sensitivity.png", dpi=130); plt.close(fig)
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main(*sys.argv[1:2])

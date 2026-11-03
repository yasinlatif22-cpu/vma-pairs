"""Print decision-time facts for the best, worst and suppressed trades of a run.

  python case_studies.py results/val_none_open_next [data/raw/earnings.csv]

Only facts observable when the order was placed are listed. The 'thesis check' lines are for YOU to fill in
from filings and news; do not read a cause into a price move after the fact.
Optional earnings.csv columns: ticker,date  (report dates).
"""
import sys

import pandas as pd

run = sys.argv[1]
tr = pd.read_csv(f"{run}/trades.csv", parse_dates=["signal_date", "entry_date", "exit_date"])
wins = pd.read_csv(f"{run}/windows.csv", parse_dates=["start", "end"])
earn = pd.read_csv(sys.argv[2], parse_dates=["date"]) if len(sys.argv) > 2 else None


def show(r, title):
    w = wins[(wins.start <= r.signal_date) & (wins.end >= r.signal_date)].iloc[0]
    side = "long V / short MA" if r.side == 1 else "short V / long MA"
    print(f"\n=== {title}: {side}, signal {r.signal_date.date()}, in {r.entry_date.date()}, out {r.exit_date.date()} ({r.exit_reason})")
    print(f"  known at signal time: window fit beta {w.beta:.2f}, formation half-life {w.half_life:.1f}d, "
          f"EG p {w.eg_p:.2f}, max hold {w.max_hold}d")
    print(f"  P&L: gross {r.gross_pnl:,.0f} + div {r.dividends:,.0f} - costs {r.costs:,.0f} - borrow {r.borrow:,.0f} = net {r.net_pnl:,.0f}")
    print(f"  V {r.entry_px_y:.2f}->{r.exit_px_y:.2f} ({r.exit_px_y / r.entry_px_y - 1:+.1%}), "
          f"MA {r.entry_px_x:.2f}->{r.exit_px_x:.2f} ({r.exit_px_x / r.entry_px_x - 1:+.1%})")
    if earn is not None:
        e = earn[(earn.date >= r.entry_date) & (earn.date <= r.exit_date)]
        print("  earnings inside the holding period:", ", ".join(f"{x.ticker} {x.date.date()}" for x in e.itertuples()) or "none")
    print("  thesis check (fill in): what changed in the V/MA relationship?  what would have invalidated convergence?")


tr = tr.sort_values("net_pnl")
for _, r in tr.tail(3).iloc[::-1].iterrows():
    show(r, "WINNER")
for _, r in tr.head(3).iterrows():
    show(r, "LOSER")
print("\nTrades by exit reason:\n", tr.groupby("exit_reason").net_pnl.agg(["count", "sum", "mean"]).round(0))

"""Print decision-time facts for the best, worst and suppressed trades of a run.

  python case_studies.py results_rerun/val_none_open_next

Only facts observable when the order was placed are listed. Causes are not inferred here; sourced write-ups
are in docs/CASE_STUDIES.md.
"""
import sys

import pandas as pd


def main(run):
    tr = pd.read_csv(f"{run}/trades.csv", parse_dates=["signal_date", "entry_date", "exit_date"])
    wins = pd.read_csv(f"{run}/windows.csv", parse_dates=["start", "end"])

    def show(r, title):
        w = wins[(wins.start <= r.signal_date) & (wins.end >= r.signal_date)].iloc[0]
        side = "long V / short MA" if r.side == 1 else "short V / long MA"
        print(f"\n=== {title}: {side}, signal {r.signal_date.date()}, in {r.entry_date.date()}, out {r.exit_date.date()} ({r.exit_reason})")
        print(f"  known at signal time: window fit beta {w.beta:.2f}, formation half-life {w.half_life:.1f} sessions, "
              f"EG p {w.eg_p:.2f}, max hold {w.max_hold} sessions")
        print(f"  P&L: gross {r.gross_pnl:,.0f} + div {r.dividends:,.0f} - costs {r.costs:,.0f} - borrow {r.borrow:,.0f} = net {r.net_pnl:,.0f}")
        print(f"  V {r.entry_px_y:.2f}->{r.exit_px_y:.2f} ({r.exit_px_y / r.entry_px_y - 1:+.1%}), "
              f"MA {r.entry_px_x:.2f}->{r.exit_px_x:.2f} ({r.exit_px_x / r.entry_px_x - 1:+.1%})")
        print(f"  held {r.hold_sessions} sessions ({r.hold_calendar_days} calendar days)")

    tr = tr.sort_values("net_pnl")
    for _, r in tr.tail(3).iloc[::-1].iterrows():
        show(r, "WINNER")
    for _, r in tr.head(3).iterrows():
        show(r, "LOSER")
    print("\nTrades by exit reason:\n", tr.groupby("exit_reason").net_pnl.agg(["count", "sum", "mean"]).round(0))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results_rerun/val_none_open_next")

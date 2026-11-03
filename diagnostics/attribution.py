"""Why does fill=open_next differ from fill=close_next?  Descriptive diagnostic; changes no strategy rule.

  python diagnostics/attribution.py [results_dir]        (default results_rerun; uses only the recorded trade prices)

Both runs hold identical trades and dates (signals use closes only), so the whole gross-P&L difference is fill prices.
Per trade, with open-fill quantities q and close-fill quantities q':
  G_open - G_close = sum_legs q*[(C_e-O_e) - (C_x-O_x)]  +  sum_legs (q-q')*(C_x-C_e)
                     = entry-day open->close move  -  exit-day open->close move  +  quantity term
The three components are computed separately and checked to sum to the difference (no residual plug)."""
import sys

import numpy as np
import pandas as pd

D = ["signal_date", "entry_date", "exit_signal_date", "exit_date"]


def trade_table(res, period):
    a = pd.read_csv(f"{res}/{period}_none_open_next/trades.csv", parse_dates=D)
    b = pd.read_csv(f"{res}/{period}_none_close_next/trades.csv", parse_dates=D)
    m = a.merge(b, on=["signal_date", "side"], suffixes=("_o", "_c"))
    assert len(m) == len(a) == len(b), "open and close runs must contain the same trades"
    assert (m.entry_date_o == m.entry_date_c).all() and (m.exit_date_o == m.exit_date_c).all()
    rows = []
    for _, r in m.iterrows():
        ent = ex = qty = 0.0
        for leg in ("y", "x"):                     # recorded fill prices: entry/exit price in each run, per leg
            qo, qc = r[f"qty_{leg}_o"], r[f"qty_{leg}_c"]
            pe_o, pe_c, px_o, px_c = r[f"entry_px_{leg}_o"], r[f"entry_px_{leg}_c"], r[f"exit_px_{leg}_o"], r[f"exit_px_{leg}_c"]
            ent += qo * (pe_c - pe_o)              # entry: close-run fills at the entry-day close, open-run at its open
            ex += qo * (px_c - px_o)               # exit: same on the exit day (zero for an end-of-data mark-out)
            qty += (qo - qc) * (px_c - pe_c)       # sizing differs slightly because equity differs at signal time
        diff = r.gross_pnl_o - r.gross_pnl_c
        assert abs(diff - (ent - ex + qty)) < 1e-6 * max(1.0, abs(diff)), "attribution components must reconcile"
        rows.append(dict(signal=r.signal_date.date(), side=int(r.side), reason=r.exit_reason_o, gross_open=r.gross_pnl_o,
                         gross_close=r.gross_pnl_c, diff=diff, entry_intraday=ent, exit_intraday=-ex, qty_term=qty))
    return pd.DataFrame(rows)


def report(res, period):
    d = trade_table(res, period)
    print(f"\n=== {period}: {len(d)} matched trades (identical dates and exit reasons)")
    print(d[["gross_open", "gross_close", "diff", "entry_intraday", "exit_intraday", "qty_term"]].sum().round(0).to_string())
    top = d.reindex(d["diff"].abs().sort_values(ascending=False).index).head(5)
    print("largest |diff| trades:\n", top.round(0).to_string(index=False))
    mar = pd.to_datetime(d.signal).between("2020-03-01", "2020-03-31")
    if mar.any():
        rest = d[~mar]["diff"]
        print(f"March-2020 signals: {mar.sum()} trades, diff {d[mar]['diff'].sum():,.0f}; other {len(rest)} trades, diff {rest.sum():,.0f} "
              f"(mean {rest.mean():,.0f}, t {rest.mean() / (rest.std() / np.sqrt(len(rest))):.2f})")
    print(f"open beat close in {(d['diff'] > 0).mean():.0%} of trades; mean diff {d['diff'].mean():,.0f}, "
          f"t {d['diff'].mean() / (d['diff'].std() / np.sqrt(len(d))):.2f}")
    return d


def main(res="results_rerun"):
    for p in ("dev", "val"):
        report(res, p)


if __name__ == "__main__":
    main(*sys.argv[1:2])

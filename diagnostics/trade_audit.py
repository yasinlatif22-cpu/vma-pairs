"""Independent re-computation of selected trades from raw CRSP fields (not from market.csv or the engine).
Works in ACTUAL shares and RAW prices: N_actual(t) = qty_adj / cfacpr(t).  Run locally; prints only
audit lines. Checks gross P&L, dividends (cash = (ret-retx)*prior raw close * shares held at start of day), costs, borrow
and net P&L against trades.csv.  Costs/borrow are re-derived from the documented assumptions (5 bps/leg-fill; 30 bps/yr/night on short MV)."""
import sys
import numpy as np
import pandas as pd

raw = pd.read_csv("data/raw/crsp_daily.csv", parse_dates=["date"])
raw["p"] = raw.prc.abs(); raw["o"] = raw.openprc.abs()
R = {t: g.set_index("date").sort_index() for t, g in raw.groupby("ticker")}
CB, BB = 5e-4, 30e-4 / 365


def audit(path, signal_date, fill="open"):
    t = pd.read_csv(path, parse_dates=["signal_date", "entry_date", "exit_signal_date", "exit_date"])
    r = t[t.signal_date == pd.Timestamp(signal_date)].iloc[0]
    e, x = r.entry_date, r.exit_date
    print(f"\n--- trade signal {r.signal_date.date()} entry {e.date()} exit {x.date()} side {int(r.side)} reason {r.exit_reason} ({r.hold_days}d)")
    gross = div = costs = borrow = 0.0
    px = "o" if fill == "open" else "p"
    legs = {"V": r.qty_y, "MA": r.qty_x}
    for tk, q in legs.items():
        d = R[tk]; cf = d.cfacpr
        n_e = q / cf[e]                    # adjusted price = raw/cfacpr, so actual shares = adjusted shares / cfacpr
        P_e, P_x = d.at[e, px], d.at[x, px]
        n_x = q / cf[x]
        g = n_x * P_x - n_e * P_e
        gross += g
        days = d.loc[e:x].index[1:]
        for k in days:
            prev = d.index[d.index.get_loc(k) - 1]
            n_hold = q / cf[prev]
            cash = (d.at[k, "ret"] - d.at[k, "retx"]) * d.at[prev, "p"]
            if cash > 1e-4 * 1: div += n_hold * cash
        costs += CB * (abs(n_e) * P_e + abs(n_x) * P_x)
        if q < 0:
            for k in d.loc[e:x].index[:-1]:       # nights held short: close(k) -> next day, calendar nights
                nxt = d.index[d.index.get_loc(k) + 1]
                borrow += BB * abs(q / cf[k]) * d.at[k, "p"] * (nxt - k).days
    net = gross + div - costs - borrow
    out = lambda n, a, b: print(f"  {n:9s} independent {a:>12,.2f}  engine {b:>12,.2f}  diff {a-b:>9,.2f}")
    out("gross", gross, r.gross_pnl); out("dividends", div, r.dividends); out("costs", costs, r.costs)
    out("borrow", borrow, r.borrow); out("net", net, r.net_pnl)
    return r


if __name__ == "__main__":
    path = sys.argv[1]
    for sd in sys.argv[2:]:
        audit(path, sd)

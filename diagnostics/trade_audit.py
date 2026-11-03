"""Independent re-computation of complete trades from raw CRSP fields.

  python diagnostics/trade_audit.py [results_dir]        (default results_rerun; needs data/raw/crsp_daily.csv)

Independence: this file does not import the engine or data_io. It reads the raw CRSP extract (unadjusted price, open,
cfacpr, ret, retx), works in ACTUAL shares (adjusted quantity / cfacpr) at RAW prices, derives distributions as
(ret - retx) * prior raw close, pays them to shares held at the start of each day after entry, and re-derives costs
(5 bps per fill) and borrow (30 bps/yr per calendar night, on short value at each close held, none after the exit).
What it does NOT verify: that the CRSP file is correct (both implementations read it). See docs/ACCOUNTING_AUDIT.md."""
import sys

import pandas as pd

CB, BB = 5e-4, 30e-4 / 365
D = ["signal_date", "entry_date", "exit_signal_date", "exit_date"]


def load_raw(path="data/raw/crsp_daily.csv"):
    raw = pd.read_csv(path, parse_dates=["date"])
    raw["p"], raw["o"] = raw.prc.abs(), raw.openprc.abs()
    return {t: g.set_index("date").sort_index() for t, g in raw.groupby("ticker")}


def audit(R, r, fill="open"):
    """r: one row of trades.csv. Returns dict of independent vs engine amounts."""
    e, x = r.entry_date, r.exit_date
    gross = div = costs = borrow = 0.0
    exit_col = "p" if r.exit_reason == "end_of_data" else ("o" if fill == "open" else "p")   # final mark-out is at the close
    entry_col = "o" if fill == "open" else "p"
    for tk, q in (("V", r.qty_y), ("MA", r.qty_x)):
        d = R[tk]; cf = d.cfacpr
        n_e, n_x = q / cf[e], q / cf[x]                  # adjusted price = raw/cfacpr, so actual shares = adjusted shares / cfacpr
        P_e, P_x = d.at[e, entry_col], d.at[x, exit_col]
        gross += n_x * P_x - n_e * P_e
        for k in d.loc[e:x].index[1:]:
            prev = d.index[d.index.get_loc(k) - 1]
            cash = (d.at[k, "ret"] - d.at[k, "retx"]) * d.at[prev, "p"]
            if cash > 1e-4:
                div += (q / cf[prev]) * cash
        costs += CB * (abs(n_e) * P_e + abs(n_x) * P_x)
        if q < 0:
            for k in d.loc[e:x].index[:-1]:
                nxt = d.index[d.index.get_loc(k) + 1]
                borrow += BB * abs(q / cf[k]) * d.at[k, "p"] * (nxt - k).days
    return dict(gross=(gross, r.gross_pnl), dividends=(div, r.dividends), costs=(costs, r.costs), borrow=(borrow, r.borrow),
                net=(gross + div - costs - borrow, r.net_pnl))


def pick(t):
    """Selection rule (stated, not cherry-picked): first long-V trade, first short-V trade, a split-spanning trade, the
    dividend-heavy trade with the largest absolute dividends, the first window-boundary exit, and any end-of-data exit."""
    out = {}
    out["long V / short MA"] = t[t.side == 1].iloc[0]
    out["short V / long MA"] = t[t.side == -1].iloc[0]
    for nm, dt in (("spans MA 10-for-1 split (2014-01-22)", "2014-01-22"), ("spans V 4-for-1 split (2015-03-19)", "2015-03-19")):
        s = t[(t.entry_date <= dt) & (t.exit_date >= dt)]
        if len(s):
            out[nm] = s.iloc[0]
    out["largest |dividends|"] = t.loc[t.dividends.abs().idxmax()]
    w = t[t.exit_reason == "window_end"]
    if len(w):
        out["window-boundary exit"] = w.iloc[0]
    eod = t[t.exit_reason == "end_of_data"]
    if len(eod):
        out["end-of-data liquidation"] = eod.iloc[0]
    return out


def main(res="results_rerun", tol=0.01):
    R = load_raw()
    t = pd.concat([pd.read_csv(f"{res}/{p}_none_open_next/trades.csv", parse_dates=D) for p in ("dev", "val", "holdout")], ignore_index=True)
    worst = 0.0
    for label, r in pick(t).items():
        a = audit(R, r)
        print(f"\n--- {label}: signal {r.signal_date.date()} entry {r.entry_date.date()} exit {r.exit_date.date()} "
              f"side {int(r.side)} {r.exit_reason} ({r.hold_sessions} sessions / {r.hold_calendar_days} calendar days)")
        for k, (ind, eng) in a.items():
            print(f"  {k:9s} independent {ind:>12,.2f}  engine {eng:>12,.2f}  diff {ind - eng:>9,.4f}")
            worst = max(worst, abs(ind - eng))
    print(f"\nlargest absolute difference across audited trades: {worst:.4f}")
    assert worst < tol, "independent reconstruction disagrees with the engine"


if __name__ == "__main__":
    main(*sys.argv[1:2])

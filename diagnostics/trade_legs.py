"""Leg-level dollar attribution for every trade, re-derived from the market file without the engine's helpers.

  python diagnostics/trade_legs.py [results_dir] [period]      (defaults results_rerun, all periods; prints the case trades)

For each trade and leg (V, MA), using the recorded share counts and fill prices:
  price P&L   = shares x (exit fill - entry fill)
  dividends   = shares x cash distribution on each ex-date after the entry session up to and including the exit session
                (holders at the start of a session receive that session's distribution, as in the engine)
  costs       = cost rate x |shares| x (entry fill + exit fill)
  borrow      = the engine's daily borrow charge on the short leg for each close while held (read from daily.csv)
The legs must add to the trade's net P&L within one cent, otherwise the script fails.

Estimated market contribution (labelled an estimate): each leg's beta is the OLS slope of its daily total return on the market
return (Fama-French mktrf + rf) over the 252 sessions ending at the signal close, so it uses past data only. Contribution =
beta x signed entry notional x market return over the holding interval. The interval is approximated by close-to-close market
returns from the session before entry through the session before exit (the fills are at opens, the factor data are close to
close). Residual = leg price P&L - estimated market contribution."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from config import DEFAULT  # noqa: E402

CASES = {"2019-01-28": "val", "2021-03-19": "val", "2024-11-06": "holdout"}


def load_inputs(res="results_rerun"):
    m = pd.read_csv("data/processed/market.csv", parse_dates=["date"])
    px = {k: m.pivot(index="date", columns="ticker", values=k) for k in ("open", "close", "div")}
    f = pd.read_csv("data/raw/rf.csv", parse_dates=["date"]).set_index("date")
    mkt = (f.mktrf + f.rf).rename("mkt")
    return px, mkt


def legs(trades, daily, px, mkt, spec=DEFAULT, window=252):
    names = (spec.y, spec.x)
    close, div = px["close"][list(names)], px["div"][list(names)].fillna(0.0)
    tr = (close + div) / close.shift(1) - 1
    cal = close.index
    rows = []
    for t in trades.itertuples():
        e, x, s = cal.get_loc(t.entry_date), cal.get_loc(t.exit_date), cal.get_loc(t.signal_date)
        held_div_days = cal[e + 1: x + 1]
        borrow = daily.borrow.reindex(cal[e:x]).fillna(0.0).sum()      # closes while held (none after the exit fill)
        est = tr.iloc[s - window + 1: s + 1].join(mkt, how="inner").dropna()
        mret = (1 + mkt.reindex(cal[e - 1: x])).prod() - 1
        rec = dict(signal_date=t.signal_date, entry_date=t.entry_date, exit_date=t.exit_date, side=t.side, exit_reason=t.exit_reason,
                   net_pnl=t.net_pnl, equity_basis=t.equity_basis, market_return=mret, borrow=borrow)
        total = -borrow
        for leg, q, p0, p1 in ((names[0], t.qty_y, t.entry_px_y, t.exit_px_y), (names[1], t.qty_x, t.entry_px_x, t.exit_px_x)):
            price = q * (p1 - p0)
            dv = q * div[leg].reindex(held_div_days).sum()
            cost = spec.cost_bps / 1e4 * abs(q) * (p0 + p1)
            b = np.polyfit(est["mkt"], est[leg], 1)[0] if len(est) > 60 else np.nan
            mc = b * q * p0 * mret
            rec.update({f"{leg}_shares": q, f"{leg}_notional": q * p0, f"{leg}_price_pnl": price, f"{leg}_dividends": dv,
                        f"{leg}_costs": cost, f"{leg}_beta": b, f"{leg}_market_est": mc, f"{leg}_residual": price - mc})
            total += price + dv - cost
        rec["legs_total"] = total
        if abs(total - t.net_pnl) > 0.01:
            raise AssertionError(f"leg attribution {total:,.2f} != trade net {t.net_pnl:,.2f} for signal {t.signal_date.date()}")
        rows.append(rec)
    return pd.DataFrame(rows)


def main(res="results_rerun", period=None):
    px, mkt = load_inputs(res)
    out = []
    for p in ([period] if period else ["dev", "val", "holdout"]):
        d = f"{res}/{p}_none_open_next"
        t = pd.read_csv(f"{d}/trades.csv", parse_dates=["signal_date", "entry_date", "exit_signal_date", "exit_date"])
        daily = pd.read_csv(f"{d}/daily.csv", parse_dates=["date"]).set_index("date")
        out.append(legs(t, daily, px, mkt).assign(period=p))
    al = pd.concat(out, ignore_index=True)
    print(f"{len(al)} trades: legs reconcile to net P&L within $0.01 (max abs diff {np.abs(al.legs_total - al.net_pnl).max():.2e})")
    for sd in CASES:
        r = al[al.signal_date == pd.Timestamp(sd)].iloc[0]
        print(f"\nsignal {sd} ({'long V / short MA' if r.side == 1 else 'short V / long MA'}), {r.exit_reason}, net ${r.net_pnl:,.0f}; "
              f"market return over hold {r.market_return:+.2%}")
        for leg in ("V", "MA"):
            print(f"  {leg:2s} notional ${r[f'{leg}_notional']:>11,.0f}  price P&L ${r[f'{leg}_price_pnl']:>9,.0f}  dividends ${r[f'{leg}_dividends']:>6,.0f}  "
                  f"costs ${r[f'{leg}_costs']:>6,.0f}  beta {r[f'{leg}_beta']:.2f}  est. market ${r[f'{leg}_market_est']:>8,.0f}  residual ${r[f'{leg}_residual']:>9,.0f}")
        print(f"  borrow ${r.borrow:,.0f}; estimated net market contribution ${r.V_market_est + r.MA_market_est:,.0f}")
    return al


if __name__ == "__main__":
    main(*sys.argv[1:3])

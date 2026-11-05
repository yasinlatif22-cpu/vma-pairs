"""Financing scenarios as one coherent account, with holdings fixed exactly as run (fixed-holdings attribution).

The engine run supplies holdings, trades, costs, borrow fees and dividends, sized off the engine's own equity E. Financing
income or cost accrues to a separate cash balance F and is NOT used to resize positions. The financed account's equity is
E + F, and every daily return uses the same denominator:
    ret_t = (E_t - E_{t-1} + f_t) / (E_{t-1} + F_{t-1}),   f_t = financing accrued over day t on prior-close balances.

Balances at the prior close (engine values; positions are cash-funded, no margin loan):
  E  equity;  L  long market value;  S  short market value (absolute);  cash = E - L + S (short-sale proceeds sit in cash)
  restricted short proceeds   S            held as collateral by the lender; earn a rebate only in S2
  posted margin               m x S        own cash posted against the short (m = 0.5: Regulation T initial margin, total
                                           collateral 150% of short value); earns nothing
  free cash                   E + F - L - m x S   earns rf in S1 and S2; if negative it is a debit balance charged
                                           rf + DEBIT_SPREAD (not observed in these runs; reported if it occurs)
Scenarios:  S0 as run (no financing);  S1 interest on free cash;  S2 = S1 + rebate of max(0, rf - REBATE_SPREAD) on S.
Borrow fees are already inside the engine's trading P&L and are not charged again. rf is the Fama-French daily risk-free
return (decimal per trading day), applied to the previous close's balances.
Benchmark: $1M in T-bills compounding at rf over the same dates. Rebate and debit spreads are illustrative assumptions;
actual terms depend on the broker, the lender and the name."""
from pathlib import Path

import numpy as np
import pandas as pd

MARGIN = 0.5
REBATE_SPREAD = 0.005     # annual
DEBIT_SPREAD = 0.005      # annual


def account(daily, rf, scenario="S1", initial=1_000_000.0, margin=MARGIN, rebate_spread=REBATE_SPREAD, debit_spread=DEBIT_SPREAD):
    """daily: engine daily frame (equity, long_mv, short_mv). rf: daily decimal Series. Returns a frame of daily components."""
    if scenario not in ("S0", "S1", "S2"):
        raise ValueError("scenario must be S0, S1 or S2")
    r = rf.reindex(daily.index).ffill().fillna(0.0).to_numpy()
    E = daily.equity.to_numpy(float)
    L = daily.long_mv.to_numpy(float)
    S = np.abs(daily.short_mv.to_numpy(float))
    n = len(E)
    Ep, Lp, Sp = np.r_[initial, E[:-1]], np.r_[0.0, L[:-1]], np.r_[0.0, S[:-1]]
    F = np.zeros(n); interest = np.zeros(n); rebate = np.zeros(n); debit = np.zeros(n); ret = np.zeros(n)
    f_prev = 0.0
    for t in range(n):
        if scenario != "S0":
            free = Ep[t] + f_prev - Lp[t] - margin * Sp[t]
            if free >= 0:
                interest[t] = r[t] * free
            else:
                debit[t] = (r[t] + debit_spread / 252) * free          # negative
            if scenario == "S2":
                rebate[t] = max(0.0, r[t] - rebate_spread / 252) * Sp[t]
        f = interest[t] + rebate[t] + debit[t]
        ret[t] = (E[t] - Ep[t] + f) / (Ep[t] + f_prev)
        f_prev += f
        F[t] = f_prev
    out = pd.DataFrame(dict(trading_pnl=E - Ep, interest=interest, rebate=rebate, debit=debit, financing_cum=F,
                            equity_fin=E + F, ret=ret, rf=r), index=daily.index)
    err = out.equity_fin.iloc[-1] - initial - out.trading_pnl.sum() - (interest.sum() + rebate.sum() + debit.sum())
    if not np.isfinite(err) or abs(err) > 0.01:
        raise AssertionError(f"financing account does not reconcile: {err}")
    return out


def tbill(index, rf, initial=1_000_000.0):
    r = rf.reindex(index).ffill().fillna(0.0)
    return initial * (1 + r).cumprod()


def load_rf(raw="data/raw"):
    """Daily risk-free return series and a label saying where it came from.

    Preferred: Fama-French MONTHLY rf (rf_monthly.csv) spread evenly over the month's trading days, compounding to the monthly
    rate: daily = (1 + rf_m) ** (1 / n_days) - 1, using the trading calendar of rf.csv. Fallback: Fama-French DAILY rf as stored
    on WRDS, which is rounded to 0.0001 a day (it can only show 0%, 2.52% or 5.04% a year); results from it are approximate."""
    raw = Path(raw)
    daily = pd.read_csv(raw / "rf.csv", parse_dates=["date"]).set_index("date").rf
    mpath = raw / "rf_monthly.csv"
    if mpath.exists():
        m = pd.read_csv(mpath, parse_dates=["date"])
        m["ym"] = m.date.dt.to_period("M")
        cal = pd.Series(daily.index, index=daily.index)
        ym = cal.dt.to_period("M")
        n = ym.map(ym.value_counts())
        rm = ym.map(m.set_index("ym").rf)
        out = ((1 + rm) ** (1 / n) - 1).rename("rf")
        if out.notna().any():
            return out.dropna(), "Fama-French monthly rf, spread over trading days"
    return daily, "Fama-French daily rf as stored on WRDS (rounded to 0.0001 a day; approximate, re-pull pending)"

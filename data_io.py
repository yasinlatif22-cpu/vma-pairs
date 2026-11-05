"""Canonical market file, CRSP conversion, and a synthetic generator for tests.

Canonical long file: date,ticker,open,close,div
  open/close: split-adjusted (NOT dividend-adjusted) prices; div: cash per split-adjusted share on ex-date.
Market file: date,mkt_ret (CRSP value-weighted index return) used only for exposure/regime reporting.
"""
import numpy as np
import pandas as pd


def from_crsp(raw):
    """raw columns: date, ticker, prc, openprc, ret, retx, cfacpr  (legacy CRSP names; see extract_wrds.py).
    Split-adjusts prices with cfacpr and derives the cash distribution as (ret - retx) * previous adjusted close."""
    r = raw.sort_values(["ticker", "date"]).copy()
    r["close"] = r.prc.abs() / r.cfacpr
    r["open"] = r.openprc.abs() / r.cfacpr
    r["div"] = ((r.ret - r.retx).clip(lower=0) * r.groupby("ticker").close.shift(1)).where(lambda s: s > 1e-4, 0.0)
    return r[["date", "ticker", "open", "close", "div"]].assign(date=lambda d: pd.to_datetime(d.date))


def load_market(path, tickers, start=None, end=None):
    """Wide open/close/div frames on the dates where BOTH tickers have a close. Dates with a missing open
    keep the row; the engine raises if an order must fill at a missing price. Nothing is forward-filled."""
    df = pd.read_csv(path, parse_dates=["date"])
    df = df[df.ticker.isin(tickers)]
    wide = {k: df.pivot(index="date", columns="ticker", values=k)[list(tickers)] for k in ("open", "close", "div")}
    ok = wide["close"].notna().all(axis=1)
    wide = {k: v[ok] for k, v in wide.items()}
    wide["div"] = wide["div"].fillna(0.0)
    if start or end:
        wide = {k: v.loc[start:end] for k, v in wide.items()}
    return wide["open"], wide["close"], wide["div"]


def synthetic_market(seed=0, n=1800, beta=1.0, alpha=0.0, half_life=12.0, spread_sd=0.04, cointegrated=True,
                     start="2012-01-02", return_truth=False):
    """Simulated pair for tests and demonstrations. NOT market data.

    Construction (closes, in logs):   log V_t = alpha + beta * log MA_t + s_t
      log MA_t : random walk with drift (common market factor plus idiosyncratic noise)
      s_t      : stationary AR(1) with the given half-life and stationary s.d. when cointegrated=True;
                 a driftless random walk with the same innovation s.d. when cointegrated=False (control: no relation).
    Opens: each open lies on the overnight path from the previous close, log o_t = log c_{t-1} + u_t (log c_t - log c_{t-1})
      + small noise, u_t ~ U(0.2, 0.6), so the open-to-close and close-to-open moves add up to the day's move.
    Distributions: a cash amount on quarterly ex-dates equal to a fixed yield on the previous close (MA 0.15%, V 0.20%).
      Prices are the constructed series and are not reduced on ex-dates, so total return = price return + distribution.
    Returns (long frame, market return); with return_truth=True also a dict holding the exact spread and parameters."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    mkt = rng.normal(0.0003, 0.008, n)
    lm = np.log(100.0) + np.cumsum(mkt + rng.normal(0, 0.007, n))
    phi = np.exp(-np.log(2) / half_life)
    sd_eps = spread_sd * np.sqrt(1 - phi ** 2)
    eps = rng.normal(0, sd_eps, n)
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = (phi if cointegrated else 1.0) * s[t - 1] + eps[t]
    lv = alpha + beta * lm + s
    out = []
    for name, lc, dy in (("MA", lm, 0.0015), ("V", lv, 0.002)):
        c = np.exp(lc)
        prev = np.r_[c[0] / np.exp(mkt[0]), c[:-1]]
        u = rng.uniform(0.2, 0.6, n)
        o = np.exp(np.log(prev) + u * (lc - np.log(prev)) + rng.normal(0, 0.001, n))
        ex = (np.arange(n) % 63) == 30
        d = np.where(ex, dy * prev, 0.0)
        out.append(pd.DataFrame({"date": idx, "ticker": name, "open": o, "close": c, "div": d}))
    long = pd.concat(out, ignore_index=True)
    mret = pd.Series(mkt, idx, name="mkt_ret")
    if return_truth:
        return long, mret, dict(spread=pd.Series(s, idx), alpha=alpha, beta=beta, phi=phi if cointegrated else 1.0,
                                cointegrated=cointegrated, innovations=pd.Series(eps, idx))
    return long, mret

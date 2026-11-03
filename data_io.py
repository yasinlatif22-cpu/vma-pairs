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
    keep the row (the engine skips fills on missing prices); nothing is forward-filled."""
    df = pd.read_csv(path, parse_dates=["date"])
    df = df[df.ticker.isin(tickers)]
    wide = {k: df.pivot(index="date", columns="ticker", values=k)[list(tickers)] for k in ("open", "close", "div")}
    ok = wide["close"].notna().all(axis=1)
    wide = {k: v[ok] for k, v in wide.items()}
    wide["div"] = wide["div"].fillna(0.0)
    if start or end:
        wide = {k: v.loc[start:end] for k, v in wide.items()}
    return wide["open"], wide["close"], wide["div"]


def synthetic_market(seed=0, n=1800, beta=1.0, half_life=12.0, spread_sd=0.04, planted=True):
    """Simulated Y/X with opens and quarterly dividends. planted=False: spread is a random walk (no edge)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2012-01-02", periods=n)
    m_gap, m_in = rng.normal(0, .003, n), rng.normal(0.0003, .008, n)
    x_gap, x_in = m_gap + rng.normal(0, .003, n), m_in + rng.normal(0, .007, n)
    y_gap, y_in = m_gap + rng.normal(0, .003, n), m_in + rng.normal(0, .007, n)
    phi = np.exp(-np.log(2) / half_life)
    eps = rng.normal(0, spread_sd * np.sqrt(1 - phi ** 2), n) if planted else rng.normal(0, .004, n)
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = (phi if planted else 1.0) * s[t - 1] + eps[t]
    y_in = y_in + beta * 0 + np.diff(s, prepend=0)
    out, mret = [], pd.Series(m_gap + m_in, idx)
    for name, g, i_, dy in (("X", x_gap, x_in, 0.0015), ("Y", y_gap, y_in, 0.002)):
        close, prev, o, c, d = 100.0, 100.0, np.zeros(n), np.zeros(n), np.zeros(n)
        for t in range(n):
            ex = t % 63 == 30
            d[t] = dy * prev if ex else 0.0
            o[t] = prev * np.exp(g[t]) - d[t]
            c[t] = o[t] * np.exp(i_[t])
            prev = c[t]
        out.append(pd.DataFrame({"date": idx, "ticker": {"X": "MA", "Y": "V"}[name], "open": o, "close": c, "div": d}))
    return pd.concat(out), mret.rename("mkt_ret")

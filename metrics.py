"""Performance, exposure and inference helpers."""
import numpy as np
import pandas as pd
import statsmodels.api as sm


def drawdown(r):
    """Drawdown path of a return series, with the initial capital (equity 1.0) included in the running peak,
    so an immediate first-day loss counts as a drawdown."""
    r = pd.Series(r).fillna(0.0)
    eq = (1 + r).cumprod()
    peak = np.maximum.accumulate(np.r_[1.0, eq.values])[1:]
    return pd.Series(eq.values / peak - 1, index=r.index)


def perf(r, periods=252):
    """mean_ann_ret: arithmetic mean daily return x periods (what Sharpe uses). cagr: compound annual growth.
    ann_ret is kept as an alias of mean_ann_ret for existing callers."""
    r = pd.Series(r).dropna()
    if len(r) < 2 or r.std() == 0:
        return dict(ann_ret=np.nan, mean_ann_ret=np.nan, cagr=np.nan, ann_vol=np.nan, sharpe=np.nan, max_dd=np.nan)
    m = r.mean() * periods
    cagr = float((1 + r).prod() ** (periods / len(r)) - 1)
    return dict(ann_ret=m, mean_ann_ret=m, cagr=cagr, ann_vol=r.std() * np.sqrt(periods),
                sharpe=r.mean() / r.std() * np.sqrt(periods), max_dd=float(drawdown(r).min()))


def market_regression(r, mkt, periods=252):
    df = pd.concat([r, mkt], axis=1, keys=["y", "x"]).dropna()
    res = sm.OLS(df.y, sm.add_constant(df.x)).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return dict(alpha_ann=res.params["const"] * periods, alpha_t=res.tvalues["const"],
                beta=res.params["x"], beta_t=res.tvalues["x"])


def bootstrap_sharpe(r, runs, blocks=(5, 10, 21, 42), seed=0, periods=252):
    """Circular block bootstrap 95% interval of the annualised Sharpe, for several block lengths.
    This resamples the realised return path; it does NOT re-run the research process or selection."""
    r = np.asarray(pd.Series(r).dropna())
    n, rng, out = len(r), np.random.default_rng(seed), {}
    for b in blocks:
        nb, sh = int(np.ceil(n / b)), np.empty(runs)
        for k in range(runs):
            idx = (rng.integers(0, n, nb)[:, None] + np.arange(b)).ravel()[:n] % n
            s = r[idx]
            sh[k] = s.mean() / s.std() * np.sqrt(periods) if s.std() > 0 else 0.0
        out[b] = tuple(np.percentile(sh, [2.5, 97.5]))
    return out


def rolling_beta(close, mkt, window=252):
    """Each stock's beta to the market using returns up to t-1 only."""
    rets = close.pct_change()
    cov = rets.rolling(window).cov(mkt.reindex(rets.index))
    var = mkt.reindex(rets.index).rolling(window).var()
    return cov.div(var, axis=0).shift(1)


def exposure_report(daily, close, mkt, spec):
    """Daily gross, net and estimated market exposure (beta-weighted) as % of equity."""
    out = daily[["gross_pct", "net_pct"]].copy()
    if mkt is not None:
        b = rolling_beta(close, mkt).reindex(daily.index)
        out["mkt_exposure_pct"] = (daily.mv_y * b[spec.y] + daily.mv_x * b[spec.x]) / daily.equity
    return out


def past_only_vol_regimes(r, mkt, window=21, min_obs=252):
    """Tercile of trailing market vol, with cut-offs from past observations only (expanding quantiles)."""
    vol = mkt.rolling(window).std().shift(1) * np.sqrt(252)
    lo = vol.expanding(min_obs).quantile(1 / 3).shift(1)
    hi = vol.expanding(min_obs).quantile(2 / 3).shift(1)
    lab = pd.Series(np.where(vol <= lo, "low", np.where(vol <= hi, "mid", "high")), index=vol.index)
    lab[lo.isna() | vol.isna()] = np.nan
    df = pd.concat([r, lab], axis=1, keys=["r", "reg"]).dropna()
    return df.groupby("reg").r.agg(days="size", mean_daily="mean", sharpe=lambda x: x.mean() / x.std() * np.sqrt(252))

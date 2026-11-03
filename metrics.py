"""Performance, exposure and inference helpers."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


def perf(r, periods=252):
    r = pd.Series(r).dropna()
    if len(r) < 2 or r.std() == 0:
        return dict(ann_ret=np.nan, ann_vol=np.nan, sharpe=np.nan, max_dd=np.nan)
    eq = (1 + r).cumprod()
    return dict(ann_ret=r.mean() * periods, ann_vol=r.std() * np.sqrt(periods),
                sharpe=r.mean() / r.std() * np.sqrt(periods), max_dd=float((eq / eq.cummax() - 1).min()))


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


def deflated_sharpe(r, n_trials):
    """Bailey-Lopez de Prado. Returns P(true Sharpe > SR0) where SR0 is the expected best Sharpe among
    n_trials zero-skill trials. Assumes independent trials (an upper bound on the true count dependence
    penalty) and uses the realised skew/kurtosis. It is NOT the probability that the strategy 'works'."""
    r = pd.Series(r).dropna()
    T, sr = len(r), r.mean() / r.std()
    g3, g4 = stats.skew(r), stats.kurtosis(r, fisher=False)
    em = 0.5772156649
    N = max(n_trials, 2)
    sr0 = np.sqrt(1.0 / T) * ((1 - em) * stats.norm.ppf(1 - 1 / N) + em * stats.norm.ppf(1 - 1 / (N * np.e)))
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)))


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

"""The synthetic generator builds the stated relationship exactly; beta changes the data; the control has no relation."""
import numpy as np
import pandas as pd

from data_io import synthetic_market


def _wide(long, col="close"):
    return long.pivot(index="date", columns="ticker", values=col)


def test_constructed_relationship_holds_exactly_and_beta_matters():
    for beta in (0.5, 2.0):
        long, _, truth = synthetic_market(seed=5, beta=beta, alpha=0.3, return_truth=True)
        c = _wide(long)
        resid = np.log(c.V) - 0.3 - beta * np.log(c.MA)
        assert np.allclose(resid.values, truth["spread"].values, atol=1e-10)
    a, _ = synthetic_market(seed=5, beta=0.5)
    b, _ = synthetic_market(seed=5, beta=2.0)
    assert not np.allclose(_wide(a).V.values, _wide(b).V.values)          # beta is used
    assert np.allclose(_wide(a).MA.values, _wide(b).MA.values)            # MA path depends on the seed only


def test_spread_is_ar1_when_cointegrated_and_random_walk_in_control():
    _, _, t1 = synthetic_market(seed=9, half_life=10, return_truth=True)
    s, e = t1["spread"].values, t1["innovations"].values
    assert np.allclose(s[1:], t1["phi"] * s[:-1] + e[1:])
    assert 0 < t1["phi"] < 1
    _, _, t0 = synthetic_market(seed=9, cointegrated=False, return_truth=True)
    s0, e0 = t0["spread"].values, t0["innovations"].values
    assert t0["phi"] == 1.0 and np.allclose(np.diff(s0), e0[1:])


def test_fixed_seed_ols_recovers_beta_reasonably():
    # one predetermined seed per beta; a loose tolerance, not a significance requirement
    for beta in (0.5, 2.0):
        long, _ = synthetic_market(seed=21, n=2500, beta=beta)
        c = _wide(long)
        b = np.polyfit(np.log(c.MA), np.log(c.V), 1)[0]
        assert abs(b - beta) < 0.15


def test_opens_closes_and_distributions_are_consistent():
    long, mret = synthetic_market(seed=2)
    assert (long[["open", "close"]] > 0).all().all() and np.isfinite(long[["open", "close", "div"]]).all().all()
    for tk, g in long.groupby("ticker"):
        g = g.set_index("date")
        prev = g.close.shift(1)
        lo, hi = np.minimum(prev, g.close), np.maximum(prev, g.close)
        inside = ((g.open >= lo * 0.99) & (g.open <= hi * 1.01)).iloc[1:]
        assert inside.mean() > 0.95                                         # opens lie on the overnight path (small noise)
        d = g["div"]
        assert (d >= 0).all() and (d > 0).sum() == len(g) // 63 + (1 if len(g) % 63 > 30 else 0)
        assert np.allclose(d[d > 0], {"MA": 0.0015, "V": 0.002}[tk] * prev[d > 0])
    assert isinstance(mret, pd.Series) and len(mret) == long.date.nunique()

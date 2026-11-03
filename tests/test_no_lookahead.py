import numpy as np
import pandas as pd

from config import Spec
from data_io import load_market, synthetic_market
from engine import run_engine
from signals import build_signals


def _market(tmp_path, seed=11, n=900):
    long, _ = synthetic_market(seed=seed, n=n)
    p = tmp_path / "m.csv"
    long.to_csv(p, index=False)
    return load_market(p, ["V", "MA"])


def test_future_data_cannot_change_past_signals_or_ledger(tmp_path):
    spec = Spec()
    o, c, d = _market(tmp_path)
    cut = spec.formation + 3 * spec.trade_len                     # a window boundary
    sig_a, _ = build_signals(c.iloc[:cut], spec)
    c2 = c.copy()
    c2.iloc[cut:] *= np.random.default_rng(0).uniform(0.5, 2.0, (len(c) - cut, 2))   # wreck the future
    sig_b, _ = build_signals(c2, spec)
    cols = ["target", "reason", "beta", "window"]
    pd.testing.assert_frame_equal(sig_a[cols], sig_b.iloc[:cut][cols])
    assert np.allclose(sig_a.z.fillna(0), sig_b.iloc[:cut].z.fillna(0))
    sl = slice(spec.formation, cut)
    da, ta = run_engine(o.iloc[sl], c.iloc[sl], d.iloc[sl], sig_a.iloc[sl], spec)
    o2, d2 = o.copy(), d.copy()
    o2.iloc[cut:] *= 3
    db, tb = run_engine(o2.iloc[sl], c2.iloc[sl], d2.iloc[sl], sig_b.iloc[sl], spec)
    pd.testing.assert_series_equal(da.equity, db.equity)


def test_hedge_ratio_fit_uses_only_formation_window(tmp_path):
    spec = Spec()
    o, c, d = _market(tmp_path)
    sig, wins = build_signals(c, spec)
    c2 = c.copy()                                                  # perturb everything from the first trade day on
    c2.iloc[spec.formation:] *= np.random.default_rng(1).uniform(0.7, 1.4, (len(c) - spec.formation, 2))
    _, wins2 = build_signals(c2, spec)
    assert wins.iloc[0].beta == wins2.iloc[0].beta and wins.iloc[0].alpha == wins2.iloc[0].alpha

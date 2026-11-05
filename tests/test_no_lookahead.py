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


def _perturbed(o, c, d, cut, seed):
    rng = np.random.default_rng(seed)
    c2, o2, d2 = c.copy(), o.copy(), d.copy()
    c2.iloc[cut:] *= rng.uniform(0.5, 2.0, (len(c) - cut, 2))        # wreck every future price and distribution
    o2.iloc[cut:] *= rng.uniform(0.5, 2.0, (len(c) - cut, 2))
    d2.iloc[cut:] = d2.iloc[cut:] * 3 + 0.5
    return o2, c2, d2


def test_future_data_cannot_change_past_signals_or_ledger(tmp_path):
    """Run the full original and the full future-perturbed inputs through signals AND the engine, then compare the history
    before the perturbation. Nothing is sliced away before the engine sees it. Perturbation points are chosen where a position
    is open on the previous close, so a one-session peek at future prices (in marking, fills or risk checks) changes the
    compared prefix."""
    spec = Spec()
    o, c, d = _market(tmp_path)
    sl = slice(spec.formation, None)                                  # full run to the end of the data
    sig_a, _ = build_signals(c, spec)
    da, ta = run_engine(o.iloc[sl], c.iloc[sl], d.iloc[sl], sig_a.iloc[sl], spec)
    held = np.flatnonzero(da.in_trade.to_numpy() == 1) + spec.formation + 1   # cut sessions whose previous close is in a trade
    held = held[(held > spec.formation + spec.trade_len) & (held < len(c) - 5)]
    assert len(held) >= 3
    for k, cut in enumerate(held[[0, len(held) // 2, -1]]):
        o2, c2, d2 = _perturbed(o, c, d, cut, seed=k)
        sig_b, _ = build_signals(c2, spec)
        cols = ["target", "reason", "beta", "window"]
        pd.testing.assert_frame_equal(sig_a.iloc[:cut][cols], sig_b.iloc[:cut][cols])
        assert np.allclose(sig_a.z.iloc[:cut].fillna(0), sig_b.z.iloc[:cut].fillna(0))
        db, tb = run_engine(o2.iloc[sl], c2.iloc[sl], d2.iloc[sl], sig_b.iloc[sl], spec)
        n = cut - spec.formation                                      # rows strictly before the first perturbed session
        pd.testing.assert_frame_equal(da.iloc[:n], db.iloc[:n])       # equity, holdings, borrow, dividends, in_trade
        done = c.index[cut]
        pd.testing.assert_frame_equal(ta[ta.exit_date < done].reset_index(drop=True), tb[tb.exit_date < done].reset_index(drop=True))
        assert not da.equity.equals(db.equity)                        # the future did differ


def test_hedge_ratio_fit_uses_only_formation_window(tmp_path):
    spec = Spec()
    o, c, d = _market(tmp_path)
    sig, wins = build_signals(c, spec)
    c2 = c.copy()                                                  # perturb everything from the first trade day on
    c2.iloc[spec.formation:] *= np.random.default_rng(1).uniform(0.7, 1.4, (len(c) - spec.formation, 2))
    _, wins2 = build_signals(c2, spec)
    assert wins.iloc[0].beta == wins2.iloc[0].beta and wins.iloc[0].alpha == wins2.iloc[0].alpha

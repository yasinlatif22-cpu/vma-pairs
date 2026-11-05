"""Invalid inputs and non-finite accounting fail loudly."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from config import Spec
from engine import InputError, ReconciliationError, reconcile, run_engine
from metrics import drawdown, perf
from tests.helpers import ZERO_COST, script, tiny


def _base():
    o, c, d = tiny([100] * 6, [100] * 6, [50] * 6, [50] * 6)
    return o, c, d, script(6, entries=[(1, 1)], exits=[3])


def test_reconcile_rejects_non_finite_values():
    o, c, d, s = _base()
    daily, trades = run_engine(o, c, d, s, ZERO_COST)
    bad = daily.copy(); bad.iloc[-1, bad.columns.get_loc("equity")] = np.nan
    with pytest.raises(ReconciliationError):
        reconcile(bad, trades, ZERO_COST)
    bad_t = trades.copy(); bad_t.loc[0, "net_pnl"] = np.inf
    with pytest.raises(ReconciliationError):
        reconcile(daily, bad_t, ZERO_COST)


@pytest.mark.parametrize("break_it", ["nonpositive_close", "nan_close", "negative_open", "negative_div", "nan_div"])
def test_invalid_prices_and_distributions_are_rejected(break_it):
    o, c, d, s = _base()
    if break_it == "nonpositive_close":
        c.iloc[2, 0] = 0.0
    elif break_it == "nan_close":
        c.iloc[2, 1] = np.nan
    elif break_it == "negative_open":
        o.iloc[2, 0] = -1.0
    elif break_it == "negative_div":
        d.iloc[2, 0] = -0.5
    else:
        d.iloc[2, 1] = np.nan
    with pytest.raises(InputError):
        run_engine(o, c, d, s, ZERO_COST)


def test_misaligned_signals_or_missing_security_are_rejected():
    o, c, d, s = _base()
    with pytest.raises(InputError):
        run_engine(o, c, d, s.iloc[1:], ZERO_COST)                     # signal index shorter
    s2 = s.copy(); s2.index = s.index + pd.Timedelta(days=1)
    with pytest.raises(InputError):
        run_engine(o, c, d, s2, ZERO_COST)                             # same length, different dates
    with pytest.raises(InputError):
        run_engine(o, c, d.drop(columns="MA"), s, ZERO_COST)           # a security missing from distributions


def test_max_drawdown_counts_an_immediate_loss_from_initial_capital():
    assert perf([-0.10, 0.0])["max_dd"] == pytest.approx(-0.10)
    # immediate loss, full recovery, then a later and deeper drawdown from a new peak
    r = [-0.05, 0.0, 0.10, -0.15, 0.02]
    eq = np.cumprod(1 + np.array(r))
    assert drawdown(r).iloc[0] == pytest.approx(-0.05)
    assert drawdown(r).iloc[3] == pytest.approx(eq[3] / eq[2] - 1)
    assert perf(r)["max_dd"] == pytest.approx(min(-0.05, eq[3] / eq[2] - 1))
    p = perf([0.02, 0.0] * 126)                                      # one year: mean 1%/day, compounding 1.02 ** 126
    assert p["mean_ann_ret"] == pytest.approx(2.52) and p["cagr"] == pytest.approx(1.02 ** 126 - 1)


def test_fill_lag_default_is_unchanged_and_lag_two_fills_a_session_later():
    o, c, d = tiny([100, 100, 101, 102, 103, 104, 105, 106], [100] * 8, [50] * 8, [50] * 8)
    s = script(8, entries=[(1, 1)], exits=[4])
    _, t1 = run_engine(o, c, d, s, ZERO_COST)
    _, t1b = run_engine(o, c, d, s, ZERO_COST, fill_lag=1)
    pd.testing.assert_frame_equal(t1, t1b)
    _, t2 = run_engine(o, c, d, s, ZERO_COST, fill_lag=2)
    assert t2.entry_date.iloc[0] == t1.entry_date.iloc[0] + pd.tseries.offsets.BDay(1)
    assert t2.entry_px_y.iloc[0] == 102 and t1.entry_px_y.iloc[0] == 101
    with pytest.raises(InputError):
        run_engine(o, c, d, s, ZERO_COST, fill_lag=0)

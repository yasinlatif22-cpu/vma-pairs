"""Financing account (fixed holdings, one denominator), earnings exposure boundaries, leg attribution."""
import numpy as np
import pandas as pd
import pytest

from diagnostics.earnings_analysis import exposed, hold_points
from diagnostics.financing import account, load_rf, tbill


def _daily(E, L, S, start="2020-01-02"):
    idx = pd.bdate_range(start, periods=len(E))
    return pd.DataFrame({"equity": E, "long_mv": L, "short_mv": S}, index=idx)


def test_s0_is_the_run_and_zero_rf_changes_nothing():
    d = _daily([1.01e6, 0.99e6, 1.02e6], [5e5, 5e5, 0], [-5e5, -5e5, 0])
    rf0 = pd.Series(0.0, d.index)
    a0, a1 = account(d, rf0, "S0"), account(d, rf0, "S1")
    assert np.allclose(a0.ret, d.equity.pct_change().fillna(0.01))
    assert np.allclose(a0.ret, a1.ret)


def test_flat_account_earns_exactly_the_tbill_rate():
    n = 30
    d = _daily([1e6] * n, [0.0] * n, [0.0] * n)
    rf = pd.Series(np.linspace(0.0001, 0.0002, n), d.index)
    a = account(d, rf, "S1")
    assert np.allclose(a.ret, rf)                                        # same denominator for every component
    assert a.equity_fin.iloc[-1] == pytest.approx(tbill(d.index, rf).iloc[-1])


def test_interest_uses_free_cash_after_longs_and_margin_and_rebate_is_on_proceeds():
    rf = pd.Series(0.0001, pd.bdate_range("2020-01-02", periods=2))
    d = _daily([1e6, 1e6], [4e5, 4e5], [-6e5, -6e5])
    s1, s2 = account(d, rf, "S1", margin=0.5), account(d, rf, "S2", margin=0.5, rebate_spread=0.0)
    # day 1 starts from the initial $1M flat (interest 100); day 2 uses day-1 balances plus that interest:
    # free = 1e6 + 100 - 4e5 - 0.5 * 6e5 = 300,100
    assert s1.interest.iloc[0] == pytest.approx(100.0)
    assert s1.interest.iloc[1] == pytest.approx(0.0001 * 300_100)
    assert s2.rebate.iloc[1] == pytest.approx(0.0001 * 6e5)
    assert (s1.trading_pnl == s2.trading_pnl).all()                      # financing never changes the holdings' P&L


def test_negative_free_cash_is_a_debit_not_interest():
    rf = pd.Series(0.0001, pd.bdate_range("2020-01-02", periods=2))
    d = _daily([1e6, 1e6], [9e5, 9e5], [-6e5, -6e5])                     # free = 1e6 - 9e5 - 3e5 < 0
    a = account(d, rf, "S1", margin=0.5)
    assert a.interest.iloc[1] == 0 and a.debit.iloc[1] < 0


def test_monthly_rf_compounds_back_to_the_monthly_rate(tmp_path):
    days = pd.bdate_range("2020-01-01", "2020-02-28")
    pd.DataFrame({"date": days, "rf": 0.0001, "mktrf": 0.0}).to_csv(tmp_path / "rf.csv", index=False)
    pd.DataFrame({"date": ["2020-01-31", "2020-02-28"], "rf": [0.0013, 0.0012]}).to_csv(tmp_path / "rf_monthly.csv", index=False)
    rf, label = load_rf(tmp_path)
    assert "monthly" in label
    jan = rf[rf.index.month == 1]
    assert (1 + jan).prod() - 1 == pytest.approx(0.0013)


# earnings: sessions 0..; open of s = 2s, close = 2s + 1
@pytest.mark.parametrize("entry,exit_,release,timing,expected", [
    (3, 6, 5, "after_close", True),      # held over close 5 -> open 6 (exit fill at the open of 6)
    (3, 5, 5, "after_close", False),     # exited at the open of 5, before the release after the close of 5
    (3, 5, 5, "pre_open", True),         # released before the open of 5; the exit fill at that open already carries the gap
    (5, 8, 5, "pre_open", False),        # entered at the open of 5, after the gap
    (5, 8, 5, "after_close", True),      # entered at the open of 5, held through the close of 5 and the night
    (3, 5, 5, "either", True),
])
def test_release_exposure_boundaries_for_open_fills(entry, exit_, release, timing, expected):
    assert exposed(*hold_points(entry, exit_, "open_next"), [release], timing) is expected


def test_end_of_data_exit_is_at_the_close():
    s, e = hold_points(3, 9, "open_next", end_of_data=True)
    assert (s, e) == (6, 19) and not exposed(s, e, [9], "after_close")


def test_leg_attribution_adds_up_to_engine_net_pnl(tmp_path):
    from config import Spec
    from data_io import load_market, synthetic_market
    from diagnostics.trade_legs import legs
    from engine import run_engine
    from signals import build_signals
    spec = Spec()
    long, mret = synthetic_market(seed=8, n=900)
    p = tmp_path / "m.csv"; long.to_csv(p, index=False)
    o, c, d = load_market(p, ["V", "MA"])
    sig, _ = build_signals(c, spec)
    sl = slice(spec.formation, None)
    daily, trades = run_engine(o.iloc[sl], c.iloc[sl], d.iloc[sl], sig.iloc[sl], spec)
    px = {"open": o, "close": c, "div": d}
    out = legs(trades, daily, px, mret.rename("mkt"), spec)                # raises if any trade does not reconcile
    assert len(out) == len(trades) > 3 and np.allclose(out.legs_total, trades.net_pnl, atol=0.01)

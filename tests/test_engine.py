from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from config import Spec
from data_io import synthetic_market, load_market
from engine import reconcile, run_engine
from signals import build_signals
from tests.helpers import ZERO_COST, script, tiny


def test_flat_has_no_trades_costs_or_borrow():
    o, c, d = tiny([100] * 10, [100] * 10, [50] * 10, [50] * 10)
    daily, trades = run_engine(o, c, d, script(10), replace(ZERO_COST, cost_bps=5, borrow_bps=30))
    assert trades.empty and (daily.equity == 1_000_000).all() and (daily.borrow == 0).all()


def test_hand_calculated_trade_and_fill_timing():
    # signal at close of day 1 (short spread: short V, long MA), beta 1, equity 1,000,000.
    # fill at OPEN of day 2: V 110 (not the day-1 close of 100), MA 50. exit signal at close of day 4,
    # exit fill at OPEN of day 5: V 104, MA 53.
    oy, cy = [100, 100, 110, 108, 104, 104], [100, 100, 109, 106, 105, 105]
    ox, cx = [50, 50, 50, 51, 53, 53], [50, 50, 50, 52, 52, 52]
    o, c, d = tiny(oy, cy, ox, cx)
    spec = replace(ZERO_COST, cost_bps=10, borrow_bps=0)
    daily, trades = run_engine(o, c, d, script(6, entries=[(1, -1)], exits=[4]), spec)
    t = trades.iloc[0]
    q_v, q_x = -(500_000 / 110), 500_000 / 50          # gross 1.0x, beta 1 -> 50/50 split
    assert t.entry_px_y == 110 and t.exit_px_y == 104 and t.entry_px_x == 50 and t.exit_px_x == 53
    gross = q_v * (104 - 110) + q_x * (53 - 50)
    costs = 0.001 * (abs(q_v) * 110 + abs(q_x) * 50) + 0.001 * (abs(q_v) * 104 + abs(q_x) * 53)
    assert t.gross_pnl == pytest.approx(gross) and t.costs == pytest.approx(costs)
    assert t.net_pnl == pytest.approx(gross - costs)
    assert reconcile(daily, trades, spec) == pytest.approx(0, abs=1e-6)


def test_borrow_only_on_short_and_per_night():
    o, c, d = tiny([100] * 8, [100] * 8, [50] * 8, [50] * 8)       # day 0 is a Monday
    spec = replace(ZERO_COST, borrow_bps=365)                       # 3.65% a year -> 1 bp per night
    daily, trades = run_engine(o, c, d, script(8, entries=[(0, -1)], exits=[3]), spec)
    short_mv = 500_000.0
    # held at the closes of days 1,2,3 -> nights 1 each (Tue,Wed,Thu->next day); borrow = 3 nights
    assert trades.borrow.iloc[0] == pytest.approx(short_mv * 0.0365 * 3 / 365, rel=1e-9)
    assert daily.borrow.iloc[0] == 0 and daily.borrow.iloc[5] == 0


def test_dividends_long_receives_short_pays_ex_date_buyer_does_not():
    # long Y/short X is held through day 3, when both go ex-dividend.
    o, c, d = tiny([100] * 8, [100] * 8, [50] * 8, [50] * 8,
                   div_y=[0, 0, 0, 1, 0, 0, 0, 0], div_x=[0, 0, 0, 0.5, 0, 0, 0, 0])
    daily, trades = run_engine(o, c, d, script(8, entries=[(0, 1)], exits=[5]), ZERO_COST)
    q_y, q_x = 500_000 / 100, -500_000 / 50
    assert trades.dividends.iloc[0] == pytest.approx(q_y * 1 + q_x * 0.5)
    # entering ON the ex-date: fill at open of day 3 -> not entitled to that day's dividend
    daily, trades = run_engine(o, c, d, script(8, entries=[(2, 1)], exits=[5]), ZERO_COST)
    assert trades.dividends.iloc[0] == 0


def test_split_adjusted_series_produce_no_pnl():
    # a 2:1 split on day 3: adjusted prices are continuous, so holding through it earns nothing from it.
    o, c, d = tiny([100] * 8, [100] * 8, [50] * 8, [50] * 8)
    daily, trades = run_engine(o, c, d, script(8, entries=[(0, 1)], exits=[6]), ZERO_COST)
    assert trades.net_pnl.iloc[0] == pytest.approx(0, abs=1e-6)


def test_hedge_ratio_sizing_and_exposures():
    o, c, d = tiny([100] * 6, [100] * 6, [50] * 6, [50] * 6)
    daily, trades = run_engine(o, c, d, script(6, entries=[(0, 1)], exits=[4], beta=2.0), ZERO_COST)
    t = trades.iloc[0]
    assert t.qty_x * 50 / (t.qty_y * 100) == pytest.approx(-2.0)      # notional X = beta * notional Y
    row = daily.iloc[2]
    assert row.gross_pct == pytest.approx(1.0) and row.net_pct == pytest.approx((1 - 2) / 3)   # not dollar-neutral


def test_both_legs_fixed_shares_one_round_trip():
    o, c, d = tiny(list(100 + np.arange(12)), list(100 + np.arange(12)), list(50 - np.arange(12) * .2),
                   list(50 - np.arange(12) * .2))
    daily, trades = run_engine(o, c, d, script(12, entries=[(1, 1)], exits=[9]), Spec(cost_bps=5, borrow_bps=0,
                                                                                  loss_limit=10, dd_halt=10))
    assert len(trades) == 1 and trades.qty_y.iloc[0] != 0 and trades.qty_x.iloc[0] != 0


def test_loss_limit_exits_at_next_open_and_locks_window():
    oy = [100, 100, 100, 100, 130, 130, 130, 130]       # V gaps up 30% against a short-V position
    cy = [100, 100, 100, 112, 130, 130, 130, 130]
    o, c, d = tiny(oy, cy, [50] * 8, [50] * 8)
    s = script(8, entries=[(0, -1)], exits=[7])
    spec = replace(ZERO_COST, loss_limit=0.05)
    daily, trades = run_engine(o, c, d, s, spec)
    t = trades.iloc[0]
    assert t.exit_reason == "loss_limit" and t.exit_date == o.index[4]
    assert t.net_pnl < -0.05 * spec.initial_equity       # gap: realised loss exceeds the limit
    assert len(trades) == 1                              # locked for the rest of the window


def test_window_boundary_liquidation_charged():
    o, c, d = synthetic_market(seed=3, n=700)[0], None, None
    long, _ = synthetic_market(seed=3, n=700)
    long.to_csv("/tmp/_t.csv", index=False)
    o, c, d = load_market("/tmp/_t.csv", ["V", "MA"])
    spec = Spec()
    sig, wins = build_signals(c, spec)
    daily, trades = run_engine(o.iloc[spec.formation:], c.iloc[spec.formation:], d.iloc[spec.formation:],
                               sig.iloc[spec.formation:], spec)
    we = trades[trades.exit_reason == "window_end"]
    assert (we.costs > 0).all()
    # nothing is carried across a window boundary: every exit falls on or before the next window's first day
    ends = set(pd.to_datetime(wins.end))
    firsts = set(pd.to_datetime(wins.start))
    for _, r in we.iterrows():
        assert r.exit_date in firsts or r.exit_date == c.index[-1]


def test_reconciliation_on_random_run():
    long, _ = synthetic_market(seed=5, n=1200)
    long.to_csv("/tmp/_t2.csv", index=False)
    o, c, d = load_market("/tmp/_t2.csv", ["V", "MA"])
    spec = Spec()
    sig, _ = build_signals(c, spec)
    sl = slice(spec.formation, None)
    daily, trades = run_engine(o.iloc[sl], c.iloc[sl], d.iloc[sl], sig.iloc[sl], spec)
    assert len(trades) > 5
    assert reconcile(daily, trades, spec) == pytest.approx(0, abs=1e-6)
    assert trades.costs.sum() > 0 and trades.borrow.sum() > 0

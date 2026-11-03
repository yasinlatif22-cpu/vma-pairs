"""Conventions and failure modes added after the second review: final liquidation, window-boundary execution,
holding-period fields, missing prices, drawdown-halt cycle, and reconciliation failure."""
from dataclasses import replace

import numpy as np
import pytest

from engine import ReconciliationError, reconcile, run_engine
from tests.helpers import ZERO_COST, script, tiny


def test_final_liquidation_is_clean_and_charges_no_extra_night():
    n = 8                                                    # position opened, never exited by a signal
    o, c, d = tiny([100] * n, [100, 100, 101, 102, 103, 104, 105, 106], [50] * n, [50] * n)
    spec = replace(ZERO_COST, cost_bps=5, borrow_bps=30)
    daily, trades = run_engine(o, c, d, script(n, entries=[(1, -1)], exits=[n - 1]), spec)
    t, last = trades.iloc[0], daily.iloc[-1]
    assert t.exit_reason == "end_of_data" and t.exit_date == daily.index[-1]
    assert last.borrow == 0 and last.long_mv == 0 and last.short_mv == 0 and last.in_trade == 0
    assert last.mv_y == 0 and last.mv_x == 0
    assert last.equity == pytest.approx(spec.initial_equity + t.net_pnl)
    assert daily.borrow.sum() == pytest.approx(t.borrow)     # no borrow booked outside the holding period
    assert reconcile(daily, trades, spec) == pytest.approx(0, abs=1e-6)
    # borrow nights: closes of days 2..6 are each followed by a night (day 4 -> Mon is 3 nights); none after day 7
    nights = [(daily.index[i + 1] - daily.index[i]).days for i in range(2, 7)]
    short_mv = [(5000 / 1.0) * 0 + abs(-(500_000 / 100) * px) for px in [101, 102, 103, 104, 105]]
    assert t.borrow == pytest.approx(sum(m * 30e-4 * k / 365 for m, k in zip(short_mv, nights)))


def test_window_end_exit_fills_in_first_session_of_next_window():
    n = 12
    o, c, d = tiny([100, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110], [100] * n, [50] * n, [50] * n)
    s = script(n, entries=[(1, 1)], exits=[5])
    s.loc[s.index[5], "reason"] = "window_end"                 # last close of window 0 (days 0-5)
    s["window"] = np.where(np.arange(n) >= 6, 1, 0)
    daily, trades = run_engine(o, c, d, s, replace(ZERO_COST, cost_bps=0, borrow_bps=0))
    t = trades.iloc[0]
    assert t.exit_reason == "window_end" and t.exit_date == daily.index[6]    # first session of window 1
    assert t.exit_px_y == 105                                                  # that session's open, not the close of day 5
    assert t.exit_signal_date == daily.index[5]


def test_hold_sessions_vs_calendar_days():
    n = 10                                                   # day 0 is Monday 2020-01-06
    o, c, d = tiny([100] * n, [100] * n, [50] * n, [50] * n)
    daily, trades = run_engine(o, c, d, script(n, entries=[(3, 1)], exits=[5]), ZERO_COST)
    t = trades.iloc[0]                                       # fill Fri 2020-01-10, exit fill Tue 2020-01-14
    assert t.entry_date == daily.index[4] and t.exit_date == daily.index[6]
    assert t.hold_sessions == 2 and t.hold_calendar_days == 4


def test_missing_fill_price_fails_loudly():
    n = 8
    o, c, d = tiny([100] * n, [100] * n, [50] * n, [50] * n)
    o.iloc[2, 0] = np.nan                                    # the open at which the day-1 signal would fill
    with pytest.raises(ValueError, match="missing open price"):
        run_engine(o, c, d, script(n, entries=[(1, 1)], exits=[5]), ZERO_COST)


def test_drawdown_halt_cycle():
    # long V / short MA, 1x gross, V falls 10% on day 3 -> about -5% equity, halt threshold 2%
    n = 12
    oy = [100, 100, 100, 100, 90, 90, 90, 90, 90, 90, 90, 90]
    cy = [100, 100, 100, 90, 90, 90, 90, 90, 90, 90, 90, 90]
    o, c, d = tiny(oy, cy, [50] * n, [50] * n)
    spec = replace(ZERO_COST, dd_halt=0.02, halt_days=3)
    s = script(n, entries=[(1, 1), (5, 1), (7, 1)], exits=[4, 6, 10])
    daily, trades = run_engine(o, c, d, s, spec)
    idx = daily.index
    first = trades.iloc[0]
    assert first.exit_reason == "dd_halt" and first.exit_signal_date == idx[3] and first.exit_date == idx[4]   # activation + liquidation
    assert idx[5] not in set(trades.signal_date)                                                               # entry blocked while halted
    second = trades.iloc[1]
    assert len(trades) == 2 and second.signal_date == idx[7] and second.entry_date == idx[8]                   # resumed after 3 sessions
    assert second.exit_reason == "target"                    # peak was reset at resumption: no immediate re-halt at the old high
    assert reconcile(daily, trades, spec) == pytest.approx(0, abs=1e-6)


def test_reconcile_raises_on_material_discrepancy():
    n = 8
    o, c, d = tiny([100] * n, [100, 100, 101, 102, 103, 104, 105, 106], [50] * n, [50] * n)
    daily, trades = run_engine(o, c, d, script(n, entries=[(1, 1)], exits=[5]), ZERO_COST)
    reconcile(daily, trades, ZERO_COST)
    bad = trades.assign(net_pnl=trades.net_pnl + 5.0)
    with pytest.raises(ReconciliationError):
        reconcile(daily, bad, ZERO_COST)

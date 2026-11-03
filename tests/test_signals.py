import numpy as np

from signals import run_state_machine

E, X, S = 2.0, 0.5, 4.0


def sm(z, max_hold=10, tradable=True):
    return run_state_machine(np.array(z, dtype=float), E, X, S, max_hold, tradable)


def test_no_entry_beyond_stop():
    tgt, why = sm([5, 5, 5, 5])
    assert list(tgt) == [0, 0, 0, 0] and why[0] == "entry_suppressed_beyond_stop"


def test_blocked_until_rearm_below_entry():
    tgt, _ = sm([5, 3, 2.5, 1.0, 2.5, 0, 0])
    assert tgt[1] == 0 and tgt[2] == 0          # |z| fell back below stop but never re-armed
    assert tgt[4] == -1                          # re-armed at 1.0, then enters


def test_entry_direction_and_target_exit():
    tgt, why = sm([0, 2.5, 1.5, 0.4, 0, 0, 0])
    assert list(tgt) == [0, -1, -1, 0, 0, 0, 0] and why[3] == "target"
    tgt, _ = sm([0, -2.5, -1.5, -0.4, 0, 0, 0])
    assert list(tgt) == [0, 1, 1, 0, 0, 0, 0]


def test_stop_exit_and_block():
    tgt, why = sm([0, 2.5, 3.0, 4.2, 2.5, 2.5, 1.0, 2.5, 2.5])
    assert why[3] == "z_stop" and tgt[3] == 0 and tgt[4] == 0 and tgt[5] == 0   # blocked
    assert tgt[7] == -1                                                          # re-armed via 1.0


def test_max_hold_boundary_exact():
    # entry signal at t=1; held closes are t=2 and t=3; with max_hold=2 the exit signal is at t=3.
    tgt, why = sm([0, 2.5, 3, 3, 3, 3], max_hold=2)
    assert list(tgt) == [0, -1, -1, 0, 0, 0] and why[3] == "max_hold"


def test_window_end_forces_flat_and_no_last_bar_entry():
    tgt, why = sm([0, 2.5, 3, 3])
    assert tgt[-1] == 0 and why[-1] == "window_end"
    tgt, _ = sm([0, 0, 0, 2.5])
    assert tgt[-1] == 0


def test_untradable_and_nan():
    assert not sm([0, 3, 3, 3], tradable=False)[0].any()
    tgt, _ = sm([0, 2.5, np.nan, np.nan, 0.2, 0])
    assert tgt[2] == -1 and tgt[3] == -1 and tgt[4] == 0

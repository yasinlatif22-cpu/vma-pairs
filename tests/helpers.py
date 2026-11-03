import numpy as np
import pandas as pd

from config import Spec


def tiny(open_y, close_y, open_x, close_x, div_y=None, div_x=None, start="2020-01-06"):
    """Hand-built two-name market. Returns (open, close, div) frames with columns V, MA."""
    n = len(close_y)
    idx = pd.bdate_range(start, periods=n)
    o = pd.DataFrame({"V": open_y, "MA": open_x}, index=idx, dtype=float)
    c = pd.DataFrame({"V": close_y, "MA": close_x}, index=idx, dtype=float)
    d = pd.DataFrame({"V": div_y if div_y is not None else np.zeros(n),
                      "MA": div_x if div_x is not None else np.zeros(n)}, index=idx, dtype=float)
    return o, c, d


def script(n, entries=(), exits=(), beta=1.0, start="2020-01-06"):
    """Signal frame that enters (side) at the close of day i and exits at the close of day j."""
    idx = pd.bdate_range(start, periods=n)
    s = pd.DataFrame({"target": 0, "reason": "", "z": 0.0, "beta": beta, "window": 0}, index=idx)
    for (i, side), j in zip(entries, exits):
        s.iloc[i:j, s.columns.get_loc("target")] = side       # target is 0 again at the exit close j
        s.iloc[i, s.columns.get_loc("reason")] = "entry"
        s.iloc[j, s.columns.get_loc("reason")] = "target"
    return s


ZERO_COST = Spec(cost_bps=0.0, borrow_bps=0.0, loss_limit=10.0, dd_halt=10.0)

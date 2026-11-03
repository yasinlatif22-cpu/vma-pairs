"""Walk-forward hedge-ratio fit and the signal state machine (past data only)."""
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint


def fit_hedge(ly, lx):
    """OLS log Y = alpha + beta log X + e on the formation window. Returns (alpha, beta, resid)."""
    res = sm.OLS(ly, sm.add_constant(lx)).fit()
    return float(res.params[0]), float(res.params[1]), np.asarray(res.resid)


def half_life(spread):
    """Ornstein-Uhlenbeck half-life (days) from AR(1); inf if not mean-reverting."""
    s = np.asarray(spread)
    phi = sm.OLS(s[1:], sm.add_constant(s[:-1])).fit().params[1]
    return float(-np.log(2) / np.log(phi)) if 0 < phi < 1 else np.inf


def eg_pvalue(ly, lx):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(coint(ly, lx, trend="c", maxlag=1, autolag=None)[1])


def run_state_machine(z, entry, exit_, stop, max_hold, tradable=True):
    """Convert a z-score path into target positions decided at each CLOSE.

    target: +1 long spread (long Y / short X), -1 short spread, 0 flat.
    Intended behaviour (tested in tests/test_signals.py):
      * entry only if entry <= |z| < stop (an extreme |z| >= stop is a regime-break warning, not a signal);
        after |z| >= stop while flat, entries stay blocked until |z| < entry (re-arm).
      * exit order (filled at the next execution price) on: adverse |z| >= stop ('z_stop'),
        reversion |z| <= exit ('target'), `max_hold` closes held ('max_hold'), last window bar ('window_end').
      * held counts closes AFTER the entry fill: signal at close t, fill t+1, first held close = t+1.
      * z_stop / max_hold exits block re-entry until re-arm; 'target' exits do not.
      * NaN z: hold; no new entries.
    """
    n = len(z)
    tgt = np.zeros(n, dtype=int)
    why = np.array([""] * n, dtype=object)
    pos, held, blocked = 0, 0, False
    for t in range(n):
        zt, last = z[t], t == n - 1
        if pos != 0:
            held += 1
            reason = None
            if not np.isnan(zt):
                if (pos == -1 and zt >= stop) or (pos == 1 and zt <= -stop):
                    reason = "z_stop"
                elif (pos == -1 and zt <= exit_) or (pos == 1 and zt >= -exit_):
                    reason = "target"
            if reason is None and held >= max_hold:
                reason = "max_hold"
            if reason is None and last:
                reason = "window_end"
            if reason:
                pos, held, why[t] = 0, 0, reason
                blocked = reason in ("z_stop", "max_hold")
        elif not np.isnan(zt):
            if blocked and abs(zt) < entry:
                blocked = False
            if abs(zt) >= stop:
                blocked = True
                why[t] = "entry_suppressed_beyond_stop"
            elif tradable and not blocked and not last and abs(zt) >= entry:
                pos, held, why[t] = -int(np.sign(zt)), 0, "entry"
        tgt[t] = pos
    return tgt, why


def build_signals(close, spec, first_trade_idx=None):
    """Per-window fit + signals. Uses only data at or before each date.

    close: DataFrame (date index) with spec.y, spec.x split-adjusted closes.
    first_trade_idx: integer position of the first trading day (default: spec.formation).
    Returns (sig, windows): sig has target/reason/z/beta/window per date; windows holds fit diagnostics.
    """
    ly, lx = np.log(close[spec.y].values), np.log(close[spec.x].values)
    idx, n, F, T = close.index, len(close), spec.formation, spec.trade_len
    sig = pd.DataFrame({"target": 0, "reason": "", "z": np.nan, "beta": np.nan, "window": -1}, index=idx)
    wins, t0, w = [], max(F, first_trade_idx or 0), 0
    while t0 < n:
        t1 = min(t0 + T, n)
        a, b, resid = fit_hedge(ly[t0 - F:t0], lx[t0 - F:t0])
        hl = half_life(resid)
        p = eg_pvalue(ly[t0 - F:t0], lx[t0 - F:t0])
        ok = spec.beta_min <= b <= spec.beta_max
        if spec.gate == "coint":
            ok = ok and p <= spec.gate_p and spec.gate_hl_min <= hl <= spec.gate_hl_max
        mh = int(np.clip(np.ceil(spec.maxhold_mult * hl), spec.maxhold_min, T)) if np.isfinite(hl) else T
        s = pd.Series(ly[t0 - F:t1] - b * lx[t0 - F:t1] - a)
        z = ((s - s.rolling(spec.z_lookback).mean()) / s.rolling(spec.z_lookback).std()).values[F:]
        tgt, why = run_state_machine(z, spec.entry_z, spec.exit_z, spec.stop_z, mh, ok)
        sl = slice(t0, t1)
        sig.iloc[sl, sig.columns.get_loc("target")] = tgt
        sig.iloc[sl, sig.columns.get_loc("reason")] = why
        sig.iloc[sl, sig.columns.get_loc("z")] = z
        sig.iloc[sl, sig.columns.get_loc("beta")] = b
        sig.iloc[sl, sig.columns.get_loc("window")] = w
        wins.append(dict(window=w, start=idx[t0], end=idx[t1 - 1], alpha=a, beta=b, half_life=hl,
                         eg_p=p, tradable=ok, max_hold=mh))
        t0, w = t1, w + 1
    return sig, pd.DataFrame(wins)

"""Frozen research specification. Every field is fixed BEFORE any real-data run.

Changing any field changes spec_hash(); results are stamped with the hash, and the
holdout runner refuses to run unless the hash matches the one recorded in SPEC_LOCK.
Fields marked ASSUMPTION are not observed from data.
"""
import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Spec:
    # pair (fixed a priori on economic grounds, see docs/THESIS.md; NOT selected from data)
    y: str = "V"
    x: str = "MA"

    # walk-forward
    formation: int = 252          # trading days used to fit hedge ratio (fixed within the window)
    trade_len: int = 63           # trading days per window; position forced flat at window end

    # signal: z-score of the log-price spread
    z_lookback: int = 60
    entry_z: float = 2.0          # enter when entry_z <= |z| < stop_z
    exit_z: float = 0.5           # take profit when |z| <= exit_z (on the reverting side)
    stop_z: float = 4.0           # SIGNAL stop (not a loss limit); also blocks entries at |z| >= stop_z
    maxhold_mult: float = 3.0     # time stop = ceil(mult * formation half-life), bounded below
    maxhold_min: int = 5
    beta_min: float = 0.3         # skip windows whose formation hedge ratio is implausible
    beta_max: float = 3.0
    gate: str = "none"            # 'none' (primary) | 'coint' (secondary): formation-window EG test + half-life
    gate_p: float = 0.10
    gate_hl_min: float = 3.0
    gate_hl_max: float = 60.0

    # execution
    fill: str = "open_next"       # signal at close t, fill at open t+1 | 'close_next': fill at close t+1
    gross_frac: float = 1.0       # gross notional at entry as a fraction of last-close equity
    # sizing: notional(X) / notional(Y) = beta (OLS log-price hedge; cointegration is not established). NOT dollar-neutral
    # unless beta == 1 and NOT market-beta-neutral; both exposures are reported daily.

    # frictions (ASSUMPTIONS, see docs/METHODOLOGY.md)
    cost_bps: float = 5.0         # per trade, per leg, on traded notional (spread + fees + impact)
    borrow_bps: float = 30.0      # annualised, on short market value, charged per night held
    # no interest on cash/short proceeds (rf = 0). Sharpe vs risk-free is a reported sensitivity.

    # risk controls (set ex ante; not tuned)
    loss_limit: float = 0.05      # exit if trade net MTM <= -5% of entry equity; locks pair for rest of window
    dd_halt: float = 0.20         # flatten + halt if equity drawdown from peak >= 20%
    halt_days: int = 63           # trading days halted; peak resets on resume
    initial_equity: float = 1_000_000.0

    # evaluation periods (inclusive). Dev: design checks only. Val: one look. Holdout: once.
    dev: tuple = ("2009-01-01", "2017-12-31")
    val: tuple = ("2018-01-01", "2022-12-31")
    holdout: tuple = ("2023-01-01", "2025-12-31")

    bootstrap_runs: int = 2000
    seed: int = 7

    def hash(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, default=list)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]


DEFAULT = Spec()

if __name__ == "__main__":
    print(DEFAULT.hash())

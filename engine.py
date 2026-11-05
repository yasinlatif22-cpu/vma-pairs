"""Share-based ledger: one pair, fills at a stated price, every cash flow recorded.

Per day: (1) dividends to holders at the start of the day, (2) fill the order created at
yesterday's close, (3) mark at close and charge overnight borrow, (4) check risk limits,
(5) create tomorrow's order from today's signal. Share counts only change on fills.

Conventions (tested):
  * Orders created at a close fill at the NEXT session's open or close (spec.fill). This includes the order that
    exits at a window end: a position is flat after the first session of the next window, not at the window's last
    close. Borrow is charged for every night a short is held, including that one.
  * A missing price on a fill date raises ValueError; an order is never dropped silently.
  * Inputs are validated before the run: identical date indexes for prices, distributions and signals, both securities
    present, closes finite and positive, opens positive where present, distributions finite and non-negative.
  * fill_lag (default 1, the frozen specification) is the number of sessions between the signal close and the fill. Values
    above 1 exist only for exploratory execution-delay scenarios; an order is never created if it could not fill
    before the final date, so nothing is left pending at the end.
  * At the final date any open position is liquidated at the final close with costs, and no borrow is charged for a
    night that does not occur. The final row is then flat (holdings, exposures, in_trade) and equity equals cash.
"""
import numpy as np
import pandas as pd


class InputError(ValueError):
    pass


def validate_inputs(px_open, px_close, div, sig, names):
    """Raise InputError on misaligned or invalid inputs instead of producing a silently wrong ledger."""
    idx = px_close.index
    for label, f in (("open", px_open), ("distribution", div), ("signal", sig)):
        if not f.index.equals(idx):
            raise InputError(f"{label} index does not match the close-price index ({len(f)} vs {len(idx)} rows)")
    if not idx.is_monotonic_increasing or idx.has_duplicates:
        raise InputError("dates must be strictly increasing without duplicates")
    for label, f in (("open", px_open), ("close", px_close), ("distribution", div)):
        missing = [t for t in names if t not in f.columns]
        if missing:
            raise InputError(f"{label} frame lacks {missing}")
    c = px_close[names].to_numpy(dtype=float)
    if not np.isfinite(c).all() or (c <= 0).any():
        raise InputError("close prices must be finite and positive on every date")
    o = px_open[names].to_numpy(dtype=float)
    if (~np.isnan(o) & ~(np.isfinite(o) & (o > 0))).any():
        raise InputError("open prices must be positive where present (missing opens raise only if a fill needs one)")
    dv = div[names].to_numpy(dtype=float)
    if not np.isfinite(dv).all() or (dv < 0).any():
        raise InputError("distributions must be finite and non-negative")
    for col in ("target", "reason", "beta", "window"):
        if col not in sig.columns:
            raise InputError(f"signal frame lacks '{col}'")


def run_engine(px_open, px_close, div, sig, spec, fill_lag=1):
    """px_*, div: DataFrames [date x (y, x)], div = cash per split-adjusted share on ex-date.
    sig: output of signals.build_signals restricted to the same dates.
    Returns (daily, trades)."""
    names = [spec.y, spec.x]
    validate_inputs(px_open, px_close, div, sig, names)
    if int(fill_lag) != fill_lag or fill_lag < 1:
        raise InputError("fill_lag must be a whole number of sessions >= 1")
    dates = px_close.index
    n = len(dates)
    bps, borrow_rate = spec.cost_bps / 1e4, spec.borrow_bps / 1e4
    cash = equity_prev = peak = spec.initial_equity
    sh = {t: 0.0 for t in names}
    cur, pending = None, None
    prev_target, locked_window, halted_until = 0, None, -1
    trades, rows = [], []

    def fill(px, kind, reason, side=0, beta=np.nan, sig_date=None, d=None, i=None):
        nonlocal cash, cur
        cost = 0.0
        if kind == "exit":
            for t in names:
                cash += sh[t] * px[t]
                cost += bps * abs(sh[t]) * px[t]
            cash -= cost
            gross = sum(sh[t] * (px[t] - cur["entry_px"][t]) for t in names)
            net = gross + cur["div"] - cur["cost"] - cost - cur["borrow"]
            trades.append(dict(
                side=cur["side"], beta=cur["beta"], signal_date=cur["sig_date"], entry_date=cur["entry_date"],
                entry_px_y=cur["entry_px"][names[0]], entry_px_x=cur["entry_px"][names[1]],
                qty_y=sh[names[0]], qty_x=sh[names[1]], exit_signal_date=cur["exit_sig_date"], exit_date=d,
                exit_px_y=px[names[0]], exit_px_x=px[names[1]], exit_reason=reason,
                hold_sessions=i - cur["entry_i"], hold_calendar_days=(d - cur["entry_date"]).days, gross_pnl=gross, dividends=cur["div"],
                costs=cur["cost"] + cost, borrow=cur["borrow"], net_pnl=net, equity_basis=cur["equity"]))
            for t in names:
                sh[t] = 0.0
            cur = None
        else:
            ny = spec.gross_frac * equity_prev / (1 + beta)
            q = {names[0]: side * ny / px[names[0]], names[1]: -side * beta * ny / px[names[1]]}
            for t in names:
                cash -= q[t] * px[t]
                cost += bps * abs(q[t]) * px[t]
                sh[t] = q[t]
            cash -= cost
            cur = dict(side=side, beta=beta, sig_date=sig_date, entry_date=d, entry_i=i, entry_px=dict(px), div=0.0,
                       cost=cost, borrow=0.0, equity=equity_prev, exit_sig_date=None)

    for i, d in enumerate(dates):
        o, c = px_open.iloc[i], px_close.iloc[i]
        day_div = sum(sh[t] * div.at[d, t] for t in names)          # holders at start of day
        cash += day_div
        if cur:
            cur["div"] += day_div
        if pending and i >= pending["due"]:
            p, pending = pending, None
            px = o if spec.fill == "open_next" else c
            if px.isna().any():
                raise ValueError(f"missing {'open' if spec.fill == 'open_next' else 'close'} price on {d.date()} for pending {p['kind']} order "
                                 f"(signal {p['sig_date'].date()}); fix the data rather than skipping the order")
            if p["kind"] == "exit" and cur:
                cur["exit_sig_date"] = p["sig_date"]
                fill(px, "exit", p["reason"], d=d, i=i)
            elif p["kind"] == "entry" and not cur:
                fill(px, "entry", "entry", p["side"], p["beta"], p["sig_date"], d, i)
            else:
                raise RuntimeError(f"order/position state mismatch on {d.date()}: {p['kind']} with cur={cur is not None}")
        # mark at close; borrow is charged for the night(s) until the next session
        mv = {t: sh[t] * c[t] for t in names}
        short_mv = -sum(v for v in mv.values() if v < 0)
        nights = (dates[i + 1] - d).days if i + 1 < n else 0     # no night follows the final close
        borrow = short_mv * borrow_rate * nights / 365
        cash -= borrow
        if cur:
            cur["borrow"] += borrow
        equity = cash + sum(mv.values())
        long_mv = sum(v for v in mv.values() if v > 0)
        rows.append(dict(date=d, equity=equity, long_mv=long_mv, short_mv=-short_mv, borrow=borrow,
                         mv_y=mv[names[0]], mv_x=mv[names[1]],
                         div=day_div, in_trade=int(cur is not None), ret=equity / equity_prev - 1))
        equity_prev = equity
        # risk limits
        s = sig.iloc[i]
        exit_reason = None
        if cur:
            mtm = sum(sh[t] * (c[t] - cur["entry_px"][t]) for t in names) + cur["div"] - cur["cost"] - cur["borrow"]
            if mtm <= -spec.loss_limit * cur["equity"]:
                exit_reason, locked_window = "loss_limit", s["window"]
        peak = max(peak, equity)
        if i >= halted_until and halted_until > 0:
            halted_until, peak = -1, equity                          # resume; peak resets (documented)
        if halted_until < 0 and equity / peak - 1 <= -spec.dd_halt:
            halted_until, exit_reason = i + spec.halt_days, exit_reason or "dd_halt"
        # orders for the next execution
        if i + fill_lag <= n - 1:
            due = i + fill_lag
            if cur and not pending:
                if exit_reason:
                    pending = dict(kind="exit", reason=exit_reason, sig_date=d, due=due)
                elif s["target"] == 0:
                    pending = dict(kind="exit", reason=s["reason"] or "signal", sig_date=d, due=due)
            elif (not cur and not pending and s["target"] != 0 and prev_target == 0
                  and halted_until < 0 and s["window"] != locked_window):
                pending = dict(kind="entry", side=int(s["target"]), beta=s["beta"], sig_date=d, due=due)
        prev_target = s["target"]

    if cur:                                                          # mark-out at the final close
        cur["exit_sig_date"] = dates[-1]
        fill(px_close.iloc[-1], "exit", "end_of_data", d=dates[-1], i=n - 1)
        rows[-1].update(equity=cash, long_mv=0.0, short_mv=0.0, mv_y=0.0, mv_x=0.0, in_trade=0)
    daily = pd.DataFrame(rows).set_index("date")
    daily["ret"] = daily.equity.pct_change().fillna(daily.equity.iloc[0] / spec.initial_equity - 1)
    daily["gross_pct"] = (daily.long_mv - daily.short_mv) / daily.equity
    daily["net_pct"] = (daily.long_mv + daily.short_mv) / daily.equity
    return daily, pd.DataFrame(trades)


class ReconciliationError(AssertionError):
    pass


def reconcile(daily, trades, spec, tol=0.01):
    """Trade-level net P&L must equal the change in portfolio equity (no cash interest is modelled).
    Returns the difference in dollars; raises ReconciliationError if it exceeds `tol` dollars (float noise is ~1e-8)
    or if any equity, cash-flow or trade value is not finite (NaN or infinite never passes)."""
    cols = [c for c in ("equity", "long_mv", "short_mv", "borrow", "div") if c in daily.columns]
    if not len(daily) or not np.isfinite(daily[cols].to_numpy(dtype=float)).all():
        raise ReconciliationError("non-finite or missing values in the daily ledger")
    tcols = [c for c in ("gross_pnl", "dividends", "costs", "borrow", "net_pnl") if c in trades.columns]
    if len(trades) and not np.isfinite(trades[tcols].to_numpy(dtype=float)).all():
        raise ReconciliationError("non-finite values in the trade ledger")
    err = float(daily.equity.iloc[-1] - spec.initial_equity - (trades.net_pnl.sum() if len(trades) else 0.0))
    if not np.isfinite(err) or abs(err) > tol:
        raise ReconciliationError(f"trade P&L does not reconcile to equity: difference {err:,.4f} (tolerance {tol})")
    return err

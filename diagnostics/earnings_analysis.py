"""Earnings-exposure diagnostic over actual holding intervals (docs/PREREG_EARNINGS.md, revised). Exploratory; changes no rule.

  python diagnostics/earnings_analysis.py [results_dir]    (default results_rerun; needs data/raw/earnings.csv)

Time on the trading calendar is a sequence of points: the open of session s is 2s and its close is 2s + 1.
A position is held from its entry fill to its exit fill: [2e, 2x] for next-open fills, [2e+1, 2x+1] for next-close fills, and an
end-of-data exit is at the final close. An earnings release moves prices across one overnight gap:
  released before the open of session r  -> gap from close r-1 to open r   = (2r-1, 2r)
  released after the close of session r  -> gap from close r to open r+1   = (2r+1, 2r+2)
A trade is exposed to a release if it is held across that gap. Compustat report dates (rdq) carry no time of day, so results
are shown under three labelled assumptions: every release before the open, every release after the close, and "either"
(exposed under at least one timing; the inclusive primary definition). A report date on a non-trading day counts as before the
next open. Only the gap is counted, not any continued reaction during the following session.
Trade outcomes are compared as net P&L divided by the equity at entry, so years with different equity are comparable. Longer
trades have more chances to span a release, so the comparison is also shown within holding-length groups."""
import sys

import numpy as np
import pandas as pd

TIMINGS = ("pre_open", "after_close", "either")


def hold_points(entry_i, exit_i, fill="open_next", end_of_data=False):
    start = 2 * entry_i + (0 if fill == "open_next" else 1)
    end = 2 * exit_i + (1 if (end_of_data or fill == "close_next") else 0)
    return start, end


def gap(r_i, timing):
    return (2 * r_i - 1, 2 * r_i) if timing == "pre_open" else (2 * r_i + 1, 2 * r_i + 2)


def exposed(start, end, release_sessions, timing):
    if timing == "either":
        return exposed(start, end, release_sessions, "pre_open") or exposed(start, end, release_sessions, "after_close")
    return any(start <= a and end >= b for a, b in (gap(r, timing) for r in release_sessions))


def release_sessions(rdq, cal):
    """Session index of each report date (first trading session on or after the date)."""
    idx = cal.searchsorted(pd.DatetimeIndex(pd.Series(rdq).dropna()))
    return sorted(set(int(i) for i in idx if i < len(cal)))


def boot_diff(a, b, B=10000, seed=7):
    rng = np.random.default_rng(seed)
    d = [rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(B)]
    return np.percentile(d, [2.5, 97.5])


def classify(trades, cal, rel, fill="open_next"):
    pos = {d: i for i, d in enumerate(cal)}
    out = trades.copy()
    for tm in TIMINGS:
        out[f"exp_{tm}"] = [exposed(*hold_points(pos[r.entry_date], pos[r.exit_date], fill, r.exit_reason == "end_of_data"), rel, tm)
                            for r in trades.itertuples()]
    out["pnl_pct"] = out.net_pnl / out.equity_basis
    return out


def daily_gap_days(daily, trades, cal, rel):
    """Every day whose P&L belongs to a position (entry day to exit day inclusive, so exit-day P&L is kept), with a flag for days
    whose P&L window includes a release gap (held at the previous close and a release falls in that overnight gap)."""
    pos = {d: i for i, d in enumerate(cal)}
    pre, aft = set(rel), {r + 1 for r in rel}             # after-close release on r -> gap before the open of r + 1
    rows = []
    ret = daily.equity.pct_change().fillna(daily.equity.iloc[0] / 1e6 - 1)
    for t in trades.itertuples():
        e, x = pos[t.entry_date], pos[t.exit_date]
        for s in range(e, x + 1):
            d = cal[s]
            overnight = s > e                                # the position was held at the previous close
            rows.append(dict(date=d, ret=ret.get(d, np.nan), pnl=daily.equity.diff().get(d, np.nan) if s > 0 else np.nan,
                             gap_pre=overnight and s in pre, gap_after=overnight and s in aft))
    df = pd.DataFrame(rows).dropna(subset=["ret"])
    df["gap_either"] = df.gap_pre | df.gap_after
    return df


def main(res="results_rerun"):
    ev = pd.read_csv("data/raw/earnings.csv", parse_dates=["datadate", "rdq"])
    cal = pd.DatetimeIndex(pd.read_csv("data/processed/market.csv", parse_dates=["date"]).date.drop_duplicates().sort_values())
    rel = release_sessions(ev.rdq, cal)
    print(f"report dates: {ev.rdq.notna().sum()} (missing rdq excluded: {int(ev.rdq.isna().sum())}); distinct release sessions {len(rel)}")
    T, D = {}, {}
    for p in ("dev", "val", "holdout"):
        t = pd.read_csv(f"{res}/{p}_none_open_next/trades.csv", parse_dates=["entry_date", "exit_date"])
        T[p] = classify(t, cal, rel).assign(period=p)
        D[p] = pd.read_csv(f"{res}/{p}_none_open_next/daily.csv", parse_dates=["date"]).set_index("date")
    al = pd.concat(T.values(), ignore_index=True)
    print("\nTRADES: net P&L as % of entry equity, by release-timing assumption (exploratory, post hoc)")
    for tm in TIMINGS:
        a, b = al[al[f"exp_{tm}"]].pnl_pct.values, al[~al[f"exp_{tm}"]].pnl_pct.values
        lo, hi = boot_diff(a, b)
        print(f"  {tm:11s} exposed n={len(a):3d} mean {a.mean():+.2%} median {np.median(a):+.2%} win {np.mean(a > 0):.0%} | "
              f"not exposed n={len(b):3d} mean {b.mean():+.2%} median {np.median(b):+.2%} win {np.mean(b > 0):.0%} | "
              f"difference {a.mean() - b.mean():+.2%} [95% {lo:+.2%}, {hi:+.2%}]")
    print("\n  by period (primary 'either'):")
    for p, g in al.groupby("period", sort=False):
        a, b = g[g.exp_either].pnl_pct, g[~g.exp_either].pnl_pct
        print(f"    {p:8s} exposed n={len(a):2d} mean {a.mean():+.2%} | not exposed n={len(b):2d} mean {b.mean():+.2%} | diff {a.mean() - b.mean():+.2%}")
    al["hold_group"] = pd.qcut(al.hold_sessions, 3, labels=["short", "medium", "long"])
    print("\n  holding length matters: longer trades span more releases ('either')")
    for g, h in al.groupby("hold_group", observed=True):
        a, b = h[h.exp_either].pnl_pct, h[~h.exp_either].pnl_pct
        print(f"    {g:6s} sessions {h.hold_sessions.min():2d}-{h.hold_sessions.max():2d}: exposure rate {h.exp_either.mean():.0%}; "
              f"exposed n={len(a):2d} mean {a.mean() if len(a) else np.nan:+.2%} | not exposed n={len(b):2d} mean {b.mean() if len(b) else np.nan:+.2%}")
    dd = pd.concat([daily_gap_days(D[p], T[p], cal, rel) for p in D], ignore_index=True)
    print("\nPOSITION DAYS (entry day to exit day inclusive; daily return on equity)")
    for col in ("gap_pre", "gap_after", "gap_either"):
        a, b = dd[dd[col]].ret, dd[~dd[col]].ret
        print(f"  {col:10s} release-gap days n={len(a):4d} mean {a.mean():+.3%} sd {a.std():.3%} | other position days n={len(b):5d} mean {b.mean():+.3%} sd {b.std():.3%}")
    exit_days = int(sum(len(t) for t in T.values()))
    print(f"\n(includes {exit_days} exit days that the earlier version dropped by filtering on in_trade)")
    return al, dd


if __name__ == "__main__":
    main(*sys.argv[1:2])

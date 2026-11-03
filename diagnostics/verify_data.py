"""Data validation and cross-checks against independent CRSP fields.   python diagnostics/verify_data.py

Always runs (needs data/raw/crsp_daily.csv and data/processed/market.csv): dates, duplicates, price positivity,
missing values, alignment between the two securities, split-factor events, extreme moves.
Runs when extract_aux.py has been executed: price flags, closes vs the CIZ close field, opens inside the day's range,
and derived distributions vs the file's own distribution amounts and the CRSP distribution events.
Exits non-zero if a hard check fails."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

fails = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FAIL'}] {name} {detail}")
    if not ok:
        fails.append(name)


def main():
    raw = pd.read_csv("data/raw/crsp_daily.csv", parse_dates=["date"])
    mk = pd.read_csv("data/processed/market.csv", parse_dates=["date"])
    for tk, g in raw.groupby("ticker"):
        g = g.sort_values("date")
        check(f"{tk}: no duplicate dates", not g.date.duplicated().any(), f"({len(g)} rows {g.date.min().date()} -> {g.date.max().date()})")
        check(f"{tk}: dates strictly increasing and weekdays", g.date.is_monotonic_increasing and (g.date.dt.weekday < 5).all())
        check(f"{tk}: close/open > 0 and not missing", (g.prc.abs() > 0).all() and (g.openprc.abs() > 0).all() and g[["prc", "openprc", "cfacpr"]].notna().all().all())
        miss = g[g[["ret", "retx"]].isna().any(axis=1)]
        check(f"{tk}: return fields missing only on the first listing day", len(miss) == 0 or (len(miss) == 1 and miss.date.iloc[0] == g.date.min()),
              f"({len(miss)} missing: {[str(x.date()) for x in miss.date]})")
        check(f"{tk}: prc >= 0 in raw file (no negative bid/ask-average flag)", (g.prc >= 0).all())
        check(f"{tk}: cfacpr positive", (g.cfacpr > 0).all(), f"values {sorted(g.cfacpr.unique())}")
        gap = g.date.diff().dt.days.dropna()
        check(f"{tk}: largest gap between observations is a holiday weekend (<= 5 calendar days)", gap.max() <= 5, f"(max {int(gap.max())})")
    d = {t: set(g.date) for t, g in raw.groupby("ticker")}
    start = max(min(d["V"]), min(d["MA"]))                      # later listing date
    check("after the later listing, V and MA have identical date sets", {x for x in d["V"] if x >= start} == {x for x in d["MA"] if x >= start},
          f"(common start {start.date()}; {len(d['V'] ^ d['MA'])} unpaired dates, all before it)")
    c = mk.pivot(index="date", columns="ticker", values="close")
    check("processed market.csv: both securities present on every date from the common start", c.loc[start:].notna().all().all(), f"({len(c.loc[start:])} dates)")
    c = c.loc[start:]
    adj = np.log(mk.pivot(index="date", columns="ticker", values="open").loc[start:] / c.shift(1)).abs()
    big = adj.stack().loc[lambda s: s > 0.10]
    print("  adjusted overnight gaps > 10%:", [(str(i[0].date()), i[1], round(float(v), 3)) for i, v in big.items()])
    ret = c.pct_change().abs().stack().loc[lambda s: s > 0.15]
    print("  adjusted close-to-close moves > 15%:", [(str(i[0].date()), i[1], round(float(v), 3)) for i, v in ret.items()] or "none")

    p = Path("data/raw/crsp_checks.csv")
    if not p.exists():
        print("\n(data/raw/crsp_checks.csv not found: run extract_aux.py for flag, range and distribution cross-checks)")
    else:
        k = pd.read_csv(p, parse_dates=["dlycaldt"]).rename(columns={"dlycaldt": "date"})
        tick = {92611: "V", 91233: "MA"}; k["ticker"] = k.permno.map(tick)
        m = raw.merge(k, on=["ticker", "date"], how="inner", suffixes=("", "_c"))
        check("check file covers every raw row", len(m) == len(raw), f"({len(m)}/{len(raw)})")
        check("dlyprcflg is trade-based for every row", set(k.dlyprcflg.dropna().unique()) <= {"TR", "TRD", "T"}, f"(values {sorted(k.dlyprcflg.dropna().unique())})")
        check("price equals the CIZ close field (dlyclose)", ((m.prc.abs() - m.dlyclose).abs() < 1e-6).mean() > 0.999,
              f"({((m.prc.abs() - m.dlyclose).abs() < 1e-6).mean():.4%} equal)")
        inside = ((m.openprc >= m.dlylow - 1e-6) & (m.openprc <= m.dlyhigh + 1e-6))
        check("open within the day's [low, high]", inside.all(), f"({inside.mean():.4%}; open is not independently sourced, this is a range check only)")
        raw_cash = ((m.ret - m.retx) * m.groupby("ticker").prc.shift(1).abs()).where(lambda s: s > 1e-4, 0.0)
        file_cash = (m.dlyorddivamt.fillna(0) + m.dlynonorddivamt.fillna(0))
        ev = m[(raw_cash > 0) | (file_cash > 0)].assign(derived=raw_cash, filecash=file_cash)
        dd = (ev.derived - ev.filecash).abs()
        check("derived distribution dates match the file's distribution dates", ((ev.derived > 0) == (ev.filecash > 0)).all(), f"({len(ev)} event days)")
        check("derived amount within 1 cent/share of the file's amount", (dd < 0.01).all(), f"(max abs diff {dd.max():.5f}; median {dd.median():.5f})")
    q = Path("data/raw/crsp_distributions.csv")
    if q.exists():
        e = pd.read_csv(q)
        print(f"\ndistribution events file: {len(e)} rows; columns {list(e.columns)}")
    print("\nHARD FAILURES:" if fails else "\nall hard checks passed", fails or "")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

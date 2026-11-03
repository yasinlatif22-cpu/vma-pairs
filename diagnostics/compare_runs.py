"""Compare two results directories (e.g. the originally reported runs and the post-correction re-runs).
  python diagnostics/compare_runs.py results_v1 results_rerun"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main(a="results_v1", b="results_rerun"):
    rows = []
    for d in sorted(p.name for p in Path(a).iterdir() if p.is_dir()):
        if not (Path(b) / d).exists():
            continue
        ta, tb = (pd.read_csv(Path(x) / d / "trades.csv") for x in (a, b))
        da, db = (pd.read_csv(Path(x) / d / "daily.csv", index_col=0) for x in (a, b))
        same_trades = len(ta) == len(tb) and (ta.net_pnl - tb.net_pnl).abs().max() < 0.01 if len(ta) == len(tb) else False
        k = [c for c in ("signal_date", "entry_date", "exit_date", "exit_reason") if c in ta and c in tb]
        same_keys = len(ta) == len(tb) and (ta[k].astype(str).values == tb[k].astype(str).values).all()
        sh = lambda r: r.mean() / r.std(ddof=1) * np.sqrt(252)
        rows.append(dict(run=d, trades=f"{len(ta)}/{len(tb)}", same_trade_keys=same_keys,
                         max_trade_net_diff=round(float((ta.net_pnl - tb.net_pnl).abs().max()), 4) if len(ta) == len(tb) else np.nan,
                         net_pnl_a=round(ta.net_pnl.sum(), 2), net_pnl_b=round(tb.net_pnl.sum(), 2),
                         final_equity_diff=round(float(db.equity.iloc[-1] - da.equity.iloc[-1]), 4),
                         sharpe_a=round(sh(da.ret), 4), sharpe_b=round(sh(db.ret), 4),
                         max_daily_ret_diff=round(float((da.ret - db.ret).abs().max()), 8)))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:3])

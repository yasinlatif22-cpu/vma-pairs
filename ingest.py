"""Convert data/raw/*.csv to the canonical files and print a data-quality report.  python ingest.py"""
import numpy as np
import pandas as pd

from data_io import from_crsp

raw = pd.read_csv("data/raw/crsp_daily.csv", parse_dates=["date"])
mkt = pd.read_csv("data/raw/mkt_raw.csv", parse_dates=["date"])
out = from_crsp(raw)
out.to_csv("data/processed/market.csv", index=False)
mkt[["date", "mkt_ret"]].to_csv("data/processed/mkt.csv", index=False)

print("rows per ticker, first/last date:")
print(out.groupby("ticker").date.agg(["count", "min", "max"]))
wide = out.pivot(index="date", columns="ticker", values="close")
print("\ndates where only one name has a close (dropped by the loader):", int(wide.isna().any(axis=1).sum()))
print("missing open prices (fills skipped on those dates):", int(out.open.isna().sum()))
print("\ncash distributions derived per ticker per year:")
print(out[out["div"] > 0].groupby(["ticker", out.date.dt.year])["div"].agg(["count", "sum"]).round(3).unstack(0))
jumps = out.assign(r=out.groupby("ticker").close.pct_change()).query("abs(r) > 0.15")
print("\nabs daily close-to-close moves > 15% (check these are real, not unadjusted splits):")
print(jumps[["date", "ticker", "close", "r"]].to_string() if len(jumps) else "none")
gaps = wide.dropna().index.to_series().diff().dt.days
print("\nlargest calendar gaps between usable dates:", gaps.nlargest(3).to_dict())

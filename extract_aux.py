"""Auxiliary WRDS pulls: risk-free rate / market factor and earnings report dates.  Run on your own machine.

  python extract_aux.py            # -> data/raw/rf.csv, data/raw/earnings.csv  (both git-ignored)

wrds.Connection() prompts for credentials (nothing is stored here).  Outputs are licensed data: do not commit them.
 rf.csv        date, rf, mktrf    daily Fama-French risk-free rate and market excess return (decimals), ff.factors_daily
 earnings.csv  ticker, gvkey, datadate, rdq   Compustat quarterly report date (rdq) for V and MA
Each step is independent; a failure prints the reason and moves on.
"""
from pathlib import Path

import wrds

db = wrds.Connection()
Path("data/raw").mkdir(parents=True, exist_ok=True)

try:
    rf = db.raw_sql("select date, rf, mktrf from ff.factors_daily where date >= '2008-01-01' order by date", date_cols=["date"])
    rf.to_csv("data/raw/rf.csv", index=False)
    print("rf.csv rows", len(rf), rf.date.min().date(), "->", rf.date.max().date())
except Exception as e:
    print("ff.factors_daily failed:", str(e).strip().splitlines()[0][:160])

try:
    co = db.raw_sql("select gvkey, conm from comp.company where strpos(upper(conm), 'VISA INC') = 1 "
                    "or strpos(upper(conm), 'MASTERCARD') = 1")
    print(co)                                        # check the company names before trusting the ids
    keep = co[co.conm.str.upper().str.contains("VISA INC|MASTERCARD")].copy()
    keep["tic"] = keep.conm.str.upper().map(lambda n: "V" if n.startswith("VISA") else "MA")
    ids = ",".join(f"'{g}'" for g in keep.gvkey)
    q = (f"select gvkey, datadate, fyearq, fqtr, rdq from comp.fundq where gvkey in ({ids}) and indfmt='INDL' "
         f"and datafmt='STD' and consol='C' and popsrc='D' and datadate >= '2007-06-30' order by gvkey, datadate")
    e = db.raw_sql(q, date_cols=["datadate", "rdq"]).merge(keep[["gvkey", "tic"]], on="gvkey").rename(columns={"tic": "ticker"})
    e.to_csv("data/raw/earnings.csv", index=False)
    print("earnings.csv rows", len(e), "missing rdq", int(e.rdq.isna().sum()))
    print(e.groupby("ticker").rdq.agg(["min", "max", "count"]))
except Exception as ex:
    print("Compustat pull failed:", str(ex).strip().splitlines()[0][:160])

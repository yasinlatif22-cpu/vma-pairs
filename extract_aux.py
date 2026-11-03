"""Auxiliary WRDS pulls for verification, financing and fundamental context. Run on your own machine.

  python extract_aux.py            # writes git-ignored files under data/raw/ and data/raw/extraction_log.json

wrds.Connection() prompts for credentials (nothing is stored here). The outputs are licensed data: do not commit them.
 rf.csv               date, rf, mktrf        Fama-French daily risk-free rate and market excess return (decimals)
 earnings.csv         ticker, gvkey, datadate, fyearq, fqtr, rdq, saleq, oiadpq, niq, epspxq, epsfxq, ajexq   Compustat quarterly
 crsp_checks.csv      CIZ daily file fields used to cross-check prices and distributions (flags, high/low, dividend amounts)
 crsp_distributions.csv   CRSP distribution events (independent of the return-based dividend inference)
 field_definitions.csv    column comments from the database catalogue, if WRDS provides them
Each step is independent: a failure prints the reason and the script moves on. The log records UTC time, row counts,
date ranges, SHA-256 of each output and the query text (no market data).
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

import wrds

PERMNOS = {"V": 92611, "MA": 91233}          # confirmed against issuer names in extract_wrds.py (stksecurityinfohist)
IDS = ",".join(map(str, PERMNOS.values()))
RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)
log = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "permnos": PERMNOS, "steps": {}}
db = wrds.Connection()


def step(name, query, fname, date_cols=None, post=None):
    try:
        df = db.raw_sql(query, date_cols=date_cols)
        if post is not None:
            df = post(df)
        path = RAW / fname
        df.to_csv(path, index=False)
        dcol = next((c for c in df.columns if c in ("date", "dlycaldt", "rdq", "exdt", "disexdt")), None)
        log["steps"][name] = dict(file=fname, rows=len(df), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), query=" ".join(query.split()),
                                  first=str(df[dcol].min()) if dcol and len(df) else None, last=str(df[dcol].max()) if dcol and len(df) else None)
        print(f"{name}: {len(df)} rows -> {fname}")
        return df
    except Exception as e:
        msg = str(e).strip().splitlines()[0][:200]
        log["steps"][name] = dict(error=msg, query=" ".join(query.split()))
        print(f"{name} FAILED: {msg}")


step("rf", "select date, rf, mktrf from ff.factors_daily where date >= '2008-01-01' order by date", "rf.csv", ["date"])

co = db.raw_sql("select gvkey, conm from comp.company where strpos(upper(conm), 'VISA INC') = 1 or strpos(upper(conm), 'MASTERCARD') = 1")
print(co)
keep = co[co.conm.str.upper().str.contains("VISA INC|MASTERCARD")].copy()
keep["ticker"] = keep.conm.str.upper().map(lambda n: "V" if n.startswith("VISA") else "MA")
gv = ",".join(f"'{g}'" for g in keep.gvkey)
step("compustat_fundq",
     f"select gvkey, datadate, fyearq, fqtr, rdq, saleq, oiadpq, niq, epspxq, epsfxq, ajexq from comp.fundq where gvkey in ({gv}) "
     f"and indfmt='INDL' and datafmt='STD' and consol='C' and popsrc='D' and datadate >= '2007-06-30' order by gvkey, datadate",
     "earnings.csv", ["datadate", "rdq"], post=lambda e: e.merge(keep[["gvkey", "ticker"]], on="gvkey"))

step("crsp_checks",
     f"select permno, dlycaldt, dlyprc, dlyprcflg, dlyclose, dlyopen, dlyhigh, dlylow, dlybid, dlyask, dlyvol, dlyret, dlyretx, "
     f"dlyorddivamt, dlynonorddivamt, dlyfacprc, dlycumfacpr, dlydistretflg from crsp.dsf_v2 where permno in ({IDS}) "
     f"and dlycaldt >= '2008-01-01' order by permno, dlycaldt", "crsp_checks.csv", ["dlycaldt"])

dist = step("crsp_distributions",
            f"select permno, distcd, divamt, facpr, facshr, exdt, rcrddt, paydt, declardt from crsp.dsedist where permno in ({IDS}) order by permno, exdt",
            "crsp_distributions.csv", ["exdt"])
if dist is None:
    step("crsp_distributions_ciz", f"select * from crsp.stkdistributions where permno in ({IDS})", "crsp_distributions.csv")

step("field_definitions",
     "select c.relname as table_name, a.attname as column_name, d.description from pg_attribute a "
     "join pg_class c on c.oid = a.attrelid join pg_namespace n on n.oid = c.relnamespace "
     "left join pg_description d on d.objoid = c.oid and d.objsubid = a.attnum "
     "where n.nspname = 'crsp' and c.relname in ('dsf_v2', 'dsf') and a.attnum > 0 order by c.relname, a.attnum", "field_definitions.csv")

(RAW / "extraction_log.json").write_text(json.dumps(log, indent=2, default=str))
print("wrote data/raw/extraction_log.json")

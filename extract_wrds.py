"""Pull daily CRSP data for the pair from WRDS. Run this yourself on your own machine.

  python extract_wrds.py --check     # entitlement + schema check; writes data/raw/wrds_manifest.json (safe to share)
  python extract_wrds.py             # download -> data/raw/crsp_daily.csv, data/raw/mkt_raw.csv

Credentials: wrds.Connection() prompts for your WRDS username/password (and a Duo push). Nothing is stored in
this code. Do not commit data/raw/ or data/processed/: CRSP data cannot be redistributed (.gitignore covers it).
Column names for the newer CRSP format differ from the legacy ones; the --check output shows which exist.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
import wrds

NAMES = {"V": "VISA", "MA": "MASTERCARD"}
FORMATS = {   # field names are best guesses; --check prints the real columns so mismatches are caught
    "legacy": dict(table="dsf", date="date", prc="prc", openprc="openprc", ret="ret", retx="retx", cfacpr="cfacpr"),
    "ciz": dict(table="dsf_v2", date="dlycaldt", prc="dlyprc", openprc="dlyopen", ret="dlyret", retx="dlyretx",
                cfacpr="dlycumfacpr"),
}
WATCH = ["dsf", "dsf_v2", "dsi", "stocknames", "stksecurityinfohist"]


def columns(db, lib, table):
    try:
        return list(db.describe_table(lib, table).name)
    except Exception:
        return None


def check(db):
    libs = db.list_libraries()
    man = {"has_crsp": "crsp" in libs, "has_ff": "ff" in libs, "tables": {}}
    for t in WATCH:
        cols = columns(db, "crsp", t)
        man["tables"][t] = {"exists": cols is not None, "columns": cols}
    for fmt, f in FORMATS.items():
        cols = man["tables"].get(f["table"], {}).get("columns")
        if cols:
            man[f"{fmt}_missing_fields"] = [v for k, v in f.items() if k != "table" and v not in cols]
            q = f"select min({f['date']}) a, max({f['date']}) b, count(*) n from crsp.{f['table']} where permno = 14593"
            man[f"{fmt}_coverage_probe"] = db.raw_sql(q).astype(str).to_dict("records")  # 14593 = Apple, probe only
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/raw/wrds_manifest.json").write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(man, indent=2, default=str))


def find_permnos(db):
    out = {}
    for tick, name in NAMES.items():
        df, errs = None, []
        for q in (f"select distinct permno, issuernm as name, ticker, secinfostartdt as start, secinfoenddt as end_ "
                  f"from crsp.stksecurityinfohist where strpos(upper(issuernm), '{name}') = 1",
                  f"select distinct permno, comnam as name, ticker, namedt as start, nameenddt as end_ "
                  f"from crsp.stocknames where strpos(upper(comnam), '{name}') = 1"):  # no % (driver treats it as a parameter)
            try:
                df = db.raw_sql(q)
                break
            except Exception as e:
                errs.append(str(e).strip().splitlines()[0][:160])
        print(f"\n{tick} candidates:\n{df if df is not None else 'lookup failed: ' + ' | '.join(errs)}")
        out[tick] = sorted(df.permno.unique()) if df is not None else []
    return out


def show_names(db, ids):
    """Print the issuer name and ticker behind each permno so a wrong id is caught before analysis."""
    q = (f"select distinct permno, issuernm, ticker from crsp.stksecurityinfohist "
         f"where permno in ({','.join(map(str, ids.values()))})")
    try:
        print("\npermno check:\n", db.raw_sql(q))
    except Exception as e:
        print("permno name check unavailable:", str(e).strip().splitlines()[0][:120])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--format", choices=list(FORMATS), help="legacy (dsf) or ciz (dsf_v2); use the one whose coverage reaches today")
    ap.add_argument("--permno", nargs="*", default=[], help="override, e.g. V=92611 MA=91233 (verify against the candidates printed)")
    ap.add_argument("--start", default="2008-01-01")
    a = ap.parse_args()
    db = wrds.Connection()
    if a.check:
        return check(db)
    if not a.format:
        raise SystemExit("Pass --format legacy|ciz (see --check coverage).")
    f = FORMATS[a.format]
    perm = {kv.split("=")[0]: [int(kv.split("=")[1])] for kv in a.permno} or find_permnos(db)
    bad = {k: v for k, v in perm.items() if len(v) != 1}
    if bad:
        raise SystemExit(f"Need exactly one permno per ticker, got {bad}. Re-run with --permno V=<id> MA=<id>.")
    ids = {t: v[0] for t, v in perm.items()}
    show_names(db, ids)
    sel =", ".join(f"{v} as {k}" for k, v in f.items() if k != "table")
    q = (f"select permno, {sel} from crsp.{f['table']} where permno in ({','.join(map(str, ids.values()))}) "
         f"and {f['date']} >= '{a.start}' order by permno, {f['date']}")
    df = db.raw_sql(q, date_cols=["date"])
    df["ticker"] = df.permno.map({v: k for k, v in ids.items()})
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    df.to_csv("data/raw/crsp_daily.csv", index=False)
    print(df.groupby("ticker").date.agg(["min", "max", "count"]), "\nmissing open:", df.openprc.isna().mean().round(3))
    for q, cols in ((f"select date, vwretd as mkt_ret from crsp.dsi where date >= '{a.start}'", None),
                    (f"select date, mktrf + rf as mkt_ret, rf from ff.factors_daily where date >= '{a.start}'", None)):
        try:
            m = db.raw_sql(q, date_cols=["date"])
            m.to_csv("data/raw/mkt_raw.csv", index=False)
            print("market series rows:", len(m))
            break
        except Exception as e:
            print("market query failed:", str(e)[:80])


if __name__ == "__main__":
    main()

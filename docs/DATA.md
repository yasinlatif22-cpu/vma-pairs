# Getting the data (WRDS / CRSP)

## What you need
CRSP daily stock file (price, open price, return with and without distributions, price adjustment factor) for Visa
and Mastercard, plus a daily market return series. Which CRSP products your school licenses, and whether the newer
format (`dsf_v2`) is the one that reaches today, is what `--check` tells you.

## Steps
1. `pip install -r requirements.txt`
2. `python extract_wrds.py --check` and enter your WRDS login when prompted (approve the Duo push). Credentials are
   never written anywhere by this code. It writes `data/raw/wrds_manifest.json` (table and column names, coverage probe,
   no market data); paste its contents back so field names can be confirmed.
3. `python extract_wrds.py --format legacy` or `--format ciz`, whichever the check shows has all fields and coverage
   through the present. It prints permno candidates for each company; if there is not exactly one per ticker, re-run with
   `--permno V=<id> MA=<id>`.
4. `python ingest.py` prints the quality report. Read it: rows per ticker and start dates, dropped dates, missing opens,
   derived dividends per year, any |daily move| > 15% (a missed split would show up here), and gaps.

## Conventions
- Prices are split-adjusted with CRSP's cumulative factor and not dividend-adjusted. Pull all history in one extraction;
  mixing pulls taken before and after a later split corrupts the adjustment.
- Cash distribution per share = (ret - retx) x prior adjusted close, from the same file.
- If the open field is missing or empty, run with `--fill close_next` and say so in the write-up.
- CRSP data is licensed: do not commit `data/raw/` or `data/processed/`, and do not publish the extracted files.
  `.gitignore` already excludes them. Publish code and result summaries, not the data.

## Not available from this route
Historical borrow rates and availability (use the 30 bps assumption and its sensitivity), intraday data, and the
quoted spread at the time of trade.

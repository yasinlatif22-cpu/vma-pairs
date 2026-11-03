# Independent accounting audit and data verification

**Two different things are verified, and only the first is complete.**
1. *Internal arithmetic* (done): the engine's ledger agrees with separately written code reading the same CRSP extract.
2. *Source data* (partly done, and partly pending your WRDS pulls): whether the CRSP fields mean what the code assumes and
   whether inferred distributions match independent distribution records.

## 1. Arithmetic verification (`diagnostics/trade_audit.py`)
Does not import the engine or data helpers. Works in actual share counts and raw prices: actual shares = adjusted shares /
`cfacpr`; gross P&L at raw prices; distributions = (ret - retx) x prior raw close, paid to shares held at the start of each
day after entry; costs 5 bps per fill; borrow 30 bps/yr per calendar night on short value at each close held, none after the exit.
Selection rule (stated, not cherry-picked): first long-V trade, first short-V trade, a trade spanning each split if one
exists, the largest-|dividend| trade, the first window-boundary exit, and the end-of-data liquidation.

| case | signal | exit | what it exercises |
|---|---|---|---|
| long V / short MA | 2009-10-23 | target | basic long/short |
| short V / long MA | 2009-04-28 | max-hold | short leg with dividend charged on the short |
| spans MA 10-for-1 split | 2014-01-15 | max-hold | split-adjusted quantities across 2014-01-22 |
| largest |dividends| | 2014-04-08 | target | dividend-spanning long position |
| window-boundary exit | 2010-09-13 | window_end | exit filled in the next window |
| end-of-data liquidation | 2017-12-27 | end_of_data | final-close liquidation, no extra borrow night |
Result: gross, dividends, costs, borrow and net match the engine to under $0.0001 in all six (output in
`public_results/diagnostics_output.txt`). No trade spans V's 2015-03-19 split, so that split is checked only through the data
checks below. Before the fix in `CORRECTIONS.md` item 1, the end-of-data trade disagreed by the one extra borrow night
($6.06); the audit is what exposes that class of error.

## 2. Data checks (`diagnostics/verify_data.py`)
Run now, on the files as pulled: no duplicate or non-weekday dates; positive prices; no missing price, open or factor; returns
missing only on V's first listing day (2008-03-19); after V's listing both securities have identical date sets; gaps
between observations are at most a holiday weekend; `cfacpr` changes only on the two splits (MA 10-for-1 on 2014-01-22,
V 4-for-1 on 2015-03-19); adjusted overnight gaps above 10% fall on known market dates (2008-10-24, 2015-08-24, 2020-03-16,
2020-11-09). No negative (bid/ask-average) prices appear in the extract.

## 3. What is not yet verified
- **Field definitions.** Official CIZ definitions (DlyOpen, DlyPrc, DlyRet, DlyRetx, DlyCumFacPr and the price flag) were not
  retrievable from a source I could reach from this environment. The code assumes: `dlyopen` is the day's opening price;
  `dlyprc` is the closing price (bid/ask average only when `dlyprcflg` says so); `dlyret` includes distributions and
  `dlyretx` excludes them; `dlycumfacpr` divides raw prices into split-adjusted ones. The CIZ table also carries `dlyclose`,
  `dlyorddivamt`, `dlynonorddivamt`, `dlyfacprc` and `dlyhigh/dlylow`, which `extract_aux.py` pulls so these assumptions can be
  tested against the file itself; the database catalogue comments are pulled to `data/raw/field_definitions.csv` for review.
- **Distributions.** Inferred amounts look right on inspection (e.g. V $0.105 per share in 2008, MA $0.15), but that is my
  recollection, not a sourced check. `verify_data.py` compares them with the file's own distribution amounts, and
  `crsp_distributions.csv` supplies CRSP distribution events; both need `extract_aux.py` to be run (pending).
- **Opening prices.** Whether `dlyopen` is the exchange opening-auction print is not verified. After the pull the script checks
  that each open lies inside the day's [low, high], which is a range check, not a source comparison.
- **Both implementations read the same CRSP extract**, so neither can catch an error in that extract.

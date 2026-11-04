# Independent accounting audit and data verification

**Two different things are verified: the first is complete; the second is consistency checking with the limits in section 4.**
1. *Internal arithmetic* (done): the engine's ledger agrees with separately written code reading the same CRSP extract.
2. *Source data* (consistency checks done; limits in section 4): whether the CRSP fields behave as the code assumes and
   whether inferred distributions match CRSP's distribution records.

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

## 3. Source-data verification (run 2026-11-03 after `extract_aux.py`; `diagnostics/verify_data.py`)
Passed: no duplicate or non-increasing dates; prices and opens positive and non-missing; return fields missing only on each
security's first listing day; V and MA share identical dates from the common start 2008-03-19 (53 earlier unpaired dates);
largest calendar gap 5 days (holiday weekends). `dlyprc` equals the CIZ `dlyclose` field on 100% of 9,005 rows and
`dlyprcflg` is `TR` (trade-based) on every row, so no bid/ask-average prices enter. Every open lies inside the day's
[low, high]. Distributions inferred from `(dlyret - dlyretx) x prior raw close` fall on the same 142 event days as CRSP's
own distribution-event table (`crsp.stkdistributions`, 147 ordinary cash dividends plus 2 split events) and agree
within 1 cent per share (maximum difference $0.00034, median $0.00005). The split events in that table (MA 2014-01-22,
V 2015-03-19) carry factors consistent with `dlycumfacpr` of 10 and 4.

## 4. What is still not verified
- **Field definitions.** The WRDS catalogue comments (`field_definitions.csv`) are short labels only ("Daily Open", "Daily
  Price Return", "Daily Cumulative Factor to Adjust Price"). They do not say whether the open is the exchange auction print
  or the first trade, so that meaning rests on CRSP documentation I did not obtain; the checks above test consistency, not that.
- **Opens are not independently sourced.** The range check cannot detect an open that is consistently different from the
  official auction price.
- **Distributions were compared with CRSP's own event table, not with company disclosures.** That tests the return-based
  inference, not CRSP. A check against Visa's and Mastercard's announced dividends has not been done.
- **Both implementations read the same CRSP extract**, so neither can catch an error in that extract.

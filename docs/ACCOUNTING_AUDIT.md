# Independent accounting audit (2026-11-03)

**Method.** `diagnostics/trade_audit.py` recomputes selected trades from raw CRSP fields (unadjusted price, open,
`cfacpr`, `ret`, `retx`) in actual share counts, without using `market.csv` or the engine. It converts the engine's
split-adjusted quantity to actual shares (adjusted quantity / cfacpr), books gross P&L at raw prices, derives the
cash distribution per share as (ret - retx) x prior raw close, pays it to shares held at the start of each day after
entry, and re-derives costs (5 bps per fill) and borrow (30 bps/yr per calendar night on short value).

**Trades checked (all in the dev run, primary open-fill):**
| signal date | type | what it exercises |
|---|---|---|
| 2009-10-23 | long V / short MA, target, 2 days | basic long/short, no dividend |
| 2009-04-28 | short V / long MA, max-hold, 16 days | short leg, dividend charged on short |
| 2014-01-15 | short V / long MA, max-hold, 57 days | spans MA's 10-for-1 split (2014-01-22) and dividends |
| 2010-09-13 | long V / short MA, window-end exit | forced window-end liquidation |
| 2013-10-31 | long V / short MA, window-end, 47 days | long-leg dividends |

**Result.** Gross, dividends, costs, borrow and net P&L match the engine to the cent in all five (differences below
$0.01); see `results/diagnostics/trade_audit.txt` (local). Reconciliation of trade P&L to equity is also zero in every run.

**What this does and does not establish.** It confirms arithmetic, split handling (cumulative-factor logic checked
across a real 10-for-1 split), share-count conversion, dividend timing and the fill/exit conventions, with code
written separately from the engine. It does not independently verify the CRSP data itself: both implementations read
the same file.

**CRSP field checks (from the local file).**
- `cfacpr` changes exactly on the two known splits (MA 2014-01-22, V 2015-03-19; V 4-for-1 from the factor of 4,
  MA 10-for-1 from the factor of 10). No other factor changes.
- Largest adjusted overnight gaps (V/MA): 2020-03-16 (+15%/+14%), 2008-10-24, 2015-08-24 (index-wide flash-crash open):
  these are known market events, so the open prices are not obviously corrupt. No missing opens in V or MA.
- Derived distributions: 70 (V) and 72 (MA) events, quarterly spacing 84-99 days. Spot values look right (V $0.105 in
  2008, $0.59 in May 2025, $0.67 in Nov 2025; MA $0.15 in 2008, $0.76 in 2025). **These are from my knowledge of public
  declarations and have not been checked against a fetched source**; a one-time check against a dividend history page
  or Compustat `comp.sec_dprc`/dividend fields would close that.
- Not verified externally: that CRSP `dlyopen` is the official opening-auction print rather than a first-trade
  or quote-based value. No independent open-price source was reachable from this environment.

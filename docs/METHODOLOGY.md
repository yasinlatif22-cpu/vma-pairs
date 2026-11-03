# Methodology

## Portfolio construction
Three different "neutralities" exist and cannot all hold at once:
- **Cointegration (log-spread) hedge**: notional(X) / notional(Y) = beta. This matches the signal, so a spread
  move is what the position earns. Chosen as primary.
- **Dollar neutral**: equal notionals. Matches the signal only if beta = 1.
- **Market-beta neutral**: needs the two stocks' market betas to offset. Not enforced; V and MA betas are similar,
  so net market exposure should be small, but it is measured, not assumed.

Sizing at entry: gross notional = `gross_frac` x last-close equity; Y notional = gross / (1 + beta). Share counts are
then fixed until exit, so exposures drift with prices (reported daily as gross %, net % and beta-weighted market %).

## Execution
Signal at the close of day t; order fills at the open of t+1 (`fill=open_next`) or the close of t+1 (`close_next`,
used if opens are unavailable or as a delay sensitivity). A missing price on a fill date stops the run with an error: an order
is never cancelled, retried or dropped silently.

**Window boundaries and "flat at window end".** The signal state machine sets the target to flat at the last close of each
63-session window and issues an exit order then. That order fills at the next session's open (or close), which is the first
session of the following window. A position therefore carries across the boundary for one overnight gap, and borrow is
charged for that night. The next window's hedge ratio does not govern the exiting order. Tested in
`tests/test_engine_conventions.py`; the historical results were produced under this convention and nothing about it changed.

**Final date.** Any position open at the last date is liquidated at the final close, with costs and no borrow charge for a night
that does not occur; the final row is flat (holdings, exposures, `in_trade`, equity equals cash).

**Holding periods.** Maximum holding periods are counted in sessions (closes held after the entry fill). Trade records carry both
`hold_sessions` (sessions from entry fill to exit fill) and `hold_calendar_days`. Gap risk is real: stops are evaluated at closes and fill
at the next open, so the realised loss can exceed the limit (the test suite includes such a gap; every trade records
its realised P&L).

## Risk controls (fixed in advance, not tuned)
- `z_stop` is a **signal stop** on the spread z-score, not a loss limit. It also blocks entering at |z| >= 4.
- **Loss limit**: exit if trade net mark-to-market <= -5% of entry equity; pair locked for the rest of the window.
- **Drawdown halt**: flatten and stop trading for 63 days at -20% from peak; peak resets on resume.
- Max holding time and window-end liquidation are charged like any other exit.
These levels were chosen before any real data were run. Any change is logged in `EXPERIMENTS.md`.

## Accounting
Daily loop: dividends to holders at the start of the day (ex-date buyers get none; sellers on the ex-date keep it),
then fills, then close-of-day marking and borrow, then risk checks, then orders for tomorrow.
Each trade records entry/exit signal and fill dates, prices, quantities, exit reason, gross P&L, dividends,
costs, borrow and net P&L. `reconcile()` checks that the sum of trade P&L equals the change in equity (no cash
interest is modelled, so it should be zero) and raises `ReconciliationError` beyond $0.01, so a run with a material
discrepancy fails rather than printing a number.

| input | status |
|---|---|
| prices (open, close), splits, ex-date cash distributions | **observed** (CRSP; distribution derived as (ret - retx) x prior adjusted close) |
| trading cost 5 bps per leg per trade | **assumption** (spread + fees + small impact for mega caps) |
| borrow 30 bps annualised, charged per night on short market value | **assumption** (V and MA are general collateral; your broker's rate may differ) |
| interest on cash / short proceeds | **assumption: zero**. Not automatically conservative: it understates return on idle cash but means returns are not excess-of-rf. Scenarios and excess returns are in `RESULTS.md` |
| fills exactly at the open or close print, full size | **assumption** (no impact model) |

## Data conventions
Split-adjusted, not dividend-adjusted, prices; dividends are explicit cash flows. Dates where either name lacks a
close are dropped (log printed by `ingest.py`); nothing is forward-filled; a missing open that an order needs raises an error.
Both names trade through the whole sample after Visa's March 2008 listing, so no delisting handling is needed
here; it would be required for a broader universe.

## Evaluation discipline
- Periods: dev 2009-2017 (design checks), validation 2018-2022 (one look per pre-declared variant), holdout
  2023-Oct 2026 (once, guarded by the spec hash and a lock file).
- Pre-declared variants only: `gate=none` (primary) and `gate=coint`; `fill=open_next` and `close_next`.
- Every run is appended to `EXPERIMENTS.md`. I froze the implementation before its first market-data evaluation
  (file modification times show the code predates the data pull and the first results), while acknowledging that the
  pair and research design were informed by historical knowledge of the two companies and of the market in those
  years. The study is not unbiased: V and MA were chosen with hindsight, and the holdout is a test of the rule, not of
  the author's ignorance. Later diagnostics (open-vs-close attribution, pooled statistics, cash scenarios, accounting
  audit, case studies) were run after all evaluation periods were spent; they are classified in `EXPERIMENTS.md`.
- Bootstrap: circular block bootstrap of the realised daily returns for several block lengths. It conditions on
  the realised path and does not repeat the research process.
- Deflated Sharpe: P(true Sharpe > the best Sharpe expected from N zero-skill trials). N is the logged run count;
  trials are correlated, so N overstates the independent count (a lenient adjustment). It is not the probability that
  the strategy "works".
- Volatility regimes: cut-offs are expanding quantiles of past market volatility, so labels use only past data.

**Reproductions.** After an engine correction the evaluated periods were re-run into `results_rerun/` with
`run_study.py --reproduce`. Reproductions are labelled as such in `EXPERIMENTS.md`, never overwrite the original results, and
the holdout reproduction does not create a new holdout.

## Not implemented (deliberately, until the baseline is trusted)
Multi-pair universes, ticker-level aggregation and exposure caps, random-pair and matched-filter placebos, and
Kalman hedge ratios. When added: overlapping pairs will be separate books with netted execution per ticker and
pro-rata cost allocation; the placebo will match candidate set, pair count, capital and trading rules; Kalman will be
labelled a full alternative strategy unless the hedge model and the signal definition are changed one at a time.

## Claims removed from the earlier scaffold
"Dollar-neutral" (it was not), "roughly two false positives per window" (an unmeasured calculation), "probability the
Sharpe is real", full-sample volatility tercile cut-offs, and synthetic control results presented as proof of no bias.

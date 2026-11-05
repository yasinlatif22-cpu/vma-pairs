# Methodology

## Portfolio construction
Three different "neutralities" exist and cannot all hold at once:
- **OLS log-price hedge**: notional(X) / notional(Y) = beta, the slope of an OLS regression of log V on log MA over the
  formation window. This matches the signal, so a spread move is what the position earns. Chosen as primary. Cointegration
  is not established: most formation windows show no Engle-Granger evidence, so the fit is a hedge ratio, not a
  cointegrating relation.
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
| interest on cash / short proceeds | **assumption: zero** in the engine. Not automatically conservative: it understates income on free cash but means returns are not excess-of-rf. Financing is analysed separately (below) |
| fills exactly at the open or close print, full size | **assumption** (no impact model) |

## Performance measures
- **Mean annual return** = mean daily return x 252 (what the Sharpe ratio uses); **CAGR** = compound annual growth of equity.
  Both are reported; they differ when returns vary.
- **Drawdown** uses a running peak that starts at the initial capital, so a loss on the first day counts (`metrics.drawdown`).
- **Sharpe** is on total-equity daily returns (cash earning nothing), never on invested days only. Excess-of-T-bill Sharpe is
  reported separately under the financing scenarios.

## Financing (fixed-holdings attribution; `diagnostics/financing.py`)
The engine's holdings, trades, costs, borrow fees and dividends are kept exactly as run. Financing accrues to a separate cash
balance F that is never used to resize positions. Daily return = (change in engine equity + financing accrued) / (engine
equity + F) at the previous close, one denominator for every component.
- Longs are bought with the account's own cash (no margin loan). Short-sale proceeds stay in the account as collateral held
  for the lender (restricted); they earn a rebate only in S2.
- Posted margin: 50% of short value of the account's own cash (Regulation T initial margin; total collateral 150%), earning nothing.
- Free cash = equity + F - long value - 0.5 x short value earns the risk-free rate in S1 and S2; a negative balance would be a
  debit charged rf + 0.5% (it does not occur in these runs).
- S0 as run; S1 interest on free cash; S2 adds a rebate of rf - 0.5% on short proceeds. Borrow fees are already in the trading
  P&L and are not charged twice. The benchmark is $1M in T-bills over the same dates.
- Risk-free rate: Fama-French monthly rf spread over each month's trading days when `data/raw/rf_monthly.csv` exists; otherwise
  the daily series stored on WRDS, which is rounded to 0.0001 a day (it can only show 0%, 2.52% or 5.04% a year) and makes the
  excess-of-T-bill figures approximate. The printed output names the source used.

## Data conventions
Split-adjusted, not dividend-adjusted, prices; dividends are explicit cash flows. Dates where either name lacks a
close are dropped (log printed by `ingest.py`); nothing is forward-filled; a missing open that an order needs raises an error.
Both names trade through the whole sample after Visa's March 2008 listing, so no delisting handling is needed
here; it would be required for a broader universe.

## Evaluation discipline
- Periods: dev 2009-2017 (design checks), validation 2018-2022 (one look per pre-declared variant), holdout
  2023-2025 (once, guarded by the spec hash). Which period/variant combinations are spent is recorded in the committed
  `evaluations.json`; `run_study.py` refuses to treat any of them as a fresh evaluation.
- Pre-declared variants only: `gate=none` (primary) and `gate=coint`; `fill=open_next` and `close_next`.
- Every run is appended to `EXPERIMENTS.md`. I froze the implementation before its first market-data evaluation
  (file modification times show the code predates the data pull and the first results), while acknowledging that the
  pair and research design were informed by historical knowledge of the two companies and of the market in those
  years. The study is not unbiased: V and MA were chosen with hindsight, and the holdout is a test of the rule, not of
  the author's ignorance. Later diagnostics (open-vs-close attribution, pooled statistics, cash scenarios, accounting
  audit, case studies) were run after all evaluation periods were spent; they are classified in `EXPERIMENTS.md`.
- Bootstrap: circular block bootstrap of the realised daily returns for several block lengths. It conditions on
  the realised path and does not repeat the research process.
- No deflated Sharpe ratio is reported. An earlier version computed one with the number of experiment-log rows as the trial
  count, which mixed documentation and diagnostic rows with strategy trials; no defensible trial count exists for this study,
  so the statistic was removed rather than replaced. Multiple testing is addressed by the log itself and by reporting every
  variant that was run.
- Volatility regimes: cut-offs are expanding quantiles of past market volatility, so labels use only past data.

**Reproductions.** After an engine correction the evaluated periods were re-run into `results_rerun/` with
`python reproduce.py` (which calls `run_study.py --reproduce` for each entry in `evaluations.json`; no private lock file is needed). Reproductions are labelled as such in `EXPERIMENTS.md`, never overwrite the original results, and
the holdout reproduction does not create a new holdout.

## Not implemented (deliberately, until the baseline is trusted)
Multi-pair universes, ticker-level aggregation and exposure caps, random-pair and matched-filter placebos, and
Kalman hedge ratios. When added: overlapping pairs will be separate books with netted execution per ticker and
pro-rata cost allocation; the placebo will match candidate set, pair count, capital and trading rules; Kalman will be
labelled a full alternative strategy unless the hedge model and the signal definition are changed one at a time.

## Claims removed from the earlier scaffold
"Dollar-neutral" (it was not), "roughly two false positives per window" (an unmeasured calculation), "probability the
Sharpe is real", full-sample volatility tercile cut-offs, and synthetic control results presented as proof of no bias.

## Exploratory scenario grid (`scenarios.py`; computed after every period was evaluated)
504 full engine reruns: transaction cost {0, 2.5, 5, 7.5, 10, 15, 20} bps per leg per fill x borrow {0, 30, 100, 300} bps a year x
fill timing {open or close of the session 1, 2 or 3 sessions after the signal close}, for each period. Because each cell reruns
the engine, assumption changes flow through equity, sizing, the loss limit and the drawdown halt. The baseline cells reproduce
the published runs and the declared next-close variant to the cent (the script fails otherwise). The grid is descriptive
sensitivity; no cell was selected and none is a validated optimum. Fill lags above one session use the engine's `fill_lag`
argument, which is not part of the frozen specification (its hash is unchanged).

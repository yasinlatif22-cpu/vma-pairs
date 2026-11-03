# Results (written 2026-11-03; revised after the second review)

Pair: Visa (V) / Mastercard (MA). Data: CRSP daily, 2008-2025 (market index series ends 2024-12-31). Spec hash
26be1bbf6e29 (variants differ only in the declared `gate` / `fill` fields). Figures are net of assumed costs (5 bps
per leg per fill), borrow (30 bps/yr on short value) and derived dividends. Returns are on total equity ($1M) with
**zero interest on cash**, so they are not excess-of-risk-free. The strategy is deployed 26-39% of days.

## Headline
Positive net Sharpe in each period (0.60, 0.47, 0.40), none individually distinguishable from zero. In the
2018-2025 period (validation + holdout) the Sharpe is 0.44, Newey-West t about 1.3. Measured against actual T-bill rates
instead of zero, the 2018-2025 excess Sharpe is -0.33 (see Cash and financing). The result also
depends on the fill convention. This is an exploratory study of one pair, not evidence of a tradable edge.

## Runs (primary = fill at next open)
| period | variant | trades | ann. return | vol | Sharpe | max DD | alpha (t) |
|---|---|---|---|---|---|---|---|
| dev 2009-17 | primary | 58 | 3.58% | 5.98% | 0.60 | -8.4% | 3.6% (1.9) |
| dev | fill next close | 58 | 3.76% | 5.97% | 0.63 | -6.8% | 3.8% (2.0) |
| dev | cointegration gate | 11 | 1.32% | 4.14% | 0.32 | -6.4% | n/a |
| val 2018-22 | primary | 32 | 1.78% | 3.82% | 0.47 | -4.9% | 1.7% (1.1) |
| val | fill next close | 32 | 0.36% | 3.78% | 0.09 | -4.3% | 0.3% (0.2) |
| val | cointegration gate | 10 | 0.42% | 2.17% | 0.19 | -3.4% | 0.4% (0.5) |
| **holdout 2023-25** | **primary (run once)** | **17** | **1.26%** | **3.12%** | **0.40** | **-3.8%** | **1.8% (1.0)** |

## Pooled statistics, from the actual daily series (`diagnostics/pooled_stats.py`)
Each run is an independent evaluation: capital resets to $1M, positions are flat at start and end, and formation
windows can use pre-run history. Stitching concatenates daily returns; it does not describe one continuous account.
| sample | days | ann. return | vol | Sharpe | Newey-West t | 95% block-bootstrap Sharpe (21d) |
|---|---|---|---|---|---|---|
| dev 2009-17 | 2265 | 3.58% | 5.98% | 0.60 | 2.04 | [0.07, 1.11] |
| val 2018-22 | 1259 | 1.78% | 3.82% | 0.47 | 1.07 | [-0.39, 1.31] |
| holdout 2023-25 | 752 | 1.26% | 3.12% | 0.40 | 0.76 | [-0.63, 1.47] |
| **val + holdout 2018-25** | 2011 | 1.58% | 3.57% | 0.44 | 1.31 | [-0.20, 1.10] |
| dev-inclusive 2009-25 | 4276 | 2.64% | 5.00% | 0.53 | 2.42 | [0.13, 0.91] |
The dev-inclusive line contains the period the design was checked on, so it is the least independent. The
earlier hand-pooled "Sharpe about 0.5, t about 2" is replaced by these figures. Magnitudes are lower in the later
samples; with these intervals that is a pattern, not a demonstrated decline.

## Open vs close fills (`diagnostics/attribution.py`)
The open- and close-fill runs have identical trades, dates and exit reasons (signals use closes only), so the whole
difference is the fill price. Per trade, open minus close gross P&L equals the entry-day open-to-close move minus the
exit-day open-to-close move (plus a small quantity term).
| | gross open | gross close | difference | entry-day part | exit-day part | quantity |
|---|---|---|---|---|---|---|
| dev (58 trades) | $444.7k | $467.8k | -$23.1k | +$33.1k | -$54.9k | -$1.3k |
| val (32 trades) | $126.3k | $50.7k | +$75.6k | +$42.7k | +$29.7k | +$3.2k |
In validation the open beat the close in 59% of trades (mean +$2.4k per trade, t about 1.5). Three trades from
March 2020 (signals 03-16, 03-20, 03-25) account for $50.7k of the $75.6k; the other 29 trades add $25.0k (mean
$0.9k, t 0.6). In dev the sign is reversed. So there is no systematic open-vs-close advantage; the validation gap is
a few trades during the March 2020 volatility spike. An opening-auction fill of full size in that period is the
least realistic part of the assumption. I did not add or change any timing rule.

## Cash and financing
The engine books no interest on cash and none on short proceeds. Zero interest is a modelling choice, not an
automatically conservative one: against a positive risk-free rate it understates the return on idle cash, but it
also means the reported return is not an excess return. Total-equity Sharpe stays the principal measure; utilisation
is reported separately (in-trade days: dev 35%, val 26%, holdout 39%; mean long market value about 13-19% of equity,
short about 13-21%).
Actual risk-free series: Fama-French daily rf from WRDS (`ff.factors_daily`, pulled by `extract_aux.py`). Mean annual
rf: about 0.0% in 2009-17, 1.4% in 2018-22, 5.0% in 2023-25. Excess-of-rf Sharpe of the as-run returns (cash earns 0):
dev 0.60, val 0.10, holdout -1.21, val+holdout -0.33, dev-inclusive 0.27.
Scenarios on validation + holdout ("excess" subtracts the same rf, because crediting interest raises raw Sharpe
mechanically):
| scenario | ann. return | excess-of-rf return | excess Sharpe |
|---|---|---|---|
| S0 as run (cash earns 0) | 1.58% | -1.17% | -0.33 |
| S1 idle cash (equity - long value) earns rf | 3.87% | +1.11% | 0.31 |
| S2 short proceeds also earn rf (optimistic) | 4.39% | +1.64% | 0.46 |
Reading: the strategy beats T-bills only if idle cash, and optionally short proceeds, earn interest. That is a
financing assumption about a real prime-broker account, not a result of the strategy. In the 2023-25 holdout, when
rf was about 5%, the as-run return (1.26%) was far below cash.

## Accounting audit
Five trades (long/short, short/long, split-spanning, dividend-paying, window-end exit) were recomputed independently
from raw CRSP fields and match the ledger to the cent; trade P&L reconciles to equity in every run. This checks the
arithmetic, not the CRSP data itself. See `ACCOUNTING_AUDIT.md`.

## What the evidence supports
- The mechanics are sound and internally consistent (above); net exposure averaged -0.03x to -0.06x when in a trade;
  estimated market beta is near zero (holdout beta uses 2023-2024 only).
- Small positive average returns in each period, none significant alone.

## What it does not support
- Statistical significance in any single period, or an edge over T-bills without a financing assumption.
- Robustness to the opening-auction assumption (see above).
- Cost headroom: costs are 16% (dev), 27% (val), 29% (holdout) of gross profit; cost breakevens are rough scalings.
- That cointegration gating adds value: it only reduced trading.
- That the model can tell information from noise: the case studies show winners and losers following
  company-specific news (`CASE_STUDIES.md`).

Losing target exits exist: 3 of 41 (dev), 1 of 21 (val), 3 of 11 (holdout) target exits had negative net P&L, because
exits use the rolling z-score, whose mean moves with the price, not a return on the entry spread.

## Payoff shape (validation, 32 trades)
Target exits: 21, +$221k (avg +$10.5k). z-stop: 4, -$90k (avg -$22.4k). Max-hold: 4, -$39k. Window-end: 3, -$3k.
Many small wins and a few larger losses.

## Earnings (exploratory; run as pre-registered in `PREREG_EARNINGS.md`)
Report dates: Compustat `rdq`, V (77 dates) and MA (78); one missing date excluded. Window: report day and the next
trading day, for either company. Half of all trades (50 of 107) touch an earnings window.
| trades | n | mean net P&L | median | win rate | z-stop share |
|---|---|---|---|---|---|
| no earnings day | 57 | +$7.6k | +$7.3k | 79% | 2% |
| any earnings day | 50 | +$1.0k | +$5.2k | 58% | 8% |
Difference in mean (exposed minus not) -$6.6k, bootstrap 95% interval [-$14.7k, +$1.1k], which includes zero.
By period the gap is -$8.2k (dev, 27 vs 31 trades) and -$7.6k (val, 16 vs 16), but +$0.5k in the holdout (7 vs 10).
In-trade days: earnings-exposed days average -$956 (n=98, sd $9.1k) vs +$469 (n=1,319, sd $6.0k) on other days, a gap
of roughly 1.5 standard errors. Conclusion: the direction is consistent in dev and validation and absent in the
holdout, and the interval includes zero; this is a suggestive pattern in a small sample, not a finding. No earnings
rule was added. "Avoid trades spanning earnings" is recorded as a new hypothesis that needs data after 2025-12-31 or
paper trading.

## Limitations
One pair and few trades; hindsight in choosing V and MA (see `THESIS.md`); no market impact or opening-auction
model; assumed borrow and cost rates; market series ends 2024-12-31; holdout run once and now spent, so further
changes would be tested on data already looked at.

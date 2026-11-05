# Results (reproductions with the corrected engine; financing and earnings sections revised 2026-11-04)

Pair: Visa (V) / Mastercard (MA). Data: CRSP daily (CIZ `dsf_v2`), 2008-2025; see `PROVENANCE.md`. Spec hash 26be1bbf6e29
(variants change only the declared `gate` / `fill` fields). Figures are net of assumed costs (5 bps per leg per fill),
borrow (30 bps/yr on short value) and dividends inferred from CRSP returns. Returns are on total equity ($1M) with cash
earning nothing, so they are not excess of any risk-free rate. The strategy is in a trade on 26-39% of days.
Every number can be regenerated locally with `make_public_results.py`, `diagnostics/*.py` and `scenarios.py`; the interactive app (`build_site.py`) shows the same values.
All runs here are **reproductions** after an engine correction (`CORRECTIONS.md`); the holdout was evaluated once, earlier,
and this re-run does not make it fresh.

## Headline
Positive net Sharpe in each period (0.60, 0.47, 0.40). None is individually distinguishable from zero except
development, which is the period the design was checked on. For 2018-2025 (validation plus holdout) the Sharpe is 0.44
with a Newey-West t of about 1.3. Against T-bill rates the as-run return is below cash in the validation and holdout
periods; it exceeds cash only under explicit financing assumptions. The validation result depends on the fill
assumption, and three March 2020 trades carry most of that dependence. This is an exploratory single-pair study, not
evidence of a persistent edge.

## Runs
| period | variant | trades | mean ann. return | vol | Sharpe | max DD | gross P&L $ | costs $ | net P&L $ |
|---|---|---|---|---|---|---|---|---|---|
| dev | primary (fill at next open) | 58 | 3.58% | 5.98% | 0.60 | -8.4% | 444,735 | 73,494 | 357,560 |
| dev | fill at next close | 58 | 3.76% | 5.97% | 0.63 | -6.8% | 467,826 | 73,583 | 380,399 |
| dev | cointegration gate | 11 | 1.32% | 4.14% | 0.32 | -6.4% | 129,870 | 11,612 | 117,591 |
| val | primary (fill at next open) | 32 | 1.78% | 3.82% | 0.47 | -4.9% | 126,341 | 33,760 | 88,874 |
| val | fill at next close | 32 | 0.36% | 3.78% | 0.09 | -4.3% | 50,707 | 32,732 | 14,433 |
| val | cointegration gate | 10 | 0.42% | 2.17% | 0.19 | -3.4% | 30,079 | 10,150 | 20,096 |
| holdout | primary (run once; re-run here is a reproduction) | 17 | 1.26% | 3.12% | 0.40 | -3.8% | 59,763 | 17,516 | 36,754 |

Costs are 16% (dev), 27% (val) and 29% (holdout) of gross profit. Holdout detail: win rate 59%; exits 11 target, 3 max-hold,
3 window-end; market beta -0.02 (t -1.8, 2023-2024 only because the CRSP index series ends 2024-12-31).

## Combined statistics from the actual daily series
Each run is an independent evaluation: capital resets to $1M, positions start and end flat, risk-control state (drawdown
peak, halts, loss locks) restarts, and each window's 252-day formation can use pre-run data. Stitching concatenates daily
returns; it is not one continuous account.

| sample | days | mean ann. return | vol | Sharpe | Newey-West t | 95% block-bootstrap Sharpe (21d) |
|---|---|---|---|---|---|---|
| dev 2009-17 | 2265 | 3.58% | 5.98% | 0.60 | 2.04 | [0.07, 1.11] |
| val 2018-22 | 1259 | 1.78% | 3.82% | 0.47 | 1.07 | [-0.39, 1.31] |
| holdout 2023-25 | 752 | 1.26% | 3.12% | 0.40 | 0.76 | [-0.63, 1.47] |
| val + holdout 2018-25 | 2011 | 1.58% | 3.57% | 0.44 | 1.31 | [-0.20, 1.10] |
| dev-inclusive 2009-25 | 4276 | 2.64% | 5.00% | 0.53 | 2.42 | [0.13, 0.91] |

The dev-inclusive line contains the period used to check the design, so it is the least independent. Point estimates are
lower in later samples, but the intervals overlap heavily; that does not establish a change in any underlying edge.
Utilisation is reported separately from returns: in-trade days 35% / 26% / 39% (dev / val / holdout); while in a trade
gross exposure is 1.02-1.03x equity (long about 0.49x, short about 0.52-0.55x). Sharpe is computed on total-equity daily
returns, never on invested days only.

## Execution sensitivity: open vs close fills
Signals use closes, so the two runs hold identical trades, dates and exit reasons; the entire gross difference is fill
price. Per trade it decomposes exactly (no residual) into the entry-day open-to-close move, the exit-day open-to-close
move and a small sizing term (`diagnostics/attribution.py`, components asserted to sum to the difference).

| | gross, open fill | gross, close fill | open minus close | entry-day part | exit-day part | sizing |
|---|---|---|---|---|---|---|
| dev (58 trades) | $444.7k | $467.8k | -$23.1k | +$33.1k | -$53.6k | -$2.5k |
| val (32 trades) | $126.3k | $50.7k | +$75.6k | +$42.7k | +$29.7k | +$3.2k |

In validation the open fill was better in 59% of trades (mean +$2.4k, t about 1.5). Three March 2020 trades (signals
2020-03-16, -20, -25) contribute $50.7k of the $75.6k; the other 29 trades contribute $25.0k (mean $0.9k, t 0.6). In
development the sign is reversed (-$23.1k). This sample does not establish a persistent opening-fill advantage, and
filling a full-size order at the opening print during the March 2020 volatility spike is the least realistic assumption
in the study. No timing rule was changed.

## Concentration (descriptive sensitivity, not alternative strategies)
| period | trades | net P&L | largest winner / top-3 winners, share of gross wins | net excl. top-3 winners | mean trade P&L, 95% CI |
|---|---|---|---|---|---|
| dev | 58 | $357.6k | 16% / 32% | $125.7k (n=55) | $6.2k [-$0.2k, $13.2k] |
| val | 32 | $88.9k | 9% / 26% | $29.6k (n=29) | $2.8k [-$2.0k, $7.2k] |
| holdout | 17 | $36.8k | 25% / 53% | **-$10.5k (n=14)** | $2.2k [-$2.5k, $6.9k] |
| all | 107 | $483.2k | 11% / 22% | $251.4k (n=104) | $4.5k [$0.6k, $8.6k] |
Holdout profit disappears without its three best trades. Excluding the largest by absolute size, or the largest losers,
is in the diagnostics output produced by `make_public_results.py`. The "all" interval includes the development period.

## Cash, financing and a feasible benchmark
Total-equity return (cash earning nothing) is the principal measure. CAGR (compound) is 3.46% / 1.72% / 1.22% by period against
mean annual returns of 3.58% / 1.78% / 1.26%. Financing is a separate, fixed-holdings account (`METHODOLOGY.md`): holdings are
exactly as run, interest accrues to cash and never resizes positions, and every daily return uses the same denominator.

**Provisional risk-free rate.** The figures below use the Fama-French daily rf as stored on WRDS, which is rounded to 0.0001 a day
(0%, 2.52% or 5.04% a year). It shows 0% for 2009-2017 and 2021, and 5.04% for 2025, when bill yields actually fell. Re-running
`extract_aux.py` adds the monthly series, and every script then switches to it automatically and says so. Expect the 2009-2017 excess
returns to fall a little and the 2025 excess returns to rise.

| period | trading P&L $ | borrow $ (inside trading) | S1 interest $ | S2 rebate $ | T-bills on $1M $ | CAGR S0 / S1 / S2 / T-bills | excess-of-rf Sharpe S0 / S1 / S2 |
|---|---|---|---|---|---|---|---|
| dev | 357,560 | 6,425 | 0 | 0 | 0 | 3.46% / 3.46% / 3.46% / 0.00% | 0.60 / 0.60 / 0.60 |
| val | 88,874 | 2,076 | 58,224 | 7,870 | 71,754 | 1.72% / 2.78% / 2.93% / 1.40% | 0.10 / 0.39 / 0.43 |
| holdout | 36,754 | 1,985 | 117,658 | 29,392 | 162,282 | 1.22% / 4.93% / 5.88% / 5.17% | -1.21 / -0.06 / 0.25 |
| val + holdout | | | | | | | -0.33 / 0.24 / 0.37 (mean ann. excess -1.17% / +0.83% / +1.25%) |

S0: as run. S1: rf on free cash after funding longs and posting 50% margin on the short (Regulation T). S2: S1 plus a rebate of rf
minus 50 bps on short proceeds (illustrative; actual rebates depend on the lender and the name, and proceeds are not freely
investable cash). No debit balance arose. Interest income does not establish or refute trading skill. As run, the strategy does
not beat T-bills in 2018-2025; with free-cash interest it roughly matches them (S1 excess Sharpe 0.24, not distinguishable from
zero), and whether it beats them depends on financing terms I cannot observe.

## Accounting verification
Six complete trades were reconstructed with separate code from raw CRSP fields and match the ledger to the cent: long-V/
short-MA, short-V/long-MA, one spanning MA's 2014 split, the largest-dividend trade, a window-boundary exit and the
end-of-data liquidation (`ACCOUNTING_AUDIT.md`). Trade-level net P&L reconciles to portfolio equity in every run (the run
fails otherwise). This is internal arithmetic verification; source-data verification status is in `ACCOUNTING_AUDIT.md`.

## Earnings (post-hoc, exploratory; `PREREG_EARNINGS.md`, revised)
Compustat report dates (155; one missing excluded), 136 distinct release sessions. A trade is exposed if it is held across the
overnight gap in which a release is priced; release times are not in the data, so three assumptions are shown. Outcomes are net
P&L as a share of entry equity.

| timing assumption | exposed n | mean | not exposed n | mean | difference, 95% bootstrap interval |
|---|---|---|---|---|---|
| every release before the open | 34 | +0.26% | 73 | +0.49% | -0.24% [-0.98%, +0.48%] |
| every release after the close | 35 | +0.27% | 72 | +0.49% | -0.22% [-0.96%, +0.51%] |
| either (primary) | 36 | +0.30% | 71 | +0.48% | -0.18% [-0.89%, +0.53%] |

By period (either): dev -0.34% (22 vs 36), val -0.24% (11 vs 21), holdout +0.50% (3 vs 14). Longer trades span more releases
(exposure 22% / 36% / 44% for short / medium / long holds), and within holding-length groups the sign is mixed. Position days
that include a release gap (n=95, all exit days included) averaged -0.064% of equity against +0.036% on other position days (n=1,428),
with higher dispersion (sd 0.87% vs 0.50%). The earlier version reported a larger trade-level difference (-$6.6k, interval
[-$14.7k, +$1.1k]); most of it came from misclassified boundary trades and dropped exit days (`CORRECTIONS.md`). There is no
reliable earnings pattern in this sample. No rule was added; "avoid report dates" stays an untested hypothesis.

## Exploratory scenario grid (computed after all evaluations; `scenarios.py`)
504 engine reruns over cost, borrow and fill timing. Total-equity Sharpe at 30 bps borrow:

| sample | fill t+1 open (spec), cost 0 / 5 / 10 / 20 bps | at 5 bps: t+1 close / t+2 open / t+2 close / t+3 open / t+3 close |
|---|---|---|
| dev | 0.71 / 0.60 / 0.49 / 0.27 | 0.63 / 0.54 / 0.33 / 0.31 / 0.18 |
| val | 0.63 / 0.47 / 0.30 / -0.04 | 0.09 / -0.02 / -0.13 / 0.02 / 0.03 |
| holdout | 0.58 / 0.40 / 0.22 / -0.15 | 0.01 / 0.12 / 0.00 / -0.05 / 0.11 |
| val + holdout | 0.61 / 0.44 / 0.27 / -0.07 | 0.07 / 0.03 / -0.09 / -0.00 / 0.05 |

Borrow matters little (val + holdout Sharpe 0.46 / 0.44 / 0.41 / 0.32 at 0 / 30 / 100 / 300 bps). In 2018-2025 every fill timing
other than the next open leaves a Sharpe near zero; in 2009-2017 the result survived later fills. The holdout close-fill cells are
new information about a spent period, not a test. The grid shows how much the result depends on assumptions; it does not select one.

## What the evidence does and does not support
- Supports: the engine's accounting is internally consistent and independently re-derivable; net market exposure is small
  (beta near zero); small positive average returns in each period, none significant on its own after the design period.
- Does not support: a persistent edge; beating T-bills without a financing assumption; robustness to the opening-auction
  assumption or to any later fill in 2018-2025; an earnings effect; that cointegration gating adds value (it only reduced trading); that the model separates information from noise.
- Losing target exits exist (3 of 41 dev, 1 of 21 val, 3 of 11 holdout) because exits use a rolling z-score whose mean moves.
- Payoff shape, validation: target exits 21 trades +$221k; z-stop 4 trades -$90k; max-hold 4 trades -$39k; window-end 3 trades -$3k.

## Limitations
One pair and few trades; hindsight in choosing V and MA (`THESIS.md`); no market impact or opening-auction model; assumed costs
and borrow; CRSP index series ends 2024-12-31; the holdout was run once and is spent, as is every other 2009-2025 year.

# Corrections after the third review (2026-11-03)

The first set of results is preserved: the original run directories are kept locally (git-ignored, because they hold
CRSP-derived trade prices) and the originally reported figures remain in the repository's earlier commit. Corrections
below were found by inspecting the engine after all periods had been evaluated. Re-running an unchanged calculation to
verify it is not a new strategy test, and re-running the spent holdout does not make it fresh: every re-run is logged in
`EXPERIMENTS.md` as a reproduction.

| # | Issue | Verified? | Fix | Numerical effect |
|---|---|---|---|---|
| 1 | Overnight borrow was charged at the final close for a night that does not exist, before the end-of-data liquidation | Confirmed (`nights = 1` on the last row) | no borrow after the final close | Only runs holding a position at the final date are affected: dev primary and dev close-fill (one trade each, 2017-12-27 signal). Net P&L +$6.06 and +$6.15; Sharpe unchanged to 4 decimals; largest daily-return change 4e-6. The other five runs are identical to the cent |
| 2 | After end-of-data liquidation the final row kept the pre-liquidation holdings, exposures and `in_trade` | Confirmed | final row is flat: holdings, exposures, `in_trade` = 0, equity = cash | Final-row exposure statistics only (in-trade day count 1,319 -> 1,318 in the earnings diagnostic; mean P&L of non-earnings in-trade days 468.7 -> 469.2). Equity series unchanged apart from item 1 |
| 3 | Window-end wording ("flat at window end") vs execution | Confirmed as a documentation gap, not a code bug | convention documented and tested: the exit order issued at the window's last close fills at the first session of the next window | None (no strategy change) |
| 4 | `hold_days` counted calendar days while max-hold counts sessions | Confirmed | columns `hold_sessions` and `hold_calendar_days`; case studies say which | None |
| 5 | A missing fill price skipped the order silently | Confirmed in code; no missing opens exist in this data | the engine raises `ValueError` | None on these data |
| 6 | Drawdown-halt path was untested (never activated historically) | Confirmed | deterministic test of activation, liquidation, waiting period, peak reset, resumption | None |
| 7 | Reconciliation printed a number but could not fail | Confirmed | `reconcile` raises `ReconciliationError` beyond $0.01 | None (all runs reconcile to ~1e-9) |
| 8 | Attribution used a residual-style quantity term and treated the end-of-data exit as an open fill | Confirmed | components computed separately from recorded fill prices and asserted to sum to the difference | Dev: exit-day part -$54,875 -> -$53,627; quantity term -$1,278 -> -$2,526; total -$23,091 unchanged. Validation unchanged ($75,634) |
| 9 | Financing scenarios assumed all short proceeds earn the risk-free rate; "idle cash" ignored short collateral | Confirmed (a modelling choice I had presented too favourably) | S1: rf on cash not needed for longs or 100% short collateral; S2: adds a rebate of rf minus 50 bps on short value (illustrative) | Val+holdout excess-of-T-bill return: S1 +1.11% -> +0.67% (Sharpe 0.31 -> 0.19); S2 +1.64% -> +1.13% (0.46 -> 0.32). Trading results unchanged |
| 10 | README stated that no real-data evaluation had been performed (contradicting the log and results) | **Confirmed.** The pushed README (commit 2b86276) still carried the pre-evaluation status paragraph; my earlier edit to the status text had silently not applied and I had not re-checked the file | README rewritten with findings first; every text replacement in this round is asserted to match | None |

My earlier README claim (status paragraph updated) was wrong for the committed file; the review was right on this item.
I checked the other earlier text edits in the committed copies (METHODOLOGY cash and evaluation wording, README layout
table): those had applied. Every text replacement in this round is asserted to match.

Evidence regenerated: all seven runs re-executed into `results_rerun/` with the corrected engine; trade keys (signal,
entry and exit dates, exit reasons) are identical to the original runs in every case.

# Fourth review (2026-11-04)

An external review of commit 2326767 ran the tests and the synthetic workflow but could not run the licensed data. Every item was
reproduced against the code before changing it. Original results stay in `EXPERIMENTS.md` and Git history.

| # | Issue | Verified? | Fix | Numerical effect |
|---|---|---|---|---|
| 1 | A fresh clone could not reproduce the holdout: it required `results/HOLDOUT_USED`, which is git-ignored. `ingest.py` assumed `data/processed/` existed; the reproduction loop was shell-specific; `--gate`/`--fill` accepted any value | Confirmed (an unknown `--gate` silently behaved as `none`) | committed `evaluations.json` records spent periods; `--reproduce` checks it and labels outputs; `reproduce.py` runs all seven; argparse choices; `ingest.py` creates folders; workflow tests run in a clean directory | None. All seven reproductions identical to the cent |
| 2 | Synthetic generator did not construct a cointegrated pair; `beta` was unused (beta 0.5 and 2.0 gave identical data) | Confirmed (`y_in + beta * 0`) | `log V = alpha + beta log MA + AR(1) spread`, consistent opens and distributions, non-cointegrated control, exact-construction tests | Synthetic outputs only |
| 3 | No-lookahead ledger test sliced the perturbed future away before the engine; `reconcile()` returned NaN without raising; no input validation | Confirmed. The old test still passed with three planted one-session peeks (next close in marking, next open in fills, next distribution) | full-input test at several in-position cut points catches all three; `reconcile()` rejects non-finite values; `validate_inputs()` checks index alignment of prices, distributions and signals, positivity and finiteness | None |
| 4 | `perf([-0.10, 0.0])` reported zero drawdown (initial capital not in the peak); mean return labelled as annual return | Confirmed | `metrics.drawdown()` includes the initial capital; CAGR reported beside mean annual return; README figure uses the same function | No published drawdown changed (dev -8.36%, val -4.91%, holdout -3.77%): no run's worst drawdown began at its start. CAGR 3.46% / 1.72% / 1.22% vs mean 3.58% / 1.78% / 1.26% |
| 5 | Financing mixed interest divided by a fixed $1M with trading returns on changing equity | Confirmed | one account per run with fixed holdings and a single daily denominator; collateral, restricted proceeds, margin and debit documented | val+holdout excess-of-rf: S0 -1.17% / Sharpe -0.33 (unchanged); S1 +0.67% / 0.19 before, +0.58% / 0.17 with the same 100% margin, +0.83% / 0.24 with Regulation T 50% margin (now used); S2 +1.13% / 0.32 before, +1.01% / 0.29 at 100%, +1.25% / 0.37 at 50% |
| 6 | Earnings diagnostic dropped exit-day P&L (`in_trade` is 0 on the exit day) and misclassified boundary trades | Confirmed: 107 exit days with -$41.6k of P&L were dropped. The reviewer's -$50k single-day example was not found in these outputs (largest exit day -$29.8k) | exposure over actual holding intervals by overnight release gap, three timing assumptions, outcomes as % of entry equity, holding-length groups | before: exposed 50 vs 57 trades, mean difference -$6.6k [-$14.7k, +$1.1k]; after: 36 vs 71, -0.18% of entry equity [-0.89%, +0.53%]. The suggestive earnings pattern was largely a classification artefact |
| 7 | Compustat filtered by `rdq <= signal date` is not point-in-time; same-day releases may follow the close | Confirmed | relabelled as a historical reconstruction from current data; strict `rdq <` signal date; case 1 checked against the original releases | No case used a same-day report. Case 1: reported trailing P/E ratio V/MA 0.76; on company-adjusted EPS from the filings 29.5 vs 32.9 (ratio 0.90) |
| 8 | Case attribution used an unweighted V-minus-MA percentage gap; Mastercard's low 2017 EPS was unexplained | Confirmed | leg-level dollar attribution for every trade (`diagnostics/trade_legs.py`, reconciles to the cent) with past-only betas; Q4 2017 resolved from Mastercard's 8-K ($873M Tax Act charge, $0.82 a share; $0.10 Venezuela charge; adjusted EPS $1.14) | Case 1 loss -$32.3k: MA leg price -$26.3k, V leg -$5.0k, estimated market +$1.5k. The earlier text, which emphasised Visa's call, misdescribed where the loss came from |
| 9 | Deflated Sharpe counted every experiment-log row (including documentation rows) as a trial | Confirmed (synthetic run printed DSR vs 25 rows) | removed from run output and code | Earlier DSR printouts should be disregarded |
| 10 | Stale provenance, assistant-directed wording, "cointegration hedge" where cointegration is not established | Confirmed | docs rewritten; OLS log-price hedge throughout; provenance regenerated | None |

**Found during this review, not raised by it.**
- The Fama-French daily rf stored on WRDS is rounded to 0.0001 a day, so it reads 0% for 2009-2017 and 2021 and 5.04% for 2025.
  `extract_aux.py` now pulls the monthly series, which the scripts prefer. Excess-of-T-bill figures are provisional until it is run.
- WRDS terms require a citation in publications; it was missing and is now in the README and the app.
- `docs/img/pair_deviation.png` (normalised V and MA prices) was removed from the README pending permission; it remains in history.
- `make_dashboard.py` and `make_figures.py` were superseded by the research app (`build_site.py`) and removed.
- Execution sensitivity was extended with an exploratory engine-rerun grid (`scenarios.py`): in 2018-2025 every fill timing other
  than the next open leaves a Sharpe near zero.

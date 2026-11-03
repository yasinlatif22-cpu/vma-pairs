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

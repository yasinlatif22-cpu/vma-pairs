# Review of the first scaffold: findings and outcome

| # | Finding | Verdict | What was found / done |
|---|---|---|---|
| 1 | Not dollar-neutral | **Confirmed** | Weights were 1/(1+b) vs b/(1+b); b=2 gives 33% long, 67% short, and constant weights imply daily rebalancing nobody paid for. v2 sizes by the hedge ratio on purpose, holds share counts, reports exposures. |
| 2 | Fills at the signal close | **Confirmed** | A one-day shift still earns close-to-close from the same close. v2 fills at next open (or next close, declared). |
| 3 | Stop logic | **Confirmed, plus a second bug** | z=[5,5,5,5] returned [-1,0,0,0] (entry beyond stop). Also max-hold was off by one (held 3 bars at max_hold=2). Fixed and tested; stop is now a signal stop, with a separate loss limit. |
| 4 | Accounting | **Confirmed** | Daily target-weight returns, approximate Kalman turnover. Replaced with a share/cash ledger and per-trade records that reconcile. |
| 5 | Overlapping pairs | **Confirmed, deferred** | The old selector reused names (PYPL, FIS in many pairs). Moot for one pair; the design is stated for the later universe. |
| 6 | Placebo not controlled | **Confirmed** | Random path skipped the correlation/half-life filters and the cointegration path averaged ~1.5 pairs vs 5 random, so capital deployed differed. Not carried into v2; matched placebo is deferred with the universe. |
| 7 | OLS vs Kalman confound | **Confirmed** | Different hedge model and different signal. Deferred; will be labelled as complete strategy variants. |
| 8 | Inference | **Confirmed, one nuance** | DSR trial count, wording, full-sample regime cut-offs fixed. On "~2 false picks per window": the README line was an unmeasured 45 x 0.05 calculation and is removed. For the record the null-simulation control selected ~1.45 pairs per window under all filters, so the number was not wildly off, but it was not calibrated either. |
| 9 | WRDS | **Confirmed** | Extraction script and ingestion added. I cannot reach WRDS from the workspace; the script is untested against a live connection, which is why `--check` exists. |
| 10 | Sector thesis | **Accepted** | `docs/THESIS.md`; case studies list only decision-time facts and leave the narrative for the user. |
| 11 | Validation | **Confirmed, with an admission** | The old control runs were not a proof, and after the first control read +0.10 I ran more seeds until it looked reassuring: that is the seed-search the review warns about. v2 uses deterministic unit tests, and each was mutation-checked (see below). |

## Test verification actually performed
29 tests pass (20 at this review, 9 added in the third review: see `CORRECTIONS.md`). Six deliberate bugs were planted one at a time to check the suite catches them: same-close fill,
no dividends, borrow on gross, no stop check at entry, off-by-one holding limit, and a hedge fit that sees the trade
window. The first run missed the look-ahead mutation (weak test); the test was strengthened and then caught it.

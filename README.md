# V/MA Pairs Trading: A Walk-Forward Study

**Question.** Does the log-price spread between Visa and Mastercard mean-revert tradably, after realistic
execution, costs and borrow, out of sample?

**Status.** The engine, signals and tests are complete. Real-data results have not been produced yet: no evaluation
period has been run on CRSP data. Nothing in this repository is a performance claim.

## Design in one paragraph
Each 63-trading-day window fits a hedge ratio on the prior 252 days, then trades the spread using a 60-day
z-score: enter at |z| in [2, 4), exit at |z| <= 0.5, signal stop at |z| >= 4, time stop at 3x the formation
half-life, flat at window end. Signals use the close; fills happen at the next open (or next close as a
declared variant). Positions are fixed share counts, so there is no daily rebalancing. Risk limits: a 5% per-trade
loss limit and a 20% drawdown halt, both fixed in advance. Costs, borrow and dividends are booked in a share ledger;
trade P&L reconciles to portfolio P&L.

Position sizing is the **cointegration hedge** (notional of MA = beta x notional of V). It is not dollar-neutral
unless beta = 1 and is not market-beta-neutral. Daily gross, net and estimated market exposure are reported.

## Layout
| file | purpose |
|---|---|
| `config.py` | the frozen specification and its hash |
| `signals.py` | per-window hedge fit and the signal state machine |
| `engine.py` | share/cash ledger, fills, costs, borrow, dividends, risk limits |
| `metrics.py` | performance, market regression, bootstrap, deflated Sharpe, exposure |
| `data_io.py`, `ingest.py`, `extract_wrds.py` | data conversion and WRDS extraction |
| `run_study.py` | runs `dev`, `val`, `holdout` (once) or `synthetic` |
| `case_studies.py`, `diagnostics/` | decision-time facts; open-vs-close attribution, pooled stats, trade audit, earnings diagnostic |
| `extract_aux.py` | WRDS pull of the risk-free rate and Compustat report dates |
| `tests/` | 20 automated tests |
| `docs/` | methodology, data steps, thesis, review log |

## Run
```bash
pip install -r requirements.txt
python -m pytest                       # all tests
python run_study.py --period synthetic # engine demo on simulated data (not evidence)
```
Real data: follow `docs/DATA.md`, then `python run_study.py --period dev`, `--period val`, and finally
`--period holdout --confirm <spec hash>` once.

## Limitations
One pair, so one effectively independent bet at a time and few trades; results will be noisy. Costs and borrow are
assumptions (see `docs/METHODOLOGY.md`). V and MA are survivors chosen with hindsight about industry quality. No
market impact, intraday path or borrow-availability model. Open prices depend on what CRSP supplies.

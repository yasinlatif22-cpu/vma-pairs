# Conclusion (completed version; numbers from `RESULTS.md`)

**1. What was tested.** A walk-forward pairs rule on one pair, Visa and Mastercard (CRSP daily, 2008-2025), with fixed
parameters: 252-session OLS log-price hedge ratio (cointegration not established), 60-day z-score, enter at 2 to 4 sigma, exit at 0.5, stop at 4, time stop at three
half-lives (5 to 63 sessions). Signals at a close, fills at the next open (primary) or next close. Costs, borrow and
dividends are modelled. Periods: development 2009-17, validation 2018-22, holdout 2023-25 (spent). Variants were declared before
runs: a cointegration gate and next-close fills. No parameters were tuned to results.

**2. What was observed.** Total-equity Sharpe 0.60, 0.47 and 0.40 by period; 0.44 for 2018-2025 (Newey-West t about 1.3,
bootstrap interval [-0.20, 1.10]). The strategy is in a trade on 26-39% of days and makes about six trades a year, so
samples are small. Market beta is near zero. Against T-bills, the as-run 2018-2025 return is below cash (excess Sharpe
-0.33); with interest on free cash it roughly matches cash (S1 +0.24) and beats it only under favourable rebate terms
(S2 +0.37), all on a provisional risk-free series. The validation gain from open fills (+$75.6k gross) comes largely from three
March 2020 trades, and the sign is reversed in development. Exploratory engine reruns show that in 2018-2025 any fill later than
the next open leaves a Sharpe near zero. Holdout profit is negative without its three best trades. Once exposure is measured over
actual holding intervals, there is no reliable earnings pattern (post hoc).

**3. What remains uncertain.** Whether any edge exists: the intervals include zero outside the design period. Whether
open-auction fills at full size were achievable in March 2020. Actual borrow, rebate and cash terms. Whether the selection of V
and MA was influenced by hindsight (it was chosen as an obvious pair, which is a form of selection). Whether CRSP
opens are the official auction prints (consistency checks pass; that meaning is unverified) and whether dividends match
company disclosures (checked only against CRSP's own distribution table; see `ACCOUNTING_AUDIT.md`). Valuation in the case
studies is a reconstruction from current Compustat data, verified against filings only for the deepened case; reported P/E is
distorted for Mastercard by a 2017 tax charge (company-adjusted figures narrow Visa's apparent discount from 0.76 to 0.90 of
Mastercard's multiple).

**4. What evidence would justify allocating capital.** Forward, pre-registered evaluation on data after 2025-12-31 (or live
paper trading with timestamped fills) over enough trades for an interval that excludes cash-plus-costs, on realistic financing
and borrow quotes; fills measured at the venue rather than assumed; and a written economic reason for each position that is
checked against what happened. A different pair or a broader universe would need its own untouched data. Nothing here meets
that bar.

**5. Temporary divergence versus fundamental mispricing.** The model sees only price. In the three cases studied, the large
moves coincided with company-specific information (two earnings reports, a Justice Department report) that the spread rule
treats as noise. In the worst validation trade the rule bought the slower-growing company into both companies' reports, and the
loss came from the short leg rallying on its own results; adjusted for one-off charges, the cheaper-looking stock was only modestly
cheaper, so there was no valuation case for convergence. Trades did best where the dislocation was a one-day shock and worst where information kept arriving
(report dates inside the holding window; a drift with no sourced catalyst). An analyst's added value would be the filter: a
stated reason why this move is not new information, and an observable event that would prove it wrong. That filter is a
hypothesis, not a result of this study.

**Future hypotheses (untested; need data not yet examined).** Skip entries and holds across report dates; require a
written fundamental reason before entry; measure real opening-auction fills; test other pairs with their own formation
periods.

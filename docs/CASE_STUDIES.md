# Case studies (three trades chosen by rule before reading any news)

Rule, fixed before looking: the largest validation winner, the largest validation loser, and the worst holdout
trade, all by net P&L in the primary (open-fill) run. The holdout trade is described after the holdout was spent,
so it is a post-evaluation description, not a test. Facts below carry their source; anything else is labelled.
Price moves are computed from the local CRSP file (open-to-open over the holding period; daily close-to-close).

## 1. Largest validation loser: long V / short MA, signal 2019-01-28, net -$32.3k (z-stop)
**At the signal date.** Both names fell on 2019-01-28 (V -1.9%, MA -1.4%) and V lagged, so the spread was stretched
enough to trigger a long-V / short-MA entry at the next open (2019-01-29).
**Economic reason to expect convergence (hypothesis, not evidence).** Two networks with similar business models and
the same end demand; relative performance has historically mean-reverted over weeks.
**What differed.** Visa reported fiscal Q1 2019 on 2019-01-30: net revenue $5.5B (+13%), EPS $1.30, outlook
reaffirmed ([Visa 8-K](https://www.sec.gov/Archives/edgar/data/1403161/000140316119000002/fy19q1pressrelease.htm)).
Reported EPS beat the $1.25 forecast, but shares reversed on the call when the CFO described slowing growth in the
U.S., U.K. and Brazil ([Motley Fool](https://www.fool.com/investing/2019/01/31/visa-earnings-a-strong-quarter-but-there-could-be.aspx)).
Mastercard's Q4 2018 report: EPS $1.55 vs $1.53 consensus, revenue $3.81B in line, stock up about 3% on Thursday
2019-01-31 ([InvestorPlace](https://investorplace.com/2019/01/mastercard-earnings-boost-ma-stock/)).
**Later information.** On 2019-01-31 V fell 1.9% and MA rose 3.5% (spread -5.4 points in one day), which hit the
z-stop; the exit filled at the 2019-02-01 open. V then rebounded 3.8% vs MA 1.3% on 2019-02-01, after the exit.
Open-to-open over the trade: V -0.9%, MA +5.9%.
**Attribution.** Market: small (the day's market return was +0.9%, offset by the long/short structure). Fundamentals:
V's cautious commentary is a plausible partial cause of its underperformance, but MA's in-line quarter does not
obviously explain a +3.5% day; the available evidence does not explain the full size of the move. Valuation: not
analysed. Unexplained: most of the 5.4-point day.
**Invalidating evidence.** A company-specific growth warning arriving after entry (here, V's regional slowdown
commentary) is exactly what a stat-arb thesis cannot see in advance. The stop worked as designed, but it also
exited just before a partial rebound.

## 2. Largest validation winner: long V / short MA, signal 2021-03-19, net +$20.8k (target)
**At the signal date.** On 2021-03-19 V fell 6.2% and MA 2.9%. The Wall Street Journal reported that the Justice
Department was examining whether Visa's debit practices lead to unlawful market dominance
([XTB summary of the report](https://www.xtb.com/int/market-analysis/news-and-research/us-justice-department-probing-visa-over-debit-card-practices)).
The model treated the V-specific drop as a spread deviation and bought V against MA.
**Later information.** The Justice Department sued Visa over debit practices on 2024-09-24
([PYMNTS](https://pymnts.com/?p=2105079)). So the signal day coincided with news that later became a real legal
risk for V, and the trade made money anyway: open-to-open V +5.8%, MA +3.1% over 14 days (both names rose in the
reopening trade of that spring; the spread effect is the difference).
**Attribution.** Market/sector: both legs up, the long/short structure removes most of it. Fundamentals: no earnings
in the window (Visa reported 2021-04-27, after the exit). Why V recovered faster is not established here; one
hypothesis, untested, is that the probe was seen as a long-dated risk without near-term earnings impact.
**Lesson.** A win on a news-driven dislocation is not evidence the signal separates noise from information. The
same rule would have lost money had the market priced the probe permanently.

## 3. Worst holdout trade: short V / long MA, signal 2024-11-06, net -$17.0k (max-hold)
**At the signal date.** 2024-11-06 was a market-wide rally day (+2.6%); V rose 4.8% and MA 3.1%, so V outperformed by
1.7 points and the model shorted V against MA at the 2024-11-07 open.
**Context known at the time.** The Justice Department debit-monopolization suit against Visa was already public
(filed 2024-09-24, source above).
**Outcome.** The position was held to its max-hold limit (57 days) and exited at the 2025-01-03 open: V +2.2%,
MA -0.3% open-to-open, so the short-V leg lost; the dividend paid on the short leg cost $1.2k.
**Attribution.** Market: small. Fundamentals: no report date in the window that I verified (earnings dates are not
loaded yet; see `PREREG_EARNINGS.md`). The largest daily spread moves in the window were +1.3% (2024-11-13), +1.2%
(2025-01-06, after exit) and -1.1% (2024-11-22); I did not find a sourced explanation for them. The available evidence
does not explain this move.
**Invalidating evidence.** Here the stop logic did not trigger: the spread drifted rather than jumped, which is the
failure mode a time stop only caps.

## What the three cases show
Winners and losers both followed company-specific news that the model cannot read. The strategy is a statistical
bet on mean reversion; it has no view on which dislocations are information. A fundamental analyst's value-add
would be that filter, which is a hypothesis for future work, not something this study tested.

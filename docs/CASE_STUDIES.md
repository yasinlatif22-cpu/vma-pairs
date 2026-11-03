# Case studies (three trades chosen by rule before reading any news)

Rule, fixed before looking: the largest validation winner, the largest validation loser and the worst holdout trade, by net
P&L in the primary (open-fill) run. The holdout trade is described after the holdout was spent, so it is a description, not a
test. Facts carry a source. **Decision-time facts** are separated from **later information**. Durations are labelled sessions
(trading days) or calendar days. Price figures come from the local CRSP file; "market" is the CRSP value-weighted index
(series ends 2024-12-31). Report dates are Compustat `rdq`, matching the sources cited.
Relative valuation at entry (trailing P/E, growth, margin, point-in-time) is produced by `diagnostics/case_valuation.py` from
Compustat fields that `extract_aux.py` now pulls; **it has not been run yet** (pending your WRDS pull), so no valuation
numbers are quoted below.

## 1. Largest validation loser, deepened: long V / short MA, signal 2019-01-28, net -$32.3k (z-stop)

**Decision-time facts (known at the 2019-01-28 close; entry filled at the 2019-01-29 open).**
- Model state: hedge ratio 0.78, formation half-life 11.2 sessions, Engle-Granger p = 0.19 (no cointegration evidence at 5%),
  maximum hold 34 sessions. On 2019-01-28 V fell 1.9% and MA 1.4%, leaving V cheap relative to the 60-day spread mean.
- Both companies reported inside the holding window: Visa fiscal Q1 on 2019-01-30, Mastercard Q4 on 2019-01-31 (Compustat
  report dates). I did not verify that those dates were publicly announced by 2019-01-28; companies normally pre-announce them.
- Relative valuation and the two businesses' operating differences at that date: pending (see header). I will not infer them.

**Why convergence was plausible, and where the thesis was weak.** Plausible: both are card networks selling the same service into
the same consumer and merchant demand, so a relative move of several points over days usually needs a company-specific cause.
Weak: the entry sat directly in front of both companies' earnings releases, the one setting where company-specific
information arrives; and the cointegration evidence for the fitted hedge was absent (p = 0.19). A defensible fundamental
thesis would have had to say why V, not MA, was mispriced into those reports. The statistical signal alone did not.

**Later information (not known at decision time).**
- Visa released fiscal Q1 2019 on 2019-01-30: net revenue $5.5B (+13%), EPS $1.30, outlook reaffirmed
  ([Visa 8-K](https://www.sec.gov/Archives/edgar/data/1403161/000140316119000002/fy19q1pressrelease.htm)). EPS beat the
  $1.25 forecast but shares reversed on the call when the CFO described slowing growth in the U.S., U.K. and Brazil
  ([Motley Fool](https://www.fool.com/investing/2019/01/31/visa-earnings-a-strong-quarter-but-there-could-be.aspx)).
- Mastercard's Q4 2018: EPS $1.55 vs $1.53 consensus, revenue $3.81B in line, stock up about 3% on Thursday 2019-01-31
  ([InvestorPlace](https://investorplace.com/2019/01/mastercard-earnings-boost-ma-stock/)).
- 2019-01-31: V -1.9%, MA +3.5% (spread -5.4 points in a day), which breached the stop; the exit filled at the 2019-02-01
  open. On 2019-02-01 V rose 3.8% vs MA 1.3%, after the exit. Open-to-open over the trade (held 3 sessions,
  3 calendar days): V -0.9%, MA +5.9%.

**Attribution (quantified where I can).** Close of 2019-01-28 to close of 2019-01-31: V -0.7%, MA +5.5%, market +2.2%. The
long/short structure offsets market moves, so the loss is the relative move: about 6.2 points between the legs, not market
direction. How much of that gap was fundamental: Visa's guidance-style commentary is a plausible partial cause of V
lagging, but Mastercard's in-line quarter does not by itself explain a +3.5% day; the available evidence does not
explain the full size of the move, and I do not assign it. Valuation effect: not assessed (pending).

**A specific invalidating condition (observable).** If, before the planned exit, a company-specific growth warning or
guidance change for either name is published (as Visa's CFO commentary on 2019-01-30 was), or a report-day move takes the
spread beyond the 4-sigma stop, the "same demand, so revert" thesis no longer holds and the position should be exited. Here the
stop did that mechanically; a fundamental analyst would have flagged the earnings window at entry. The model has no such
condition, and none was added to the strategy.

## 2. Largest validation winner: long V / short MA, signal 2021-03-19, net +$20.8k (target)
**Decision-time facts.** Hedge ratio 0.76, half-life 6.3 sessions, Engle-Granger p = 0.20, max hold 19 sessions. On 2021-03-19
V fell 6.2% and MA 2.9%. The Wall Street Journal reported that the Justice Department was examining whether Visa's debit
practices amount to unlawful market dominance
([XTB summary of the report](https://www.xtb.com/int/market-analysis/news-and-research/us-justice-department-probing-visa-over-debit-card-practices)).
The model read the V-specific drop as a spread deviation and bought V against MA. No earnings dates fall in the window
(Visa reported 2021-04-27, Mastercard 2021-04-29, both after the 2021-04-05 exit; Compustat).
**Later information.** The Justice Department sued Visa over debit practices on 2024-09-24
([PYMNTS](https://pymnts.com/?p=2105079)). Over 9 sessions (14 calendar days) open-to-open V rose 5.8% and MA 3.1%.
**Attribution.** Close of 2021-03-19 to the exit-signal close of 2021-04-01: V +4.8%, MA +1.9%, market +1.9%, so the 2.9-point
relative gain is the P&L driver. Why V recovered faster is not established here; one untested hypothesis is that the probe
was read as a long-dated risk with no near-term earnings effect.
**Lesson.** A win on a news-driven dislocation does not show the model separates noise from information; the signal day coincided
with news that became a real legal case three years later. The same rule would have lost had the market priced the probe in.

## 3. Worst holdout trade: short V / long MA, signal 2024-11-06, net -$17.0k (max-hold)
**Decision-time facts.** Hedge ratio 0.71, half-life 12.7 sessions, Engle-Granger p = 0.26, max hold 38 sessions. 2024-11-06 was a
market-wide rally (+2.6%); V rose 4.8% and MA 3.1%, so V outperformed by 1.7 points and the model shorted V at the 2024-11-07
open. The Justice Department's debit suit against Visa (filed 2024-09-24, source above) was already public. Neither company
reported inside the window: Visa and Mastercard reported on 2024-10-29 and 2024-10-31 (before entry) and next on 2025-01-30
(after the 2025-01-03 exit; Compustat).
**Outcome.** The position was held for its full 38-session limit (57 calendar days) and exited at the 2025-01-03 open: V +2.2%,
MA -0.3% open-to-open, so the short-V leg lost; the dividend on the short leg cost $1.2k.
**Attribution.** Close of 2024-11-06 to close of 2024-12-31 (the index series ends there): market about -0.9% to the later date; the
V-minus-MA gap through 2025-01-02 was +2.0 points. The largest daily spread moves in the window were +1.3% (2024-11-13) and -1.1%
(2024-11-22); I found no sourced explanation for them. The available evidence does not explain this move. This is a drift, not
a jump: the failure mode a time stop only caps.

## What the three cases show
Winners and losers both followed company-specific news the model cannot read. The strategy is a statistical bet on mean
reversion with no view on which dislocations are information. The analyst's contribution would be the filter, a future
hypothesis that this study did not test.

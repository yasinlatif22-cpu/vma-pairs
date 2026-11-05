# Pre-registration: earnings-window diagnostic (exploratory, descriptive)

Written 2026-11-03 before any earnings dates were loaded or analysed. This is a descriptive look at results that are
already known. It is exploratory and post-hoc in motivation (the case studies suggested it). It adds no rule to the
strategy. Any strategy change suggested by it is recorded in `EXPERIMENTS.md` as a new hypothesis needing fresh data.

**Date source.** Compustat quarterly report dates (`comp.fundq.rdq`) for V and MA, pulled by `extract_aux.py`.
Rows with missing `rdq` are listed and excluded from the event set. Report timing (before open / after close) is not
in this source, so the window is conservative and covers both.

**Event window.** For each report date r, trading days r and r+1 are "earnings days" (covers a pre-open release,
whose reaction is on r, and an after-close release, whose reaction is on r+1). A trading day is "earnings-exposed" if
it is an earnings day for either V or MA.

**Unit 1: trades.** A trade is "exposed" if any day from entry fill date to exit fill date (inclusive) is
earnings-exposed. Compare exposed and unexposed trades, separately for dev, validation and holdout and for all
three: count, mean and median net P&L, win rate, share of z-stop exits, sum of P&L. Report the difference in mean
trade P&L with a trade-resampling bootstrap 95% interval (10,000 draws).

**Unit 2: days.** Among in-trade days, compare mean and standard deviation of daily P&L ($) on earnings-exposed
vs other days; report the number of days in each group, and the number of distinct trades they come from.

**Denominators.** Every cell shows n. Exposure rates are computed over all trades and all in-trade days of the
primary (open-fill) run. Small cells (n < 10) are reported but not interpreted.

**Not done.** No threshold search, no alternative window lengths, no earnings-skip rule backtest. A finding that
earnings days carry the losses would be a hypothesis ("skip entries/holds across report dates") to be tested only
on data after 2025-12-31 or by paper trading.

## Revision after the fourth review (2026-11-04)
The definition above has two errors, found after it was run. (1) Daily analysis filtered on `in_trade`, which is 0 on the exit
day, so the exit day's P&L (the gap into the exit fill) was dropped: 107 exit days, -$41.6k in total. (2) Counting the calendar
days r and r+1 anywhere between the entry and exit dates misclassified boundary trades (for example a trade exited at the open
of r is not exposed to a release after the close of r; a trade entered at the open of r is not exposed to a release before
that open). `diagnostics/earnings_analysis.py` now defines exposure as holding a position across the overnight gap in which a
release is priced, under three labelled timing assumptions, compares outcomes as a share of entry equity, and shows the
comparison within holding-length groups. The original numbers are kept in `CORRECTIONS.md`. The analysis remains post hoc and
exploratory, and no earnings rule was added to the strategy.

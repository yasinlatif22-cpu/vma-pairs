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

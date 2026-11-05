# Data and publication permissions

**Status: unresolved.** Nothing here is legal advice. Publication of anything derived from licensed data should be confirmed with
Princeton's library or data services, which hold the WRDS and vendor subscription agreements.

## What the terms say (checked 2026-11-04)
WRDS Terms of Use (wrds-www.wharton.upenn.edu/users/tou/):
- "Except as provided under the terms of the Subscription Agreement ... you may not reproduce, distribute, modify, adapt, create
  derivative works of ..." the content "without our advance written consent", and "the terms of the Subscription Agreement shall govern."
- "The WRDS services are for academic and non-commercial research purposes only."
- Users must place this citation in all publications or communications prepared using WRDS: "Wharton Research Data Services
  (WRDS) was used in preparing [identify research piece]. This service and the data available thereon constitute valuable
  intellectual property and trade secrets of WRDS and/or its third-party suppliers." The README now carries it.
The Terms of Use do not say how much aggregated or transformed output may be published; that depends on the subscription
agreements (CRSP for prices, S&P for Compustat), which are not public. A survey of journal data-availability terms lists WRDS
data as not distributable (social-science-data-editors.github.io/reference/TermsOfUse.html).

## What each build and file contains
| item | where | derived from | status |
|---|---|---|---|
| raw and processed CRSP, Compustat, Fama-French files | `data/` (git-ignored) | licensed data | never published |
| per-run outputs (daily equity, trades with prices and share counts) | `results*/` (git-ignored) | licensed data | never published |
| local app (`build/local/`) | git-ignored | prices, spread, fills, holdings | private; do not share |
| public app, aggregate tier (`build/public/`, default) | not deployed | period statistics, scenario aggregates, attribution totals; sourced case narratives; synthetic replay | **permission unresolved** (aggregate research results; commonly published in academic work) |
| public app, derived tier (`build/public-derived/`) | not deployed | adds daily strategy equity, trade outcomes (dates, direction, exit reason, P&L) and case valuation multiples | **permission unresolved; higher risk than aggregate** |
| README figures (`docs/img/`): equity vs T-bills, execution sensitivity, trade P&L | committed, public | strategy equity and trade P&L | **permission unresolved** (same class as the derived tier) |
| documentation tables (`docs/RESULTS.md` etc.) | committed, public | aggregate statistics | **permission unresolved** (aggregate) |
| case-study facts from company filings and news | committed, public | public sources | publishable with citation |

**Removed from the current tree:** `docs/img/pair_deviation.png`, which showed V and MA prices rebased to 100. Normalised prices
are a transformation of the licensed series, not an aggregate. It remains in Git history (commit 2326767 and earlier pushes);
removing it from history would require rewriting and force-pushing, which has not been done.

## Safeguards
- `check_public_build.py` runs on every public build and fails if the bundle contains price, spread, fill or holding fields,
  any number equal to a CRSP open or close to the cent (outside the labelled synthetic section and named non-price fields),
  file-system paths, credential-like strings or AI-tool names.
- The public bundle is assembled from an allow-list in `site_export.py`, never by deleting fields from the local bundle.
- The synthetic replay uses simulated prices and session numbers instead of dates, and is labelled SYNTHETIC wherever it appears.

## Questions to put to the library
1. May aggregate performance statistics computed from CRSP (Sharpe, returns, drawdowns by period) be published in a public
   GitHub repository and website?
2. May a daily strategy equity curve and a per-trade outcome list (no prices or share counts) be published?
3. May small charts of normalised prices for two stocks be published?
4. Is the WRDS citation sufficient attribution, or do CRSP and S&P require their own notices?

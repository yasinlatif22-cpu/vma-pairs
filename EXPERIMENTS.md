# Experiment log (append-only)

Every run of `run_study.py` adds a row. Design changes made after seeing results must be added as a row
with the reason, and the affected period stops counting as untouched.

| date | period | spec hash | variant | headline | note |
|---|---|---|---|---|---|
| 2026-11-03 | spec change | 26be1bbf6e29 | holdout end 2026-10-31 -> 2025-12-31 | no real-data run yet | CRSP coverage ends 2025-12-31; changed before any evaluation |
| 2026-11-03 | dev | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.60, 58 trades | |
| 2026-11-03 | dev | a8e20fc3bc42 | gate=coint, fill=open_next | Sharpe 0.32, 11 trades | |
| 2026-11-03 | dev | 14657db813e2 | gate=none, fill=close_next | Sharpe 0.63, 58 trades | |
| 2026-11-03 | val | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.47, 32 trades | |
| 2026-11-03 | val | a8e20fc3bc42 | gate=coint, fill=open_next | Sharpe 0.19, 10 trades | |
| 2026-11-03 | val | 14657db813e2 | gate=none, fill=close_next | Sharpe 0.09, 32 trades | |
| 2026-11-03 | holdout | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.40, 17 trades | |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | diagnostic: open-vs-close attribution | no strategy change | descriptive diagnostic, run after all periods were evaluated. Val gap is $75.6k, $50.7k from 3 March-2020 trades |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | implementation verification: independent re-computation of 5 trades | no discrepancy | no rerun needed; checks arithmetic and splits, not CRSP itself |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | reporting clarification: pooled stats from daily series; cash scenarios | replaces hand-pooled Sharpe/t and "conservative" cash wording | no strategy change; stitched runs are independent resets |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | descriptive: case studies (rule fixed before reading news) | exploratory | holdout case described after the holdout was spent |
| 2026-11-03 | pre-registration | 26be1bbf6e29 | earnings-window diagnostic spec written | not yet run | needs data/raw/earnings.csv; exploratory |
| 2026-11-03 | new hypothesis (untested) | n/a | skip entries/holds across earnings dates | none | would need data after 2025-12-31 or paper trading; not added to the strategy |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | reporting: actual rf series (ff.factors_daily) replaces flat-rate scenarios | val+holdout excess Sharpe -0.33 as run | no strategy change |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | descriptive: earnings-window diagnostic run per PREREG_EARNINGS.md | exposed minus unexposed mean trade P&L -$6.6k, 95% CI [-14.7k, +1.1k] | exploratory; no rule added; skip-earnings stays an untested hypothesis |
| 2026-11-03 | reproduction (after engine correction) | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.60, 58 trades | re-run of dev in results_rerun/dev_none_open_next; not a fresh evaluation |
| 2026-11-03 | reproduction (after engine correction) | a8e20fc3bc42 | gate=coint, fill=open_next | Sharpe 0.32, 11 trades | re-run of dev in results_rerun/dev_coint_open_next; not a fresh evaluation |
| 2026-11-03 | reproduction (after engine correction) | 14657db813e2 | gate=none, fill=close_next | Sharpe 0.63, 58 trades | re-run of dev in results_rerun/dev_none_close_next; not a fresh evaluation |
| 2026-11-03 | reproduction (after engine correction) | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.47, 32 trades | re-run of val in results_rerun/val_none_open_next; not a fresh evaluation |
| 2026-11-03 | reproduction (after engine correction) | a8e20fc3bc42 | gate=coint, fill=open_next | Sharpe 0.19, 10 trades | re-run of val in results_rerun/val_coint_open_next; not a fresh evaluation |
| 2026-11-03 | reproduction (after engine correction) | 14657db813e2 | gate=none, fill=close_next | Sharpe 0.09, 32 trades | re-run of val in results_rerun/val_none_close_next; not a fresh evaluation |
| 2026-11-03 | reproduction (after engine correction) | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.40, 17 trades | re-run of holdout in results_rerun/holdout_none_open_next; not a fresh evaluation |
| 2026-11-03 | post-evaluation correction | 26be1bbf6e29 | engine: no borrow charge on the final night, final row flattened, missing price raises, reconciliation fails over $0.01 | see CORRECTIONS.md | applied after all periods were evaluated; effect: dev primary and close-fill net P&L +$6.06 and +$6.15 (final-night borrow removed); other runs identical; trade keys unchanged |
| 2026-11-03 | post-evaluation | 26be1bbf6e29 | diagnostics: concentration, financing scenarios, source-data checks, case valuation | descriptive | no strategy change; reproductions above are not fresh holdouts |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.60, 58 trades | re-run of dev in results_check/dev_none_open_next; not a fresh evaluation |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | a8e20fc3bc42 | gate=coint, fill=open_next | Sharpe 0.32, 11 trades | re-run of dev in results_check/dev_coint_open_next; not a fresh evaluation |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | 14657db813e2 | gate=none, fill=close_next | Sharpe 0.63, 58 trades | re-run of dev in results_check/dev_none_close_next; not a fresh evaluation |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.47, 32 trades | re-run of val in results_check/val_none_open_next; not a fresh evaluation |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | a8e20fc3bc42 | gate=coint, fill=open_next | Sharpe 0.19, 10 trades | re-run of val in results_check/val_coint_open_next; not a fresh evaluation |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | 14657db813e2 | gate=none, fill=close_next | Sharpe 0.09, 32 trades | re-run of val in results_check/val_none_close_next; not a fresh evaluation |
| 2026-11-05 | reproduction (check after input-validation changes; identical to the cent) | 26be1bbf6e29 | gate=none, fill=open_next | Sharpe 0.40, 17 trades | re-run of holdout in results_check/holdout_none_open_next; not a fresh evaluation |
| 2026-11-04 | post-evaluation correction | 26be1bbf6e29 | input validation, finite reconciliation, evaluation manifest, drawdown baseline | reproductions identical to the cent; no published figure changed | see CORRECTIONS.md, fourth review |
| 2026-11-04 | post-evaluation correction | 26be1bbf6e29 | financing as a fixed-holdings account; 50% short margin | val+holdout excess Sharpe S1 0.19 -> 0.24, S2 0.32 -> 0.37 (S0 -0.33 unchanged); provisional rf | reporting only; no strategy change |
| 2026-11-04 | post-evaluation correction | 26be1bbf6e29 | earnings exposure over holding intervals | difference -$6.6k -> -0.18% of entry equity [-0.89%, +0.53%] | exploratory; no rule added |
| 2026-11-04 | post-evaluation | 26be1bbf6e29 | exploratory scenario grid: 504 engine reruns over cost, borrow and fill timing | 2018-25 Sharpe 0.44 at t+1 open, about 0 at later fills | descriptive; nothing selected; holdout cells are not a test |
| 2026-11-04 | post-evaluation | 26be1bbf6e29 | leg-level dollar attribution; case 1 valuation verified against filings | case 1 loss mostly the MA short | descriptive |

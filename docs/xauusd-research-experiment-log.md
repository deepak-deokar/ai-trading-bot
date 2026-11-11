# XAUUSD research experiment log

February–April 2024 (49 approved source days / 13,524 bars) is DEVELOPMENT /
IN-SAMPLE data, used repeatedly for design, attribution and signal analysis.
It must not be represented as unseen validation. No future holdout performance
was inspected in G2C4D2. Entries below document existing work, not new experiments.

| Experiment ID | Hypothesis | Single change | Dataset | Result | Status |
| --- | --- | --- | --- | --- | --- |
| V1 / G2C4C3C–G2C4C4 | Frozen trend/short momentum agreement may provide directional information | Baseline; corrected market-fill validation, then separately recorded account sensitivity | Approved February–April 2024 DEVELOPMENT | Corrected baseline has negative expectancy; preserved reports contain full outcomes | Frozen; not independently validated |
| G2C4D1 / V2 | 3-bar and 12-bar momentum sign agreement may reduce noisy directional entries | Add momentum_12 > 0 for BUY / < 0 for SELL; retain all V1 conditions | Same DEVELOPMENT data | 287 fewer signals; modest in-sample metric improvements, expectancy still negative | Frozen single-change experiment; no tuning |
| G2C4D2 | Describe signal directional information independently of trade management | Analysis only: fixed 5/10/20-bar executable markouts of existing V1/V2 and removed signals | Same DEVELOPMENT data | Both aggregate means/medians negative at every horizon; removed signals weaker overall, with BUY-specific exceptions | Completed descriptive study; not a new strategy |

References: `xauusd-first-backtest-corrected.md`,
`xauusd-3000-sensitivity-corrected.md`,
`xauusd-v2-momentum-confirmation-development.md`, and
`xauusd-forward-signal-quality.md`.

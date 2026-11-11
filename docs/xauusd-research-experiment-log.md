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

## G2C4D3 — matched random entry benchmark

Hypothesis (fixed before examining random results): the existing trend/momentum
signals should produce better forward directional markouts than random entries
matched on source month × existing signal-time research session × direction.
No parameter change. Same February–April 2024 DEVELOPMENT / IN-SAMPLE dataset;
exact D2 5/10/20-bar semantics; 1,000 trials per strategy/horizon, deterministic
SHA-256 seed namespace `xauusd-g2c4d3-matched-random-v1`. This is a descriptive
signal benchmark, not a new strategy or portfolio backtest.

All data after April 30, 2024 remains reserved from strategy-performance analysis
until a future candidate strategy is frozen. Dates refer to source-day labels:
the already-approved fixed UTC−05:00 April 30 source day includes its existing
UTC tail through May 1 05:00. No additional May or later dataset was inspected.

D3 result/status: completed. D2 actuals reproduced exactly. Neither V1 nor V2
beats its matched-random mean markout overall at 5/10/20 bars. V2's aggregate
relative deficit narrows, with modestly above-random SELL means but below-random
BUY means. These are dependent in-sample descriptive observations, not formal
significance or a production edge. No parameter changes or new strategy version.
See `xauusd-random-entry-benchmark.md` and its JSON for fixed methodology/results.

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

## G2C4D4 — contrarian / inverted signal diagnostic

Hypothesis fixed before results: failed continuation signals may identify short-term
directional exhaustion rather than continuation. Analysis only: original BUY →
hypothetical SELL; original SELL → hypothetical BUY, at unchanged timestamps.
No parameter change. Use February–April 2024 DEVELOPMENT data, D2's fixed 5/10/20
horizons and source BID/ASK semantics, plus D3's matching method with inverted
direction strata. No new strategy, execution, trade management or holdout analysis.
A positive descriptive finding would require a separately frozen future candidate;
it is not automatic strategy approval or validation.

D4 result/status: completed. Inverted V1/V2 means and medians remain negative after
spread at all three horizons. Both outperform matched random in aggregate; the
consistent relative effect is concentrated in original BUY → hypothetical SELL.
Original SELL → BUY is modestly above random for V1, below random for V2. No
positive executable tendency, validated strategy or universal reversal effect is
claimed. Source-side inversion and 1,000-trial deterministic repeats verified.
See `xauusd-contrarian-signal-diagnostic.md` and JSON. No further experiment begun.

## G2C4E1 — frozen pullback-resumption hypothesis

Before screening: a broader trend combined with a short-term momentum pullback
and resumption may provide a better-timed continuation entry than entering during
already-positive/negative short-term momentum. New family
`xauusd-pullback-resumption-v1`; February–April 2024 development data only.
Exactly the requested EMA12/26, momentum12 direction, momentum3 sign crossing and
spread filters; no RSI, optimization, account backtest or holdout inspection.
Only 5/10/20-bar markouts and 1,000 matched controls per horizon.

E1 result: 547 BUY and 479 SELL signals. ALL mean-markout percentiles versus
matched random: 69.7 / 91.8 / 26.6 at 5/10/20 bars. BUY carries the favorable
relative pattern (87.1 / 98.9 / 85.2); SELL underperforms (35.1 / 30 / 2.7).
ALL means remain negative. This is mixed in-sample screening evidence, not a
consistent two-sided advantage or profitability result. No rules changed and no
follow-on candidate or simulator run was started. See the pullback-resumption
signal-study Markdown/JSON. Full-repeat content hashes are identical.

# XAUUSD G2C4G2 — market-state characterization

Analysis/taxonomy only. No strategies, signals, trade P&L, forward markouts or
profitability comparisons were evaluated or imported. February–April is DEVELOPMENT;
May–July was not accessed and August–October remains locked/unprocessed.

## Frozen taxonomy

`xauusd-market-state-taxonomy-v1` describes exactly three dimensions from the
unchanged `xauusd-market-state-features-v1`. Volatility and efficiency form nine
core states; range is a separate attribute. The frozen config is
`config/xauusd_market_state_taxonomy_v1.yaml`. The runner refuses to overwrite a
config with different contents. The typed runtime model is immutable.

Quantiles use sorted finite Decimal samples and nearest rank:
`sorted[ceil(n*p)-1]`, with p exactly 0.333333 and 0.666667. No interpolation,
optimized tolerance or outcome-conditioned selection. All calculations use a fixed
50-digit Decimal context. Values <= lower threshold enter the low bucket; values
> lower and <= upper enter the middle bucket; values > upper enter the high bucket.
Ties may make bucket counts unequal. If both thresholds coincide, equality enters
the lower bucket and the middle bucket can be empty.

Volatility (`mid_change_std_36`, 9,996 valid rows):

- LOW/NORMAL: `0.70772125992621078662459452035253405481804084608722`
- NORMAL/HIGH: `1.1983084785966187971510743249379515934834203015313`

Efficiency (`mid_efficiency_12`, 12,348 valid rows):

- CHOPPY/MIXED: `0.15451438336656223298205639418968954713756764454571`
- MIXED/DIRECTIONAL: `0.34332645184453819226281303294138766717529844717709`

Each dimension is calibrated on all its valid development rows, not only the
jointly classified subset. Classification requires all three inputs; any missing
input produces UNCLASSIFIED_WARMUP, with no value filling.

The primary range attribute is explicitly **BID** `bid_range_ratio_12_36`; ASK is
not mixed into it. Reference 1 is exact: <1 COMPRESSED, =1 NEUTRAL, >1 EXPANDED.
Because G1 uses nested windows, the 12-bar range cannot exceed the 36-bar range.
Therefore EXPANDED is mathematically unreachable for valid G1 observations. The
comparison helper supports >1 explicitly, but that branch is not evidence of a
reachable market state. Zero/zero uses G1's existing zero convention and is COMPRESSED.
NEUTRAL means equality of nested ranges, not flat prices or low volatility.

## Coverage and core frequencies

49 approved source days, 13,524 bars; 9,996 classified and 3,528 warmup rows.
G1 has 98 continuous segments; the first 36 bars of each lack 36-change variability.
All 49 regenerated G1 dataset hashes and source bar hashes match the frozen G1
report. Two independent data loads/generations/classifications yield identical
reports. Existing G1 formulas, reports, baselines and stored bars remain unchanged.

Percentages below use classified rows in the relevant group. JSON also includes
percentages of all rows and unclassified counts. Days count distinct approved
source dates. Labels do not imply execution permissions or profitable conditions.

| Core state | Bars | % classified | Days | February % | March % | April % | April−February pp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 1126 | 11.26 | 37 | 21.51 | 13.04 | 0.68 | -20.83 |
| LOW_VOL_MIXED | 1121 | 11.21 | 37 | 22.21 | 12.29 | 0.54 | -21.67 |
| LOW_VOL_DIRECTIONAL | 1085 | 10.85 | 36 | 24.17 | 9.18 | 0.41 | -23.76 |
| NORMAL_VOL_CHOPPY | 1188 | 11.88 | 48 | 9.19 | 13.89 | 12.61 | +3.42 |
| NORMAL_VOL_MIXED | 1094 | 10.94 | 48 | 6.83 | 13.59 | 12.39 | +5.56 |
| NORMAL_VOL_DIRECTIONAL | 1051 | 10.51 | 48 | 6.68 | 12.29 | 12.45 | +5.77 |
| HIGH_VOL_CHOPPY | 982 | 9.82 | 39 | 2.54 | 7.29 | 18.41 | +15.87 |
| HIGH_VOL_MIXED | 1069 | 10.69 | 38 | 3.06 | 8.01 | 19.72 | +16.65 |
| HIGH_VOL_DIRECTIONAL | 1280 | 12.81 | 37 | 3.80 | 10.42 | 22.79 | +19.00 |

Monthly classified/unclassified counts: 2024-02: 3264/1152, 2024-03: 3060/1080, 2024-04: 3672/1296.

2024-02: LOW_VOL 67.89%, HIGH_VOL 9.41%. 2024-03: LOW_VOL 34.51%, HIGH_VOL 25.72%. 2024-04: LOW_VOL 1.63%, HIGH_VOL 60.92%. These mix differences are descriptive percentage-point shifts, not formal
significance tests. Thresholds remain the same in every month.

## Research-session distribution

Session labels use the existing UTC configuration at feature availability/bar close.
This timing convention can move a boundary bar relative to an opening-time label.
The same fixed config is hashed in the JSON. Counts and percentages by core state
are retained in JSON; the compact table shows percentages of classified session rows.

| Session | Classified | Warmup | LOW_VOL_CHOPPY | LOW_VOL_MIXED | LOW_VOL_DIRECTIONAL | NORMAL_VOL_CHOPPY | NORMAL_VOL_MIXED | NORMAL_VOL_DIRECTIONAL | HIGH_VOL_CHOPPY | HIGH_VOL_MIXED | HIGH_VOL_DIRECTIONAL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ASIA | 1896 | 2808 | 20.62 | 18.57 | 17.41 | 10.65 | 9.28 | 9.07 | 4.22 | 4.22 | 5.96 |
| LONDON | 2891 | 49 | 11.80 | 14.29 | 15.39 | 13.04 | 14.08 | 12.76 | 4.60 | 5.29 | 8.75 |
| LONDON_NEW_YORK_OVERLAP | 1764 | 0 | 4.42 | 3.63 | 4.20 | 11.62 | 10.32 | 11.28 | 17.29 | 18.65 | 18.59 |
| NEW_YORK | 2940 | 0 | 7.82 | 7.35 | 5.78 | 12.07 | 9.49 | 8.33 | 14.90 | 16.43 | 17.82 |
| OFF_SESSION | 505 | 671 | 17.03 | 15.05 | 13.07 | 9.70 | 9.90 | 13.07 | 5.15 | 4.75 | 12.28 |

Session differences include the effects of coverage, warmup and observed volatility. They provide no recommendation to trade or avoid any session.

## Range attribute within each core state

| State | COMPRESSED % | NEUTRAL % | EXPANDED % |
| --- | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 98.22 | 1.78 | 0.00 |
| LOW_VOL_MIXED | 97.59 | 2.41 | 0.00 |
| LOW_VOL_DIRECTIONAL | 96.68 | 3.32 | 0.00 |
| NORMAL_VOL_CHOPPY | 96.97 | 3.03 | 0.00 |
| NORMAL_VOL_MIXED | 95.89 | 4.11 | 0.00 |
| NORMAL_VOL_DIRECTIONAL | 94.10 | 5.90 | 0.00 |
| HIGH_VOL_CHOPPY | 96.64 | 3.36 | 0.00 |
| HIGH_VOL_MIXED | 95.51 | 4.49 | 0.00 |
| HIGH_VOL_DIRECTIONAL | 93.67 | 6.33 | 0.00 |

Exact equality occurs on 388 classified bars (3.88%); it is not merely a floating-point artifact. There are zero EXPANDED observations.

## Persistence

Runs count adjacent same-state classified bars only. Warmups, reset markers,
non-five-minute spacing, dataset changes and fixed UTC−05:00 source-day boundaries
break runs. No jump is made to a later classified row. Minutes are bars × 5;
these are approximate coverage durations, not forecasts. P95 uses nearest rank.

| State | Runs | Min bars | Median | Mean | P95 | Max | Mean / max minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 439 | 1.00 | 2.00 | 2.56 | 6.00 | 17.00 | 12.82 / 85.00 |
| LOW_VOL_MIXED | 611 | 1.00 | 1.00 | 1.83 | 4.00 | 9.00 | 9.17 / 45.00 |
| LOW_VOL_DIRECTIONAL | 324 | 1.00 | 2.00 | 3.35 | 11.00 | 24.00 | 16.74 / 120.00 |
| NORMAL_VOL_CHOPPY | 438 | 1.00 | 2.00 | 2.71 | 8.00 | 15.00 | 13.56 / 75.00 |
| NORMAL_VOL_MIXED | 608 | 1.00 | 1.00 | 1.80 | 4.00 | 8.00 | 9.00 / 40.00 |
| NORMAL_VOL_DIRECTIONAL | 307 | 1.00 | 2.00 | 3.42 | 11.00 | 23.00 | 17.12 / 115.00 |
| HIGH_VOL_CHOPPY | 400 | 1.00 | 2.00 | 2.46 | 6.00 | 10.00 | 12.28 / 50.00 |
| HIGH_VOL_MIXED | 582 | 1.00 | 1.00 | 1.84 | 4.00 | 11.00 | 9.18 / 55.00 |
| HIGH_VOL_DIRECTIONAL | 333 | 1.00 | 2.00 | 3.84 | 12.00 | 33.00 | 19.22 / 165.00 |

## Transitions

Rows are current states, columns next adjacent classified states in the order shown.
Self-transitions are included. Each probability row is normalized by its observed
outgoing transitions; zero-outgoing rows use zeros, not a fabricated probability.
Only same-segment five-minute neighbors count. No end-of-day wrap or gap jump.

| Current → next | LOW_VOL_CHOPPY | LOW_VOL_MIXED | LOW_VOL_DIRECTIONAL | NORMAL_VOL_CHOPPY | NORMAL_VOL_MIXED | NORMAL_VOL_DIRECTIONAL | HIGH_VOL_CHOPPY | HIGH_VOL_MIXED | HIGH_VOL_DIRECTIONAL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 687 | 337 | 61 | 8 | 9 | 2 | 0 | 0 | 1 |
| LOW_VOL_MIXED | 355 | 510 | 216 | 7 | 7 | 7 | 0 | 1 | 1 |
| LOW_VOL_DIRECTIONAL | 46 | 236 | 761 | 6 | 4 | 12 | 0 | 0 | 0 |
| NORMAL_VOL_CHOPPY | 21 | 9 | 0 | 750 | 336 | 45 | 6 | 8 | 6 |
| NORMAL_VOL_MIXED | 6 | 9 | 6 | 336 | 486 | 214 | 11 | 5 | 12 |
| NORMAL_VOL_DIRECTIONAL | 0 | 4 | 13 | 42 | 214 | 744 | 2 | 5 | 20 |
| HIGH_VOL_CHOPPY | 0 | 0 | 0 | 20 | 9 | 0 | 582 | 305 | 61 |
| HIGH_VOL_MIXED | 0 | 0 | 0 | 5 | 12 | 8 | 325 | 487 | 227 |
| HIGH_VOL_DIRECTIONAL | 0 | 0 | 0 | 1 | 6 | 11 | 52 | 256 | 947 |

Transition probabilities (same ordering):

| Current → next | LOW_VOL_CHOPPY | LOW_VOL_MIXED | LOW_VOL_DIRECTIONAL | NORMAL_VOL_CHOPPY | NORMAL_VOL_MIXED | NORMAL_VOL_DIRECTIONAL | HIGH_VOL_CHOPPY | HIGH_VOL_MIXED | HIGH_VOL_DIRECTIONAL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 0.6217 | 0.3050 | 0.0552 | 0.0072 | 0.0081 | 0.0018 | 0.0000 | 0.0000 | 0.0009 |
| LOW_VOL_MIXED | 0.3216 | 0.4620 | 0.1957 | 0.0063 | 0.0063 | 0.0063 | 0.0000 | 0.0009 | 0.0009 |
| LOW_VOL_DIRECTIONAL | 0.0432 | 0.2216 | 0.7146 | 0.0056 | 0.0038 | 0.0113 | 0.0000 | 0.0000 | 0.0000 |
| NORMAL_VOL_CHOPPY | 0.0178 | 0.0076 | 0.0000 | 0.6351 | 0.2845 | 0.0381 | 0.0051 | 0.0068 | 0.0051 |
| NORMAL_VOL_MIXED | 0.0055 | 0.0083 | 0.0055 | 0.3097 | 0.4479 | 0.1972 | 0.0101 | 0.0046 | 0.0111 |
| NORMAL_VOL_DIRECTIONAL | 0.0000 | 0.0038 | 0.0125 | 0.0402 | 0.2050 | 0.7126 | 0.0019 | 0.0048 | 0.0192 |
| HIGH_VOL_CHOPPY | 0.0000 | 0.0000 | 0.0000 | 0.0205 | 0.0092 | 0.0000 | 0.5957 | 0.3122 | 0.0624 |
| HIGH_VOL_MIXED | 0.0000 | 0.0000 | 0.0000 | 0.0047 | 0.0113 | 0.0075 | 0.3055 | 0.4577 | 0.2133 |
| HIGH_VOL_DIRECTIONAL | 0.0000 | 0.0000 | 0.0000 | 0.0008 | 0.0047 | 0.0086 | 0.0408 | 0.2011 | 0.7439 |

There are 9,898 adjacent transitions; 5,954 (60.15%) retain the same core state.

Most frequent changing-state transitions:

- LOW_VOL_MIXED → LOW_VOL_CHOPPY: 355.
- LOW_VOL_CHOPPY → LOW_VOL_MIXED: 337.
- NORMAL_VOL_MIXED → NORMAL_VOL_CHOPPY: 336.
- NORMAL_VOL_CHOPPY → NORMAL_VOL_MIXED: 336.
- HIGH_VOL_MIXED → HIGH_VOL_CHOPPY: 325.

## Provenance, reproduction and limitations

Development identity: `c75186ca8e7eb54cd572a9157b6d4acaf2885591cb22b7b6ac7a9b1ce392d4c3`.
Report content hash: `4a643a414a172bef825182091a0beb7abfc28e953b88494a76cba95bae975811`.
The identity hashes G1's per-day manifests, including source checksum, processing
versions, policy identity, bar and feature hashes. The JSON links the exact G1
report and session configuration. Reproduce with securely supplied DATABASE_URL:
`PYTHONPATH=src .venv/bin/python scripts/characterize_xauusd_market_state.py`.
No database writes, migrations, dependencies or per-row payloads were added.

These are pooled **development-calibrated** thresholds, not thresholds available
before February 2024. Applying them retrospectively describes the calibration sample;
it is not an out-of-sample or live validation. G1 measurements remain causal, while
full-day policy eligibility is retrospective. Quantile labels are relative, not causal
claims about a market mechanism. Run durations are dependent overlapping-window
observations, not independent samples or promises of persistence.

Absolute price-change variability can shift as gold's price level and volatility
change. These cutoffs may not transfer to future periods or another provider. G1
was not changed to address that limitation. The nested range ratio cannot express
EXPANDED under this definition. No strategy outcomes were inspected, and no
thresholds were optimized against P&L, signals, markouts or session performance.

Recommended commit: `feat: freeze descriptive XAUUSD market-state taxonomy`

## Verification actually run

- Final `pytest -q`: **1019 passed**, one existing Starlette/AnyIO warning.
  Ten new offline taxonomy/report tests; existing NSE/XAUUSD regressions pass.
- `ruff check .`: passed.
- `black --check .`: passed, 196 files unchanged.
- Strict `mypy`: passed, 99 source files.
- `alembic current`: **0008 (head)**; `alembic check`: no schema drift.
- Two complete development feature generations and characterization runs matched.
- Git status, working diff, staged diff and whitespace checks reviewed. Six new
  checkpoint files; no tracked modifications or staged changes. The two old
  untracked $3,000 sensitivity reports remain untouched. No commit was made.

Stopped at G2. No strategies or profitability analysis were introduced.

# XAUUSD G2C4G4 — frozen market-state stability

**SHIFTED BUT STILL INFORMATIVE.** All nine core states remain populated. Absolute
volatility mix shifts away from LOW_VOL toward NORMAL_VOL/HIGH_VOL, while efficiency
continues to distinguish three populated groups and both corrected compression and
expansion remain represented. This is a qualitative assessment of non-degenerate
separation, not a formal saturation cutoff, hypothesis test or trading recommendation.
A distribution shift is not inherently a failure.

## Frozen inputs and scope

Only the existing materialized May–July 2024 validation partition was read:
50 approved source days, 13,800 bid/ask bars and 13,800 baseline feature rows.
Dataset identity:
`811d9f5db6bf55d128147b2247197d2364e31b185d005c69b33b2349ffa589c5`.
The manifest hash, per-day dataset keys, every bar hash and every stored baseline
feature hash were verified; recalculated baseline rows also match exactly. Exact
validation gap-policy approval was rechecked. No dataset or stored row was changed.

The source partition is 17 May, 15 June and 18 July days. A July source day can end
on the following UTC date because HistData uses fixed UTC−05:00. July 31's UTC tail
is part of the frozen July archive, not access to August source data. August–October
source data remains locked: no downloads, processing, classification or inspection.

`xauusd-market-state-features-v2` and `xauusd-market-state-taxonomy-v2` are unchanged.
The YAML configuration was loaded directly and compared exactly with G3; no
calibration/quantile-fitting function was called. Frozen thresholds are:

- `volatility_low`: `0.70772125992621078662459452035253405481804084608722`
- `volatility_high`: `1.1983084785966187971510743249379515934834203015313`
- `efficiency_low`: `0.15451438336656223298205639418968954713756764454571`
- `efficiency_high`: `0.34332645184453819226281303294138766717529844717709`

Equality remains in the lower bucket at each threshold. The expansion/compression
reference is exactly 1 for `mid_change_std_12 / mid_change_std_36`, without tolerance.
Core state remains volatility × efficiency, not a 27-state trading system. The ratio
is an additional attribute; a zero denominator would leave it unavailable rather than
inventing a value. No zero denominators occurred in mature validation windows.

## Availability, resets and causality

**10,200 classified; 3,600 UNCLASSIFIED_WARMUP**. The ratio is also available on
10,200 rows: 1,800 initial/day warmups and 1,800 gap warmups remain null. There are
50 DATASET_BOUNDARY resets and 50 DISCONTINUITY resets. Days are loaded separately,
so source-day resets coincide with dataset resets rather than appearing as additional
SOURCE_DAY markers. Existing tests also exercise contiguous source-day crossings.
The first 36 bars after each reset lack the 36-change variability needed by the core.
No missing bars or feature values were filled; no state crosses a source-day boundary.

Two independent full data loads/generations/classifications matched, including content
hashes. Five completed prefixes per day match full-generation prefixes. Existing and
new offline tests cover future mutation, reset boundaries, exact frozen loading and
artifact preservation. These verify causal formulas, not a claim that retrospective
approved-day selection was known live. Thresholds stay development-calibrated.

## Core state distribution

Percentages use classified rows in the corresponding group. JSON retains all counts.

| Core state | Overall count / % | May count / % | June count / % | July count / % |
| --- | ---: | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 387 / 3.79% | 96 / 2.77% | 175 / 5.72% | 116 / 3.16% |
| LOW_VOL_MIXED | 375 / 3.68% | 93 / 2.68% | 156 / 5.10% | 126 / 3.43% |
| LOW_VOL_DIRECTIONAL | 375 / 3.68% | 99 / 2.85% | 161 / 5.26% | 115 / 3.13% |
| NORMAL_VOL_CHOPPY | 1592 / 15.61% | 493 / 14.22% | 476 / 15.56% | 623 / 16.97% |
| NORMAL_VOL_MIXED | 1576 / 15.45% | 568 / 16.38% | 445 / 14.54% | 563 / 15.33% |
| NORMAL_VOL_DIRECTIONAL | 1862 / 18.25% | 615 / 17.73% | 567 / 18.53% | 680 / 18.52% |
| HIGH_VOL_CHOPPY | 1335 / 13.09% | 510 / 14.71% | 376 / 12.29% | 449 / 12.23% |
| HIGH_VOL_MIXED | 1365 / 13.38% | 528 / 15.22% | 365 / 11.93% | 472 / 12.85% |
| HIGH_VOL_DIRECTIONAL | 1333 / 13.07% | 466 / 13.44% | 339 / 11.08% | 528 / 14.38% |

Month classified/unclassified: 2024-05: 3468/1224, 2024-06: 3060/1080, 2024-07: 3672/1296.

## Development → validation shifts

No threshold is reinterpreted. Percentages use classified core rows or valid ratio rows as appropriate. Differences are percentage points, not returns.

| Dimension/bucket | Development % | Validation % | Difference pp |
| --- | ---: | ---: | ---: |
| volatility: LOW_VOL | 33.33 | 11.15 | -22.19 |
| volatility: NORMAL_VOL | 33.34 | 49.31 | +15.97 |
| volatility: HIGH_VOL | 33.32 | 39.54 | +6.22 |
| efficiency: CHOPPY | 32.97 | 32.49 | -0.48 |
| efficiency: MIXED | 32.85 | 32.51 | -0.34 |
| efficiency: DIRECTIONAL | 34.17 | 35.00 | +0.83 |
| attribute: COMPRESSED | 62.10 | 59.07 | -3.04 |
| attribute: NEUTRAL | 0.00 | 0.00 | +0.00 |
| attribute: EXPANDED | 37.90 | 40.93 | +3.04 |

There is no numerical out-of-range ceiling: the highest bucket is open-ended.
No invalid/nonfinite inputs were observed. Volatility is shifted, not nearly all
in a single bucket; efficiency remains spread across all three. All nine core
states have hundreds of observations. This supports informative separation in this
sample without imposing a post-hoc formal saturation threshold. Absolute variability
may still drift with gold's price level and future conditions.

## Corrected attribute by month and session

Percentages use valid ratios. Research sessions are the existing UTC labels at bar
completion; they do not grant execution permissions. Session summaries are affected
by the existing coverage/warmup structure. No session is recommended or excluded.

| Group | Valid | Unavailable | COMPRESSED count / % | NEUTRAL count / % | EXPANDED count / % |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 10200 | 3600 | 6025 / 59.07% | 0 / 0.00% | 4175 / 40.93% |
| 2024-05 | 3468 | 1224 | 2001 / 57.70% | 0 / 0.00% | 1467 / 42.30% |
| 2024-06 | 3060 | 1080 | 1898 / 62.03% | 0 / 0.00% | 1162 / 37.97% |
| 2024-07 | 3672 | 1296 | 2126 / 57.90% | 0 / 0.00% | 1546 / 42.10% |
| ASIA | 1800 | 3000 | 677 / 37.61% | 0 / 0.00% | 1123 / 62.39% |
| LONDON | 2950 | 50 | 1848 / 62.64% | 0 / 0.00% | 1102 / 37.36% |
| LONDON_NEW_YORK_OVERLAP | 1800 | 0 | 448 / 24.89% | 0 / 0.00% | 1352 / 75.11% |
| NEW_YORK | 3000 | 0 | 2524 / 84.13% | 0 / 0.00% | 476 / 15.87% |
| OFF_SESSION | 650 | 550 | 528 / 81.23% | 0 / 0.00% | 122 / 18.77% |

## Session core mix

Percentages among classified session rows; all counts and warmups are in JSON.

| Session | Classified | Warmup | LOW_VOL_CHOPPY | LOW_VOL_MIXED | LOW_VOL_DIRECTIONAL | NORMAL_VOL_CHOPPY | NORMAL_VOL_MIXED | NORMAL_VOL_DIRECTIONAL | HIGH_VOL_CHOPPY | HIGH_VOL_MIXED | HIGH_VOL_DIRECTIONAL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ASIA | 1800 | 3000 | 9.00 | 10.94 | 9.94 | 14.06 | 18.00 | 18.28 | 5.44 | 7.28 | 7.06 |
| LONDON | 2950 | 50 | 2.61 | 1.73 | 3.12 | 24.95 | 24.00 | 27.80 | 5.29 | 5.46 | 5.05 |
| LONDON_NEW_YORK_OVERLAP | 1800 | 0 | 0.33 | 0.61 | 0.67 | 11.78 | 10.94 | 16.78 | 19.72 | 21.17 | 18.00 |
| NEW_YORK | 3000 | 0 | 1.00 | 0.60 | 0.67 | 10.13 | 8.60 | 10.70 | 23.17 | 22.30 | 22.83 |
| OFF_SESSION | 650 | 550 | 17.23 | 15.08 | 11.08 | 13.38 | 13.69 | 13.85 | 4.77 | 3.54 | 7.38 |

Monthly volatility shares (LOW / NORMAL / HIGH):

- 2024-05: 8.30% / 48.33% / 43.37%.
- 2024-06: 16.08% / 48.63% / 35.29%.
- 2024-07: 9.72% / 50.82% / 39.46%.

## Run lengths and transitions

Identical G2 continuity rules: only five-minute neighbors within one dataset/source
day and continuous segment. Warmups, resets and gaps break runs and transitions.
Self-transitions count; there is no jump to a later classified bar. P95 is nearest
rank of observed run lengths, not a recalibration of taxonomy thresholds. Minutes
are bars × 5; this is descriptive duration, not predicted persistence.

| State | Development median / mean / p95 / max bars | Validation median / mean / p95 / max bars | Validation median / mean / p95 / max minutes |
| --- | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 2.00 / 2.56 / 6.00 / 17.00 | 2.00 / 2.42 / 6.00 / 8.00 | 10.00 / 12.09 / 30.00 / 40.00 |
| LOW_VOL_MIXED | 1.00 / 1.83 / 4.00 / 9.00 | 1.00 / 1.74 / 4.00 / 10.00 | 5.00 / 8.68 / 20.00 / 50.00 |
| LOW_VOL_DIRECTIONAL | 2.00 / 3.35 / 11.00 / 24.00 | 2.00 / 3.00 / 10.00 / 13.00 | 10.00 / 15.00 / 50.00 / 65.00 |
| NORMAL_VOL_CHOPPY | 2.00 / 2.71 / 8.00 / 15.00 | 2.00 / 2.61 / 7.00 / 12.00 | 10.00 / 13.03 / 35.00 / 60.00 |
| NORMAL_VOL_MIXED | 1.00 / 1.80 / 4.00 / 8.00 | 1.00 / 1.83 / 4.00 / 9.00 | 5.00 / 9.16 / 20.00 / 45.00 |
| NORMAL_VOL_DIRECTIONAL | 2.00 / 3.42 / 11.00 / 23.00 | 2.00 / 3.89 / 12.00 / 32.00 | 10.00 / 19.44 / 60.00 / 160.00 |
| HIGH_VOL_CHOPPY | 2.00 / 2.46 / 6.00 / 10.00 | 2.00 / 2.62 / 7.00 / 12.00 | 10.00 / 13.11 / 35.00 / 60.00 |
| HIGH_VOL_MIXED | 1.00 / 1.84 / 4.00 / 11.00 | 1.00 / 1.85 / 4.00 / 17.00 | 5.00 / 9.24 / 20.00 / 85.00 |
| HIGH_VOL_DIRECTIONAL | 2.00 / 3.84 / 12.00 / 33.00 | 2.00 / 3.62 / 13.00 / 26.00 | 10.00 / 18.11 / 65.00 / 130.00 |

10,100 adjacent transitions; 6,133 same-state transitions. Same-state frequency: **60.15% development → 60.72% validation**, +0.57 percentage points.

Transition counts (rows current, columns next; probabilities are in JSON):

| Current → next | LOW_VOL_CHOPPY | LOW_VOL_MIXED | LOW_VOL_DIRECTIONAL | NORMAL_VOL_CHOPPY | NORMAL_VOL_MIXED | NORMAL_VOL_DIRECTIONAL | HIGH_VOL_CHOPPY | HIGH_VOL_MIXED | HIGH_VOL_DIRECTIONAL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LOW_VOL_CHOPPY | 227 | 113 | 19 | 7 | 10 | 2 | 0 | 0 | 0 |
| LOW_VOL_MIXED | 97 | 159 | 72 | 15 | 7 | 10 | 0 | 0 | 1 |
| LOW_VOL_DIRECTIONAL | 16 | 68 | 250 | 4 | 7 | 15 | 0 | 0 | 0 |
| NORMAL_VOL_CHOPPY | 22 | 2 | 3 | 981 | 461 | 85 | 7 | 18 | 2 |
| NORMAL_VOL_MIXED | 9 | 13 | 0 | 464 | 716 | 326 | 18 | 5 | 8 |
| NORMAL_VOL_DIRECTIONAL | 0 | 2 | 16 | 73 | 341 | 1383 | 4 | 6 | 24 |
| HIGH_VOL_CHOPPY | 0 | 0 | 0 | 24 | 6 | 1 | 826 | 412 | 58 |
| HIGH_VOL_MIXED | 0 | 0 | 0 | 7 | 12 | 5 | 434 | 626 | 274 |
| HIGH_VOL_DIRECTIONAL | 0 | 0 | 0 | 1 | 6 | 16 | 44 | 295 | 965 |

## Interpretation and reproduction

The conclusion concerns descriptive state separation only. It does not establish
predictive value, strategy profitability, statistical stationarity or generalization
to another feed. Overlapping windows create dependence; run/transition observations
are not independent trials. Exact NEUTRAL equality can be absent without degeneracy
of the two-sided expansion/compression measurement. This is an existing validation
partition, not a claim that it is an untouched strategy holdout.

No strategy signals, P&L, strategy outcomes or forward markouts were accessed.
No threshold was altered or recalibrated on May–July. No new strategy, data download,
persistence, migration or dependency was added. All historical artifacts remain intact.

Run with DATABASE_URL supplied securely:
`PYTHONPATH=src .venv/bin/python scripts/validate_xauusd_market_state.py`.
The script reads existing database rows and writes only the compact JSON report.
The descriptive conclusion is an analyst assessment for this frozen sample, not an
automatic rule with invented numeric cutoffs. JSON retains dataset and per-day hashes,
config/feature/report hashes, count reconciliation, matrices and deterministic identity.
No row-level payload is committed.

Report content hash: `1435a8685a7f8cca907419bd8b494caf7ecbd88a972067c380289d21de859f46`.

## Verification actually run

- `pytest -q`: **1033 passed**, one existing Starlette/AnyIO deprecation warning.
  Six new offline validation cases; existing XAUUSD/NSE regressions passed.
- `ruff check .`: passed.
- `black --check .`: passed, 201 files unchanged.
- Strict `mypy`: passed, 100 source files.
- `alembic current`: **0008 (head)**; `alembic check`: no schema drift.
- Two full loads/generations/classifications matched exactly; all frozen input
  hashes and baseline rows verified. No threshold calibration ran.
- Git status, working/staged diffs and whitespace checks reviewed. Four new
  checkpoint files, no tracked modifications or staged changes. The two old
  untracked $3,000 sensitivity reports remain untouched. No commit was made.

Stopped at G4. No strategies or trading-outcome analysis were introduced.

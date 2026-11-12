# G2C4D4 — contrarian / inverted signal diagnostic

**ANALYSIS ONLY; DEVELOPMENT / IN-SAMPLE.** Hypothesis fixed before outcomes:
failed continuation signals may identify short-term directional exhaustion rather
than continuation. Only interpretation is inverted; no indicator, timestamp,
threshold, stop, target, horizon, strategy or execution rule was changed. This is
not an inverted trading strategy, profitability backtest or validation exercise.

## Source, timing and executable prices

Original counts reproduced: V1 **2,140 BUY / 1,944 SELL / 4,084 total**; V2
**2,008 BUY / 1,789 SELL / 3,797 total**. All 12,252 D2 signal/horizon records
reproduced exactly from source bars/features. Inversion preserves every signal
timestamp, original decision identity, V2 membership and unavailable-window result.

- Original BUY → hypothetical SELL: next continuous BID open − endpoint ASK close.
- Original SELL → hypothetical BUY: endpoint BID close − next continuous ASK open.

Prices were recomputed from source BID/ASK, **not negated from D2 markouts**.
Opposite markouts sum to minus the entry and endpoint spreads, rather than zero.
The entry bar counts as horizon bar 1; fixed 5/10/20 horizons span 25/50/100
minutes from entry. No signal-bar entry, gap crossing, shortening, interpolation,
day/dataset crossing, commission, volume or portfolio blocking is used.

Excursions retain D2 definitions: hypothetical BUY uses BID highs/lows relative
to entry ASK; hypothetical SELL uses ASK lows/highs relative to entry BID.
Favorable/adverse excursions are nonnegative magnitudes, clamped at zero. OHLC
extrema do not reveal intrabar ordering or guarantee achievable execution. All
values are raw quoted-price differences, not monetary account returns. Decimal
differences are exact; summaries use 60-digit Decimal ratios, displayed to four decimals.

Only the existing 49 approved February–April source days were queried. Post-April
holdout remains reserved. The already-approved fixed UTC−05:00 April 30 source
day retains its existing UTC tail into May 1; no additional later dataset was
inspected. This dataset has already informed development and is not unseen validation.

## Matched random methodology

Reuse D3 exact source month × existing signal-time research session × **contrarian
direction** matching. All horizon-eligible bars form the pool, including actual
signal bars and warmup rows. No price/outcome filtering. Sampling is without
replacement within each stratum/trial; trials can reuse candidates, and opposite
directions may share timestamps. Exact counts match without fallback. Existing
fixed-UTC session labels are analytical, never trading permissions.

Exactly 1,000 trials per version/horizon, repeated identically. Seed namespace
`xauusd-g2c4d3-matched-random-v1`; SHA256(namespace|V1-inverted-or-V2-inverted|
horizon|zero-based-trial) supplies the big-endian seed to Python random.Random.sample.
The diagnostic labels separate these fixed seeds from continuation controls. Python
version 3.12.7. No favorable seed selection. Random p05/p95 use nearest ranks
50/950; actual percentile = 100 × (below + half ties)/1,000. These are empirical
descriptive ranks, **not p-values**. Overlapping signals and serially dependent bars
do not constitute independent evidence. Matching does not control every market condition.

## V1: contrarian observations

| Bars | Interpretation | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Zero % | Mean favorable | Mean adverse |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 3909 | 175 | -0.3226 | -0.1910 | 45.0243 | 54.9245 | 0.0512 | 1.5188 | 2.3127 |
| 5 | original SELL → BUY | 1856 | 88 | -0.2980 | -0.1600 | 46.1746 | 53.7716 | 0.0539 | 1.5734 | 2.3892 |
| 5 | original BUY → SELL | 2053 | 87 | -0.3449 | -0.2300 | 43.9844 | 55.9669 | 0.0487 | 1.4694 | 2.2435 |
| 10 | ALL | 3723 | 361 | -0.2710 | -0.1910 | 45.7695 | 53.9887 | 0.2417 | 2.3806 | 3.1819 |
| 10 | original SELL → BUY | 1761 | 183 | -0.1959 | -0.1040 | 47.7570 | 51.8455 | 0.3975 | 2.4028 | 3.2585 |
| 10 | original BUY → SELL | 1962 | 178 | -0.3383 | -0.2985 | 43.9857 | 55.9123 | 0.1019 | 2.3607 | 3.1132 |
| 20 | ALL | 3374 | 710 | -0.2530 | -0.1900 | 47.7475 | 52.1340 | 0.1186 | 3.6516 | 4.4611 |
| 20 | original SELL → BUY | 1611 | 333 | -0.0892 | -0.1500 | 47.9205 | 51.8932 | 0.1862 | 3.6442 | 4.4429 |
| 20 | original BUY → SELL | 1763 | 377 | -0.4027 | -0.2500 | 47.5893 | 52.3539 | 0.0567 | 3.6584 | 4.4777 |

## V1: matched-random mean-markout comparison

| Bars | Interpretation | Actual mean | Random mean | Random p05 | Random p95 | Actual percentile |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | -0.3226 | -0.3602 | -0.4263 | -0.2917 | 82.1000 |
| 5 | original SELL → BUY | -0.2980 | -0.3066 | -0.4041 | -0.2067 | 57.1000 |
| 5 | original BUY → SELL | -0.3449 | -0.4086 | -0.5061 | -0.3189 | 86.2000 |
| 10 | ALL | -0.2710 | -0.3770 | -0.4792 | -0.2722 | 95.3000 |
| 10 | original SELL → BUY | -0.1959 | -0.2579 | -0.4040 | -0.1124 | 76.9000 |
| 10 | original BUY → SELL | -0.3383 | -0.4838 | -0.6242 | -0.3485 | 95.7000 |
| 20 | ALL | -0.2530 | -0.4061 | -0.5551 | -0.2609 | 96.2000 |
| 20 | original SELL → BUY | -0.0892 | -0.1412 | -0.3528 | 0.0706 | 66.6000 |
| 20 | original BUY → SELL | -0.4027 | -0.6481 | -0.8540 | -0.4479 | 98.1000 |

## V2: contrarian observations

| Bars | Interpretation | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Zero % | Mean favorable | Mean adverse |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 3633 | 164 | -0.3319 | -0.2000 | 44.8115 | 55.1335 | 0.0551 | 1.5164 | 2.3340 |
| 5 | original SELL → BUY | 1710 | 79 | -0.3302 | -0.1785 | 45.6725 | 54.2690 | 0.0585 | 1.5612 | 2.4356 |
| 5 | original BUY → SELL | 1923 | 85 | -0.3334 | -0.2200 | 44.0458 | 55.9022 | 0.0520 | 1.4767 | 2.2437 |
| 10 | ALL | 3464 | 333 | -0.2992 | -0.2170 | 45.1501 | 54.5901 | 0.2598 | 2.3801 | 3.2124 |
| 10 | original SELL → BUY | 1625 | 164 | -0.2631 | -0.1300 | 46.7077 | 52.8615 | 0.4308 | 2.3792 | 3.3269 |
| 10 | original BUY → SELL | 1839 | 169 | -0.3311 | -0.3000 | 43.7738 | 56.1175 | 0.1088 | 2.3810 | 3.1113 |
| 20 | ALL | 3147 | 650 | -0.2960 | -0.2270 | 47.3467 | 52.5262 | 0.1271 | 3.6429 | 4.5122 |
| 20 | original SELL → BUY | 1497 | 292 | -0.1527 | -0.1970 | 47.0942 | 52.7054 | 0.2004 | 3.6177 | 4.5205 |
| 20 | original BUY → SELL | 1650 | 358 | -0.4260 | -0.2500 | 47.5758 | 52.3636 | 0.0606 | 3.6659 | 4.5046 |

## V2: matched-random mean-markout comparison

| Bars | Interpretation | Actual mean | Random mean | Random p05 | Random p95 | Actual percentile |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | -0.3319 | -0.3590 | -0.4318 | -0.2885 | 70.9000 |
| 5 | original SELL → BUY | -0.3302 | -0.3048 | -0.4177 | -0.1973 | 32.7000 |
| 5 | original BUY → SELL | -0.3334 | -0.4073 | -0.5009 | -0.3103 | 88.6000 |
| 10 | ALL | -0.2992 | -0.3751 | -0.4823 | -0.2709 | 88.4000 |
| 10 | original SELL → BUY | -0.2631 | -0.2508 | -0.4041 | -0.0956 | 44.3000 |
| 10 | original BUY → SELL | -0.3311 | -0.4848 | -0.6292 | -0.3462 | 96.5000 |
| 20 | ALL | -0.2960 | -0.4001 | -0.5599 | -0.2440 | 87.1000 |
| 20 | original SELL → BUY | -0.1527 | -0.1300 | -0.3626 | 0.1005 | 42.9000 |
| 20 | original BUY → SELL | -0.4260 | -0.6451 | -0.8494 | -0.4340 | 95.6000 |

## Reproducibility and checks

Trial-distribution hash: `12ec885adfb134368ef04e4234c909cb08aef7dc97df878c216dd4f61fea6ca3`.
Report hash: `4d5ad17c857be524d2a401378082b07a22ccb6fba388d1256bce57157583094a`.

All six 1,000-trial runs repeated with identical selections/statistics. Four new
offline regression cases verify source-side inversion differs from negation and
that both directions preserve unavailable windows across all fixed horizons.
Existing fixed-horizon suffix-mutation and matching tests remain passing.

- Full pytest: **951 passed**, including NSE/backtester regressions; one existing
  Starlette/AnyIO deprecation warning.
- Ruff passed; Black passed (178 files); strict mypy passed (95 source files).
- Alembic current **0008 (head)**; check: no schema drift. No migration.
- D2/D3 and prior strategy/backtest reports unchanged; old partial sensitivity
  files untouched/untracked. No strategy source or shared measurement logic changed.
- Git status, working diff and staged diff reviewed; nothing staged or committed.

Reproduce with DATABASE_URL supplied securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/analyze_xauusd_contrarian.py
```

The JSON stores each inverted observation with its original side and signal identity,
all aggregate summaries, random trial results/selection hashes and matched strata.

## Factual conclusions

1. **Neither inverted V1 nor inverted V2 has positive aggregate after-spread
   tendency at any fixed horizon.** Mean and median markouts remain negative,
   with positive fractions below 50%. Both side-specific means are also negative
   at 5, 10 and 20 bars. Inversion is not a friction-free rescue of continuation.
2. **Both beat matched-random means in aggregate across all three horizons.**
   V1 empirical mean ranks: 82.1 / 95.3 / 96.2; V2: 70.9 / 88.4 / 87.1.
   Relative superiority to negative controls is distinct from positive absolute
   executable markouts. These ranks are not formal significance claims.
3. **Original BUY → SELL shows the most consistent relative reversal pattern.**
   V1 ranks: 86.2 / 95.7 / 98.1; V2: 88.6 / 96.5 / 95.6. Both outperform their
   controls at each horizon, but their absolute means remain negative.
4. **Original SELL → BUY is not consistent across versions.** V1 ranks are
   57.1 / 76.9 / 66.6, modestly above random. V2 ranks are 32.7 / 44.3 / 42.9,
   below random at all horizons. No universal two-sided reversal effect is shown.
5. Mean adverse excursion exceeds mean favorable excursion for ALL and each
   inversion direction at every horizon. Path extrema do not imply achievable
   management or a profitable exit mechanism.
6. Relative exhaustion/reversal behavior is descriptively consistent for original
   BUY signals, and for aggregate controls, but **positive after-spread tendency
   is absent**. V1's aggregate relative effect is stronger than V2's in this sample.
   No indicator cutoff, direction removal, horizon selection or trading rule follows.

The diagnostic is exploratory and conditioned on repeatedly analyzed development
observations. It does not establish causal exhaustion, statistical proof, validation,
or production readiness. Any future mean-reversion candidate would require its own
explicitly frozen design and separate authorization. No V3 or backtest was created.

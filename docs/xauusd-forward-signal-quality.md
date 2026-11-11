# G2C4D2 — forward signal quality / markout study

**DEVELOPMENT / IN-SAMPLE: February–April 2024.** These data are no longer
unseen validation data. No future holdout performance was inspected. This is
forward-price measurement, not a portfolio or stop/target backtest. No account
balance, sizing, risk budget, target, stop, commission or position blocking is used.
All overlapping/repeated signals are retained and are not statistically independent.

## Frozen source and timing

49 approved research days / 13,524 bars and feature rows were read without writes.
Both persisted bar and feature payload hashes match frozen source evidence. Every
re-evaluated V1/V2 decision hash matches its saved decision audit. Signal totals:
- V1: 2,140 BUY + 1,944 SELL = **4,084**.
- V2: 2,008 BUY + 1,789 SELL = **3,797**.
- Removed by confirmation: **287** (132 BUY, 155 SELL; 286 opposite-sign, one zero).

A signal is available at signal-bar completion. Entry is the immediately following
continuous bar opening, never the signal-bar opening/close price. The entry bar is
bar 1: 5/10/20 bars end 25/50/100 minutes after entry. The endpoint is the final
included bar close. Only these three horizons were examined.

- BUY markout = endpoint BID close − entry ASK open.
- SELL markout = entry BID open − endpoint ASK close.
- BUY favorable = max(0, highest BID high in window − entry ASK).
- BUY adverse = max(0, entry ASK − lowest BID low in window).
- SELL favorable = max(0, entry BID − lowest ASK low in window).
- SELL adverse = max(0, highest ASK high in window − entry BID).

Excursions are nonnegative magnitudes, clamped to zero when the executable side
never reaches the entry reference. Highs/lows include the entry bar through the
endpoint bar; no midpoint or later bars are used. These OHLC extrema do not reveal
intrabar ordering and are not proposed achievable trades. Units are raw XAUUSD
quoted-price differences, not account P&L. Individual arithmetic is exact Decimal;
aggregate ratios use 60-digit Decimal precision, displayed here to four decimals.

Each window stays inside one source dataset and research segment. Day endings,
provider gaps, excluded days and dataset boundaries are never crossed. A window
may end exactly at a boundary; no entry is allowed at a boundary. Incomplete
horizons remain unavailable, without shortening or filling. Counts differ across
horizons, so horizon comparisons also reflect differing eligible populations.

## V1: markouts

| Bars | Side | Signals | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Zero % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 4084 | 3909 | 175 | -0.3612 | -0.4770 | 39.6009 | 60.2968 | 0.1023 |
| 5 | BUY | 2140 | 2053 | 87 | -0.3373 | -0.4300 | 40.7209 | 59.2304 | 0.0487 |
| 5 | SELL | 1944 | 1856 | 88 | -0.3876 | -0.5205 | 38.3621 | 61.4763 | 0.1616 |
| 10 | ALL | 4084 | 3723 | 361 | -0.4127 | -0.4600 | 41.3645 | 58.5549 | 0.0806 |
| 10 | BUY | 2140 | 1962 | 178 | -0.3447 | -0.3685 | 43.3231 | 56.6259 | 0.0510 |
| 10 | SELL | 1944 | 1761 | 183 | -0.4884 | -0.5700 | 39.1823 | 60.7041 | 0.1136 |
| 20 | ALL | 4084 | 3374 | 710 | -0.4310 | -0.4600 | 44.8133 | 55.1274 | 0.0593 |
| 20 | BUY | 2140 | 1763 | 377 | -0.2789 | -0.4370 | 45.7175 | 54.2825 | 0.0000 |
| 20 | SELL | 1944 | 1611 | 333 | -0.5976 | -0.5100 | 43.8237 | 56.0521 | 0.1241 |

### V1: executable excursions

| Bars | Side | Mean favorable | Median favorable | Mean adverse | Median adverse |
| --- | --- | ---: | ---: | ---: | ---: |
| 5 | ALL | 1.6662 | 0.8100 | 2.1702 | 1.5970 |
| 5 | BUY | 1.5996 | 0.8000 | 2.1180 | 1.5100 |
| 5 | SELL | 1.7399 | 0.8415 | 2.2280 | 1.6500 |
| 10 | ALL | 2.5228 | 1.3800 | 3.0436 | 2.1300 |
| 10 | BUY | 2.4566 | 1.3750 | 3.0219 | 2.0405 |
| 10 | SELL | 2.5965 | 1.3800 | 3.0677 | 2.1900 |
| 20 | ALL | 3.7940 | 2.3150 | 4.3223 | 3.0070 |
| 20 | BUY | 3.8130 | 2.3400 | 4.3258 | 2.9600 |
| 20 | SELL | 3.7733 | 2.2500 | 4.3185 | 3.0500 |

V1 unavailable reasons (one deterministic reason per signal/horizon):

- 5 bars: SIGNAL_AT_BOUNDARY=30, INCOMPLETE_HORIZON=66, DISCONTINUITY=79.
- 10 bars: DISCONTINUITY=175, INCOMPLETE_HORIZON=156, SIGNAL_AT_BOUNDARY=30.
- 20 bars: DISCONTINUITY=352, INCOMPLETE_HORIZON=328, SIGNAL_AT_BOUNDARY=30.

## V2: markouts

| Bars | Side | Signals | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Zero % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 3797 | 3633 | 164 | -0.3509 | -0.4700 | 39.8569 | 60.0606 | 0.0826 |
| 5 | BUY | 2008 | 1923 | 85 | -0.3483 | -0.4400 | 40.4056 | 59.5424 | 0.0520 |
| 5 | SELL | 1789 | 1710 | 79 | -0.3538 | -0.4900 | 39.2398 | 60.6433 | 0.1170 |
| 10 | ALL | 3797 | 3464 | 333 | -0.3840 | -0.4370 | 41.8591 | 58.0543 | 0.0866 |
| 10 | BUY | 2008 | 1839 | 169 | -0.3517 | -0.3600 | 43.4475 | 56.4981 | 0.0544 |
| 10 | SELL | 1789 | 1625 | 164 | -0.4204 | -0.5270 | 40.0615 | 59.8154 | 0.1231 |
| 20 | ALL | 3797 | 3147 | 650 | -0.3876 | -0.4300 | 45.2812 | 54.6552 | 0.0636 |
| 20 | BUY | 2008 | 1650 | 358 | -0.2553 | -0.4400 | 45.6970 | 54.3030 | 0.0000 |
| 20 | SELL | 1789 | 1497 | 292 | -0.5335 | -0.4200 | 44.8230 | 55.0434 | 0.1336 |

### V2: executable excursions

| Bars | Side | Mean favorable | Median favorable | Mean adverse | Median adverse |
| --- | --- | ---: | ---: | ---: | ---: |
| 5 | ALL | 1.6878 | 0.8200 | 2.1666 | 1.5800 |
| 5 | BUY | 1.6000 | 0.7900 | 2.1243 | 1.5070 |
| 5 | SELL | 1.7866 | 0.8700 | 2.2142 | 1.6385 |
| 10 | ALL | 2.5533 | 1.3900 | 3.0420 | 2.1170 |
| 10 | BUY | 2.4546 | 1.3830 | 3.0412 | 2.0410 |
| 10 | SELL | 2.6649 | 1.4030 | 3.0428 | 2.1600 |
| 20 | ALL | 3.8453 | 2.3430 | 4.3129 | 2.9800 |
| 20 | BUY | 3.8395 | 2.3500 | 4.3320 | 2.9400 |
| 20 | SELL | 3.8517 | 2.3400 | 4.2917 | 3.0300 |

V2 unavailable reasons (one deterministic reason per signal/horizon):

- 5 bars: SIGNAL_AT_BOUNDARY=27, INCOMPLETE_HORIZON=63, DISCONTINUITY=74.
- 10 bars: DISCONTINUITY=155, INCOMPLETE_HORIZON=151, SIGNAL_AT_BOUNDARY=27.
- 20 bars: DISCONTINUITY=319, INCOMPLETE_HORIZON=304, SIGNAL_AT_BOUNDARY=27.

## REMOVED: markouts

| Bars | Side | Signals | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Zero % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 287 | 276 | 11 | -0.4967 | -0.5450 | 36.2319 | 63.4058 | 0.3623 |
| 5 | BUY | 132 | 130 | 2 | -0.1749 | -0.2600 | 45.3846 | 54.6154 | 0.0000 |
| 5 | SELL | 155 | 146 | 9 | -0.7833 | -0.7100 | 28.0822 | 71.2329 | 0.6849 |
| 10 | ALL | 287 | 259 | 28 | -0.7967 | -0.9800 | 34.7490 | 65.2510 | 0.0000 |
| 10 | BUY | 132 | 123 | 9 | -0.2398 | -0.5300 | 41.4634 | 58.5366 | 0.0000 |
| 10 | SELL | 155 | 136 | 19 | -1.3004 | -1.2800 | 28.6765 | 71.3235 | 0.0000 |
| 20 | ALL | 287 | 227 | 60 | -1.0330 | -0.8700 | 38.3260 | 61.6740 | 0.0000 |
| 20 | BUY | 132 | 113 | 19 | -0.6238 | -0.4200 | 46.0177 | 53.9823 | 0.0000 |
| 20 | SELL | 155 | 114 | 41 | -1.4387 | -1.2150 | 30.7018 | 69.2982 | 0.0000 |

### REMOVED: executable excursions

| Bars | Side | Mean favorable | Median favorable | Mean adverse | Median adverse |
| --- | --- | ---: | ---: | ---: | ---: |
| 5 | ALL | 1.3822 | 0.7350 | 2.2175 | 1.7200 |
| 5 | BUY | 1.5948 | 0.8165 | 2.0241 | 1.6135 |
| 5 | SELL | 1.1929 | 0.6100 | 2.3896 | 1.8435 |
| 10 | ALL | 2.1148 | 1.3000 | 3.0651 | 2.3400 |
| 10 | BUY | 2.4865 | 1.3300 | 2.7332 | 2.0400 |
| 10 | SELL | 1.7787 | 1.2400 | 3.3652 | 2.6950 |
| 20 | ALL | 3.0830 | 1.9500 | 4.4534 | 3.2740 |
| 20 | BUY | 3.4252 | 2.1100 | 4.2349 | 3.0800 |
| 20 | SELL | 2.7438 | 1.6615 | 4.6700 | 3.4835 |

REMOVED unavailable reasons (one deterministic reason per signal/horizon):

- 5 bars: DISCONTINUITY=5, INCOMPLETE_HORIZON=3, SIGNAL_AT_BOUNDARY=3.
- 10 bars: DISCONTINUITY=20, INCOMPLETE_HORIZON=5, SIGNAL_AT_BOUNDARY=3.
- 20 bars: DISCONTINUITY=33, INCOMPLETE_HORIZON=24, SIGNAL_AT_BOUNDARY=3.

## Direct V2 minus V1 comparison (ALL eligible signals)

| Bars | Mean markout delta | Median delta | Positive rate delta, pp | Mean favorable delta | Mean adverse delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5 | 0.0103 | 0.0070 | 0.2559 | 0.0216 | -0.0036 |
| 10 | 0.0287 | 0.0230 | 0.4946 | 0.0305 | -0.0016 |
| 20 | 0.0434 | 0.0300 | 0.4679 | 0.0513 | -0.0095 |

## Factual interpretation

1. V1 has **negative mean and median** executable directional markouts at all
   fixed horizons; positive fractions remain below 50%. This sample does not show
   positive aggregate after-spread directional tendency at 5, 10 or 20 bars.
2. V2 is slightly less negative overall at each horizon, but remains negative.
   This is not superiority inferred merely from fewer signals, nor independent
   validation or a statistical significance claim.
3. The removed subset has more-negative aggregate mean/median, lower positive
   fraction, smaller mean favorable excursion and larger mean adverse excursion
   than retained signals at all three horizons.
4. Side-specific results qualify that finding: removed SELL signals are weaker
   on mean markout at every horizon. Removed BUY means at 5 and 10 bars are
   less negative than retained BUY means; at 20 bars they are more negative.
   The confirmation did not uniformly remove weaker BUY signals.
5. BUY mean markouts are less negative than SELL in V1 at all horizons. V2 BUY
   means remain less negative than SELL, but V2 worsens BUY mean markouts at
   5 and 10 bars while improving SELL means at every horizon.
6. Mean adverse excursions exceed mean favorable excursions at every horizon
   for ALL signals in both versions. Excursions grow with horizon; they describe
   paths, not an instruction to change stops or targets.

No horizon, RSI/momentum cutoff, session or new strategy is recommended. No V3
or random-entry benchmark was created. Without a benchmark and independent data,
these are conditional descriptive statistics; overlapping observations and sample
selection prevent treating them as independent evidence of a causal signal edge.

## Reproduction and verification

Run with DATABASE_URL supplied securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/analyze_xauusd_markouts.py
```

JSON includes every V1 signal/horizon measurement, V2 membership, unavailable
reasons, source evidence, source report hashes and deterministic content hash.
V1 = retained V2 + removed is checked exactly for every horizon, side and count.
All frozen reports remain unchanged. Offline tests cover exact executable sides,
entry timing, all three horizons, no shortening/gap crossing, day boundaries,
UTC validation and suffix mutation after each horizon preserving its measurement.
Tests include low ambient Decimal precision to verify exact individual differences.

### Checks actually run

- Full pytest: **943 passed** (seven new markout cases); existing NSE regressions
  pass. One pre-existing Starlette/AnyIO deprecation warning remains.
- Ruff passed; Black passed (174 files); strict mypy passed (94 source files).
- Alembic current: **0008 (head)**; check: no schema drift. No migration.
- All prior XAUUSD report SHA-256 hashes remain unchanged. No existing strategy,
  feature, execution or configuration file was modified.
- Git status, working diff and staged diff inspected: only new study files plus
  the two pre-existing untracked partial sensitivity reports; nothing staged/committed.
- 12,252 signal/horizon observations retained (4,084 × 3); eligible/unavailable
  membership and V1 = V2 + removed counts reconcile exactly.

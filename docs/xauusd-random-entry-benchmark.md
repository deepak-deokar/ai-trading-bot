# G2C4D3 — matched random entry benchmark

**ANALYSIS ONLY; DEVELOPMENT / IN-SAMPLE.** No strategy, stop, target, indicator
or execution changes. No account backtest, sizing, commission, portfolio blocking
or ML. February–April 2024 is not unseen validation. No future holdout performance
was inspected. All data after April 30 remains reserved from strategy-performance
analysis until a future candidate is frozen. Source-day labels define this bound:
the already-approved fixed UTC−05:00 April 30 day includes its existing UTC tail
through May 1 05:00; no new May/later dataset was queried.

## Frozen actual reproduction

- V1: 2,140 BUY + 1,944 SELL = **4,084**.
- V2: 2,008 BUY + 1,789 SELL = **3,797**.
- All **12,252** D2 V1 signal/horizon observations reproduced exactly, including
  V2 membership, entry/endpoint timestamps, Decimal prices, excursions and unavailable
  reasons. Every ALL/BUY/SELL D2 aggregate reproduced exactly.
- Persisted bars/features matched frozen source hashes; existing D2 reports unchanged.

## Matching and sampling

Hypothesis fixed before results: trend/momentum signals should outperform matched
random forward directional markouts. No parameter change. Candidate signals are
every completed bar in the same 49 approved datasets with a valid D2 next-bar entry
and full horizon. Candidate selection uses availability/continuity, never outcomes.
Feature warmup rows and actual strategy signal bars are included; controls are not
restricted to non-signals or filtered by indicator thresholds.

Each trial exactly preserves **source month × existing signal-time research session
× direction** counts. Sessions use unchanged config/xauusd_sessions.yaml, fixed UTC
first-match precedence: ASIA [00,08), LONDON [08,13), overlap [13,16), NEW_YORK
[16,21), OFF_SESSION [21,24). Labels are analytical, not execution permissions.
All requested strata have sufficient candidates; **no fallback** was needed.
Sampling is without replacement inside a stratum/trial; independent trials may
reuse candidates. BUY and SELL strata may select the same timestamp. Candidates
and strata are sorted deterministically. Day-by-day, spread-size, volatility and
indicator distributions are not additionally matched; conclusions are conditional
on this specified control design. Overlapping signals/windows remain dependent.

Exactly **1,000 trials for each of six strategy/horizon combinations**, repeated
identically for reproducibility. Repeats are verification, not additional seeds
or seed selection. Seed namespace: `xauusd-g2c4d3-matched-random-v1`. Seed is
SHA256(`namespace|V1-or-V2|horizon|zero-based-trial`) interpreted as a big-endian
integer for Python random.Random.sample. Python version: 3.12.7.
Trial selection hashes and statistics are retained. Decimal observations are summed
as exact integer units of 10^-10, matching stored precision; aggregate divisions
use 60-digit Decimal arithmetic. No price rounding is introduced.

D2 semantics remain unchanged: entry bar is horizon bar 1; 5/10/20 bars cover
25/50/100 minutes. BUY uses ASK open to endpoint BID close; SELL uses BID open
to endpoint ASK close. No day/gap/dataset crossing, shortening or synthetic prices.
Favorable/adverse excursions use D2 nonnegative executable-side extrema.

Random distributions below summarize trial means (not pooled control ticks).
5th/95th percentiles use nearest ranks 50 and 950 of 1,000. Actual empirical
percentile = 100 × (number below actual + half the ties)/1,000. Higher markout,
positive fraction and favorable excursion are higher ranks; lower adverse excursion
is preferable. These are **descriptive ranks, not formal p-values**, confidence
intervals, statistical proof, or independent-sample evidence.

## ALL signals: actual endpoint behavior

| Version | Bars | Eligible / unavailable | Actual mean | Actual median | Actual positive % |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | 3909 / 175 | -0.3612 | -0.4770 | 39.6009 |
| V1 | 10 | 3723 / 361 | -0.4127 | -0.4600 | 41.3645 |
| V1 | 20 | 3374 / 710 | -0.4310 | -0.4600 | 44.8133 |
| V2 | 5 | 3633 / 164 | -0.3509 | -0.4700 | 39.8569 |
| V2 | 10 | 3464 / 333 | -0.3840 | -0.4370 | 41.8591 |
| V2 | 20 | 3147 / 650 | -0.3876 | -0.4300 | 45.2812 |

## Mean-markout distribution — ALL

| Version | Bars | Actual | Random mean | Random median | Random p05 | Random p95 | Actual percentile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | -0.3612 | -0.3255 | -0.3238 | -0.3958 | -0.2600 | 19.7000 |
| V1 | 10 | -0.4127 | -0.3093 | -0.3094 | -0.4059 | -0.2124 | 3.8000 |
| V1 | 20 | -0.4310 | -0.2720 | -0.2709 | -0.4227 | -0.1284 | 4.0000 |
| V2 | 5 | -0.3509 | -0.3231 | -0.3223 | -0.3934 | -0.2547 | 25.1000 |
| V2 | 10 | -0.3840 | -0.3098 | -0.3095 | -0.4134 | -0.2004 | 11.6000 |
| V2 | 20 | -0.3876 | -0.2765 | -0.2772 | -0.4397 | -0.1200 | 10.8000 |

## Positive-markout percentage distribution — ALL

| Version | Bars | Actual | Random mean | Random median | Random p05 | Random p95 | Actual percentile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | 39.6009 | 41.9912 | 41.9800 | 40.7777 | 43.1568 | 0.1000 |
| V1 | 10 | 41.3645 | 44.5127 | 44.5071 | 43.2716 | 45.7158 | 0.0000 |
| V1 | 20 | 44.8133 | 46.5863 | 46.5916 | 45.2282 | 47.8660 | 1.5000 |
| V2 | 5 | 39.8569 | 42.0375 | 42.0589 | 40.8203 | 43.2425 | 0.2000 |
| V2 | 10 | 41.8591 | 44.5196 | 44.4861 | 43.2159 | 45.8718 | 0.1000 |
| V2 | 20 | 45.2812 | 46.5625 | 46.5523 | 45.1541 | 47.8869 | 6.3500 |

## BUY: mean-markout comparison

| Version | Bars | Eligible | Actual mean | Random mean | Random median | p05 | p95 | Actual percentile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | 2053 | -0.3373 | -0.2745 | -0.2738 | -0.3650 | -0.1820 | 13.5000 |
| V1 | 10 | 1962 | -0.3447 | -0.2015 | -0.1998 | -0.3364 | -0.0680 | 4.0000 |
| V1 | 20 | 1763 | -0.2789 | -0.0287 | -0.0256 | -0.2340 | 0.1704 | 2.1000 |
| V2 | 5 | 1923 | -0.3483 | -0.2708 | -0.2718 | -0.3657 | -0.1746 | 9.1000 |
| V2 | 10 | 1839 | -0.3517 | -0.1990 | -0.2029 | -0.3350 | -0.0574 | 3.2000 |
| V2 | 20 | 1650 | -0.2553 | -0.0304 | -0.0326 | -0.2394 | 0.1957 | 3.6000 |

## SELL: mean-markout comparison

| Version | Bars | Eligible | Actual mean | Random mean | Random median | p05 | p95 | Actual percentile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | 1856 | -0.3876 | -0.3820 | -0.3813 | -0.4829 | -0.2842 | 46.6000 |
| V1 | 10 | 1761 | -0.4884 | -0.4294 | -0.4320 | -0.5767 | -0.2792 | 25.1000 |
| V1 | 20 | 1611 | -0.5976 | -0.5383 | -0.5365 | -0.7476 | -0.3297 | 32.4000 |
| V2 | 5 | 1710 | -0.3538 | -0.3820 | -0.3828 | -0.4854 | -0.2769 | 66.8000 |
| V2 | 10 | 1625 | -0.4204 | -0.4352 | -0.4380 | -0.5850 | -0.2783 | 57.4000 |
| V2 | 20 | 1497 | -0.5335 | -0.5477 | -0.5494 | -0.7792 | -0.3087 | 55.5000 |

## Favorable excursions — ALL

| Version | Bars | Actual mean | Random mean | Random median | p05 | p95 | Actual percentile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | 1.6662 | 1.5730 | 1.5742 | 1.5245 | 1.6185 | 100.0000 |
| V1 | 10 | 2.5228 | 2.4295 | 2.4282 | 2.3609 | 2.5014 | 98.4000 |
| V1 | 20 | 3.7940 | 3.7682 | 3.7655 | 3.6639 | 3.8734 | 64.8000 |
| V2 | 5 | 1.6878 | 1.5791 | 1.5789 | 1.5277 | 1.6263 | 100.0000 |
| V2 | 10 | 2.5533 | 2.4340 | 2.4325 | 2.3577 | 2.5063 | 99.7000 |
| V2 | 20 | 3.8453 | 3.7711 | 3.7717 | 3.6552 | 3.8826 | 86.4000 |

## Adverse excursions — ALL

| Version | Bars | Actual mean | Random mean | Random median | p05 | p95 | Actual percentile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 5 | 2.1702 | 2.2066 | 2.2070 | 2.1548 | 2.2564 | 11.2000 |
| V1 | 10 | 3.0436 | 3.0556 | 3.0554 | 2.9846 | 3.1254 | 39.2000 |
| V1 | 20 | 4.3223 | 4.3493 | 4.3498 | 4.2462 | 4.4475 | 32.8000 |
| V2 | 5 | 2.1666 | 2.2103 | 2.2094 | 2.1602 | 2.2637 | 7.9000 |
| V2 | 10 | 3.0420 | 3.0609 | 3.0602 | 2.9802 | 3.1373 | 34.0000 |
| V2 | 20 | 4.3129 | 4.3586 | 4.3577 | 4.2408 | 4.4750 | 23.5000 |

## Interpretation

1. **V1 does not beat its matched-random mean at any fixed horizon.** Mean-markout
   ranks are 19.7, 3.8 and 4.0 percentiles. Positive-markout fractions are also
   below random means at every horizon.
2. **V2 also does not beat its matched-random mean overall.** Mean ranks rise
   to 25.1, 11.6 and 10.8. Its actual-minus-random mean deficit narrows from
   approximately −0.03565/−0.10338/−0.15901 for V1 to
   −0.02775/−0.07419/−0.11116 for V2. This is a modest relative improvement,
   not a positive edge and not merely a claim based on fewer observations.
3. Negative absolute values alone would not prove absent signal information,
   because controls also pay spread. Here both versions are additionally below
   matched random overall, strengthening the descriptive concern on this dataset.
4. **SELL is not particularly weak relative to its controls.** V1 SELL is below
   random means but at 46.6/25.1/32.4 percentiles. V2 SELL is slightly above
   random means, at 66.8/57.4/55.5 percentiles—ordinary ranks, not proof.
   BUY is below controls in both versions; its ranks are V1 13.5/4.0/2.1 and
   V2 9.1/3.2/3.6. Absolute SELL weakness partly reflects its matched control
   environment; it does not justify disabling that direction.
5. Both versions have slightly higher mean favorable excursions and slightly
   lower mean adverse excursions than matched random. Endpoint markouts and
   positive fractions remain worse overall. Path extrema need not coincide with
   endpoint direction, and intrabar extrema do not establish achievable exits.
   No stop, target or management change follows.
6. Month/session/direction matching does not remove serial dependence or all
   confounding. No threshold, new horizon, V3 or production edge is inferred.

## Verification and artifacts

- Exactly matched stratum counts; no replacement within strata and no fallback.
- Every 1,000-trial run repeated with identical selections and statistics.
- Trial-distribution hash: `9365548b49886c8f45aa1eaa2fdedae1658d204f9b137e50fa9368521b98ffac`.
- Report hash: `6e10be5b4a473206d2f82e318e9786f8e5640f2643fbe2c15040fabaf187cb14`.
- Full pytest: **947 passed**; includes exact matching, no replacement, price-blind
  sampling, deterministic replay and percentile conventions. NSE regressions pass.
- Ruff passed; Black passed (177 files); mypy passed (95 source files).
- Alembic current **0008 (head)**; check: no schema drift. No migration.
- One existing Starlette/AnyIO deprecation warning remains.
- No historical data, existing strategies or D2/V1/V2 reports modified.
- Research experiment log updated for the completed D3 study and holdout reservation.
- Git status, working diff and staged diff reviewed; nothing staged or committed.

Reproduce with DATABASE_URL provided securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_xauusd_random.py
```

The JSON contains per-stratum candidate/requested counts, all trial summaries,
selection hashes, actual D2 summaries, side-specific distributions and provenance.

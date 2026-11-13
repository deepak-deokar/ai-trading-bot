# G2C4F1 — structural breakout signal study

New family `xauusd-structural-breakout-v1`. February–April 2024 DEVELOPMENT only:
49 approved source days, 13,524 bars and baseline feature rows, verified against
frozen D2 input hashes before evaluation. No May–July input or outcomes used for
design, tuning or this study. August–October remains LOCKED / UNPROCESSED.

The pre-run experiment log froze the hypothesis: a fresh break beyond recent
one-hour structure may contain more directional information than trend/momentum
entry conditions. Only one lookback and candidate were tested. No profitability,
stop, target, risk sizing, commission, account balance or simulator execution.

## Exact causal rule

Let T be the completed signal bar. Both sides require current spread_close <= 0.75
and relative_spread <= 0.0003. No EMA, RSI or momentum condition.

- BUY: BID close(T) > max BID high(T−12…T−1), AND BID close(T−1) <=
  max BID high(T−13…T−2).
- SELL: ASK close(T) < min ASK low(T−12…T−1), AND ASK close(T−1) >=
  min ASK low(T−13…T−2).

Every structural reference contains **exactly 12 prior bars** and excludes the
bar being tested. Freshness therefore needs 13 continuous prior bars, not a
13-bar price reference. Until that additional prior comparison is available,
NO_TRADE. Consecutive breakout bars do not repeat. A non-breakout bar can rearm a
later fresh event; this is not a permanent lockout or position-management rule.
The previous structural comparison ignores spread-filter eligibility: an earlier
price breakout remains a breakout even if its spread prevented a signal.

All 14 bars (13 prior plus T) must be continuous five-minute observations in the
same dataset/policy, with matching predecessor timestamps. No crossing provider
gaps, research-day/dataset boundaries or excluded dates. Resets inside the chain
reject, while a reset at the earliest reference bar is allowed. Completion and
aware-UTC cutoffs are enforced. Missing spread values return NO_TRADE. Invalid
negative spreads or contradictory simultaneous directions fail explicitly.
These guards are not a broker tradability schedule.

## Signal counts

**653 BUY + 529 SELL = 1182 signals**; 12342 NO_TRADE rows.

| Month/session | BUY | SELL | Total |
| --- | ---: | ---: | ---: |
| 2024-02 | 211 | 164 | 375 |
| 2024-03 | 201 | 154 | 355 |
| 2024-04 | 241 | 211 | 452 |
| ASIA | 211 | 177 | 388 |
| LONDON | 157 | 136 | 293 |
| LONDON_NEW_YORK_OVERLAP | 107 | 86 | 193 |
| NEW_YORK | 153 | 103 | 256 |
| OFF_SESSION | 25 | 27 | 52 |

Session labels use the existing configuration at signal completion. Signal
frequency caused no parameter changes. Structural signals do not require the
longer EMA warmup used by older families.

## Fixed forward markouts

D2/E1 semantics unchanged: BUY enters the next eligible ASK open and ends at BID
close; SELL enters BID open and ends at ASK close. Entry bar counts as bar 1.
Only 5/10/20 bars (25/50/100 minutes) are evaluated. No signal-bar entry, shortened
windows or crossing a gap/day boundary. Endpoints may equal a boundary. Signals
are measured independently, without position blocking. Favorable/adverse excursion
sizes are nonnegative and use executable-side highs/lows, exactly as D2.
All values are raw price units after observed spread, not monetary P&L.

| Bars | Side | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Mean favorable | Mean adverse |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 1142 | 40 | -0.392886 | -0.448500 | 38.616462 | 61.295972 | 1.788730 | 2.315814 |
| 5 | BUY | 633 | 20 | -0.464555 | -0.520000 | 37.282780 | 62.717220 | 1.701204 | 2.340619 |
| 5 | SELL | 509 | 20 | -0.303758 | -0.387000 | 40.275049 | 59.528487 | 1.897580 | 2.284967 |
| 10 | ALL | 1111 | 71 | -0.389484 | -0.497000 | 40.234023 | 59.765977 | 2.571543 | 3.178509 |
| 10 | BUY | 616 | 37 | -0.455375 | -0.518500 | 38.636364 | 61.363636 | 2.442731 | 3.224797 |
| 10 | SELL | 495 | 34 | -0.307487 | -0.470000 | 42.222222 | 57.777778 | 2.731842 | 3.120905 |
| 20 | ALL | 1024 | 158 | -0.402255 | -0.495000 | 44.726562 | 55.273438 | 3.863208 | 4.489788 |
| 20 | BUY | 557 | 96 | -0.326077 | -0.480000 | 45.780969 | 54.219031 | 3.823889 | 4.524004 |
| 20 | SELL | 467 | 62 | -0.493113 | -0.570000 | 43.468951 | 56.531049 | 3.910105 | 4.448979 |

Any positive/negative percentage remainder is zero markout. JSON includes exact
Decimal summaries, zero counts and unavailable reasons.

## Matched random benchmark

Unchanged D3 methodology: 1,000 deterministic trials per horizon; exact
month × existing signal-time session × direction strata. Sample without
replacement within strata, independently across trials. All horizon-eligible
bars, including signal and warmup bars, are candidates. Both directions may use
the same timestamp independently. No future-outcome filtering or stratum fallback.

Seed = SHA256(existing D3 namespace | new candidate name | horizon | trial index),
converted to an integer for Python Random.sample. p05/p95 are nearest-rank
percentiles; actual percentile = 100 × (less + 0.5 × ties) / 1,000. These are
descriptive comparisons, not formal significance or independence-adjusted tests.

| Bars | Side | Actual mean | Random mean | Random p05 | Random p95 | Actual percentile |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | -0.392886 | -0.325537 | -0.461594 | -0.185286 | 21.400000 |
| 5 | BUY | -0.464555 | -0.294112 | -0.476773 | -0.108404 | 5.900000 |
| 5 | SELL | -0.303758 | -0.364617 | -0.570845 | -0.181737 | 67.100000 |
| 10 | ALL | -0.389484 | -0.307201 | -0.505489 | -0.100918 | 24.600000 |
| 10 | BUY | -0.455375 | -0.235230 | -0.478830 | 0.025018 | 7.600000 |
| 10 | SELL | -0.307487 | -0.396765 | -0.693313 | -0.107202 | 68.000000 |
| 20 | ALL | -0.402255 | -0.273510 | -0.570314 | -0.003531 | 23.800000 |
| 20 | BUY | -0.326077 | -0.108927 | -0.493285 | 0.260018 | 18.400000 |
| 20 | SELL | -0.493113 | -0.469812 | -0.910116 | -0.010683 | 47.400000 |

| Bars | Side | Actual positive % | Random mean positive % | Positive-rate percentile |
| ---: | --- | ---: | ---: | ---: |
| 5 | ALL | 38.616462 | 41.895447 | 0.600000 |
| 5 | BUY | 37.282780 | 42.913744 | 0.100000 |
| 5 | SELL | 40.275049 | 40.629077 | 42.550000 |
| 10 | ALL | 40.234023 | 44.534023 | 0.300000 |
| 10 | BUY | 38.636364 | 46.517208 | 0.000000 |
| 10 | SELL | 42.222222 | 42.066061 | 53.100000 |
| 20 | ALL | 44.726562 | 46.574609 | 11.050000 |
| 20 | BUY | 45.780969 | 48.324955 | 12.050000 |
| 20 | SELL | 43.468951 | 44.486938 | 32.750000 |

## Excursion balance versus frozen old families

Ratios below are mean favorable / mean adverse excursion; higher is a more
favorable descriptive balance, not an exit rule or realized payoff ratio.
Different signal populations prevent interpreting this as a paired causal test.
Only frozen February–April summaries are used for this comparison.

| Bars | Side | Breakout | V1 | V2 | E1 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 5 | ALL | 0.772398 | 0.767782 | 0.779012 | 0.804707 |
| 5 | BUY | 0.726818 | 0.755277 | 0.753175 | 0.833902 |
| 5 | SELL | 0.830463 | 0.780930 | 0.806889 | 0.774112 |
| 10 | ALL | 0.809041 | 0.828888 | 0.839353 | 0.911972 |
| 10 | BUY | 0.757483 | 0.812936 | 0.807118 | 1.000642 |
| 10 | SELL | 0.875337 | 0.846395 | 0.875814 | 0.821922 |
| 20 | ALL | 0.860443 | 0.877769 | 0.891586 | 0.913962 |
| 20 | BUY | 0.845244 | 0.881444 | 0.886308 | 1.053850 |
| 20 | SELL | 0.878877 | 0.873741 | 0.897458 | 0.767362 |

## Screening interpretation

Structural breakout does **not** beat matched random consistently in this screen.
ALL means are below random at 5/10/20 bars, with percentiles 21.4/24.6/23.8.
All group means and medians remain negative after observed spread.

BUY underperforms at every horizon (5.9/7.6/18.4 percentiles). SELL is modestly
above random at 5 and 10 bars (67.1/68.0), but below at 20 (47.4). These ordinary
percentiles do not establish a robust edge; there is no consistent SELL advantage
across the fixed horizons. SELL's positive rate is only slightly above random at
10 bars and below it at the other two. ALL and BUY positive rates are below random
throughout. Signal frequency is not evidence of success.

Favorable/adverse balance remains below one for every group/horizon. ALL is
slightly above V1 at 5 bars but below V2/E1; at 10/20 it is below all three old
families. BUY is below every old family across all horizons. SELL's balance is
better than all three at 5, better than V1/E1 but marginally below V2 at 10, and
better than V1/E1 but below V2 at 20. These are mixed population comparisons, not
proof of improved realized outcomes or a reason to select a horizon retrospectively.

No parameter changed, no alternative candidate was created and no account backtest
was run. The results do not establish consistent directional information beyond
the matched controls in this development sample. This does not prove what another
period would do; May–July was not used and August–October remains locked.

## Determinism and no-lookahead

Two complete runs reloaded and reverified development inputs, then recomputed
signals, markouts and 1,000 trials per horizon. Results and decision/observation/
trial hashes were identical. The compact JSON stores summary distributions,
matching counts, deterministic hashes and source/report/code/config fingerprints;
no huge raw trial arrays are committed.

The detector only receives current and prior rows. Tests verify future mutations
cannot alter an earlier signal. Existing markout tests verify mutations strictly
after a horizon cannot change that completed measurement. Prices *inside* a
markout's future horizon necessarily affect that diagnostic; they never feed
back into signal construction. Strict-side/equality checks, exclusion of T from
its references, freshness, continuity and completion guards are tested offline.

Study hash: `105e80095e3d55b4106f0e22ec8c56f89cf6b805387a626026b46fbcb3c013c9`.

Report content hash: `5eb72e83e3b9b282fa708fc3df4796e7cefd180badd6cd8007bae62d428e72a6`.


Reproduce with DATABASE_URL supplied securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/study_xauusd_breakout.py
```

Database access is read-only. No migration or dependencies. Existing V1/V2/E1
source and reports, May–July reports/policy and earlier data artifacts remain
unchanged. Only the experiment log is appended alongside the new candidate,
runner, tests and reports. Old untracked sensitivity reports remain untouched.
No commit. No further candidate or profitability run is authorized here.

## Checks actually run

- Focused breakout and forward-markout tests: **20 passed**.
- Full `pytest -q`: **1,003 passed**, one existing Starlette warning. Includes
  existing V1/V2/E1, random determinism, feature causality and NSE regressions.
- Ruff passed; Black passed (190 files); mypy passed (97 source files).
- Alembic: **0008 head**, no schema drift. No migration.
- Protected-file hashes confirm existing V1/V2/E1, validation reports, source
  and configuration unchanged, except the intended experiment-log append.
- Git status, working/staged diffs and whitespace checks reviewed; no commit.

Created: candidate module, study runner, offline tests and this Markdown/JSON
pair. Updated the experiment log. No dependency added.

Recommended commit: `research: screen frozen XAUUSD structural breakout signals`.

Stopped at G2C4F1. No tuning, profitability simulation or further candidate.

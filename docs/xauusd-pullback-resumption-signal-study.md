# G2C4E1 — pullback-resumption signal study

New family: `xauusd-pullback-resumption-v1`. Development/in-sample screening only.
The hypothesis was recorded before the run: a broader trend plus a short-term
pullback and resumption may time continuation entries better. One fixed candidate,
no optimization, no profitability/account simulation, no stops, targets, sizing
or commissions. V1/V2 and all earlier reports remain unchanged.

## Frozen rules and causality

BUY: EMA12 > EMA26, momentum_12 > 0, previous momentum_3 <= 0,
current momentum_3 > 0, spread_close <= 0.75, relative_spread <= 0.0003.
SELL: EMA12 < EMA26, momentum_12 < 0, previous momentum_3 >= 0,
current momentum_3 < 0, with the same spread limits. No RSI or EMA-difference filter.

Only current and immediately previous completed feature rows are read. Missing
features/predecessors, a gap, reset, different dataset or policy prevent comparison.
Dataset keys delimit source days, including their UTC-midnight tail. UTC-aware
availability is enforced. Repeated same-sign momentum does not emit another signal.
Earliest hypothetical entry is the next contiguous eligible bar opening.

Approved February–April 2024 source days only: 49 days, 13,524 bars. Existing bar
and feature content hashes were checked against D2 before measurement. No holdout
performance was examined. The April 30 source day's existing UTC tail is part of
that approved source day, not a new May dataset.

## Signal counts

547 BUY + 479 SELL = **1,026 signals**; 12,498 NO_TRADE rows.

| Month/session | BUY | SELL | Total |
| --- | ---: | ---: | ---: |
| 2024-02 | 182 | 158 | 340 |
| 2024-03 | 179 | 123 | 302 |
| 2024-04 | 186 | 198 | 384 |
| ASIA | 145 | 131 | 276 |
| LONDON | 139 | 125 | 264 |
| LONDON_NEW_YORK_OVERLAP | 79 | 81 | 160 |
| NEW_YORK | 169 | 119 | 288 |
| OFF_SESSION | 15 | 23 | 38 |

Session labels use the unchanged configuration at signal completion. They are
research labels, not tradability rules. Counts did not cause any rule changes.

## Forward measurements

D2 infrastructure is unchanged: BUY enters next ASK open and ends at BID close;
SELL enters next BID open and ends at ASK close. Entry bar counts as horizon bar 1.
Horizons are 5/10/20 bars (25/50/100 minutes), never shortened to fit a gap or
research boundary. Endpoints may equal a boundary but cannot cross it. All signals
are measured independently; there is no position blocking. MFE/MAE are nonnegative
executable-side excursion sizes. Values below are raw price units, not account P&L;
spread is reflected, but no commissions or other account costs are modeled.

| Bars | Side | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Mean MFE | Mean MAE |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 981 | 45 | -0.273932 | -0.387000 | 42.915392 | 57.084608 | 1.662045 | 2.065403 |
| 5 | BUY | 518 | 29 | -0.132739 | -0.240500 | 44.980695 | 55.019305 | 1.669125 | 2.001585 |
| 5 | SELL | 463 | 16 | -0.431896 | -0.520000 | 40.604752 | 59.395248 | 1.654123 | 2.136801 |
| 10 | ALL | 937 | 89 | -0.131193 | -0.280000 | 45.570971 | 54.322305 | 2.645678 | 2.901052 |
| 10 | BUY | 498 | 49 | 0.217478 | -0.075000 | 48.594378 | 51.204819 | 2.752032 | 2.750267 |
| 10 | SELL | 439 | 40 | -0.526724 | -0.471000 | 42.141230 | 57.858770 | 2.525030 | 3.072103 |
| 20 | ALL | 850 | 176 | -0.352022 | -0.548500 | 43.411765 | 56.470588 | 3.936354 | 4.306913 |
| 20 | BUY | 455 | 92 | 0.265121 | -0.190000 | 47.032967 | 52.967033 | 4.338901 | 4.117191 |
| 20 | SELL | 395 | 84 | -1.062909 | -0.930000 | 39.240506 | 60.506329 | 3.472661 | 4.525453 |

Zero markouts account for any positive/negative percentage remainder. Exact Decimal
values, unavailability reasons and individual observations are retained in JSON.

## Matched random benchmark

Unchanged D3 methodology: exact month × existing signal-time session × direction,
without replacement within each stratum and independent trials. All horizon-eligible
candidate bars are available, including signal and feature-warmup bars. Opposite
directions may sample the same timestamp. There is no outcome filtering or fallback.
1,000 trials per horizon; seed is SHA256 of the existing D3 namespace, new strategy
name, horizon and zero-based trial index, passed to Python Random.sample. Each trial
series is repeated and compared exactly. p05/p95 use nearest rank; percentile is
100 × (less + 0.5 × ties) / 1000. These are descriptive percentiles, not p-values.
Overlapping windows and repeated exploration limit inferential interpretation.

| Bars | Side | Actual mean | Random mean | Random p05 | Random p95 | Actual percentile |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | -0.273932 | -0.317650 | -0.454945 | -0.172441 | 69.700000 |
| 5 | BUY | -0.132739 | -0.263957 | -0.464100 | -0.080994 | 87.100000 |
| 5 | SELL | -0.431896 | -0.377721 | -0.599510 | -0.161914 | 35.100000 |
| 10 | ALL | -0.131193 | -0.301053 | -0.503823 | -0.093699 | 91.800000 |
| 10 | BUY | 0.217478 | -0.190374 | -0.454052 | 0.088918 | 98.900000 |
| 10 | SELL | -0.526724 | -0.426606 | -0.738497 | -0.119738 | 30.000000 |
| 20 | ALL | -0.352022 | -0.240064 | -0.559733 | 0.058040 | 26.600000 |
| 20 | BUY | 0.265121 | -0.002343 | -0.423743 | 0.423259 | 85.200000 |
| 20 | SELL | -1.062909 | -0.513893 | -1.000813 | -0.040481 | 2.700000 |

| Bars | Side | Actual positive % | Random mean % | Random p05 % | Random p95 % | Actual percentile |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 5 | ALL | 42.915392 | 42.073394 | 39.551478 | 44.648318 | 71.500000 |
| 5 | BUY | 44.980695 | 43.242857 | 39.575290 | 46.525097 | 77.200000 |
| 5 | SELL | 40.604752 | 40.765011 | 36.933045 | 44.492441 | 46.450000 |
| 10 | ALL | 45.570971 | 44.498079 | 41.942369 | 47.065101 | 77.000000 |
| 10 | BUY | 48.594378 | 46.719880 | 43.172691 | 50.000000 | 79.550000 |
| 10 | SELL | 42.141230 | 41.977677 | 38.268793 | 45.785877 | 52.950000 |
| 20 | ALL | 43.411765 | 46.861059 | 44.352941 | 49.529412 | 2.200000 |
| 20 | BUY | 47.032967 | 48.758901 | 44.835165 | 52.527473 | 22.900000 |
| 20 | SELL | 39.240506 | 44.674937 | 40.506329 | 48.354430 | 1.900000 |

## Frozen old-family context

| Bars | Group | V1 mean | V2 mean | Pullback mean |
| ---: | --- | ---: | ---: | ---: |
| 5 | ALL | -0.361193 | -0.350897 | -0.273932 |
| 5 | BUY | -0.337292 | -0.348270 | -0.132739 |
| 5 | SELL | -0.387632 | -0.353850 | -0.431896 |
| 10 | ALL | -0.412679 | -0.383962 | -0.131193 |
| 10 | BUY | -0.344715 | -0.351730 | 0.217478 |
| 10 | SELL | -0.488401 | -0.420440 | -0.526724 |
| 20 | ALL | -0.431040 | -0.387617 | -0.352022 |
| 20 | BUY | -0.278875 | -0.255253 | 0.265121 |
| 20 | SELL | -0.597562 | -0.533509 | -1.062909 |

The new family's ALL means are less negative than V1/V2 at all three horizons,
but this is a comparison of different signal populations, not paired proof of an
improvement. Against its own matched controls, ALL is above the random mean at
5 and 10 bars and below it at 20; no consistent overall advantage is established.

BUY carries the favorable relative pattern: mean-markout percentiles are 87.1,
98.9 and 85.2. Only BUY at 10 bars exceeds the random 95th percentile. Its 10/20-bar
means are positive but all three medians remain negative. Its 20-bar positive-rate
percentile is only 22.9. Thus larger positive outcomes, not a broadly higher hit
rate across horizons, matter to those averages.

SELL is below its matched-random mean at every horizon; the 20-bar mean percentile
is 2.7 and positive-rate percentile 1.9. BUY MFE/MAE improve from 1.669/2.002 at
5 bars to 2.752/2.750 at 10 and 4.339/4.117 at 20. ALL MFE remains below MAE at
every horizon; SELL MFE is also below MAE throughout. Compared with the old family,
ALL MFE/MAE balance is better, particularly at 10 bars, but remains unfavorable.

Conclusion: mixed screening evidence, with a narrower BUY-side finding worth
recording, not validation of this two-sided candidate or a trading edge. Lower
signal count is not evidence of success. No side was removed and no rule was tuned.
No full simulator run or new candidate follows this checkpoint.

## Verification and reproduction

- 971 tests passed, including 20 new candidate cases and existing markout,
  deterministic random, V1/V2 and NSE regressions. One existing Starlette warning.
- Ruff passed; Black passed (181 files); mypy passed (96 source files).
- Alembic 0008 (head), no schema drift; no migration or research database writes.
- Frozen V1/V2 signal counts and all 12,252 D2 markout observations reproduced.
- Current/previous-only evaluation, completed-row guard, dataset/gap resets and
  future-mutation test preserve no-lookahead. Future bars are used only by the
  explicitly forward-looking diagnostic after signal generation.
- Each random trial series reproduced exactly. Two full study runs also produced
  identical canonical content hash `02df28e13328e3a92850e6d005a4c389c3ee6686ea18c1cf2e17b05928c40314`.
  All protected earlier reports remained byte-identical.

Run with DATABASE_URL supplied securely:
`PYTHONPATH=src .venv/bin/python scripts/study_xauusd_pullback.py`.
The runner reads approved data in PostgreSQL read-only mode and writes only this
study's JSON. It does not write earlier reports. Markdown is an interpretive report.

New files: candidate module, offline tests, signal-study runner and these two
reports. The experiment log is appended. Pre-existing D4 work and the two old
untracked $3,000 reports remain untouched. Nothing is staged or committed.

Recommended commit: `feat: study frozen XAUUSD pullback resumption signals`.

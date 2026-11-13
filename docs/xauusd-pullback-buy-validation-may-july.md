# G2C4E2C — first unseen BUY validation, May–July 2024

**NO VALIDATION SUPPORT** under the predeclared PRIMARY 10-bar rule.
This was the first strategy-performance inspection of this validation partition.
No rule, threshold, horizon hierarchy or candidate changed after results. No
SELL alternative was evaluated. No stop/target, sizing, commission, account
simulation or profitability calculation. August–October remains locked and
unprocessed. May–July has now been inspected and cannot be described as an unused
validation sample for a future tuned candidate.

## Frozen scope and rule

E2B identity verified before evaluating any row:
`811d9f5db6bf55d128147b2247197d2364e31b185d005c69b33b2349ffa589c5`.
All 50 days / 13,800 bid/ask bars / 13,800 baseline feature rows matched their
frozen content hashes; each repeated run reloaded and reverified the inputs.
Only May–July source dates were queried. Source-day UTC tails remain part of
those fixed-offset source days, not an authorization to read another archive.

Strategy family: `xauusd-pullback-resumption-v1`, BUY arm only. EMA12 > EMA26,
momentum_12 > 0, previous completed momentum_3 <= 0, current momentum_3 > 0,
spread_close <= 0.75 and relative_spread <= 0.0003. No RSI or extra filter.
The analysis runner projects the existing BUY predicate and continuity guards;
it never calls the two-sided evaluator. An AST regression check ties the BUY
predicate directly to frozen E1's expression. The E1 module remains unchanged.

The experiment log recorded the hypothesis and interpretation before evaluation:
10 bars PRIMARY; 5 and 20 supporting. Strong support requires mean > 0 AND
mean-markout percentile >=95. Partial means above the random mean but failing a
strong condition; otherwise no support. Negative executable movement is not a
positive edge, even if relatively above random. These are descriptive rules, not
formal statistical significance. Neither supporting horizon replaces the primary.

## BUY counts

**577 BUY signals**.

| Month/session | BUY |
| --- | ---: |
| 2024-05 | 177 |
| 2024-06 | 195 |
| 2024-07 | 205 |
| ASIA | 135 |
| LONDON | 140 |
| LONDON_NEW_YORK_OVERLAP | 112 |
| NEW_YORK | 156 |
| OFF_SESSION | 34 |

Existing session labels are assigned at signal completion, using the unchanged
UTC configuration. They are analytical labels, not broker permissions.

## Executable markouts

D2/E1 measurement is unchanged. Signal uses completed T and its immediately
previous continuous completed row. Entry is T+1 ASK open; endpoint is BID close;
markout = endpoint BID − entry ASK. Entry bar counts as horizon bar 1, so 5/10/20
bars represent 25/50/100 minutes. No signal-bar entry, shortened horizons, gap
bridging, excluded-date bridging or crossing the research-day end. Endpoint may
equal a boundary. Overlapping signals are measured independently with no position
blocking. Favorable/adverse excursions use the same BID highs/lows and nonnegative
floor as D2. These are raw price units after observed spread, not monetary P&L.

| Bars | Eligible | Unavailable | Mean | Median | Positive % | Negative % | Mean favorable | Mean adverse |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 559 | 18 | -0.477007 | -0.414000 | 43.291592 | 56.529517 | 1.652417 | 2.508576 |
| 10 | 529 | 48 | -0.344745 | -0.387000 | 44.801512 | 55.198488 | 2.593764 | 3.453819 |
| 20 | 477 | 100 | -0.554895 | -0.381000 | 46.121593 | 53.878407 | 3.955662 | 4.959111 |

One zero markout at 5 bars accounts for its percentage remainder.

- 5 bars unavailable reasons: `{'DISCONTINUITY': 13, 'SIGNAL_AT_BOUNDARY': 1, 'INCOMPLETE_HORIZON': 4}`.
- 10 bars unavailable reasons: `{'DISCONTINUITY': 25, 'INCOMPLETE_HORIZON': 22, 'SIGNAL_AT_BOUNDARY': 1}`.
- 20 bars unavailable reasons: `{'DISCONTINUITY': 54, 'INCOMPLETE_HORIZON': 45, 'SIGNAL_AT_BOUNDARY': 1}`.

## Matched random comparison

Exactly 1,000 trials per horizon, matched by source month × existing signal-time
session; BUY for every candidate. The pool uses identical next-bar/horizon/gap/day
availability checks. All eligible opportunities, including warmup rows and actual
signal times, may be sampled. No future outcome filtering. Sampling is without
replacement within strata, independently across trials, with no fallback.
The unchanged benchmark helper's empty opposite-direction accumulator has no
observations and is neither evaluated as an alternative nor reported.

Seed: SHA256(existing D3 namespace | frozen E1 strategy name | horizon | trial),
converted to an integer for Python Random.sample. p05/p95 use nearest rank;
empirical percentile = 100 × (less + 0.5 × equal) / 1,000. Dependence between
observations and overlapping windows limits inferential interpretation.

| Bars | Actual mean | Random mean | Random median | Random p05 | Random p95 | Actual percentile |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | -0.477007 | -0.305783 | -0.302775 | -0.521930 | -0.095381 | 8.700000 |
| 10 | -0.344745 | -0.218556 | -0.214974 | -0.540138 | 0.079905 | 26.100000 |
| 20 | -0.554895 | -0.069526 | -0.075831 | -0.497310 | 0.364042 | 3.600000 |

| Bars | Actual positive % | Random mean positive % | Positive-rate percentile |
| ---: | ---: | ---: | ---: |
| 5 | 43.291592 | 43.975850 | 36.300000 |
| 10 | 44.801512 | 47.156900 | 15.100000 |
| 20 | 46.121593 | 49.875472 | 3.400000 |

The primary 10-bar mean is negative and below random, failing both strong-support
conditions. Both supporting means are also negative and below random. At 20 bars
the actual mean is below the random 5th percentile. Positive-markout rates are
below matched random at every horizon. Mean favorable excursion is below mean
adverse excursion throughout. Excursions were not used to construct exits.

## Frozen development context — samples remain separate

| Bars | Development BUY mean | Validation BUY mean | Development percentile | Validation percentile |
| ---: | ---: | ---: | ---: | ---: |
| 5 | -0.132739 | -0.477007 | 87.1 | 8.7 |
| 10 | 0.217478 | -0.344745 | 98.9 | 26.1 |
| 20 | 0.265121 | -0.554895 | 85.2 | 3.6 |

The positive development means at 10/20 bars did not reproduce in direction or
magnitude. The 5-bar mean remains negative and is more unfavorable. The prior
above-random BUY tendency did not reproduce at any of the fixed horizons. This
is evidence against the predeclared validation hypothesis on this sample, not a
proof that all future periods must behave the same way. No development and
validation observations were pooled. No tuning, alternative side, new candidate
or profitability backtest follows these results.

## Reproducibility, causality and verification

Two full runs independently reloaded and hash-verified E2B, then recomputed all
BUY decisions, observations, matching strata and 1,000 trials per horizon.
Results and deterministic hashes matched exactly. Compact JSON retains summary
distributions, pool/stratum counts and hashes, not raw trial arrays.

Study hash: `531d43b1f632adbd68c3f7ce5c5bb5160d686c3f98661c5f06aa34365e9f9f98`.

Report content hash: `98d7db7993ff048741eb2d413f07b8705a33c644ff70400020e8a0ed2bfa7720`.


Current/previous-only evaluation, UTC completion cutoffs, dataset/policy identity
checks and gap resets are retained. Future-row mutation leaves earlier signals
unchanged; premature and naive cutoffs reject. Future observations are used only
for the explicitly forward-looking diagnostic after the signal is fixed.

Run with DATABASE_URL supplied securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/validate_xauusd_pullback_buy.py
```

The runner uses read-only PostgreSQL connections. No migration or dependencies.
Frozen development reports, E1, E2A/E2B and source/configuration are unchanged;
only the experiment log is appended alongside this new script, tests and reports.
The old untracked sensitivity reports remain untouched. Nothing committed.

Actually run: **994 tests passed**, including 13 new BUY-only/interpretation
checks and existing feature, markout, random, XAUUSD and NSE regressions; one
existing Starlette warning. Ruff passed; Black passed (187 files); mypy passed
(96 source files). Alembic current: **0008 head**; check: no schema drift.
Working/staged diffs, Git status and whitespace checks reviewed. No commit.

Recommended commit: `research: validate frozen pullback BUY signals on May-July`.

Stopped at G2C4E2C. No profitability simulation or holdout inspection.

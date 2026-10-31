# XAUUSD G2C2A — versioned HistData research gap policy

This policy accepts observed HistData research patterns only. It is not an MT5
broker schedule, execution permission, causal explanation of closures, or a
strategy-readiness certification. No data is downloaded or persisted by it.

## Explicit configuration

`config/histdata_xauusd_gap_policy_v1.yaml` defines
`histdata-xauusd-research-gap-v1`. The immutable `ProviderGapPolicy` contains typed
segments, UTC clock ranges, evidence and explicit date exclusions. Nested models
are frozen and collections are tuples. Overlapping date segments, duplicate segment
IDs, overlapping missing ranges and invalid five-minute clock labels are rejected.
Each segment is restricted to its archive month. Dates are inclusive:

| Dates | Allowed missing opening labels (UTC) |
| --- | --- |
| January 2–31, 2024 | 22:00–22:55 |
| February 1–29, 2024 | 22:00–22:55 |
| March 4–7, 2024 | 22:00–22:55 |
| March 11–27, 2024 | 21:00–21:55 |
| April 1–30, 2024 | 22:00–22:55 |

Only Monday–Thursday dates can qualify. Explicit holiday/unexplained exclusions
include January 1/12/15, February 19 and March 28/29. A future externally identified
holiday or unexplained day can also be supplied as `day_type`; any non-NORMAL value
rejects it. Friday/weekend rejection is unconditional, even if its missing set
were to match. No-data days never qualify. Dates outside segments cannot inherit
a neighboring pattern.

April's return to 22:00 is represented explicitly because that is what the evidence
shows under fixed UTC−05:00 parsing. No DST correction or universal maintenance
rule is inferred. Clock labels are UTC and align to five minutes. The research day
is fixed at [05:00 UTC, next 05:00 UTC); a clock below 05:00 refers to the next UTC
date. Ranges may cross midnight within that research day, but not its 05:00 boundary.
Missing endpoints are inclusive opening labels, not precise tick-outage endpoints.

## Pure evaluation

```python
from datetime import date
from pathlib import Path
from trading_bot.data.gap_policy import evaluate_gap_policy, load_gap_policy

policy = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
# coverage is a DailyCoverage created from validated observed QuoteBars and a
# QuoteDataset, e.g. using existing daily_coverage(dataset, bars).
result = evaluate_gap_policy(date(2024, 1, 16), coverage, policy)
print(result.status, result.reason, result.eligible)
```

The evaluator accepts a source date, coverage (including dataset provenance),
policy, and optional explicit `DayType`. It performs no database or network access.
It returns immutable `GapEligibility`: typed status, machine-readable reason,
source date, dataset key, policy version/content key and matched segment ID.

Evaluation order is deterministic: check dataset identity and source-day bounds;
validate bin accounting, missing timestamps, observed endpoints and tick counts;
reject no data; reject excluded day types/dates; require a segment; verify its
archive/processing provenance; compare the missing set. Typed statuses are:

- `ELIGIBLE_UNDER_RESEARCH_POLICY`: exact accepted missing set.
- `NO_MATCHING_POLICY_SEGMENT`: date not evidenced.
- `MISSING_SET_MISMATCH`: fewer accepted missing bins, including no missing bins.
- `UNEXPECTED_GAPS`: one or more missing bins outside the accepted set.
- `EXCLUDED_DAY_TYPE`: Friday/weekend, configured exclusion or caller classification.
- `NO_DATA`: consistent coverage with no valid observed bars.
- `PROVENANCE_MISMATCH`: wrong dataset identity, source date/bounds or evidence binding.
- `INVALID_COVERAGE`: inconsistent counts/endpoints, duplicate or invalid missing bins.

Every eligible day must match the entire allowed missing set. A subset is not
silently accepted; a superset cannot learn new exceptions. Existing
`research_usable`, `classification`, `unexpected_gaps` and old accepted-pattern
flags do not grant eligibility under the new policy. Evaluation recomputes the
comparison without modifying coverage, bars, or the G2B2 coverage implementation.

## Provenance and limits

Provider, canonical/provider symbols, interval and exact timezone descriptor must
match. Dataset key must match its embedded manifest; date, source month and UTC
bounds must agree. Segment evidence binds archive SHA-256, normalization version
and aggregation version. Evidence additionally records report path, declared
report version and exact report-file SHA-256. January references G2B2C; February–
April reference G2C1. Those analysis documents, not causal closure claims, support
acceptance. Report bytes are pinned and checked by offline tests; evaluation does
not read report files or rehash raw archives. Upstream acquisition must truthfully
supply checksum/provenance and validated bars.

A deterministic `policy_key` hashes the entire canonical JSON policy, including
version and evidence; changing any content changes the key. This prevents a reused
human version string from obscuring changed policy content. Changes to the pinned
reports require explicit policy review/update. No migration or dataset backfill.

This is a five-minute coverage gate only: it cannot detect omitted ticks within
occupied bars, verify claimed provenance against raw data, or authenticate a broker
schedule. Callers must supply trustworthy validated observations and disclose other
known day exclusions. No automatic holiday calendar or policy extrapolation exists.
G2C2B, February–April persistence, strategies and backtester changes are out of scope.

## Verification actually run

- Full `pytest -q`: **718 passed**, no skips; 35 new policy cases and the previous
  683 cases, including G2B2 coverage and NSE/backtester regressions. One existing
  Starlette/AnyIO deprecation warning.
- `ruff check .`: passed.
- `black --check .`: passed, 131 files unchanged.
- `mypy`: passed, 78 source files.
- `alembic current`: **0007 (head)**; `alembic check`: no schema drift.
- Git status, working diff, staged diff and whitespace reviewed: four new files,
  no existing files modified, nothing staged or committed.

The normal test suite uses disposable database test schemas; the policy itself
has no persistence calls and no February–April import was run. No migration or
dependency change. Existing January bars were not modified by this checkpoint.

Recommended commit: `feat: add versioned HistData research gap policy`.

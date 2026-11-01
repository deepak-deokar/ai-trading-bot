# XAUUSD G2C3C — approved baseline feature persistence

Only `xauusd-baseline-features-v1` is generated, from the existing policy-approved
February–April 2024 source datasets. No raw archive parsing, downloads, indicators,
labels, strategies, ML, execution-backtester or MT5 changes. No G2C4 work.

## Storage decision and migration

Existing NSE `feature_values` stores float64-derived numbers in JSON, and its
FeatureRow API explicitly requires float values. Reusing that API would degrade
Decimal values or obscure semantics. Migration **0008** therefore adds only
`research_feature_bars`, leaving NSE feature storage intact.

The primary key is (source dataset key, bar opening timestamp, feature version).
A composite foreign key references the actual `bid_ask_bars` row. Columns include
canonical symbol, interval, availability timestamp, feature dataset key and JSONB
payload. An index supports symbol/version/time selection. The payload round-trips
the exact typed G2C3B row, including original bid/ask input, reset reason, named
values and unavailable reasons. Decimal values are serialized as decimal strings,
not JSON floats; unavailable values are JSON null, not zero or text "None".
The repository decodes with Pydantic's JSON-mode Decimal validation. No precision
is lost from G2C3B's deterministic 50-digit arithmetic. These payload values require
Decimal-aware application decoding, not SQL casts to floating point.

Upgrade creates the new table/index/FK. Downgrade refuses a nonempty feature table;
empty downgrade/re-upgrade and no drift are tested in disposable schemas. Readiness
revision and existing migration-head test assertions advance to 0008. No other
NSE behavior is changed.

## Approval, scope and reproducibility

`ResearchFeatureRepository.generate(dataset, policy)` reads persisted source bars,
locks them for sharing during the transaction, rechecks G2C3A policy approval, then
calls the unchanged G2C3B engine. Per-day advisory locks serialize feature writers.
Callers cannot submit arbitrary precomputed feature values or an approval flag.
Unbound/excluded datasets fail before insertion. Scope selection belongs to the
bounded script, which reads existing quote-import manifests, deduplicates by source
dataset identity, verifies their identities, restricts to the configured policy and
February–April, and preflights every day's policy/feature calculation before writes.

The computed scope must match 16/15/18 days and 13,524 input/output rows; those are
discrepancy checks, not insertion selection rules. First persistence pass generates
all approved days; a second full pass regenerates from persisted source bars. It
must insert zero rows and preserve all content identities. Retrieved rows are then
hashed and compared against generated rows. No excluded source identities may appear
in the resulting table. Existing source bars and NSE feature tables are snapshotted
and verified unchanged, including January records.

Each day's deterministic manifest includes the full source manifest and dataset
key, policy identity, feature-set/engine version, declared input semantics version
`g2c3a-research-input-v1`, source/output counts, mathematical content hash, warmup
statistics and dataset/discontinuity resets. Its hash is the feature dataset key.
A deterministic aggregate identity hashes the sorted per-day identities. Generation
timestamp and run UUID live in the audit envelope, outside all content identities.
Successful attempts are recorded via existing `system_events` provenance, including
idempotent attempts; the report contains both passes.

Existing rows must match regenerated payloads, metadata and content identity exactly.
Different content, provenance or incomplete membership raises FeatureError. No
upsert overwrites historical values. Atomicity is per source day: failure rolls back
that day's rows and audit; earlier days remain resumable. Audit-write failure after
row insertion is explicitly tested for rollback.

## Query and semantics

`get_rows` requires source dataset key, canonical symbol, feature version, start,
end and as_of. UTC timestamps must be aware. Results are oldest to newest, with
opening timestamps in [start,end) and availability <= as_of. Requiring the source
identity prevents unintended mixing of data selections. Wrong version/source/symbol
queries do not silently return another dataset. This is a repository API only,
not a strategy-facing endpoint.

Warmup rows exist for every valid input bar. None values and WARMUP/GAP_WARMUP reasons
survive storage. Each dataset invocation resets the engine, and each accepted daily
gap still causes its own discontinuity reset. There is no fill, compressed gap or
state transfer between source days. The feature formulas remain those of G2C3B.
No future targets are created. Existing no-lookahead regression tests remain in the
full suite.

## Reproduction and limitations

With development DATABASE_URL securely configured, run:

```sh
PYTHONPATH=src .venv/bin/python scripts/persist_xauusd_features.py
```

The script uses persisted manifests and bars only. It writes the bounded approved
feature dataset twice for idempotency verification, then records compact evidence
in `docs/xauusd-baseline-feature-persistence.json`. A stopped/failed run can leave
prior successful days committed; per-day events remain available even if the final
whole-scope report was not written. Storage is not a general dataset-versioning
platform. Eligibility remains retrospective research selection and does not prove
broker schedules or strategy performance. A different engine/input semantics
requires explicit version review. No SQL float conversion is supported or implied.

## Measured full-dataset result

| Source month | Approved days | Input bars | Feature rows | Rows with unavailable values | Discontinuity resets |
| --- | ---: | ---: | ---: | ---: | ---: |
| February | 16 | 4,416 | 4,416 | 800 | 16 |
| March | 15 | 4,140 | 4,140 | 750 | 15 |
| April | 18 | 4,968 | 4,968 | 900 | 18 |
| Total | 49 | 13,524 | 13,524 | 2,450 | 49 |

Dataset-start resets: 49. Unavailable counts were computed from generated rows,
not supplied as expected totals. Every valid input has one output row including
warmup. First pass inserted **13,524**; second pass inserted **0**, recognizing
**13,524** existing rows with identical content hashes. Retrieved Decimal payloads
matched the generation hashes exactly.

Aggregate feature dataset identity:
`d54c300e5eead78243c38058a62a2506240247327fd46a4b9ac25ac94867ad41`.
Source policy: `histdata-xauusd-research-gap-v1`.

The resulting table's source-key/count map matched exactly the 49 approved datasets.
No Friday, weekend, holiday, unexplained/no-data or January source identity entered
the feature table; February 19 and March 28/29 remain absent. Snapshot comparison
confirmed all **14,802 source bars** unchanged (13,524 approved February–April plus
1,278 existing January bars). Existing NSE feature tables were empty and stayed
empty; no prior NSE feature data was fabricated for this check.

## Verification actually run

- Full `pytest -q`: **750 passed**, no skips; one existing Starlette/AnyIO warning.
  Existing January compatibility, XAUUSD/no-lookahead and NSE feature/backtester
  regressions remain passing.
- Ruff passed; Black check passed (142 files unchanged); mypy passed (82 source files).
- Alembic upgrade applied; current **0008 (head)**; check: no schema drift.
- Empty 0008 downgrade to 0007, re-upgrade and schema check passed in a disposable
  schema. Nonempty downgrade correctly refused.
- Conflict tests rejected changed stored identity without new audit writes; a
  forced audit failure rolled back the newly inserted feature rows while preserving
  source bars. Decimal strings, JSON nulls, chronological queries, wrong-version
  isolation and deterministic regeneration passed round-trip tests.
- The initial verification exposed a missing audit run ID and the expected readiness
  mismatch before local upgrade; both were corrected before this successful final
  full suite and real generation. No failed run is presented as passing.
- Git status, working/staged diffs and whitespace reviewed. Seven existing files
  modified (model, readiness revision and five migration-head test assertions),
  six new files (migration, repository, bounded script, tests and two reports).
  Nothing staged or committed; no dependency changes.

Recommended commit: `feat: persist approved XAUUSD baseline features`.

Stopped at G2C3C. No strategies or G2C4 work.

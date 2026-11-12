# G2C4E2B — frozen May–July validation dataset

Dataset preparation only. May–July remains FIRST UNSEEN VALIDATION with respect
to strategy performance. No strategy evaluator was imported by the materializer;
no signal counts, markouts, random benchmarks, trade outcomes or profitability
were calculated. August–October remains LOCKED / UNPROCESSED. E1 is unchanged.

## Policy and eligible scope

Policy: `histdata-xauusd-validation-gap-v1`.
Policy content key: `0d99e07697c841fde772368803cd2d6010677841b1e8878954eadce476b0a3b6`.

The separate `config/histdata_xauusd_validation_gap_v1.yaml` encodes the explicit
50-date allowlist as 50 singleton segments: each segment's start and end are the
same approved source date. This uses the existing policy abstraction unchanged
and cannot admit another date merely because it is in the month. Every segment
requires exactly the twelve missing opening labels 22:00–22:55 UTC, and is bound
to its source archive checksum, E2A report hash/version and processing versions.
Extra missing bins and fewer missing bins both reject. The development policy
is byte-identical to its pre-checkpoint version.

| Source month | Approved dates | Persisted bars | Feature rows |
| --- | ---: | ---: | ---: |
| May 2024 | 17 | 4,692 | 4,692 |
| June 2024 | 15 | 4,140 | 4,140 |
| July 2024 | 18 | 4,968 | 4,968 |
| Total | 50 | 13,800 | 13,800 |

May 27, June 19 and July 4 are explicitly excluded. Fridays, Saturdays, Sundays,
no-data and unexplained days are outside the allowlist. No policy relaxation or
new source download occurred. Dates are fixed-EST source-calendar dates, not UTC
calendar dates; their existing next-date UTC tails do not authorize another
source month or access to August's archive.

## Source and persistence verification

Archives were checked against the following frozen E2A SHA-256 values before any
persistence. Every approved day's reconstructed bid/ask bar hash and tick count
also matched E2A before database writes.

- 2024-05: `ec9128f89afb2091912310ef55a1cd6006475f27817707a0d2c08983fd74b5aa`
- 2024-06: `a94e12301134b02899f8402d6f990fb65d2e2a837daf243cb2a642625cb8a980`
- 2024-07: `cec29b35b592b3ca9810b84e0af81ea6e84af78d1d16f22e2ee2eb4bddb7c810`

The unchanged HistData parser retains fixed UTC−05:00 normalization to aware UTC,
Decimal prices and separate bid/ask OHLC. No scaling, quantization, midpoint OHLC,
interpolation or gap filling. Bars fetched after import equal the source-derived
QuoteBar objects exactly. Each dataset contains precisely 276 observed bars.

| Operation | Inserted | Existing/matching |
| --- | ---: | ---: |
| First bar import | 13,800 | 0 |
| Second identical bar import | 0 | 13,800 |
| First feature generation | 13,800 | — |
| Second identical feature generation | 0 | 13,800 |

The existing repositories retain conflict rejection and transaction rollback.
Transactions remain per source day; the checkpoint is not a single transaction
spanning all days. An interrupted run can be repeated idempotently. Audit run
UUIDs/timestamps may differ between repeats; mathematical dataset identity does not.

## Frozen features and resets

Feature set: `xauusd-baseline-features-v1`. Formulas and feature storage are unchanged.
Every approved bar has one persisted feature row, and fetched rows match the pure
engine output exactly. Generation is performed independently for each dataset.

There are **50 DATASET_BOUNDARY resets**, one at each day's first bar, plus
**50 DISCONTINUITY resets** after the provider gap. Thus there are 100 reset-marked
rows in total, not 50 total resets. The requested 50-day reset count is satisfied
without suppressing the additional required gap resets. EMA12/26, RSI14 and
momentum3/12 are unavailable at both reset points, confirming no state carry.
Excluded dates and overnight/day boundaries are never bridged.

## Immutable content identity

Validation dataset content key:

`811d9f5db6bf55d128147b2247197d2364e31b185d005c69b33b2349ffa589c5`

The canonical manifest covers provider and symbols, archive checksums, policy
version/key, all eligible dates and their dataset identities, processing versions,
feature version, counts, and each day's exact bar/feature content hashes and
feature dataset key. The compact JSON contains this manifest. Generation time
and import counters live outside it. Reordering day records or changing generation
time/import counts does not change the key; changing source content does.
This is a content-addressed research snapshot, not a new dataset-versioning service.

## Development preservation

Frozen February–April input-evidence hashes were checked before and after import:
**49 days, 13,524 bars and 13,524 baseline feature rows**, unchanged.
No strategy evaluator was used to perform these checks. Combined development
snapshot hash: `d3d1f1585f94480b8c8bf1cc3713ec9ecf6a6d30a9b39403ab2aee457e254229`.
Existing source/configuration/reports are protected by file-hash checks, except
for the intended research-log append. No E1 or development policy edits.

## Verification

- `pytest -q`: **981 passed**, one existing Starlette/AnyIO warning. Includes a
  synthetic 50-day/13,800-row persistence test, exact price round-trip, second-import
  idempotency, missing/wrong provenance, exclusions, extra/fewer gap bins, both
  reset types, deterministic identity and no strategy imports. Existing conflict,
  rollback, XAUUSD and NSE regressions pass. No internet required by tests.
- Ruff passed; Black passed (185 files); mypy passed (96 source files).
- Alembic current: **0008 (head)**; check: no schema drift. No migration.
- Actual archive-backed materialization checks independently verify the real
  cardinalities and development preservation recorded above.
- Git status, working/staged diff and whitespace checks reviewed. No commit.

Created: separate policy YAML, `scripts/materialize_xauusd_validation.py`,
`tests/integration/test_validation_materialization.py`, and this Markdown/JSON
report. Updated the experiment log with dataset-preparation status only.
No dependencies added. Raw archives remain outside Git. The old untracked
$3,000 sensitivity reports remain untouched.

Reproduce with DATABASE_URL supplied securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/materialize_xauusd_validation.py \
  /tmp/histdata-validation-2024
```

Limitations: HistData is a research feed, not a verified broker schedule or contract
specification. Accepted coverage does not establish tick-level completeness.
Eligibility is retrospective coverage-based selection. No inference about strategy
quality or validation performance has been made.

Recommended commit: `feat: materialize frozen May-July XAUUSD validation dataset`.

Stopped at G2C4E2B. No E1 evaluation or holdout processing.

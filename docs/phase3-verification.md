# Phase 3 completion and verification

Latest verification-only re-audit: [2026-09-24 audit](phase3-audit.md),
**225 passed**, with requirement-to-code/test mappings. Results below record the
original implementation verification.

Phase 3 is complete: historical bars → causal numerical features → validated,
persisted, completion-aware feature queries. No strategy, signal, ML, backtest,
broker, order, position sizing or execution functionality was added. Live mode
remains rejected. Real Groww integration remains **UNVERIFIED**. Phase 4 has not begun.

## Architecture and file inventory

The pure feature engine is separated from historical snapshot loading, parameter
resolution, numerical families, output validation, persistence and the CLI.
[The feature guide](features.md) documents all formulas and policies in detail.

Created:

- `src/trading_bot/data/snapshot.py`: exact-price snapshot/provenance contracts.
- `src/trading_bot/features/__init__.py`, `definitions.py`, `registry.py`:
  feature contracts and closed, versioned registry.
- `src/trading_bot/features/numerics.py`, `price.py`, `volume.py`:
  causal numerical primitives and feature families.
- `src/trading_bot/features/engine.py`, `validation.py`, `repository.py`,
  `service.py`, `generate.py`: calculation, validation, storage, coordination, CLI.
- `config/features.yaml`: explicit 29-output `baseline_v1`.
- `migrations/versions/0003_features.py`: feature set/value tables and indexes.
- `tests/unit/test_feature_engine.py`, `tests/integration/test_features.py`,
  `tests/fixtures/reliance_features.csv`: formula/safety tests and synthetic data.
- `scripts/demonstrate_phase3.py`: executable demonstration in a disposable schema.
- `docs/features.md`, this report, `docs/phase3-demonstration.json`.

Modified:

- `src/trading_bot/data/query.py`: bounded repeatable-read snapshot query preserving
  available_at and historical ingestion identities; existing query behavior retained.
- `src/trading_bot/database/models.py`: `FeatureSet` / `FeatureValue` models.
- `src/trading_bot/api/app.py`: readiness now expects revision 0003.
- `src/trading_bot/monitoring/logging.py`: allowlisted feature summary fields.
- `pyproject.toml`: NumPy 2.5.3 is now an explicit numerical dependency; it was
  already pinned in both lock files, which need no version changes.
- `tests/conftest.py`: deterministic shared feature input fixture.
- `tests/integration/test_history.py`: existing migration test now expects 0003;
  its historical downgrade/re-upgrade assertions remain.
- `README.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/verification.md`:
  current phase, architecture and verification links.

## Storage, baseline and safety conventions

Migration **0003** stores manifests in `feature_sets` and one JSON-valued output row
per `(feature_set_key, symbol, opening timestamp)` in `feature_values`. Exact closes
remain `NUMERIC(28,10)`; statistical outputs are finite float64-derived JSON numbers
or explicitly explained nulls. No per-indicator columns were introduced.

Baseline outputs:

- Return 1/3/5, log return 1.
- SMA10/20, EMA10/20, SMA20 distance, normalized EMA10−EMA20 spread.
- Momentum3/5/10, Wilder RSI14.
- Population rolling return volatility20, Wilder ATR14, range fraction, true range.
- Volume change, mean20, ratio to mean20.
- Rolling high/low20, close distances to both, distance to prior rolling high20.
- Minutes since session open, minutes until scheduled close, session progress.

SMA/EMA use explicit arithmetic seeds. EMA uses alpha=2/(n+1); Wilder uses alpha=1/n.
RSI requires n changes (n+1 closes); flat history returns 50. True range requires a
previous close; ATR seeds from n valid true ranges. Formula cases are independently
checked with small examples. No optional VWAP, trade-count or OI values are invented.

Warm-up is null plus `WARMUP`, not zero. Baseline has 20 warm-up rows. A missing
expected candle resets rolling state for the affected symbol; subsequent outputs
use `GAP_WARMUP` until each has enough observations. Overnight/weekend/holiday
boundaries continue normally. Session context resets daily and respects exceptional
session schedules. A zero denominator has its own unavailable reason.

Opening timestamps remain UTC-stored labels. Availability is the verified calendar
completion instant. Feature queries require an aware `as_of`, enforce completion
and return chronological rows. RAW, SPLIT_ADJUSTED and FULLY_ADJUSTED remain separate
through query selection, manifest identity and persisted feature-set keys.

The feature-set identity combines historical selection/semantics, candle-content
digest, calendar/version, definitions/parameters, NumPy/engine versions and policies.
Canonical ordering makes reruns reproducible. Changed source data or RSI period
produces a distinct identity. Ingestion UUIDs are retained as provenance, and each
feature generation emits a unique run UUID in its summary log. Identical writers
serialize by key and insert no duplicate logical rows.

## Verification actually run

Local Python 3.12.7, PostgreSQL 17.6, real PostgreSQL integration tests:

| Check | Actual result |
| --- | --- |
| Full pytest | **223 passed**, no skips; original 146 scenarios retained + 77 feature cases |
| Ruff | All checks passed |
| Black check | 61 Python files unchanged |
| Strict mypy | No issues in 39 source files |
| Alembic upgrade/current | **0003 (head)** |
| Alembic check | No new upgrade operations / no schema drift |
| Migration roundtrip | 0003 → 0002 → head passed; candles retained |
| Existing migration checks | Downgrade to 0001 / re-upgrade, legacy instrument preservation passed |
| Concurrent identical generation | One insertion, one zero-row rerun |
| Forced persistence failure | No partial feature set or feature values committed |
| Whitespace/diff check | Passed |

One pre-existing Starlette/AnyIO deprecation warning remains. The final full test run
passed; a subsequent mypy-only variable naming defect was corrected and Ruff,
Black and mypy were rerun successfully. No failed check is reported as passing.

Commands actually exercised (with development credentials exported outside Git):

```sh
export PYTHONPATH="$PWD/src"
alembic upgrade head
alembic current
alembic check
TEST_DATABASE_URL="$DATABASE_URL" pytest -q
ruff check .
black --check --workers 1 .
mypy
git diff --check
python scripts/demonstrate_phase3.py
```

Migration downgrades run inside disposable test schemas. The retained development
database remains at 0003. No credentials were added to the repository, and no real
Groww call was made.

## Executed RELIANCE demonstration

[Full machine-readable output](phase3-demonstration.json) was produced by
`python scripts/demonstrate_phase3.py`. It imports the committed **synthetic**
RELIANCE fixture through historical ingestion into a newly migrated disposable
PostgreSQL schema; it cleans up that schema afterward. These are not observed NSE
prices and the fixture's differently adjusted series is synthetic test data.

Actual baseline result: **60 bars loaded, 29 features requested, 60 rows inserted,
20 warm-up rows, zero gaps, zero invalid outputs, COMPLETED**.

Rounded display below; timestamps are candle openings in IST on 2026-01-05.
Stored timestamps/availability are UTC. Each shown row becomes visible five minutes
later. Complete precision is in the JSON artifact.

| Opening IST | Close | Return1 | EMA10 | EMA20 | RSI14 | ATR14 | Volume ratio | Session progress |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 09:15 | 1500.00 | null | null | null | null | null | null | 0.000000 |
| 09:20 | 1501.50 | 0.001000 | null | null | null | null | null | 0.013333 |
| 10:25 | 1506.00 | -0.000664 | 1504.681289 | null | 66.666667 | 4.000000 | null | 0.186667 |
| 10:50 | 1508.50 | -0.000662 | 1507.156096 | 1504.750000 | 66.638053 | 4.000000 | 1.086758 | 0.253333 |
| 10:55 | 1510.00 | 0.000994 | 1507.673169 | 1505.250000 | 69.385817 | 4.000000 | 1.085973 | 0.266667 |

Demonstrated assertions:

1. First EMA20 is null until row 19; all baseline outputs have enough history at row 20.
2. Query at **09:19:59 returns 0 rows**; query at **09:20 returns 1 row**.
3. Changing every candle from row 35 onward leaves all **35 earlier rows identical**.
   Separate tests also truncate future inputs at multiple cutoffs and compare prefixes.
4. Second persisted generation inserts **0 rows** with the same feature-set key.
5. RSI14→RSI10 changes the feature-set key.
6. RAW and SPLIT_ADJUSTED have separate keys and reference closes; integration tests
   also prove FULLY_ADJUSTED isolation.
7. Removing candle 25 yields **1 missing bar and 20 gap-affected rows**. The next
   available candle's rolling outputs are null with `GAP_WARMUP`, while session and
   current-candle features remain available. Persisting this set inserts 59 rows.
8. A database candle correction creates a new feature identity while preserving the
   earlier stored feature snapshot; earlier unaffected rows match.

## Remaining limitations and stop point

- Calendar authority before 2026 remains UNKNOWN and requires consistent explicit
  research opt-in; 2027+ remains unsupported. Calendar-version mismatches fail.
- Groww real authenticated semantics remain UNVERIFIED.
- Legacy candles without ingestion identity events require reviewed provenance;
  no implicit repair/backfill exists.
- Snapshots are bounded/in-memory; there is no incremental computation, automatic
  chunk continuation, scheduling, eviction or distributed processing.
- Floating-point statistics are intentional. Vendor correction publication times
  and full historical input vintages are not reconstructed by market completion times.
- No corporate-action transformations, optional VWAP/OI/trade-count features,
  strategies, ML, backtesting or trading were implemented.

Recommended commit: `feat: add causal reproducible NSE feature engineering`

Stopped after Phase 3. Phase 4 has not begun.

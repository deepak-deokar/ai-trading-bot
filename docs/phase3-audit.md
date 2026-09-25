# Phase 3 verification-only audit — 2026-09-24

**PHASE 3 VERIFIED COMPLETE**

This verdict is based on inspecting the current working tree and rerunning commands,
not on the previous completion report. No production code, feature definitions or
migrations changed during this audit. Two verification tests were added, the
existing deterministic demonstration was rerun, and this evidence was recorded.
No Phase 4 work was started.

## Fresh command results

| Command / check | Result |
| --- | --- |
| `pytest -q` with TEST_DATABASE_URL | **225 passed**, no skipped tests, 5.50 seconds |
| Collection excluding the two Phase 3 test files | **146 tests collected**; all are included in the successful full run |
| `ruff check .` | All checks passed |
| `black --check --workers 1 .` | 61 files would be left unchanged |
| `mypy` | Success, no issues in 39 source files |
| `alembic upgrade head` | Success |
| `alembic current` | **0003 (head)** |
| `alembic check` | No new upgrade operations detected / no schema drift |
| Downgrade/re-upgrade | Actual 0003 → 0002 → head in disposable PostgreSQL schema; historical candles retained |
| Existing historical migration roundtrips | Passed, including downgrade to 0001 and re-upgrade |
| `python scripts/demonstrate_phase3.py` | Passed against real PostgreSQL; refreshed `phase3-demonstration.json` |
| `git diff --check` | Passed |

The full suite includes 146 pre-Phase-3 cases and 79 Phase 3 cases. One existing
Starlette/AnyIO deprecation warning remains; it is not suppressed. Database URLs
were loaded from the existing external development credential file, not committed
or printed. The retained database remains at 0003. Temporary migration/demo schemas
were removed by their cleanup paths.

## Architecture: exact implementation files

All paths are relative to the repository root.

| Responsibility | Actual file / entry point |
| --- | --- |
| Feature definitions, specs, config, rows and reports | `src/trading_bot/features/definitions.py` |
| Closed registry, version and lookback resolution | `src/trading_bot/features/registry.py:resolve` |
| Pure engine, causal grouping, gaps, provenance and feature-set identity | `src/trading_bot/features/engine.py:FeatureEngine` |
| Float64 lag/window/smoothing primitives | `src/trading_bot/features/numerics.py` |
| Price, trend, momentum, volatility, structure calculations | `src/trading_bot/features/price.py:calculate` |
| Volume calculations | `src/trading_bot/features/volume.py:calculate` |
| Session context | `src/trading_bot/features/engine.py:FeatureEngine._segment` |
| Output validation | `src/trading_bot/features/validation.py:validate_row` |
| Atomic storage and chronological completion-aware queries | `src/trading_bot/features/repository.py:FeatureRepository` |
| Query → calculation → persistence → summary logging | `src/trading_bot/features/service.py:FeatureService.generate` |
| CLI | `src/trading_bot/features/generate.py:main` |
| Exact-price historical snapshot boundary | `src/trading_bot/data/snapshot.py`, `src/trading_bot/data/query.py:HistoryQuery.get_snapshot` |
| Historical identity and canonical SHA-256 helper | `src/trading_bot/data/identity.py` (existing Phase 2.1 implementation) |
| Baseline configuration | `config/features.yaml` |
| Database models | `src/trading_bot/database/models.py:FeatureSet, FeatureValue` |
| Schema migration | `migrations/versions/0003_features.py` |
| End-to-end demonstration | `scripts/demonstrate_phase3.py`, `tests/fixtures/reliance_features.csv` |

The CLI imports and invokes the service, which invokes the historical query,
engine and repository. The API readiness revision is 0003. This is a CLI/service
feature layer, not an unwired placeholder or a new HTTP feature endpoint.

## Baseline mapping and calculation evidence

All **29 aliases** below are explicitly numerically checked by
`tests/unit/test_feature_engine.py::test_audit_all_baseline_outputs_and_explicit_warmups`.
The existing `test_independent_small_formulas` adds 24 small reference cases, including
nonlinear closes for RSI/EMA and different periods from the baseline. Actual alias
parameters are in `config/features.yaml`; implementations resolve through the registry.

| Requirement | Implemented aliases | Implementation |
| --- | --- | --- |
| Simple/log returns | `return_1`, `return_3`, `return_5`, `log_return_1` | `price.py`, return/log_return branches |
| Moving averages | `sma_10`, `sma_20`, `ema_10`, `ema_20` | `price.py`, sma/ema branches; `numerics.py:rolling,smooth` |
| Trend distances | `sma_20_distance`, `ema_spread` | `price.py`, sma_distance/ema_spread branches |
| Momentum/RSI | `momentum_3`, `momentum_5`, `momentum_10`, `rsi_14` | `price.py`, momentum/rsi branches |
| Volatility/range | `rolling_volatility`, `true_range`, `atr_14`, `range_pct` | `price.py`, volatility/true_range/atr/range_pct branches |
| Volume | `volume_mean`, `volume_change`, `volume_ratio` | `volume.py:calculate` |
| Price structure | `rolling_high`, `rolling_low`, `high_distance`, `low_distance`, `breakout_distance` | `price.py`, rolling_high/low and distance branches |
| Session context | `minutes_since_open`, `minutes_until_close`, `session_progress` | `engine.py:FeatureEngine._segment` |

Volume z-score was not part of the implemented baseline and is not claimed. Optional
VWAP, trade-count and open-interest features are likewise absent by design.

Formulas and seeding were inspected: EMA uses an SMA seed and alpha=2/(n+1); RSI/ATR
use arithmetic seeds and Wilder alpha=1/n. RSI flat history is 50; ATR needs a prior
close. Return volatility uses population std (ddof=0), not annualization. Distances
and range are fractions; only RSI is scaled to 0–100. See [full formulas](features.md).

## Safety evidence: exact tests and code behavior

Unless otherwise noted, unit tests below are in `tests/unit/test_feature_engine.py`
and PostgreSQL tests are in `tests/integration/test_features.py`.

| Requirement | Verified behavior | Specific passing tests |
| --- | --- | --- |
| Opening timestamp / UTC | Row retains candle opening and its verified session completion | Unit `test_timestamp_and_completion`, `test_session_clipped_availability_other_timeframes` |
| 09:15 unavailable before 09:20 | Repository filters `available_at <= min(as_of,end)`; as_of is mandatory and aware | PostgreSQL `test_persist_rerun_order_exact_prices_and_availability`, `test_queries_require_aware_cutoff` |
| No future-candle leakage | Changing future OHLCV or truncating a sequence at multiple cutoffs preserves earlier rows | Unit `test_no_future_leakage_and_input_mutation_changes_identity`; PostgreSQL `test_changed_stored_candle_produces_new_feature_identity` |
| Warm-up | Null plus WARMUP; SMA20 null before 20 observations, RSI14/ATR14 null before 15 | Unit `test_audit_all_baseline_outputs_and_explicit_warmups`, `test_baseline_warmup_and_metadata` |
| Missing intraday candle | Reset affected symbol's rolling/recursive state; null plus GAP_WARMUP until reinitialized | Unit `test_gap_resets_state_and_recovers`, `test_leading_trailing_missing_slots`; PostgreSQL `test_gap_warnings_and_parameter_identity` |
| Overnight/weekend | Adjacent expected calendar slots continue state across valid session boundaries; context resets | Unit `test_normal_session_boundary_continues_and_context_resets` (next-day and Friday→Monday cases) |
| Special sessions | Session context uses explicit scheduled hours | Unit `test_special_session_uses_scheduled_hours` |
| Symbol isolation | Every feature row for RELIANCE/TCS/INFY equals separate single-symbol computation | Unit `test_audit_every_symbol_matches_its_standalone_series`; PostgreSQL `test_multi_symbol_persistence` |
| Adjustment/source isolation | One selected policy/source, mixed input rejected, distinct persisted keys and prices for all three policies | PostgreSQL `test_adjustments_and_sources_stay_isolated`; unit `test_reject_unsafe_inputs` |
| Deterministic identity | Same data/config stable; order canonicalized; RSI14→10 changes identity | Unit `test_identity_order_parameters_and_exact_decimal_scale`; PostgreSQL rerun/parameter tests |
| Changed stored data | Content digest changes identity; old stored features remain separate | PostgreSQL `test_changed_stored_candle_produces_new_feature_identity` |
| Exact prices / intentional floats | Decimal at historical/storage boundaries; float64 only for statistics | Unit `test_float_conversion_does_not_change_exact_close`; PostgreSQL `test_persist_rerun_order_exact_prices_and_availability` |
| NaN/+inf/-inf rejection | Invalid calculations fail; justified warm-up/zero denominators remain null | Unit `test_nonfinite_output_rejected` (three cases), `test_limits_empty_and_unexpected_nan`, `test_unexpected_volume_nan_is_not_a_zero_denominator`, `test_zero_volume_is_expected_unavailable` |
| Impossible values/parameters | Reject invalid session progress, unexplained nulls and invalid/coerced parameters | Unit `test_impossible_session_value_and_unexplained_null`, `test_bad_registry_parameters`, `test_no_parameter_coercion` |
| CLI wiring | Actual CLI main invokes real database generation using test-injected engine | PostgreSQL `test_cli_generation`; standalone demonstration additionally exercises real ingestion/service/repository |
| Live mode rejected | Existing settings validators still reject live settings/environment | `tests/unit/test_settings.py::test_rejects_unsafe_settings`, `test_environment_live_cannot_be_masked_by_yaml` |

The new audit tests strengthen evidence only; they found no production calculation
failure. Existing settings/order vocabulary predates Phase 3. No new BUY/SELL,
entry, stop, target, sizing, strategy, portfolio or broker implementation was found.
The `paper` configuration label still does not implement paper trading.

## Persistence and provenance

Design **B: persisted to PostgreSQL**. `feature_sets` holds a canonical manifest and
expected row count; `feature_values` holds one row per set/symbol/opening with JSON
numerical values/nulls, exact Numeric close, availability and quality flags.
Primary key `(feature_set_key,symbol,timestamp)` prevents duplicate logical values.

The manifest includes original historical dataset identities and ingestion runs,
exchange/segment/symbols/timeframe/range/source/adjustment, calendar provider/version/
authority, feature definitions/versions/parameters, numeric/engine versions and
calculation policies. Input content is fingerprinted, not just its requested range.
Missing legacy provenance fails explicitly. Neither adjustment nor source is a
wildcard, and the query selects one exact set key.

Idempotency and storage checks passed:

- `test_persist_rerun_order_exact_prices_and_availability`: second generation inserts
  zero and queries are chronological.
- `test_database_feature_uniqueness_and_availability`: duplicate insert and invalid
  availability rejected by database constraints.
- `test_concurrent_identical_generation`: concurrent runs insert 40 and 0 rows.
- `test_persistence_failure_is_atomic`: injected write failure leaves no partial set.
- `test_partial_cache_rejected`: incomplete stored set is not silently reused.
- `test_legacy_provenance_rejected_and_snapshot_bounded`: missing identity/oversized
  historical snapshot fail.
- `test_feature_migration_roundtrip_retains_candles`: 0003→0002→head, drift check and
  regeneration succeed while retaining original candles.
- `test_batch_query_count_not_per_candle`: bounded bulk database operations.

## Fresh RELIANCE demonstration

The committed synthetic NSE CASH 5-minute CSV was ingested through the historical
service into an isolated newly migrated PostgreSQL schema. No authenticated market
provider was called. [Refreshed raw output](phase3-demonstration.json).

Actual result: **60 bars, 29 features, 60 rows, 20 warm-up rows, 0 invalid outputs**.
The second generation inserted **0** rows. Baseline key:
`2a075af88fdb08e61107365a0236e00b325a375205603acd5462167288004a19`.

Rounded sample; openings are IST on 2026-01-05, with UTC timestamps in the raw output:

| Opening | Close | return_1 | ema_10 | ema_20 | rsi_14 | atr_14 | volume_ratio | session_progress |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 09:15 | 1500.00 | null | null | null | null | null | null | 0.000000 |
| 09:20 | 1501.50 | 0.001000 | null | null | null | null | null | 0.013333 |
| 10:25 | 1506.00 | -0.000664 | 1504.681289 | null | 66.666667 | 4.000000 | null | 0.186667 |
| 10:50 | 1508.50 | -0.000662 | 1507.156096 | 1504.750000 | 66.638053 | 4.000000 | 1.086758 | 0.253333 |
| 10:55 | 1510.00 | 0.000994 | 1507.673169 | 1505.250000 | 69.385817 | 4.000000 | 1.085973 | 0.266667 |

Actual assertions passed: 09:19:59 query returns zero, 09:20 returns one; modifying
all candles from row 35 onward preserves all 35 earlier rows. RSI10 key differs
(`1586f7dc…`); SPLIT_ADJUSTED key differs (`82144ef4…`) and reference closes stay
separate. Removing candle 25 produces one missing bar and 20 GAP_WARMUP rows; current
range/session features remain usable. No corporate-action transformation was added
to production; the adjusted series is synthetic fixture data.

## Git and interruption audit

Inspected `git status`, `git diff` and `git diff --cached`, plus all untracked Phase 3
modules, tests, migration, config and demonstration files. The staged diff is empty.
At audit completion there are **11 modified tracked files and 22 untracked files**
(expanding directories). Phase 3, including migration 0003, is not committed/staged.
No destructive Git operations, staging or commits were performed.

No partially written Python files, unresolved Phase 3 TODO/FIXME/NotImplemented
placeholders, duplicate indicator implementations, missing imports, missing test
imports or disconnected CLI/service modules were found. Type checks, formatting,
full test execution and the standalone script confirm import/wiring behavior.
The important handoff issue is that the new migration and feature package remain
untracked and must accompany the implementation in any eventual commit.

Changes made by this audit: two tests appended to the existing feature unit test
file; refreshed demo JSON; this audit report and a link from the prior report.
Production code/configuration/migrations were unchanged by the audit.

## Limits retained

Calendar authority before 2026 remains UNKNOWN with explicit research opt-in;
2027+ is unsupported. Groww authenticated semantics remain UNVERIFIED. Legacy bars
without identity metadata cannot generate features without reviewed provenance.
Generation is bounded/in-memory (100,000 rows/slots conservatively), and separate
chunks reseed; there is no automatic continuation. Float64 rounding is intentional.
Market completion is not vendor correction publication time; full vintage/bitemporal
reconstruction is not implemented. Direct SQL access bypasses application validation;
internal calculation results must be consumed through completion-aware queries.
These are documented Phase 3 limits, not claims of a full backtesting platform.

Recommended commit: `feat: add causal reproducible NSE feature engineering`

Verification ends here. Phase 4 has not begun.

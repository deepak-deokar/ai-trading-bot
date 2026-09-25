# Phase 3: deterministic numerical features

Historical candles → completion-aware historical query → feature engine → validated
PostgreSQL feature rows → later research consumers. This phase makes no decisions,
signals, orders, forecasts, rankings or corporate-action transformations. Live mode
remains rejected. Groww authenticated behavior remains **UNVERIFIED**.

## Architecture and storage

`data/query.py:get_snapshot` reads exact Decimal bars, stored availability and
historical ingestion identities in two bounded bulk queries under PostgreSQL
REPEATABLE READ. Legacy bars without Phase 2.1 identity events fail clearly; no
retrospective provenance is invented. Re-importing identical legacy bars alone does
not repair their original ingestion provenance.

`features/definitions.py` owns typed contracts. `registry.py` resolves only known
implementations and validates explicit integer parameters (1–500), unique output
names and a maximum of 64 requested outputs. `numerics.py`, `price.py` and
`volume.py` contain numerical calculations. `engine.py` isolates symbol state,
checks provenance/calendar alignment, handles gaps and computes deterministic
identities. `validation.py` rejects invalid outputs. `service.py` coordinates query,
calculation, storage and structured summary logging. `generate.py` is the CLI.

Migration **0003** adds:

- `feature_sets`: SHA-256 primary key, dataset key, name, canonical provenance and
  definition manifest, expected row count, creation time.
- `feature_values`: primary key `(feature_set_key, symbol, timestamp)`; UTC opening
  and availability timestamps; exact `NUMERIC(28,10)` close; JSON feature numbers or
  nulls; per-output unavailability reasons and sufficient-history/gap flags.

The set manifest fixes exchange, segment, source, timeframe and adjustment, so a
query cannot combine them under one set key. New indicators/parameters need no new
columns. Foreign keys, primary keys and an availability check constrain storage.
The repository validates finite numbers before insertion; direct SQL writes bypass
application validation and are outside its supported interface.

A single transaction inserts each set and batches of up to 1,000 rows. A per-key
transaction advisory lock makes concurrent identical runs idempotent. A failed
write rolls back the entire feature set. A stored set with an unexpected row count
is rejected rather than reused. Downgrade to 0002 removes feature results only;
it preserves historical candles. Migration roundtrips are tested in disposable
schemas, not against retained research results.

## Baseline and formulas

`config/features.yaml` defines **29 outputs** in `baseline_v1`. Every definition
records implementation version `1`, description, input fields, explicit parameters,
minimum prior-bar lookback and float64 output type. In formulas, `C`, `H`, `L`, `V`
mean current close, high, low and volume. Windows include the current candle unless
explicitly described as prior windows. Ratios are fractions, not multiplied by 100,
except RSI. Price differences have the input price's units.

| Outputs | Explicit formula / convention | First valid index (zero-based) |
| --- | --- | --- |
| `return_1`, `return_3`, `return_5` | `C[t] / C[t-n] - 1`, n=1,3,5 | n |
| `log_return_1` | `ln(C[t] / C[t-1])` | 1 |
| `sma_10`, `sma_20` | Arithmetic mean of n closes | n−1 |
| `ema_10`, `ema_20` | SMA seed of n closes; then `alpha*C + (1-alpha)*previous`, alpha=2/(n+1) | n−1 |
| `sma_20_distance` | `C / SMA20 - 1` | 19 |
| `ema_spread` | `(EMA10 - EMA20) / C` | 19 |
| `momentum_3`, `momentum_5`, `momentum_10` | `C[t] - C[t-n]` | n |
| `rsi_14` | Gains=max(delta,0), losses=max(-delta,0); Wilder-smoothed averages G,L; `100*G/(G+L)` | 14 |
| `rolling_volatility` | Population standard deviation (ddof=0) of 20 one-bar simple returns; not annualized | 20 |
| `true_range` | `max(H-L, abs(H-Cprev), abs(L-Cprev))`; first observation null | 1 |
| `atr_14` | Wilder-smoothed 14 true ranges, excluding the first unavailable TR | 14 |
| `range_pct` | `(H-L) / C` | 0 |
| `volume_change` | `V[t] / V[t-1] - 1` | 1 |
| `volume_mean`, `volume_ratio` | Mean of 20 volumes; `V / mean20` | 19 |
| `rolling_high`, `rolling_low` | Maximum high / minimum low across 20 bars | 19 |
| `high_distance`, `low_distance` | `C / rolling_high - 1`, `C / rolling_low - 1` | 19 |
| `breakout_distance` | `C[t] / max(H[t-20:t]) - 1`; excludes current high | 20 |
| `minutes_since_open` | Opening timestamp minus scheduled session open, in minutes | 0 |
| `minutes_until_close` | Scheduled session close minus opening timestamp, in minutes | 0 |
| `session_progress` | Minutes since open / scheduled session duration | 0 |

Wilder smoothing uses the arithmetic mean of the first n valid observations as its
seed, then `((n-1)*previous + current)/n`. RSI14 therefore needs 15 closes. Only gains
returns RSI 100; only losses returns 0; a fully flat smoothed history returns 50.
ATR deliberately requires a prior close instead of inventing the initial true range.
EMA and Wilder state retain earlier observations after their seed; the metadata
lookback describes minimum initialization, not a finite memory cutoff.

Formula references: Fidelity's [EMA definition](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/ema),
[RSI definition](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI)
and [ATR definition](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr).
Our seed, flat-history and initial-TR conventions above are explicit and tested;
other packages may make different choices. Tests use independently understandable
small examples rather than comparing the implementation to itself.

VWAP, trade-count, open-interest and volume z-score features are not included.

## Time, availability, warm-up and gaps

A feature's timestamp is its candle's **opening**. Its `available_at` is the stored
calendar closing instant, verified against the selected calendar. A 09:15 IST
5-minute candle represents `[09:15,09:20)` and its feature row becomes visible at
09:20 IST (03:50 UTC). A query at 09:19:59 returns no such row. Short final intervals
use their actual scheduled close. All earlier inputs must come from preceding
completed calendar slots, so their completion cannot follow the current slot.

`FeatureRepository.get_features` requires an explicit aware `as_of` and applies
`available_at <= min(as_of, end)`, with opening range `[start,end)`. Results are
chronological. There is no implicit current-time default. Queries select one exact
feature-set key; they never union differently adjusted/source/timeframe datasets.

No hidden preloading occurs. The request start initializes the series. Extend the
start explicitly when more warm-up history is needed. Insufficient history produces
null plus `WARMUP`, and `sufficient_history=False`. Baseline's first **20 rows** have
at least one warm-up value (volatility/breakout require 20 prior bars).

The calendar supplies the complete expected sequence for the requested range. A
missing slot resets **all** rolling and recursive state for that symbol. Affected
outputs remain null with `GAP_WARMUP` until their own history requirement is met.
The first actual row after a gap has `gap_before=True`; current-candle and session
features remain usable. No rows or prices are synthesized for missing candles.
Leading and trailing missing slots count in the summary; a trailing gap has no later
row to flag. Missing all bars for a requested symbol fails generation.

Rolling state continues across ordinary overnight/weekend/holiday boundaries when
no expected slots are missing. Session-relative features reset each session. Special
sessions use their **scheduled** hours, including a shortened or evening session;
regular NSE CASH uses 09:15–15:30 Asia/Kolkata. Calendar coverage/authority and
research opt-in retain Phase 2.1 semantics. The calendar version must match input
ingestion provenance; unknown dates are never guessed.

Zero volume denominators produce null plus `ZERO_DENOMINATOR`, not infinity or an
invented zero. This is distinct from insufficient history: the flag can be true
while a mathematically undefined volume ratio remains null. Unexpected NaN/infinity
and impossible session values fail the calculation before persistence.

## Precision, adjustment and reproducibility

Historical OHLCV prices load as Decimal. Conversion to NumPy float64 is deliberate
at the numerical calculation boundary; stored reference close stays exact. Features
are float64-derived JSON numbers using Python's round-trip serialization. They are
not exact decimal financial prices, and tiny floating-point rounding differences
are expected. Warm-up is represented by JSON null, never serialized NaN.

Each calculation selects exactly one RAW, SPLIT_ADJUSTED or FULLY_ADJUSTED policy.
Mixed inputs are rejected; historical queries already filter the selected policy.
No split/dividend adjustment is performed. Long-horizon RAW and adjusted features
may have different interpretations.

The feature dataset key hashes the selection, source, calendar metadata, historical
dataset keys and a canonical **candle-content digest** (OHLCV, optional fields,
opening/availability timestamps and bar semantics). Decimal scale, input row order,
symbol order and mapping order do not change identity. Historical ingestion UUIDs
and manifests remain attached for provenance.

The feature-set key additionally hashes engine version, NumPy version, definitions,
parameters, output aliases, configuration name and policies. Run UUIDs and wall-clock
time do not affect it. Changing RSI14 to RSI10 changes the key. Changing/removing/
adding an input candle changes the key; old results remain separately queryable.
Identical reruns insert zero rows. Definitions are versioned explicitly: numerical
behavior changes must bump a version rather than overwrite a stored set.

These persisted feature snapshots are not a full historical vendor-revision store.
They preserve feature values, reference closes and an input fingerprint, not all
original OHLCV contents. `available_at` models market completion, not the date a
vendor correction was published. Full bitemporal data/revision reconstruction is
outside Phase 3.

## Generate and query

From the repository root, with `.venv` active and the development DATABASE_URL
exported:

```sh
export PYTHONPATH="$PWD/src"
alembic upgrade head
# Deterministic synthetic example; this is not observed market data.
python -m trading_bot.data.import_history \
  --provider local --file tests/fixtures/reliance_features.csv \
  --symbol RELIANCE --timeframe 5minute --adjustment RAW \
  --start '2026-01-05T09:15:00+05:30' --end '2026-01-05T14:15:00+05:30'
python -m trading_bot.features.generate \
  --source local --exchange NSE --segment CASH --symbol RELIANCE \
  --timeframe 5minute --adjustment RAW --feature-set baseline_v1 \
  --start '2026-01-05T09:15:00+05:30' --end '2026-01-05T14:15:00+05:30'
```

Use a clean research database for the example; existing different candles at these
identities are preserved as conflicts, not overwritten. Repeat `--symbol` for
multiple instruments. Use `--config PATH` for a reviewed YAML configuration. The
CLI alone interprets naive timestamps as Asia/Kolkata; Python APIs require offsets.
Pre-2026 research requires `--allow-unverified-calendar` consistently with ingestion.
No provider network access occurs during feature generation.

```python
from datetime import datetime
from trading_bot.config.settings import load_settings
from trading_bot.database.session import build_engine
from trading_bot.features.repository import FeatureRepository

engine = build_engine(load_settings())
try:
    repository = FeatureRepository(engine)
    rows = repository.get_features(
        feature_set_key="<key printed by generation>",
        symbol="RELIANCE",
        start=datetime.fromisoformat("2026-01-05T09:15:00+05:30"),
        end=datetime.fromisoformat("2026-01-05T14:15:00+05:30"),
        as_of=datetime.fromisoformat("2026-01-05T10:55:00+05:30"),
    )
    manifest = repository.get_manifest("<same key>")
finally:
    engine.dispose()
```

The pure engine/result and raw database access are construction interfaces; later
consumers must use the completion-aware repository query. No blanket database
permission boundary is claimed around internal calculation objects.

Generation emits one structured INFO summary with feature run UUID, dataset/set
keys, symbols, timeframe/range, requested feature count, loaded/generated/inserted
rows, warm-up/gap counts, invalid output count and duration. Errors abort generation;
there is no persisted partial set or per-value INFO logging. Unknown calendar
authority or Groww inputs retain warning status and provenance.

## Bounds and limitations

Generation is deliberately bounded to 100,000 input rows and a conservative 100,000
expected slots across symbols. Periods are capped at 500. Simple operations use
NumPy arrays/windows; recursive smoothers use linear causal loops. Reads and writes
are batched. Full snapshots/results are held in memory; this is not an unbounded
streaming or incremental feature platform. Large ranges must be selected explicitly;
separately generated chunks reseed and are not automatically equivalent to one long
EMA/Wilder run. There is no automatic cache eviction, scheduled computation, or
complete vendor vintage reconstruction.

See [the actual Phase 3 demonstration and verification](phase3-verification.md).
Phase 4 has not begun.

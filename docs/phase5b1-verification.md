# Phase 5B-1 verification

**PHASE 5B-1 VERIFIED COMPLETE**

Only BaselineTrendMomentumStrategy was added as a real strategy. No optimization,
ML/AI, broad performance testing, risk engine, broker connection or paper/live orders
were added. Groww remains UNVERIFIED. Phase 5B-2 has not begun. Nothing was committed.

## Architecture and behavior

The registered `baseline_trend_momentum_v1` version `1` consumes existing Phase 3
features via Phase 5A's causal context and sends requests to Phase 4. All execution,
cost, slippage, liquidity, capital and accounting calculations remain in Phase 4.

The minimal framework additions are immutable current-symbol order snapshots,
the execution cutoff, validated cancellation requests and optional structured intent
metadata. Cancellation transitions are applied by the simulator, not the strategy.
Foreign-symbol/forced-order cancellation targets are rejected. Entire output batches
are validated first. Empty metadata is omitted from legacy intent serialization;
old stored requests still deserialize. No schema migration is needed.

Entry requires EMA10 > EMA20, momentum5 > 0, RSI inside configured inclusive bounds,
sufficient volume ratio, positive ATR and valid session progress. All seven required
features must be available and finite. The strategy is LONG ONLY, without pyramiding.
It requests a MARKET BUY only when flat and without pending requests/orders. Pending
entry state and re-arming only after a false signal prevent repeated entry spam.

| Default parameter | Value |
| --- | --- |
| quantity | 10 |
| rsi_min / rsi_max | 55 / 70 |
| min_volume_ratio | 1.0 |
| entry_start_time / last_entry_time | 09:30 / 14:45 Asia/Kolkata |
| stop_atr_multiple / target_atr_multiple | 1.5 / 2.0 |

The entry freezes the causal signal ATR. Once fills are published, protection uses
actual weighted-average fill basis, not signal close: STOP_MARKET at basis − 1.5×ATR,
LIMIT target at basis + 2×ATR. Both carry one OCO group, so a positive fill cancels its
sibling. Partial entry fills update protection quantity/basis while retaining original
ATR. Exit-start cancellation prevents an unfinished entry reopening the position.
Triggered residual stops retain market-like behavior. EMA10 <= EMA20 while long
cancels competing orders and requests one MARKET exit. Phase 4 forced liquidation
remains the final intraday safety mechanism.

All parameters are typed and included in deterministic identity. Equivalent numeric
spellings normalize consistently; changing RSI or ATR multipliers changes identity.
State is separate per symbol/run. Original dataset, feature, calendar, adjustment,
source and execution provenance remain intact.

Full rules, causal timing, partial-fill handling and limitations are documented in
[baseline-strategy.md](baseline-strategy.md).

## Actual verification

| Check | Result |
| --- | --- |
| `pytest -q` with PostgreSQL | **356 passed**, no skips, 14.14 seconds |
| Previous tests | All **306** retained and passing |
| New cases | 48 unit + 2 PostgreSQL integration |
| `ruff check .` | All checks passed |
| `black --check .` | 93 Python files unchanged |
| `mypy` | No issues in 62 source files |
| `alembic current` | **0004 (head)** |
| `alembic check` | No new upgrade operations detected |
| Existing migration round-trip tests | Passed |
| `git diff --check` | Passed |

One existing Starlette/AnyIO deprecation warning remains. Database tests actually ran
against local PostgreSQL. No connection secrets were printed or committed.

Tests cover configuration validation, every entry gate, warm-up, exact time-window
boundaries, one BUY/pending suppression, actual-fill protection instead of signal-close
protection, fixed original ATR, OCO stop/target cancellation, reversal cancellation,
partial-entry weighted basis, partial stop execution, cancellation isolation,
future-feature/candle mutation, multiple symbols, fresh state on reruns, canonical
identity and persistence/CLI using real computed features. Previous Phase 4 and 5A
causal/accounting tests remain passing.

## Fresh deterministic RELIANCE demonstration

The committed 75-bar synthetic session uses the real CSV ingestion and Phase 3 feature
engine. Warm-up completes before one qualifying signal. A deliberate opening gap makes
the actual fill different from signal close. The script ran twice in a disposable
PostgreSQL schema and checked complete deterministic payload equality and persisted
round-trip equality. The schema was removed afterward.

**SIMULATED BASELINE TEST OUTPUT — NOT PROFITABILITY EVIDENCE.**

| Observation | Actual result |
| --- | --- |
| Bars / feature rows | 75 / 75 |
| Entry requests / completed trades | 1 / 1 |
| Signal time | 10:55 IST (05:25 UTC) |
| Eligible fill bar opening | 11:00 IST (05:30 UTC) |
| Fill publication time | 11:05 IST (05:35 UTC) |
| Actual entry fill | ₹1517.7585 |
| Original signal ATR | 2.5313029913131437 |
| Stop | ₹1513.9615455130 |
| Target | ₹1522.8211059826 |
| Exit | STOP; target cancelled by OCO |
| Gross P&L before slippage | −₹40.00 |
| Estimated slippage | ₹15.15 |
| Execution P&L after slippage | −₹55.15 |
| Charges | ₹41.15 |
| Net P&L | **−₹96.30** |
| Starting / ending equity | ₹200000 / ₹199903.70 |
| Identical rerun | Passed; separate audit IDs |

No parameter tuning or profitability assessment was performed. The inherited reference
cost profile emits its existing fixed-rate, source-split and rounding warnings.
The compact [demonstration JSON](phase5b1-demonstration.json) contains full simulated
orders/fills, metadata, configuration identity, run IDs and metrics.

Strategy identity:
`2ecdbba029f57187692ec7a44762970ace21a2d12ee2b385e84d43f04cca6006`.

## Files created

```text
config/strategy_baseline_trend_momentum_v1.yaml
docs/baseline-strategy.md
docs/phase5b1-demonstration.json
docs/phase5b1-verification.md
scripts/demonstrate_phase5b1.py
src/trading_bot/strategies/baseline.py
tests/fixtures/reliance_baseline.csv
tests/integration/test_baseline_storage.py
tests/unit/test_baseline_strategy.py
```

## Files modified

```text
README.md
docs/architecture.md
docs/roadmap.md
docs/strategies.md
docs/verification.md
src/trading_bot/backtesting/engine.py
src/trading_bot/backtesting/orders.py
src/trading_bot/backtesting/run.py
src/trading_bot/strategies/contracts.py
src/trading_bot/strategies/registry.py
src/trading_bot/strategies/runtime.py
```

## Final hygiene, limitations and stop point

Final inventory: **11 modified and 9 new files**, unstaged and uncommitted.
Reviewed working-tree diffs and the empty cached diff. No new migration, `.env`
change, temporary/debug file, unfinished scope TODO, generated cache/build artifact
or large dataset is included. The one-session fixture and compact JSON are deliberate
verification artifacts. Secret-pattern inspection found no actual credentials;
the existing documentation's shell variable in a database URL is a placeholder,
not a password. Pattern checks cannot guarantee detection of every secret format.

Protection is created only after a fill is published and obeys strictly subsequent
opening eligibility. That creates an explicitly documented unprotected interval and
cancel/replace latency; this is not an instantaneous live bracket. OHLC ambiguity,
stop gaps, approximate participation and fixed reference fees remain Phase 4
limitations. No tick-size/margin/shorting/risk-authority model is added. Trusted Python
strategy code is not sandboxed. This single fixture proves mechanics only; no broader
strategy validation was attempted.

Recommended commit:
`feat: add fixed baseline trend momentum strategy with fill-based ATR exits`

Stopped after Phase 5B-1. Phase 5B-2 has not begun.

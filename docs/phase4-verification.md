# Phase 4 verification — complete

**PHASE 4 COMPLETE.** Event-driven historical simulation only. Phase 5 has not
begun. No strategy, optimization, ML, broker authentication, paper/live orders or
live enablement was added. Groww authenticated behavior remains **UNVERIFIED**.
No commit was created.

## Actual verification

Final run on the local PostgreSQL development instance:

| Check | Result |
| --- | --- |
| `pytest -q` | **280 passed**, no skips, 11.74 seconds |
| Existing scenarios | All 225 retained and passing |
| New scenarios | 44 unit and 11 PostgreSQL integration cases |
| `ruff check .` | All checks passed |
| `black --check .` | 83 Python files unchanged |
| `mypy` | No issues in 57 source files |
| `alembic upgrade head` | Successful |
| `alembic current` | **0004 (head)** |
| `alembic check` | No new upgrade operations detected |
| Migration round trip | 0004 → 0003 → head passed; existing historical/feature round trips also passed |
| `git diff --check` | Passed |

One existing Starlette/AnyIO deprecation warning remains. PostgreSQL integration
checks ran; they were not skipped or replaced with SQLite. Credentials were loaded
from an external local file and were not added to the repository.

To repeat, activate `.venv`, export the development `DATABASE_URL` securely, then:

```sh
export PYTHONPATH="$PWD/src"
alembic upgrade head
TEST_DATABASE_URL="$DATABASE_URL" pytest -q
ruff check .
black --check .
mypy
alembic current
alembic check
python scripts/demonstrate_phase4.py
```

## Architecture and policies

The [backtesting guide](backtesting.md) documents the implementation, formulas,
CLI and limitations. Existing historical and feature query layers supply validated
inputs; a deterministic clock dispatches session, market, feature, scripted-decision,
order, fill and portfolio events. Execution, slippage, charges, Decimal accounting,
metrics and persistence are separate modules.

- **Timing:** `STRICT_NEXT_OPEN_SETTLE_ON_COMPLETE_V1`. A 09:15 feature becomes
  available at 09:20. A decision at 09:20 can first use the 09:25 opening, with its
  fill published at 09:30 after the execution bar completes. No signal-bar fill.
- **MARKET:** next eligible opening plus adverse slippage.
- **LIMIT:** BUY requires low ≤ limit, base=min(open,limit); SELL requires high ≥
  limit, base=max(open,limit). Slippage cannot violate the limit.
- **STOP_MARKET:** BUY high ≥ trigger, base=max(open,trigger); SELL low ≤ trigger,
  base=min(open,trigger). Opening gaps use the adverse opening. Triggered residual
  quantities remain market-like on subsequent bars.
- **Ambiguity:** if long stop and favorable exit limit are both reachable, process
  the stop first, suppress the favorable limit for that bar and record
  `INTRABAR_AMBIGUITY`. Explicit OCO siblings cancel after a positive fill.
- **Liquidity:** shared per-symbol/bar floor(volume × participation rate), default
  10%; partial fills persist. Explicitly disabling participation removes the cap.
- **Capital/accounting:** whole shares, long-only, 1× cash; insufficient available
  cash rejects the order. Decimal cash and weighted-average inventory support adds,
  partial exits and full exits. Fees are deducted once; slippage is embedded in price.
- **Session:** configurable cutoff, default 10 minutes before close, forced
  liquidation with fees/slippage; remaining DAY orders expire. Incomplete forced
  liquidation fails the run. Missing expected candles also fail the run.
- **Provenance:** dataset/feature keys, source, exchange/segment, symbols, interval,
  adjustment, range, calendar, feature definitions, script and all assumptions enter
  the manifest/configuration identity. Repeated runs have distinct audit UUIDs and
  identical deterministic results; they are not deduplicated.

Migration `0004_backtesting.py` adds six simulated-only tables:
`backtest_runs`, `backtest_orders`, `backtest_fills`, `backtest_trades`,
`backtest_equity_points`, `backtest_events`. Run foreign keys and fill-to-order
foreign keys enforce ownership. A RUNNING audit commits first; completed results
commit atomically. Failures roll back result writes and retain a FAILED audit when
the database is available. Financial JSON amounts retain exact decimal strings.

Metrics include gross/execution/net P&L, each cost component, slippage, return,
trade statistics, expectancy, turnover, holding duration, exposure, daily P&L and
peak-to-equity drawdown. Daily Sharpe/Sortino require at least 20 sessions and valid
nonzero denominators; annualization uses 252 and zero risk-free/target returns.
Trade markers, equity/drawdown curves and cost distributions are available as data;
no dashboard was built.

## Cost reference and worked results

Profile: `groww_nse_intraday_reference_v1`, version **2026-09-24-research-1**.
It records sources and explicitly unverified broker rounding/effective dates.
Per-order cumulative brokerage for turnover T is
`max(min(20, .001*T), min(5, .025*T))`, with zero at zero turnover. SELL STT is
0.025%, BUY stamp is 0.003%, exchange is 0.00297%, SEBI/IPFT are each 0.0001%,
and GST is 18% on configured taxable fee components. Partial fills pay cumulative
fee increments. The research rounding policy is paise HALF_UP. No delivery DP fee.

The guide links the official sources and explains the discrepancy between Groww's
published exchange/IPFT split and the NSE circular effective March 2026. Fixed
reference rates, the split discrepancy and unverified rounding are visible run
warnings, not claims of authenticated billing accuracy.

The fresh demonstration imported 75 synthetic RELIANCE 5-minute candles, generated
features and persisted four runs in a disposable PostgreSQL schema. Starting
capital was **₹2,00,000**. The schema was removed after assertions passed; compact
retained evidence is [phase4-demonstration.json](phase4-demonstration.json).

| Metric | Reference costs, 5 bps |
| --- | ---: |
| Gross P&L before slippage | ₹85.0000 |
| Estimated slippage | ₹15.0475 |
| Brokerage | ₹30.09 |
| Other taxes/fees | ₹10.79 |
| Total charges | ₹40.88 |
| Net P&L | **₹29.0725** |
| Ending equity | **₹2,00,029.0725** |
| Completed trades | 1 |
| Maximum equity drawdown | ₹26.2425 / 0.01312125% |

BUY 10: decision 09:20 IST, eligible opening 09:25, published fill 09:30;
base ₹1500.50, slipped price ₹1501.25025, charges ₹18.74.
SELL 10: decision 10:30, eligible opening 10:35, published fill 10:40;
base ₹1509.00, slipped price ₹1508.2455, charges ₹22.14.
The ledger, cash, position, equity and drawdown reconcile:
₹85 − ₹15.0475 − ₹40.88 = ₹29.0725.

| Comparison | Net P&L | Assertion |
| --- | ---: | --- |
| Identical rerun, 5 bps/reference costs | ₹29.0725 | Deterministic payload identical, distinct run UUID |
| Higher slippage, 10 bps/reference costs | ₹14.0250 | Worse execution/net result |
| Zero costs, 5 bps | ₹69.9525 | Difference equals ₹40.88 charges |

These are **SIMULATED TEST OUTPUT**, not strategy-profitability evidence. Profit
factor and daily ratios are null for this one-trade, one-session demonstration.

## Evidence for causal and accounting guarantees

`tests/unit/test_backtesting.py` explicitly tests the extreme signal candle
(open 100/high 200/low 90/close 190) and proves execution uses the later opening.
Future-candle mutation leaves earlier event/order/fill/equity records unchanged.
Other tests cover feature availability/warm-up, exact adverse slippage, independent
BUY/SELL fee components, minimum/cap rules, partial charges, limit/stop reachability,
a ₹100 stop gapping to ₹95, conservative ambiguous exits, shared participation,
persistent triggered stops, insufficient cash, partial exits, session flattening,
weekend-separated sessions, multiple symbols and known drawdown/ratio examples.

`tests/integration/test_backtest_storage.py` checks all ledgers and typed Decimal
round trips, deterministic reruns, chronological records, foreign keys, failed-write
rollback, durable failed audits, incompatible/stale/missing inputs, migration
round trips and the CLI against PostgreSQL.

## Files and repository hygiene

Created:

```text
config/groww_nse_intraday_reference_v1.yaml
docs/backtesting.md
docs/phase4-demonstration.json
docs/phase4-verification.md
migrations/versions/0004_backtesting.py
scripts/demonstrate_phase4.py
src/trading_bot/backtesting/__init__.py
src/trading_bot/backtesting/accounting.py
src/trading_bot/backtesting/clock.py
src/trading_bot/backtesting/config.py
src/trading_bot/backtesting/costs.py
src/trading_bot/backtesting/decisions.py
src/trading_bot/backtesting/engine.py
src/trading_bot/backtesting/events.py
src/trading_bot/backtesting/execution.py
src/trading_bot/backtesting/inputs.py
src/trading_bot/backtesting/metrics.py
src/trading_bot/backtesting/orders.py
src/trading_bot/backtesting/report.py
src/trading_bot/backtesting/repository.py
src/trading_bot/backtesting/results.py
src/trading_bot/backtesting/run.py
src/trading_bot/backtesting/service.py
src/trading_bot/backtesting/slippage.py
tests/fixtures/backtest_decisions.yaml
tests/fixtures/reliance_backtest.csv
tests/integration/test_backtest_storage.py
tests/unit/test_backtesting.py
```

Modified:

```text
README.md
docs/architecture.md
docs/roadmap.md
docs/verification.md
src/trading_bot/api/app.py
src/trading_bot/database/models.py
tests/conftest.py
tests/integration/test_features.py
tests/integration/test_history.py
```

The existing integration assertions and API readiness now expect schema 0004;
previous test scenarios were retained. All 37 changed/new files above belong to
Phase 4. Nothing is staged or committed. The migration, complete simulator package,
tests, fixtures, reference config and documentation are included in this inventory.

Repository checks found no known local database credential or recognizable token/
private-key patterns in tracked or candidate files. No `.env` changes, generated
caches/build artifacts, temporary/debug files or Phase 4 TODO/unfinished placeholders
were found among candidates. The small synthetic fixture and approximately 38 KB
compact demonstration JSON are intentional test/documentation evidence, not large
market datasets. This inspection is not a guarantee against every possible secret
format.

## Remaining limitations and stop point

OHLC reachability, conservative ambiguity and participation are approximations;
there is no queue, spread, tick-size or precise intrabar model. Positions/fills are
published on the completion clock. Only complete intraday sessions, long inventory
and 1× cash are supported. Data and events are held in bounded in-memory snapshots.
Costs are fixed research assumptions, not historical contract-note reproduction.
Corporate-action transformations, vendor vintages, crash recovery, strategies,
optimization, ML, short/margin models and broker integration are outside this phase.
Existing historical calendar authority/coverage limitations remain unchanged.

Recommended commit:
`feat: add causal event-driven historical backtesting simulator`

Stopped after Phase 4. Phase 5 has not begun.

# XAUUSD G2C4B1 — bid/ask execution and position lifecycle

This is a deterministic research execution-mechanics component, not a broker or
strategy backtester. The existing NSE backtester, G2C4A strategy and market-data
storage are unchanged. No historical strategy signals are consumed.

## Central side selection

`execution/xauusd.py` reuses existing PositionDirection, PositionSnapshot,
MarketQuote, Side and raw_price_movement. No duplicate direction/position model is
introduced. Each transition centrally selects the executable side:

| Lifecycle action | Side | Observed price |
| --- | --- | --- |
| LONG open | BUY | ASK |
| LONG close | SELL | BID |
| SHORT open | SELL | BID |
| SHORT close | BUY | ASK |

The API takes a validated quote, not a caller-selected fill price or action side.
ExecutionFill independently validates that direction, intent, action and price
agree, so even a manually constructed midpoint fill record is rejected when it
is not the executable side. Midpoint remains analytical only. With a legitimate
zero-spread quote, bid, ask and midpoint numerically coincide; side selection still
uses BUY/ASK or SELL/BID, not a midpoint rule.

## Lifecycle, validation and timing

`XAUUSDExecution` is immutable: FLAT -> OPEN LONG/SHORT -> CLOSED. Methods return
a new validated state; prior states and fills remain intact. A closed lifecycle
is terminal. Another lifecycle needs a new explicitly supplied simulation UUID.
No partial closes, pyramiding, simultaneous hedged positions, atomic reversals,
auto-reentry or account-level hedging/netting policy is implemented.

Opening requires an explicit positive finite Decimal volume; no default trading
lot is supplied. Volume is metadata only, with no risk calculation or broker
volume-step assertion. Price values must be finite positive Decimals; ask must
be >= bid. Naive timestamps are rejected and aware timestamps normalized to UTC.

The execution timestamp must equal the supplied quote's observed timestamp exactly.
Future and stale observations are both rejected: this checkpoint has no stale-quote
policy, candle-to-quote conversion, latency or slippage model. A close cannot precede
entry, but equal timestamps are allowed for the mechanical unchanged-quote example.
A stored five-minute OHLC bar is not automatically a quote executable at its boundary.
Callers must provide truthful available quote data and source identity; the simulator
does not independently authenticate those assertions.

Invalid opens/closes, duplicate closes, invalid volume/quotes, inconsistent lifecycle
records and wrong execution sides fail without mutating state. Required open/close
information is still validated by the existing PositionSnapshot model.

## Immutable audit records and determinism

Each ExecutionFill contains deterministic execution UUID, position UUID, direction,
OPEN/CLOSE intent, BUY/SELL action, exact executed price, full immutable quote,
source market-data identity and optional strategy-decision UUID. Canonical symbol,
UTC timestamp, bid, ask and spread are exposed from the retained quote. Serialization
preserves the quote and Decimal strings; derived accessors need not duplicate them.

Position and fill UUIDs are UUID5 values derived from the explicit simulation UUID
and lifecycle role. Identical simulation ID, inputs and actions reproduce identical
states and records. Distinct independent runs must use distinct simulation IDs.
Entry and exit share position identity and have different execution identities.
The optional correlation slot supports a future real strategy decision; the demo
leaves it None. No fake G2C4A relationship or database journal event is created.

## Raw movement and bounded demonstration

LONG raw movement = exit price - entry price.
SHORT raw movement = entry price - exit price.
The existing exact Decimal direction-aware helper is reused. Before close, movement
is None. Favorable movement is positive and adverse movement negative; volume does
not multiply it. Raw movement is not final monetary/account P&L.

Run `PYTHONPATH=src .venv/bin/python scripts/demo_xauusd_execution.py`.
The script uses only a synthetic TEST_FIXTURE quote at 2024-02-20T10:00:00Z with
bid 2000.00 and ask 2000.50, and explicitly synthetic volume 0.37. It produces
`docs/xauusd-execution-demo.json`, including both full fill records and quotes.

| Synthetic lifecycle | Entry | Exit at unchanged quote | Raw movement |
| --- | ---: | ---: | ---: |
| LONG | ASK 2000.50 | BID 2000.00 | -0.50 |
| SHORT | BID 2000.00 | ASK 2000.50 | -0.50 |

Each unchanged-quote round trip has a mechanical disadvantage of one 0.50 spread
in price units, not two spreads and not a separately debited cash fee. There is no
claim about real fills, profitability or account balances.

Contract sizing/conversion, commissions, slippage, margin/leverage, swap/financing,
SL/TP, trailing stops, broker rejections, latency and strategy integration remain
future work. No MT5, live orders, migrations, or G2C4B2 work.

## Verification actually run

- Focused execution tests: 16 passed. Full `pytest -q`: **782 passed**, no skips,
  one existing Starlette/AnyIO deprecation warning. Existing position/quote,
  XAUUSD and NSE backtester regressions passed.
- Ruff passed. Final Black check passed (149 files unchanged). Mypy passed
  (85 source files). Final checks include the synthetic demonstration script.
- Alembic current **0008 (head)**; Alembic check: no schema drift.
- Both deterministic synthetic lifecycles were executed and saved as JSON evidence.
- Git status, working/staged diffs and whitespace reviewed: six new files, no
  existing files modified, nothing staged or committed. No dependencies/migrations.

Recommended commit: `feat: add XAUUSD bid ask execution lifecycle`.

Stopped at G2C4B1. No strategy integration, account P&L or G2C4B2 work.

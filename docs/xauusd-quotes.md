# XAUUSD G1F — quoted bid, ask and spread

`MarketQuote` is an immutable concept separate from NSE OHLC candles. It records
canonical symbol, aware timestamp normalized to UTC, positive finite Decimal bid
and ask, and an optional typed source. Actual Decimal objects are required;
binary floats, integers and numeric strings are rejected at Python construction.
JSON output preserves prices as strings. Naive timestamps and crossed quotes
(bid > ask) are rejected. Equal bid/ask is intentionally allowed, including for
synthetic zero-spread data; equality alone makes no claim about market realism.

Bid is the price at which the market/broker buys from us. Ask is the price at
which it sells to us. Therefore `price_for_side(Side.BUY)` returns ask and
`price_for_side(Side.SELL)` returns bid, regardless of opening or closing intent.
An explicit side is required; there is no midpoint execution default.

- LONG opens by buying at ask and closes by selling at bid.
- SHORT opens by selling at bid and closes by buying at ask.

At an unchanged quote, either immediate round trip has raw directional movement
of minus the spread. This explains why a newly opened position can appear
slightly negative when marked to its closing side. These helpers do not calculate
monetary P&L, fill orders, or guarantee that the quoted price is executable.

`spread` is exactly ask minus bid. `mid` is exactly (bid + ask) / 2 and is for
analytics, not normally execution. Decimal precision is locally expanded for
these calculations; no float arithmetic or rounding of inputs is used.

`spread_in_ticks(specification)` requires an explicit ContractSpecification and
matching canonical symbol. It returns an exact Decimal whole-tick count. A
fractional count raises `SpreadAlignmentError` rather than rounding. The check
concerns spread alignment only, not individual quote price alignment to a broker
price grid; callers can separately use contract price validation. There is no pip
size or pip definition. Broker applicability of the supplied specification is the
caller's responsibility; the canonical-symbol match does not verify broker identity.

QuoteSource supports TEST_FIXTURE, HISTORICAL_PROVIDER and the future label
MT5_TERMINAL. Source defaults to unknown/None, never MT5. Labels are provenance
assertions, not authenticated verification. No adapter or broker connection is
implemented. Test examples are synthetic. No arbitrary provider payload or
credentials are accepted as fields. There is no persisted quote identity/store.

Existing NSE historical and backtest behavior is unchanged. No slippage, latency,
market impact, partial fills, broker rejection, strategy, sizing, margin/leverage,
SL/TP management or monetary accounting has been introduced. No schema change or
migration is needed. G2 has not begun.

## Verification actually run

- `pytest -q`: **649 passed**, no skips; one existing Starlette/AnyIO warning.
  Includes all 621 prior cases and 28 quote cases; NSE/backtester regressions pass.
- `ruff check .`: passed.
- `black --check .`: passed, 116 files unchanged.
- `mypy`: passed, 73 source files.
- `alembic current`: **0006 (head)**.
- `alembic check`: no new upgrade operations detected.
- Git status/diff reviewed; `git diff --check` clean. G1F adds three files;
  three pre-existing untracked G1E files are preserved unchanged. No tracked files
  modified, no migration or commit created.

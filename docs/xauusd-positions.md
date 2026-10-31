# XAUUSD G1E — long and short position semantics

`PositionDirection` explicitly distinguishes LONG and SHORT. It reuses the existing
generic `domain.models.Side` BUY/SELL enum (whose serialized values are lowercase):

| Direction | Open | Close |
| --- | --- | --- |
| LONG | BUY | SELL |
| SHORT | SELL | BUY |

These are conceptual relationships only; they do not submit orders. The separate
backtester side vocabulary and mutable long-inventory accounting remain unchanged.
Short positions in this domain do not enable shorting in the NSE backtester.

`PositionSnapshot` is immutable and contains a position UUID, canonical symbol,
direction, positive volume, entry price and opening timestamp. A closed snapshot
requires both exit price and closing timestamp. Closing before opening is rejected;
equal timestamps are allowed because source timestamp resolution may be coarse.
Partial closing information is rejected. No partial-close lifecycle is implemented.
Symbols are canonical identities; LONG and SHORT carry no NSE or asset-class
classification. A representation alone does not assert market eligibility.

Volume is always positive. Direction is never inferred from its sign. Volume and
prices require actual finite positive Decimal objects; binary floats, integers
and numeric strings are rejected at the Python construction boundary. JSON output
uses decimal strings, which callers must explicitly decode to Decimal when
constructing from a Python mapping. Datetimes must be timezone-aware and are
normalized to UTC. Naive datetimes are rejected.

`raw_price_movement(direction, entry_price, exit_price)` returns:

- LONG: exit minus entry.
- SHORT: entry minus exit.

Positive means favorable, negative unfavorable, zero unchanged. Decimal precision
is locally increased to retain exact subtraction for the input prices, independent
of ambient precision. This is price movement, **not final monetary P&L**. It does
not multiply by volume, contract size or tick value, or apply spread, commission,
swap, margin or account-equity changes.

MT5 hedging versus netting is unresolved broker/account behavior. The snapshot
imposes neither account policy. Position sizing, execution, SL/TP/trailing,
strategies, order submission and MT5 integration are outside this checkpoint.
There is no persistence change or migration. G1F has not begun.

## Verification actually run

- `pytest -q`: **621 passed**, no skips; one existing Starlette/AnyIO warning.
  All 572 prior cases and 49 new position cases passed, including NSE/backtesting.
- `ruff check .`: passed.
- `black --check .`: passed, 114 files unchanged.
- `mypy`: passed, 72 source files.
- `alembic current`: **0006 (head)**.
- `alembic check`: no new upgrade operations detected.
- Git status and diff reviewed: three new files, no existing files modified;
  `git diff --check` clean. No commit or migration created.

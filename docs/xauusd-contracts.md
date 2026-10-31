# XAUUSD G1D — contract and lot specification

A lot is broker-defined quantity metadata. XAUUSD contract size, minimum volume,
volume step and tick size are not universal and have no production defaults.
`ContractSpecification` is an immutable domain model, independent of NSE bars,
orders, sessions and persistence. No migration is needed.

Required fields: canonical symbol XAUUSD (default), contract size, minimum volume,
volume step, tick size and specification source. Optional fields: broker symbol,
maximum volume, tick value, price digits, minimum stop distance and observed-at.
Schema version is 1. Broker aliases such as GOLD or XAUUSDm never replace the
canonical symbol. A missing broker symbol is valid for research metadata.

All quantity/price/value fields require actual finite positive `Decimal` objects;
Python floats, integers and strings are rejected for these fields. Optional
unknown values should be omitted. Zero minimum stop distance is not represented
in this version: absence means unspecified, not an asserted zero restriction.
Price digits is a nonnegative integer. Observation datetimes must be aware and
are normalized to UTC. JSON serialization emits exact decimal strings; callers
loading a Python mapping from JSON must explicitly reconstruct Decimal fields.

Contract size describes underlying units per lot; volume fields use lots. Tick
size and minimum stop distance use price units, not platform-specific points.
Tick value is optional caller-supplied metadata; its currency and calculation
basis are not modeled/verified in G1D and must be resolved before future risk
calculations. Price digits is display metadata; tick size determines alignment.

`validate_volume(Decimal(...))` checks positivity, inclusive minimum/maximum and
exact step alignment. `validate_price(Decimal(...))` checks positive tick-aligned
prices. Success returns None; failure raises `ContractValidationError` with a
stable `ContractValidationCode`. Neither validator rounds, sizes or submits
anything. Integer-ratio arithmetic avoids dependence on Decimal context precision.
Both grids have an explicit zero origin. Minimum volume must be on the volume
grid; maximum volume is an inclusive cap, not necessarily a grid point. Offset
broker grids would need a later explicit model extension, never silent rounding.

`specification_id` is SHA-256 of a canonical serialization of every field,
including provenance, broker symbol, observation time and schema version.
Equivalent Decimal scales (37 versus 37.000) have identical identities; changed
broker-relevant values produce different identities. A new observation time also
produces a new identity. This is a reproducibility fingerprint, not proof of
broker authenticity or a persisted version history.

Sources: MT5_TERMINAL, BROKER_DOCUMENTATION, TEST_FIXTURE, MANUAL_RESEARCH. These
are declarations, not verification. All added test specifications are explicitly
synthetic TEST_FIXTURE data. No real broker specification is claimed.

Future MT5 integration will read actual broker specifications. The future risk
engine will combine account risk + stop distance + contract specification →
allowed volume. That calculation is **not implemented** here. There is no MT5,
broker connection, strategy, margin/leverage, order or SL/TP behavior. Existing
NSE functionality remains unchanged. G1E has not begun.

## Verification actually run

- `pytest -q`: **572 passed**, no skips; one existing Starlette/AnyIO warning.
  Includes all 486 prior cases and 86 new contract cases; NSE regressions passed.
- `ruff check .`: passed.
- `black --check .`: passed, 112 files unchanged.
- `mypy`: passed, 71 source files.
- `alembic current`: **0006 (head)**.
- `alembic check`: no new upgrade operations detected.
- Git status/diff reviewed: three new files, no existing files modified;
  `git diff --check` clean. No commit or migration created.

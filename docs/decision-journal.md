# XAUUSD G1B — decision and trade audit journal

Technical logs **are not** the trading decision journal. Existing technical logs
continue to describe infrastructure errors. The PostgreSQL `decision_events`
table records structured business explanations for future dashboard questions:
**“What did the bot do, and why?”** G1B provides storage and vocabulary only.
No component makes trading decisions, sends orders or fetches gold data here.
Indian-market behavior remains preserved.

A future lifecycle can be reconstructed as:
market evaluated → setup detected → trade approved/rejected → order → position
→ SL/TP management → close. Event and reason enums describe these concepts; their
presence does not mean the corresponding rules or management behaviors exist.
New enum members can be added explicitly in code, with compatibility tests. There
is no inferred event/reason compatibility or lifecycle state machine in G1B.

## Schema and storage

`DecisionEvent` is frozen, has an event UUID, UTC timestamp, canonical symbol,
source/component, schema version 1, typed event and reason, required summary and
structured details. Strategy ID and UUID correlation references (evaluation,
trade, order, position, strategy run) are optional. Optional market/account
snapshots and previous/new values support later explanations. No NSE fields or
broker identifiers are required. Naive timestamps are rejected; aware timestamps
are normalized to UTC.

`MarketSnapshot` optionally records timestamp, bid, ask, spread, mid, timeframe,
feature values, regime, volatility state and session label. `AccountSnapshot`
requires currency (INR or USD) and optionally records timestamp, balance, equity,
free/used margin, open-position count, daily realized/unrealized P&L and current
drawdown. Drawdown is an account-currency amount, not a percentage. Snapshots are
observations supplied by callers; the journal calculates none of their values
and does not verify their financial consistency or freshness.

Migration **0006** adds only `decision_events`. Searchable identifiers, event/reason
codes, source and version use typed columns; the complete versioned record is
stored in JSONB. Composite indexes cover timestamp, symbol, event type, reason,
trade and strategy queries. Correlation UUIDs are opaque audit identifiers with
no foreign keys to future trading tables. The readiness schema revision advances
to 0006. Downgrade refuses to remove a nonempty journal.

`DecisionJournal.record_event()` validates and commits one plain INSERT. Duplicate
IDs fail rather than overwrite. There are no edit/delete/upsert methods. This is
append-only at the application API level, not a database permission/trigger or
cryptographic tamper-proof guarantee. Direct privileged SQL remains possible.
Future corrections should be new audit events; no correction workflow exists yet.

Reads return immutable events ordered by timestamp, then event UUID for equal
instants. UUID ordering is a deterministic tie-breaker, not causal sequence.
`get_events()` supports all correlation filters and optional UTC `[start, end)`.
Convenience methods provide trade, symbol/range and reason queries. Queries return
all matching records; pagination/retention are deferred. Inserts are independent
transactions, not yet coordinated with future trading operations.

```python
from trading_bot.journal.repository import DecisionJournal
from trading_bot.journal.models import ReasonCode

journal = DecisionJournal(engine)
journal.record_event(event)
events = journal.get_trade_journal(event.trade_id)
rejections = journal.get_events_by_reason(ReasonCode.MINIMUM_LOT_EXCEEDS_RISK)
```

## Exact values and secret safety

Snapshot financial fields are finite Decimal values; JSON writes exact decimal
strings. Nested Decimal metadata and previous/new values normalize to strings
while preserving scale. Metadata reads keep those strings: the journal does not
guess which arbitrary strings are financial values. Binary floats are rejected
in financial fields and arbitrary metadata. Nested mappings and sequences are
copied and frozen; the caller cannot mutate recorded values through shared inputs.

Known credential key patterns are recursively rejected, including password,
secret, token, API key, private key, credential, authorization and database URL.
Unknown schema fields and arbitrary non-JSON objects are rejected. Validation
messages hide input values. Existing technical-log utilities only allowlist log
context, so the journal uses its own recursive metadata guard instead of changing
logging. Key detection is conservative and is not a general secret detector:
callers must never put secrets in summaries, plain string values or misleadingly
named fields. Do not log validation `.errors()` payloads, which can include inputs.

## Synthetic demonstration

`journal.demo.synthetic_events(Path("config/xauusd_v1.yaml"))` creates seven fixed
records using the USD `Decimal("500")` reference account. All are explicitly marked
synthetic, with `rules_implemented=false` and deterministic timestamps/IDs.

1. Market evaluated → setup detected → trade rejected, with fixture reason
   `MINIMUM_LOT_EXCEEDS_RISK`, allowed risk `"2.50"`, illustrative minimum lot
   `"0.01"` and calculated risk `"4.80"`.
2. A **separate** synthetic trade: position opened → stop created → stop moved
   → position closed. The stop-move example records `"4097.80"` → `"4102.60"`.

These are hand-authored fixture observations, not calculations, a sizing default
or evidence of an implemented risk rule. The JSON example is in
[decision-journal-demo.json](decision-journal-demo.json). Integration tests persist
and retrieve these records only in disposable PostgreSQL schemas. Nothing emits
these events into the normal application journal automatically.

No MT5, strategy, risk authorization, stop/target management, broker operations,
or gold data has been introduced. G1C has not begun.

## Verification actually run

- Full PostgreSQL `pytest -q`: **449 passed**, no skips; one existing
  Starlette/AnyIO deprecation warning. Includes 401 prior cases and 48 new cases.
- `ruff check .`: all checks passed.
- `black --check .`: 108 files unchanged.
- `mypy`: no issues in 69 source files.
- `alembic upgrade head`: succeeded.
- `alembic current`: **0006 (head)**.
- `alembic check`: no new upgrade operations detected.
- Downgrade to 0005/re-upgrade and nonempty-journal downgrade rejection passed
  in disposable PostgreSQL schemas; existing migration regression tests passed.
- `git diff --check`: clean. Status, working diff and staged diff reviewed;
  staged diff empty. New files reviewed for credentials, temporary artifacts,
  debug output and unfinished markers; none found.

No automatic commit was made. Recommended commit:
`feat: add append-only decision audit journal for XAUUSD research`.

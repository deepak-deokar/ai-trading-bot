# Strategy framework (introduced in Phase 5A)

Market/completed features → Strategy → TradeIntent → existing backtester.
**Strategy suggests. Execution executes. A future risk engine will authorize or
reject.** The framework adds no broker capabilities or risk engine. NoOp never requests a trade. Phase 5B-1 also registers the fixed
[Baseline Trend Momentum](baseline-strategy.md) strategy. Phase 5B-2 has not begun.

## Interface and lifecycle

`strategies.contracts.Strategy` is a runtime-checkable protocol:

```python
def evaluate(self, context: StrategyContext) -> Sequence[StrategyRequest]:
    ...
```

An empty list/tuple is normal no-action. There is no mandatory signal, order or
position. The registered factory creates a fresh instance for each symbol for each
run. State can live on that instance; it must never live in module/class globals or
shared factory closures. Constructors initialize/reset state. Built-in NoOp has no
state. Test-only callbacks exercise intents and state without adding a registered
trading strategy or duplicating Phase 4's scripted-decision source.

## Causal observations

Each completed candle triggers one evaluation, after Phase 4 has settled eligible
orders and marked known prices. `StrategyContext` contains:

- UTC simulated current time, completed immutable Bar (including symbol, exchange,
  segment, timeframe, source and adjustment) and availability timestamp;
- only that bar's feature values and unavailable/warm-up reasons, in read-only maps;
- that symbol's position quantity and average entry price;
- current shared-account cash/equity as Decimal snapshots;
- current session open/close, immutable scalar parameters and strategy identity.

The runtime provides no database, history array, future row, mutable portfolio,
engine or order-execution reference. Bar objects and feature mappings are detached
from engine inputs. Context and mappings are immutable through normal APIs.
`available_at <= current_time` is checked before calling a strategy. A delayed
feature row fails the run; it is never supplied early. Warm-up values remain null,
and an intent naming them in `required_features` is rejected.

For a 09:15–09:20 bar, the first evaluation is **09:20 IST**. An intent created
then first qualifies for **09:25 opening**, with fill publication at **09:30**,
exactly as Phase 4 specifies. Evaluation also occurs at the final candle completion;
no-action is valid, while new intents at session close are rejected. Cutoff and
capital checks remain in the existing execution pipeline.

Market/feature data and strategy state are symbol-local. Account cash/equity are
intentionally shared observations of the portfolio, not per-symbol allocations.
Simultaneous completions retain Phase 4's deterministic event order; the account
snapshot reflects events already processed. Cross-sectional observations are absent.

This is an API boundary for trusted application code, **not a Python security
sandbox**. Arbitrary hostile Python could import external services or inspect process
internals. Configuration cannot import code; only reviewed registry implementations
are permitted. Future implementations must remain deterministic, avoid wall-clock/
random/external inputs and obey the factory state-isolation contract.

## Trade intents and validation

The framework reuses `backtesting.orders.TradeIntent` (also importable from
`strategies.contracts`) instead of introducing a second competing request model.
It remains distinct from SimOrder, Fill and Trade. Fields include unique run-local
`reference`, symbol, side, whole-share quantity, order type, created_at,
feature_timestamp, optional limit/trigger, required_features, DAY validity and the
existing optional OCO group. No new sizing, stop-loss or target decision logic exists.

Returned values are revalidated even if a callback used unchecked Pydantic copying.
Quantity must be positive integral, side/type/symbol must be valid, and LIMIT/STOP
requests must have their required prices. The runtime also requires:

- the context symbol and exact evaluation time;
- the current context's feature timestamp;
- unique references across the run and available required features;
- a sequence of at most 10,000 total intents, before session close.

Failures raise `IntentValidationError`/`StrategyError`, both simulation errors.
Ordinary Pydantic model construction raises its typed `ValidationError` for invalid
fields. At the service boundary, failures retain a sanitized FAILED run audit;
no partial successful results are published. Strategy identity is linked through
manifest and STRATEGY/DECISION events rather than changing historical intent payloads.

## Typed configuration, registry and identity

```yaml
name: noop
version: '1'
parameters: {}
```

`StrategyConfig` validates names, version and scalar parameters. Each registered
`Definition` has a stable name/version/implementation ID, a typed parameter model
and a trusted factory. NoOp rejects all extra parameters. Registry resolution
rejects unknown names/versions; duplicate registration also fails. It exposes a
validated `StrategyPlan`, whose `manifest()` supplies configuration and identity.

SHA-256 identity covers name, version, stable implementation ID and validated
parameters, using canonical serialization. Reordered parameter keys produce the
same hash; changed parameters/version/implementation ID change it. Configuration is
snapshotted at resolution so later mutation of the caller's dictionary cannot alter
a run. Implementation/version identifiers must be maintained when code changes;
this is not automatic source-code hashing.

The optional strategy manifest participates in the existing backtest configuration
hash and is recorded before execution and on completion. Dataset/feature/calendar/
source/adjustment/cost/execution provenance remains present. Separate reruns have
unique audit IDs but identical deterministic result payloads. Existing script-only
runs retain their previous manifest format and numerical behavior.

## CLI and demonstration

The existing runner takes exactly one decision source:
`--decision-script PATH`, `--strategy noop`,
`--strategy baseline_trend_momentum_v1`, or
`--strategy-config config/strategy_noop.yaml`.

After importing the existing RELIANCE fixture and generating its feature set:

```sh
python -m trading_bot.backtesting.run \
  --symbol RELIANCE --source local --timeframe 5minute --adjustment RAW \
  --start '2026-01-05T09:15:00+05:30' --end '2026-01-05T15:30:00+05:30' \
  --starting-capital 200000 --feature-set-key '<generated-key>' \
  --strategy-config config/strategy_noop.yaml --cost-model zero --slippage-bps 5
```

For a fresh end-to-end check with DATABASE_URL exported securely and PYTHONPATH=src:

```sh
python scripts/demonstrate_phase5a.py
```

It creates a disposable PostgreSQL schema, imports the existing 75-bar synthetic
fixture, generates/loads features, runs NoOp twice, asserts no intents/orders/fills
and unchanged capital, checks persistence and deterministic equality, writes compact
[demonstration evidence](phase5a-demonstration.json), then drops only its own schema.

No new migration is required: existing backtest JSON manifests/events store strategy
provenance. The Phase 5A checkpoint added no real strategy. Phase 5B-1 adds the fixed baseline;
optimization, ML, broker connection and live enablement remain absent. Groww stays
UNVERIFIED. Current-bar observations, scalar parameters and
trusted per-symbol factories are intentional checkpoint limits. Rolling context,
state checkpoint recovery and a production risk authorization layer are deferred.

## Phase 5B-1 additions

Contexts also expose immutable current-symbol OrderSnapshot values and the simulator
exit cutoff. StrategyRequest is TradeIntent or CancelIntent; cancellations are
validated for the current symbol and cannot target forced orders. They pass through
the simulator transition ledger. TradeIntent optionally records structured string
metadata; empty metadata is omitted to preserve legacy serialized intent payloads.
See [baseline rules and partial-fill lifecycle](baseline-strategy.md).

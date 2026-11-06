# XAUUSD G2C4B5 — explicit-plan simulator core

This is deterministic orchestration of the existing XAUUSD mechanics, not a
strategy or profitability study. One explicit plan is processed in memory:

explicit plan → eligible opening → risk sizing → executable-side entry → static
protection → completed-bar monitoring → protective close → USD accounting.

There are no strategy signals, stop/target selection rules, parameter optimization,
portfolio scheduling, pyramiding, reversal, margin, swap, MT5 or database writes.
No existing domain/execution/accounting/sizing/protective/NSE code was modified.

## Plan and causal entry

`TradePlan` is immutable and retains plan UUID, canonical XAUUSD, direction,
creation and earliest-entry timestamps, explicit stop/optional target, USD equity,
exactly one explicit risk fraction or amount, `LinearUSDContract`, `Commission`
and source/reason identity. Financial inputs are strict Decimal. Timestamps must
be aware and normalize to UTC. Entry cannot precede plan creation. Malformed plans
raise Pydantic validation errors; no live risk fraction or broker defaults exist.

`simulate_trade(plan, observations, as_of=...)` accepts an iterable of identified
`SimulationBar` objects containing existing separate bid/ask `QuoteBar` data.
Consumed observations must have strictly increasing opening times and distinct
market-data IDs; invalid order is rejected, never sorted. Missing intervals stay
missing. The first incomplete bar ends processing at the explicit `as_of` cutoff.
The simulator does not enter from an incomplete bar.

The first completed bar with opening >= earliest entry is replayed in two phases:
opening, then completion. If a plan is created at the close of a prior signal bar,
its earliest entry can be that boundary, which is the next bar's opening; it
cannot enter inside the prior bar. An entry time inside a bin waits for the next
available bin opening. Pre-entry bars cannot supply fills or trigger protection.
Only `bid_open` and `ask_open` participate in sizing and entry. That bar's full
high/low can then be used for protective evaluation at completion, after the
instruction is attached at opening. No earlier extrema are used retroactively.

The entry convention is explicitly `MODELED_BAR_OPEN_BID_ASK`: a side-open quote
is constructed for the existing central lifecycle's BUY-at-ASK / SELL-at-BID
method. This is a historical simulation assumption, not a claim that the first
tick occurred exactly on the bin boundary or that a live fill was achievable.
The original opening bar and source ID are retained in `entry_observation`; the
modeled quote does not claim MT5 or another provider through its source enum.

## Component reuse and rejection

The existing directional price-movement helper derives the positive adverse
entry-to-stop distance: LONG executable ask minus stop; SHORT stop minus
executable bid. It is supplied to `SizingRequest` / `size_position`; the simulator
has no competing volume or risk formula. Protective relationships are preflighted
against the opening market and entry/stop/target prices against the supplied
contract tick grid. A market-incompatible plan returns `REJECTED_INVALID_PLAN`
without a position; structurally malformed inputs raise validation errors.

`NO_VALID_VOLUME` becomes `NO_TRADE_RISK`, with the sizing result retained and no
entry, protection or charged commission. A successful `XAUUSDExecution.open`
uses exactly the returned volume. Only then is `PROTECTION_ATTACHED` emitted for
the unchanged supplied levels. No resizing or protection modification occurs.

Each completed bar is delegated to G2C4B4 `evaluate_bar`. Its bid/ask triggers,
gap pricing, target-level convention, stop-first ambiguity and single-close
lifecycle are reused. The result retains each protective evaluation and its
source evidence. Once closed, `realize_usd` produces the existing accounting
result, including commission exactly once; no additional spread is deducted.
Unsupported or malformed consumed data is rejected, not silently repaired.

## Outcomes, events and risk

Terminal outcomes are `CLOSED_TARGET`, `CLOSED_STOP`, `CLOSED_STOP_AMBIGUOUS`,
`NO_TRADE_RISK`, `REJECTED_INVALID_PLAN`, `OPEN_AT_END`, and `PENDING_AT_END`.
`OPEN_AT_END` retains its entry and protection but has no exit or realized P&L.
`PENDING_AT_END` means no eligible completed observation was available. Neither
case invents a liquidation or charges a realized round-trip commission.

`SimulationResult` retains the plan, lifecycle/fills, sizing, original entry bar,
protective evaluations, accounting, processed count, typed reasons and events.
Convenience properties expose plan/position IDs, volume, stop/target, fills,
budget, projected stop risk and gross/cost/net USD results. The full request and
component models are serialized for reproducibility. Budget/projected-risk fields
are null if sizing never ran; realized P&L fields are null unless closed.

Events have a sequence, deterministic UUID5 identity, aware UTC time, typed kind,
reason and optional source observation ID. Equal-time ordering uses sequence:
`PLAN_ACCEPTED` → `VOLUME_SIZED` → `ENTRY_FILLED` → `PROTECTION_ATTACHED`, then
`NO_EXIT` or trigger → `POSITION_CLOSED` → `ACCOUNTING_COMPLETED`, with optional
`RISK_BUDGET_BREACH`. `PLAN_ACCEPTED` acknowledges structurally valid input; market
preflight can subsequently reject it. End-of-data emits `DATA_ENDED` at `as_of`.
The simulator ID derives from plan ID and the versioned simulator namespace.
Reuse a plan ID only for replay of that logical plan; no persistent ID registry
or dataset freezing is provided.

Bars processed counts completed observations consumed, including skipped pre-entry
bars; protective evaluation count covers only the open-position interval. The
iterator is not advanced after a terminal decision, so changing even invalid
suffix data after closure cannot alter the trade or its event log. Callers remain
responsible for truthful data availability, correct plan creation times and feed
identity; this core neither manufactures nor independently verifies those inputs.

Projected entry stop risk is not a guaranteed realized loss cap. If accounting
net USD < negative original risk budget, the actual fill and monetary result are
preserved and `RISK_BUDGET_EXCEEDED_BY_GAP` is recorded. With these fixed levels,
linear costs and conservative targets, the adverse opening gap is the mechanism
that can breach a correctly sized stop budget. No price is adjusted to hide it.
No running equity or balance is maintained. Margin affordability remains unknown.

## Synthetic demonstration actually executed

The TEST_FIXTURE contract has 10 ounces per volume unit, minimum/step 0.25,
maximum 2, and tick 0.01. Equity is $500; the explicit demonstration fraction is
5% ($25 budget), except the no-volume case at 1% ($5). Neither percentage is a
production setting. Commission is an explicit $1.25 round trip. Entry quote is
bid 2000 / ask 2001. LONG stop/target = 1995/2005; SHORT = 2005/1995.

| Scenario | Status | Volume | Projected stop risk | Net realized USD |
| --- | --- | ---: | ---: | ---: |
| LONG target | CLOSED_TARGET | 0.25 | 16.25 | 8.75 |
| LONG stop | CLOSED_STOP | 0.25 | 16.25 | -16.25 |
| SHORT target | CLOSED_TARGET | 0.25 | 13.75 | 11.25 |
| SHORT stop | CLOSED_STOP | 0.25 | 13.75 | -13.75 |
| Unaffordable minimum | NO_TRADE_RISK | — | — | — |
| LONG gap to bid 1990 | CLOSED_STOP + risk breach | 0.25 | 16.25 | -28.75 |
| Both levels touched | CLOSED_STOP_AMBIGUOUS | 0.25 | 16.25 | -16.25 |
| No protective trigger | OPEN_AT_END | 0.25 | 16.25 | — |

The gap example loses $28.75 versus a $25 budget; its 1990 fill is unchanged.
The short-gap test independently demonstrates the same breach at ask 2011.
These examples verify mechanics only; they are not profitability evidence.
Full fixtures, results, events and component evidence are in
`xauusd-simulator-demo.json`. Reproduce offline:

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_xauusd_simulator.py
```

The simulator is bar-based, one-plan only, with static instructions. It inherits
G2C4B4's OHLC ambiguity and modeled fill limitations, including unknown intrabar
ordering and skipped price levels. No tick replay, scheduling of multiple plans,
live execution, liquidity, latency, financing or strategy evaluation is added.
No migration, new dependency or trade ledger is required. G2C4C has not begun.

## Verification actually run

- Focused simulator tests: **30 passed**, fully offline.
- Full `pytest -q`: **881 passed**, no skips; one existing Starlette/AnyIO
  deprecation warning. Existing execution, accounting, sizing, protective exits,
  other XAUUSD and NSE/backtester regressions pass.
- Ruff passed; Black check passed (162 files); mypy passed (90 source files).
- Alembic current: **0008 (head)**; Alembic check: no new upgrade operations.
- All eight synthetic scenarios executed; the report and ordered events reviewed.
- Strong no-lookahead test uses an iterator that raises if any item after closure
  is requested. Modified suffix bars leave the entire result/events identical.
  Pre-entry extrema changes leave results unchanged; changing the eligible open
  changes entry and sizing as expected.
- Git status, working diff, staged diff and whitespace reviewed: five new files,
  no existing file modifications, nothing staged or committed. No dependencies,
  migrations, historical downloads or database writes added by the simulator.

Recommended commit: `feat: add explicit-plan XAUUSD event-driven simulator`.
Stopped at G2C4B5; G2C4A signals and G2C4C are not integrated or started.

# XAUUSD G2C4B4 — protective stop and target execution

This checkpoint evaluates fixed protective exits for an already-open, already-sized
XAUUSD position. It reuses `XAUUSDExecution`, `ExecutionFill`, `PositionSnapshot`,
`MarketQuote`, separate-side `QuoteBar` and existing USD accounting. It does not
integrate signals, choose/optimize levels, resize volume, maintain account equity,
or implement trailing stops, margin, swap, broker orders or MT5.

## Instructions and quote triggers

`ProtectiveInstruction` is immutable: position UUID, direction, positive strict
Decimal stop, optional positive strict Decimal target, aware UTC creation timestamp,
source identity and the contemporaneous XAUUSD creation quote. Naive timestamps,
floats, mismatched creation time and invalid relationships are rejected. Non-UTC
aware timestamps normalize to UTC. LONG stop < current bid < target; SHORT target
< current ask < stop (when a target is supplied). Position identity/direction and
entry chronology are verified on evaluation. There is no modification API.

LONG closes by SELLING at BID: bid <= stop, or bid >= target.
SHORT closes by BUYING at ASK: ask >= stop, or ask <= target.
Midpoint is analytical and cannot trigger execution. Quote evaluation requires
an observation at exactly the supplied evaluation timestamp, no earlier than
creation. The actual executable quote is used, including worse-than-stop gap
prices and observed favorable target prices. No synthetic slippage is added.

## Explicit bar convention

Bar evaluation uses only the supplied completed five-minute bar. The instruction
must exist at or before its opening, and cannot precede position entry. Evaluation
before bar completion is rejected. No future bar is consulted; subsequent changes
to future observations cannot change an earlier result.

- LONG: stop tests bid low; target tests bid high.
- SHORT: stop tests ask high; target tests ask low.
- Ordinary stop crossing fills at the stop level by modeling convention.
- LONG stop fill = min(stop, bid open); SHORT stop fill = max(stop, ask open).
  Thus a worse opening after a gap is respected.
- A target fills at its requested level, including a favorable opening gap.
  Highs/lows and gaps do not grant unobserved favorable price improvement.
- If both levels are touched, `STOP_FIRST_CONSERVATIVE` selects the stop and
  returns `STOP_TRIGGERED_AMBIGUOUS`, with reason
  `BOTH_LEVELS_TOUCHED_TICK_ORDER_UNKNOWN`. This conservative policy applies even
  when the opening favors the target; it is not reconstructed tick chronology.

The existing NSE stop pricing and stop-first ambiguity concepts were inspected.
Their implementation is unchanged. In particular, the new XAUUSD target rule
is deliberately conservative rather than importing NSE limit price improvement.

OHLC shows reachability, not liquidity, an exact execution time, or tick order.
Even an ordinary level fill is modeled, not a verified trade at that level.
A target-level modeled fill can lie outside the observed bar range when the
entire bar gaps favorably past it; that is an explicit no-improvement convention,
not a claim that a quote existed there. Stop levels can also be skipped inside
a bar without OHLC identifying the first executable tick. Exact quote evaluation
is preferred whenever that observation is available.

## Lifecycle and auditability

`ProtectiveEvaluation` retains the instruction, input observation/evidence,
evaluation time, trigger, source ID and resulting immutable lifecycle. It exposes
position ID, execution side, BID/ASK trigger side, fill price/ID and ambiguity
reason. `NO_EXIT` keeps the original lifecycle. Re-evaluating a closed lifecycle
returns `ALREADY_CLOSED`, no new fill, and no new fill ID. Callers carry the returned
lifecycle forward; this pure API has no global state or persistence ledger.

An `ExecutionFill` now accepts exactly one of a genuine quote or explicit
`ProtectiveBarEvidence`. Bar evidence retains the original side OHLC, instruction,
evaluation time, market-data ID and versioned literal policy/convention. Only
closing fills may use it. Fill validation recomputes the trigger/price from the
evidence. It does not manufacture a zero-spread quote or infer the opposite
market side. The `quote`, `bid`, `ask`, and `spread` accessors are null for bar
fills; consumers must use the explicit side OHLC evidence instead.

Bar-derived close timestamps are the bar completion boundary, the earliest time
its full OHLC is available, not a claim of an exact intrabar tick time. Actual
`evaluated_at` is retained separately and may be later. Existing quote fill times
and prices are unchanged. Deterministic CLOSE fill identity and the lifecycle's
single-close validation are reused. Accounting consumes the closed position's
prices and volume, so bar closes need no competing monetary model.

The G2C4B3 stop-distance convention remains executable entry to intended exit.
No sizing is recalculated. Gap-through stop execution can exceed the originally
projected stop risk. This checkpoint makes no guarantee of a risk cap, price-grid
or broker stop acceptance; supplied contract validation still applies when
accounting is requested. There is no new migration, trade ledger or account state.

## Synthetic demonstration actually executed

All data below is synthetic, with entry bid 2000 / ask 2001 and positive volume
0.5. Stops/targets are explicit fixtures, not recommendations. Full source side
OHLC, entry/close fills, provenance and accounting are retained in
`xauusd-protective-exits-demo.json`.

| Scenario | Entry | Stop | Target | Exit | Raw movement | Ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| LONG target | 2001 | 1995 | 2005 | 2005 | 4 | No |
| LONG stop | 2001 | 1995 | 2005 | 1995 | -6 | No |
| SHORT target | 2000 | 2005 | 1995 | 1995 | 5 | No |
| SHORT stop | 2000 | 2005 | 1995 | 2005 | -5 | No |
| LONG gap-through stop | 2001 | 1995 | 2005 | 1993 | -8 | No |
| LONG both levels touched | 2001 | 1995 | 2005 | 1995 | -6 | Yes |

The synthetic 10-ounce/volume-unit contract and explicit $1.25 round-trip fee
produce gross -$40 and net -$41.25 for the gap example. Commission is counted
once; spread is already embedded in executable prices.

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_xauusd_protective_exits.py
```

This is exit mechanics, not a full trading backtest: no signal integration,
portfolio results, execution latency/liquidity, account margin, dynamic protection
or G2C4B5 work. Normal tests use offline synthetic observations only.

## Verification actually run

- 33 new offline protective-exit tests; full `pytest -q`: **851 passed**, no skips.
  One existing Starlette/AnyIO deprecation warning remains.
- Existing XAUUSD lifecycle, contract, accounting, sizing and NSE/backtester
  regressions pass. Coverage includes side-specific quotes/extrema, both gap
  directions, conservative targets, ambiguity, no duplicate close, UTC/Decimal,
  invalid evidence, no lookahead, deterministic repetition and USD accounting.
- Ruff passed; Black check passed (159 files); mypy passed (89 source files).
- Alembic current: **0008 (head)**; Alembic check: no schema drift.
- Synthetic six-scenario demo executed and its JSON reviewed.
- Git status, working diff, staged diff and whitespace reviewed: one existing
  execution file modified, six new files, nothing staged or committed.
- No dependencies, migrations, downloaded data or database persistence added.

Recommended commit: `feat: add conservative XAUUSD protective exit semantics`.
Stopped at G2C4B4.

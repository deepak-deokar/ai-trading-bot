# XAUUSD G2C4C1 — causal initial stop and target planning

This checkpoint converts an already-issued `XAUUSDSignalDecision` into fixed
initial levels. It does not evaluate historical strategy signals, execute trades,
optimize parameters or modify an open position. Existing strategy, sizing,
protection, simulator and NSE code remain unchanged.

## Signal-time structure

`plan_structure` consumes identified `StructureBar` observations: existing
`QuoteDataset` provenance, a separate-side `QuoteBar`, and an optional explicit
`discontinuity_before` marker. It revalidates the consumed prefix and stops at the
signal bar. The signal must identify a completed five-minute bar available at
the supplied cutoff. Passing a later cutoff does not authorize later prices.

The immutable `StructurePlan` retains the existing decision and strategy version,
a deterministic SHA-256 decision identity, direction, signal opening/completion,
12 source bars with dataset/archive/processing provenance, structural stop,
fixed Decimal 2R multiple, derivation convention, status and machine-readable
reason. Source identities combine dataset key and bar opening. This captures
provenance supplied by the caller; it does not authenticate external data or
recompute the strategy's feature-row hash from raw bars.

The fixed rule includes signal bar T and exactly 11 preceding completed bars:

- BUY/LONG: minimum **BID low**, because the protective exit sells at bid.
- SELL/SHORT: maximum **ASK high**, because the protective exit buys at ask.

No midpoint extrema are created or used. A 12-bar deque excludes older prices.
The window resets on a dataset change, research-day change, non-five-minute
spacing or explicit discontinuity. Bars must be inside their supplied dataset's
UTC bounds; duplicate/out-of-order bars are rejected. Dataset identity includes
the source day and provenance. The source-day boundary is taken from those
explicit bounds, not assumed to be UTC midnight or inferred from DST.

If 12 continuous bars ending at T from the decision's dataset are unavailable,
return `NO_TRADE_INSUFFICIENT_STRUCTURE`. The lookback is never shortened and gaps
are never filled. Twelve bars mean one hour only when continuity is established.
A decision with no BUY/SELL side returns `NO_TRADE_SIGNAL`.

## Entry-time finalization

`finalize_levels` takes the retained structural result and a later executable
XAUUSD quote (at or after signal completion), market-data identity, existing
`LinearUSDContract` / `Commission`, and explicit equity/risk inputs. It recomputes
the structural result from retained evidence before trusting it. No future entry
information participates in the original stop calculation.

LONG uses ASK entry; SHORT uses BID entry. The original structural stop must
still straddle the **current exit side** as G2C4B4 requires: below bid for LONG,
above ask for SHORT. This is stronger than merely testing entry ask/bid and
rejects an immediately-triggered stop. An invalidating gap returns
`NO_TRADE_INVALID_STOP` **before alignment**, without moving the stop to rescue it.

Tick rules are explicit and use exact integer ratios:

- LONG stop rounds down to the zero-origin contract tick grid.
- SHORT stop rounds up.
- Sizing distance uses this outward-aligned stop, so alignment cannot understate
  stop risk. Both raw structure and effective aligned stop remain visible.
- LONG raw target = executable ASK entry + 2 × effective stop distance.
- SHORT raw target = executable BID entry − 2 × effective stop distance.
- LONG target rounds down; SHORT target rounds up. Alignment never increases
  reward beyond the raw derived target.

Entry must already be tick-aligned; it is never rounded or price-overridden.
With a valid grid-aligned entry, aligned stop and integer 2R, the target is
mathematically on that same grid already. The directed target alignment and
validation remain explicit. Nonpositive aligned stops/targets or unsupported
entry alignment are rejected; no guessed price is substituted. A nonpositive
raw target returns `NO_TRADE_INVALID_TARGET`. Decimal calculations use sufficient
local precision, independent of the ambient Decimal context. No standalone
spread adjustment is added.

The immutable `FinalizedLevels` retains the actual quote, source identity, raw
and aligned levels, status/reason, existing `SizingRequest`, and existing
`TradePlan`. It constructs **no position, fill or realized P&L** and does not call
sizing or the simulator. Risk fraction has no default. Equity/risk and contract
validation reuse the existing request models. Contract broker stop-distance
permissions are not claimed by this domain-level tick validation.

The resulting TradePlan is tied to the supplied actual entry quote/time. Future
integration must finalize at the simulator's actual entry event. It must not
finalize from an earlier quote and then replay that fixed target at an unrelated
later opening. G2C4C1 deliberately does not add that integration or run G2C4C2.
For all rejected finalizations, there is no executable TradePlan.

## Bounded synthetic demonstration actually executed

All inputs are TEST_FIXTURE observations and synthetic already-issued decisions,
not a historical strategy run. The 12 openings are 2024-02-20 10:00 through 10:55
UTC; signal availability is 11:00 UTC. A separate later-event entry observation
at 11:00 has bid 2001 / ask 2002. Full source bars/identities are retained in
`xauusd-initial-levels-demo.json`.

| Case | Structural stop | Executable entry | Stop distance | Multiple | Target / outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| BUY | 1990 | ASK 2002 | 12 | 2R | BID 2026 |
| SELL | 2011.1 | BID 2001 | 10.1 | 2R | ASK 1980.8 |
| Eleven bars only | — | — | — | — | Insufficient structure |
| Missing interior bar | — | — | — | — | Discontinuity; insufficient structure |
| BUY entry gap to bid 1989 / ask 1990 | 1990 retained | — | — | — | Invalid stop; no repair |

The synthetic contract uses 10 ounces per volume unit, 0.25 minimum/step, maximum
2 and tick 0.01; supplied equity is $500 and illustrative risk fraction 5%, with
explicit round-trip cost $1.25. These are retained request parameters only: no
volume or execution is calculated. No production risk setting is established.

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_xauusd_levels.py
```

Twelve bars and 2R are single transparent V1 research constants. No alternative
lookbacks or multiples were evaluated and no profitability inference is justified.
No migration, persistence, downloads, MT5, trailing/breakeven logic or margin
behavior is added.

## Verification actually run

- Focused planner suite: **18 passed**, offline.
- Full `pytest -q`: **899 passed**, no skips; one existing Starlette/AnyIO
  deprecation warning. Existing strategy, lifecycle, accounting, sizing,
  protective-exit, simulator, XAUUSD and NSE/backtester regressions passed.
- Ruff passed; Black check passed (165 files); mypy passed (91 source files).
- Alembic current: **0008 (head)**; Alembic check: no new upgrade operations.
- Synthetic demonstration executed and JSON evidence reviewed.
- No-lookahead includes a guarded iterable that fails if anything after the
  signal bar is requested, changed future extrema and exclusion of old outliers.
- Git status, working/staged diffs and whitespace reviewed: five new files only,
  no existing modifications, no staging or commit. No dependency or schema changes.

Recommended commit: `feat: add causal XAUUSD structural stop and 2R planning`.
Stopped at G2C4C1; no historical strategy execution or G2C4C2 work.

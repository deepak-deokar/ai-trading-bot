# XAUUSD G2C4B3 — risk-based position sizing

This pure calculation reuses `ContractSpecification`, `LinearUSDContract` and
`Commission`. It does not integrate signals, execute stops, select stops, assess
margin, update equity or connect to a broker. No database changes are made.

`SizingRequest` is immutable and retains positive Decimal account equity, USD
currency, exactly one explicit risk fraction (0 < fraction <= 1) or risk amount
(positive and no greater than equity), positive stop distance, the full contract
and explicit fixed round-trip commission. No risk percentage has a default.
Unsupported currencies/contract units/tick-value conversions and malformed inputs
raise Pydantic `ValidationError`, as in the existing accounting models. Inputs are
revalidated on evaluation, including unchecked model copies.

## Convention and calculation

Stop distance is an adverse price difference in USD per troy ounce from actual
executable entry to intended executable stop exit. LONG uses entry ask and exit
bid; SHORT uses entry bid and exit ask. Once this adverse distance is supplied,
both directions have the same linear loss. No separate spread charge is added.
The input is not a mid-price distance. No entry, exit or actual stop order is
created or verified here; price-grid and broker stop permissions remain separate
from this risk-budget computation.

Budget = equity × risk fraction, or the explicit USD risk amount.
Gross stop loss = distance × ounces per volume unit × selected volume.
Total projected stop loss = gross loss + explicit fixed round-trip USD commission.
Commission is included once. There are no invented slippage, swap or financing
charges, and no currency or settlement rounding.

The algorithm uses exact integer ratios (`Fraction`) internally to floor
(budget − commission) / (loss per volume × volume step). It caps that integer
step count by the maximum volume, when supplied, then checks the minimum.
The grid is the existing contract's zero-origin grid. A non-grid maximum caps
at the largest step below it. Financial boundaries use Decimal; finite results
are converted exactly without dependence on ambient Decimal precision.
Unlike G1D validation of externally supplied volumes, sizing intentionally floors
a computed candidate. It never rounds upward to meet the minimum.

Successful results satisfy total loss <= budget. When a further contract-valid
step exists, its total loss must exceed budget. At the contract maximum there
is no next valid step. A valid request with unaffordable minimum returns
`NO_VALID_VOLUME`, with reason `MINIMUM_EXCEEDS_BUDGET` or
`COSTS_CONSUME_BUDGET`; it does not invent a zero-volume trade. Selected loss and
volume fields are null in that case. The explicit fee remains visible as input
cost metadata, not a charge incurred by choosing no trade.

Results retain the entire request, contract hash, conversion identity, exact cost
configuration, calculation version, budget, selected volume, gross/total loss and
next-step risk. They are deterministic and immutable. `SIZED` means only that
volume fits this stop-loss budget, not that it is margin-affordable or executable.

## Research demonstration only

The same synthetic contract family as G2C4B2 uses 10 ounces per volume unit,
minimum/step 0.25, maximum 2 and price tick 0.01. The illustrative $500 equity
and explicit 1% fraction yield $5 risk. These are not live recommendations or
production defaults. Explicit round-trip commission is $1.25.

| Stop distance | Selected volume | Gross loss USD | Total risk USD | Next-step risk USD | Decision |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 2 | 2 | 3.25 | — | Contract maximum |
| 0.5 | 0.75 | 3.75 | 5 | 6.25 | Risk bound |
| 1 | 0.25 | 2.5 | 3.75 | 6.25 | Risk bound |
| 2 | — | — | — | — | Minimum exceeds budget |

At distance 1, the unconstrained 0.375 volume floors to 0.25; 0.50 would risk
$6.25. At distance 2, minimum 0.25 would risk $6.25, so no volume is selected.
Full retained inputs and outputs are in `xauusd-risk-sizing-demo.json`. Reproduce:

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_xauusd_sizing.py
```

Only linear USD contracts with explicit units and unset tick value are supported.
No margin affordability, actual stop fills, gap/slippage risk, dynamic fees,
strategy integration or G2C4B4 behavior is implemented.

## Verification actually run

- Focused sizing tests: 23 passed, including 324 exact-arithmetic combinations
  across equities, fractions, stop distances, contract sizes and volume steps.
- Full `pytest -q`: 818 passed, no skips; one pre-existing Starlette/AnyIO
  deprecation warning. Existing contracts, accounting, XAUUSD and NSE/backtester
  regressions pass.
- Ruff passed; Black check passed (155 files); mypy passed (87 source files).
- Alembic current: 0008 (head); Alembic check: no new upgrade operations.
- Synthetic demonstration executed. Git status and working/staged diffs reviewed:
  five new files only, no existing modifications, no staged changes or commit.
- No dependencies, migration, account persistence or source data changes.

Recommended commit: `feat: add exact contract-aware XAUUSD risk sizing`.
Stopped at G2C4B3; no strategy integration or G2C4B4 work.

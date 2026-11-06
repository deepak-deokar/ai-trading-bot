# XAUUSD G2C4B2 — contract-aware USD realized accounting

Only closed synthetic/research lifecycle accounting is added. G1D contract and
G2C4B1 execution behavior remain unchanged. No strategy integration, account equity
curve, risk sizing, default lot, SL/TP, leverage, margin, financing or MT5.

## Explicit conversion contract

The existing ContractSpecification contains contract_size and volume constraints,
but no currency or physical-unit declaration. New immutable `LinearUSDContract`
wraps it with required explicit assertions:

- price_unit = USD_PER_TROY_OUNCE;
- contract_size_unit = TROY_OUNCES_PER_VOLUME_UNIT;
- quote_currency = USD;
- account_currency = USD.

These fields have no inferred defaults. Unsupported currencies/units are rejected;
there is no FX conversion engine. This is an operator assertion of a suitable linear
contract, not independent broker verification. Existing broker-neutral contracts
are not retroactively assigned these units. The original specification identity is
retained; a separate conversion identity hashes specification ID plus unit/currency
assertions. tick_value must be unset in this profile: its units are not established
by G1D, and this checkpoint deliberately implements no tick-value conversion.

`realize_usd(closed_lifecycle, profile, commission)` revalidates the lifecycle and
profile, requires a fully closed position, validates its explicit volume against
minimum/maximum/zero-origin step, and validates executed entry/exit tick alignment.
No volume or price rounding is performed. The existing execution lifecycle supplies
entry and exit prices; callers cannot supply independent accounting fill prices.

Gross USD = directional executed price movement (USD/ounce)
× contract_size (ounces/volume-unit) × explicit volume (volume-units).

LONG uses exit BID minus entry ASK. SHORT uses entry BID minus exit ASK. The existing
exact direction-aware helper supplies movement. Spread is already in those fills;
**there is no additional spread deduction**. This is realized monetary conversion
for one supplied valid volume, not advice about how much an account should trade.

## Costs, exactness and audit

`Commission` requires USD and an explicit nonnegative Decimal
`fixed_round_trip_usd`. It is the total fee for both fills combined and is deducted
once. Zero is allowed only when explicitly supplied, not as a hidden commission
default. No broker commission is invented. Net USD = gross USD - commission USD.
Slippage is explicitly zero and fill prices remain unchanged. No commissions are
implicitly applied per side or per lot; other commission models are deferred.

All monetary inputs/outputs are Decimal; floats/nonfinite values are rejected.
Multiplication and fee subtraction use precision sized from their finite Decimal
operands, avoiding caller-context rounding. No currency-cent rounding is imposed;
fractional-cent results are preserved for a later explicit cash-settlement policy.

Immutable RealizedUSDResult retains the entire validated lifecycle (position ID,
entry/exit fill IDs, timestamps, direction, volume, bid/ask quotes, fill prices and
source identities), full contract/profile and hashes, raw movement, commission
inputs, gross, commission, net, explicit zero slippage and spread-treatment label.
The full nested objects are intentionally retained for reproducibility. No running
account balance or portfolio ledger is maintained or written.

## SYNTHETIC / TEST ONLY demonstration

Run `PYTHONPATH=src .venv/bin/python scripts/demo_xauusd_accounting.py`.
The saved JSON is `docs/xauusd-usd-accounting-demo.json`.

Explicit TEST_FIXTURE specification: **10 troy ounces per volume unit**,
minimum volume 0.25, maximum 2, step 0.25, tick size 0.01 USD/ounce. Supplied
synthetic volume is **0.5**, hence converted quantity is **5 ounces**. These are
not MT5/broker defaults. Round-trip commission is explicitly **$1.25 total**.

| Synthetic lifecycle | Entry bid / ask | Entry fill | Exit bid / ask | Exit fill | Raw movement | Gross USD | Commission | Net USD |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| LONG | 2000 / 2000.50 | 2000.50 | 2002 / 2002.50 | 2002 | 1.50 | 7.50 | 1.25 | 6.25 |
| SHORT | 2000 / 2000.50 | 2000 | 1998 / 1998.50 | 1998.50 | 1.50 | 7.50 | 1.25 | 6.25 |

Independent calculation: 1.50 × 10 × 0.5 = 7.50; subtract 1.25 once = 6.25.
At unchanged bid 2000 / ask 2000.50, both directions instead have -0.50 movement,
so gross = -0.50 × 10 × 0.5 = **-$2.50**, not -$5.00. Explicit zero commission
leaves net -$2.50 in the tests. No historical strategy signals or performance
statistics are used.

## Scope limitations

Only linear USD/ounce contracts with explicitly asserted units and unset tick_value
are supported. Actual broker metadata, commission schedules and settlement rounding
remain unverified. Account-risk sizing, commissions beyond an explicit fixed total,
slippage, margin, swap, strategy integration and G2C4B3 remain future work.
No database migration, source data change or portfolio-ledger persistence.

## Verification actually run

Focused tests: **13 passed**. Full `pytest -q`: **795 passed**, no skips; one
existing Starlette/AnyIO deprecation warning. Existing contract, lifecycle, XAUUSD
and NSE/backtester regressions passed. Tests cover positive/negative movements in
both directions, unchanged-quote spread effect, linear volume scaling, volume
bounds/step rejection, commission once, unsupported currencies, Decimal enforcement,
closed-only accounting, tick alignment and deterministic repeated results.

Final Ruff passed; Black check passed (152 files unchanged); mypy passed (86 source
files). Alembic current **0008 (head)**; check: no drift. The initial Ruff stage
caught a long demo string after pytest passed; it was formatted and the remaining
quality checks rerun successfully, without a behavior change.

Synthetic demo executed for both directions with the hand-checkable values above.
Git status, working/staged diffs and whitespace reviewed: five new files, no existing
files modified, nothing staged or committed. No dependencies or migration added.

Recommended commit: `feat: add explicit contract-aware XAUUSD USD accounting`.

Stopped at G2C4B2. No signal integration, account-risk sizing or G2C4B3 work.

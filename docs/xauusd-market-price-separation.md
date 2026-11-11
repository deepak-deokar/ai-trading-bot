# XAUUSD G2C4C3B — observed market prices and submitted levels

Observed BID/ASK entries, exits and gap-through fills retain their exact validated
Decimal values. MarketQuote and lifecycle revalidation still enforce positive,
finite Decimal prices, correct executable side, quote/bar evidence, identities and
UTC timestamps. No source price is rounded or quantized.

`finalize_levels` no longer applies submitted-price alignment to the observed entry.
`simulate_trade` preflight applies contract alignment to stop/target only. Accounting
revalidates the lifecycle and volume, validates generated protective levels when
bar evidence carries them, and uses exact executed prices in the unchanged linear
USD formula. Commission remains charged once; sizing uses the actual entry-to-stop
distance. ContractSpecification.validate_price remains unchanged.

The synthetic research tick remains 0.01. Generated stops/targets retain their
existing directed alignment rules, 12-bar structure and 2R target construction.
This does not establish a real broker specification or imply that an arbitrary
submitted off-grid order would be accepted.

## Bounded historical verification

A read-only database check matched all 13,524 approved bar payloads and feature
payloads against the frozen report's per-dataset hashes. It reconstructed causal
12-bar structures from the frozen feature decisions and finalized only the 4,054
recorded candidate entries, using their original source BID/ASK and timestamps.
Account balance remained $500, risk 1%, and all contract/commission configuration
came from the frozen report. No trade simulation or profitability run was performed.

- Candidates examined and successfully planned: **4,054**.
- Remaining observed-market grid rejections: **0**.
- Generated stops passing the unchanged contract grid: **4,054**.
- Generated targets passing the unchanged contract grid: **4,054**.
- Prior grid rejections reproduced from frozen records: **4,047**.

The old 4,047 failures arose from applying the submitted-level rule to source
market entries. The frozen G2C4C2 reports remain unchanged historical records.
Machine-readable bounded results are in `xauusd-market-price-separation.json`.
Passing planning does not establish sizing eligibility, trade counts or returns.

Offline regressions cover SHORT BID 2042.165, off-grid LONG ASK, SHORT boundary
ASK 2035.956, LONG exit BID, exact gap-through BID 1993.957 against stop 1995,
exact accounting and commission, invalid observed prices, and generated stop/target
rejection. The gap example yields gross -17.6075 and net -18.8575 with synthetic
size 10, volume 0.25, entry 2001 and commission 1.25.

No migration, data correction, strategy/risk parameter change or broker integration
is included. The existing $3,000 sensitivity reports remain untouched and untracked.

The saved failed $3,000 lifecycle was also revalidated in isolation: entry 2034,
SHORT exit 2035.956, volume 1.25 accounts at gross -24.45 and net -25.70. This is
only an accounting regression of existing evidence, not a completed sensitivity
backtest or a replacement profitability report.

## Verification

Final full suite: **925 passed**, one existing Starlette/AnyIO deprecation warning.
NSE/backtester, execution, accounting, sizing, protection and strategy regressions
pass. Ruff passed; Black passed (168 files); mypy passed (92 source files).
Alembic current: **0008 (head)**; check: no schema drift. Git working/staged diffs
and whitespace checked; nothing staged or committed. Protected frozen reports,
sensitivity reports and original run configuration have unchanged SHA-256 hashes.

Recommended commit: `fix: separate observed XAUUSD fills from submitted price grid`.

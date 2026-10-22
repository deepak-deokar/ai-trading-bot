# XAUUSD V1 — G1A

G1A adds domain/configuration support only. Indian-market functionality remains
preserved. The existing NSE bars, providers, features, backtester, strategies,
settings and persisted schema are unchanged.

Canonical market **XAUUSD** has asset class **SPOT_METAL**, base asset **XAU (Gold)**
and quote currency **USD**. This class describes the research underlying; a future
broker's actual contract (including whether it is a CFD) remains unspecified.
There is no NSE exchange/segment on this identity. Provider symbols belong to
future adapter mappings, not the canonical instrument. No MT5 symbol suffix is
assumed.

The reference demo account is **$500 USD**, represented by `Decimal("500")`.
This is reference capital, not an instruction to deploy all capital. The generic
reference-account model also supports INR, independently of this USD-only V1
profile. The V1 profile validates its fixed reference currency and balance;
generic reference accounts accept positive finite Decimal balances.

Load the metadata explicitly, without changing runtime settings:

```python
from pathlib import Path
from trading_bot.config.research import load_xauusd_research

profile = load_xauusd_research(Path("config/xauusd_v1.yaml"))
```

The target execution platform is **MT5**, as metadata only. Future long/short,
bid/ask, lot quantity and contract-specification requirements are declarations,
not implemented capabilities. Future risk percentages and maximum positions are
optional validated fields, all unset in the supplied profile. Unset means
unspecified, not unlimited or authorized. No production risk values are chosen.
There is no fixed lot default. Future sizing will require market-derived stop
distance, allowed account risk and broker contract specifications.

Development sequence: historical research → backtesting → MT5 demo → live much
later. Future dynamic stops/targets, breakeven, trailing stops and early exits
remain research intent only.

No gold sessions, broker hours, market data, connection, orders, sizing, margin,
leverage, spreads, swaps, strategy, ML or execution behavior is implemented here.
The canonical instrument is not wired into the legacy NSE candle or execution
pipeline; it does not make those systems gold-ready. No credentials or broker
server details are accepted by the profile. No persistence change or migration
is needed. Currency vocabulary is currently limited to INR and USD; currency
conversion is not provided. G1B has not begun.

## Verification

Actually run for G1A:

- `pytest -q`: **401 passed**, no skips; one existing Starlette/AnyIO deprecation warning.
- `ruff check .`: all checks passed.
- `black --check .`: 101 files unchanged.
- `mypy`: no issues in 65 source files.
- `alembic current`: **0005 (head)**.
- `alembic check`: no new upgrade operations detected.

The full PostgreSQL suite includes existing NSE regression and migration checks.
There are 26 new G1A cases. No existing source, tests, configuration or migration
files were modified. No gold data or broker endpoint was accessed.

# Temporary Yahoo historical provider — RELIANCE pilot

**YAHOO RELIANCE PILOT BLOCKED**

The connection and bounded ingestion worked, but the sample contains eight invalid
NaN-price placeholders. **367 valid bars were committed; eight expected candles are
missing after validation.** No session has complete accepted coverage. This pilot
must not be used for the current FAIL_RUN backtester or Phase 5B-2 evaluation.
No strategy, optimization, broker connection, orders or Phase 5C work was performed.

## Actual request and results

| Field | Observed result |
| --- | --- |
| Symbol / provider symbol | RELIANCE / RELIANCE.NS |
| Source / market | yahoo_finance / NSE CASH |
| Internal / provider interval | 5minute / 5m |
| Requested start | 2026-10-15 09:15 IST / 03:45 UTC |
| Requested end | 2026-10-22 15:30 IST / 10:00 UTC, exclusive |
| Selected completed sessions | October 15, 16, 19, 21, 22: 5 sessions |
| Expected / received rows | 375 / 375 |
| Accepted / inserted | 367 / 367 |
| Rejected | 8 |
| Duplicates / conflicts | 0 / 0 |
| Missing validated candles | 8 |
| Complete accepted sessions | 0 |
| First timestamp | 2026-10-15 09:15 IST / 03:45 UTC |
| Last timestamp | 2026-10-22 15:25 IST / 09:55 UTC |
| Input timezone | Asia/Kolkata |
| Stored timestamp convention | Opening, UTC; existing available_at rules |
| Adjustment policy | **YAHOO_NATIVE — UNVERIFIED** |
| Ingestion status | COMPLETED_WITH_WARNINGS |

Dataset key:
`19b5fe600a03fc5820c0a239fdce42b4a6ecf34b1fffc58261b8354a674024c3`

Ingestion run: `4af5f1e6-8e31-4cfa-bfb1-93cb66db9a41`.

The actual request was selected dynamically from the existing calendar, using the
last five sessions closed at least 30 minutes before execution. No incomplete session
was requested. October 20 is excluded by the supplied calendar. Calendar authority
is **REVIEWED_POLICY**, not a new claim of independently authoritative exchange history.
Full provider/version/policy hash is retained in the ingestion identity and JSON.

An initial network preflight passed but the standalone process lacked DATABASE_URL;
it stopped without writing bars. The bounded request was then repeated with the
existing local database configuration and normal ingestion. A final read-only
re-read of exactly the same window identified the rejection causes; it did not
reingest or expand the range. No other symbols were fetched.

## Quality findings

All eight rejected rows in the diagnostic re-read had NaN open/high/low/close and
zero volume. Their labels match the original ingestion rejection/gap timestamps:

- October 15: 11:45, 11:50, 15:20 IST.
- October 16, 19 and 21: 15:20 IST each.
- October 22: 15:15 and 15:20 IST.

The returned index itself had all 375 expected slots and regular intraday 300-second
spacing. These are **price-data gaps**, not initially missing index labels. Keeping
NaNs allowed the existing normalization/quality pipeline to reject and report them.
No interpolation, repair, zero-price replacement or fabricated candle was introduced.
The data-quality report contains eight INVALID_BAR findings, eight MISSING_BAR findings,
a LARGE_GAP finding and the unverified-provider warning. Unexpected timestamps,
out-of-order input, duplicates and conflicts were not found in the actual sample.

A final read-only database check confirmed 367 yahoo_finance/YAHOO_NATIVE bars, the
original 9 local/RAW verification bars unchanged, and **0 backtest runs**. No feature
set or strategy evaluation was created for this pilot. Compact machine-readable
coverage, provenance, quality findings and diagnostic evidence are in
[yahoo-pilot.json](yahoo-pilot.json); no bulk OHLCV export was committed.

## Provider and semantics

`YahooHistoricalDataProvider` implements the existing provider boundary and emits
RawCandle objects. IngestionService still performs normalization, Bar validation,
quality checks, conflict/duplicate handling and transactional persistence. No pandas
or Yahoo object reaches strategy/backtest code. Explicit maps cover RELIANCE.NS,
TCS.NS, INFY.NS, HDFCBANK.NS and ICICIBANK.NS; only RELIANCE was requested.
Requests are restricted to one mapped symbol, five-minute data and at most five
complete recent sessions. Old, incomplete or unsupported requests fail clearly.

The pilot calls `prepare` before ingestion, records its evidence in provider semantics,
and reuses the same in-memory sample for persistence. This avoids a second network
fetch between verification and ingestion. Generic provider fetch also runs the gate
if it has not yet prepared that exact request.

Explicit yfinance options: `auto_adjust=False`, `back_adjust=False`, `actions=True`,
`repair=False`, `keepna=True`, `prepost=False`, `rounding=False`, interval `5m`,
20-second request timeout. Native OHLC prices are quantized to the domain's ten
Decimal places for float transport compatibility, not to an assumed exchange tick.
Invalid quantities and OHLC values remain subject to normal rejection.

The [yfinance history API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)
and [implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py)
distinguish automatic adjustment, back adjustment, repair and corporate-action
columns. Disabling library adjustment does **not** establish the upstream Yahoo
price history as RAW. This implementation records Yahoo-native semantics as
UNVERIFIED and does not map them to RAW, SPLIT_ADJUSTED or FULLY_ADJUSTED.
Dividend/split columns were present; no nonzero actions appeared in this small
response. That is not proof of a complete corporate-action history.

The actual metadata matched RELIANCE.NS, exchange NSI, EQUITY, INR, 5m and the Indian
exchange timezone. Every session included its 09:15 opening, every label aligned
with expected slots and the final label was 15:25 rather than 15:30. This is sufficient
observational evidence for opening labels for this bounded pilot, without shifting
labels. It is not tick-level or contractual verification for every possible Yahoo
response. Missing opening anchors, naive/incorrect zones, mismatched identity/interval
or unexpected labels fail closed before ingestion. Broader provider/adjustment
verification remains explicitly UNVERIFIED.

## Dependency and schema changes

`yfinance==1.7.0` is explicitly pinned in pyproject.toml and both existing dependency
locks include its runtime dependency closure. Existing lock versions were preserved;
this is not an untracked one-off installation. The [project's upstream page](https://pypi.org/project/yfinance/)
identifies it as an unofficial research/personal-use tool rather than a broker API.

Migration **0005_yahoo_native** is justified because the old database CHECK allowed
only three adjustment values. The new enum/check admits YAHOO_NATIVE and enforces
that it belongs only to source yahoo_finance, which in turn cannot use other policies.
The same pairing is enforced by the Bar domain model. Existing values are unchanged;
queries still filter one explicit source and adjustment policy, defaulting to RAW.
No Yahoo data can silently enter a default RAW query.

Downgrade refuses while native bars exist, preserving research data rather than deleting
or relabeling it. Migration upgrade/downgrade/re-upgrade and this guard were tested in
disposable schemas. Public schema is now **0005 (head)**. API readiness and existing
migration-head assertions were updated accordingly. The legacy three-policy query
isolation test retains all original assertions; dedicated tests cover native isolation.

Local environment caveat: a separately installed `growwapi==1.5.0`, absent from the
project dependency files, conflicts with the project's already-pinned pandas 3.0.6
and certifi 2026.7.22 versions restored during installation. `pip check` reports those
two conflicts. The Groww package was not imported, connected, removed or changed;
no clean whole-environment dependency check is claimed. Project tests and Yahoo ran
using the project pins. Keep unrelated SDK experiments in a separate environment.

## Verification and reproducibility

Activate the project environment and set DATABASE_URL securely, then:

```sh
export PYTHONPATH="$PWD/src"
alembic upgrade head
TEST_DATABASE_URL="$DATABASE_URL" pytest -q
ruff check .
black --check .
mypy
alembic current
alembic check
```

`scripts/pilot_yahoo.py` is an explicit network/ingestion entry point, not an automatic
test. A later invocation chooses a new recent five-session window, so do not treat it
as immutable historical replay. Normal tests use mocked frames and metadata only.

Tests cover mappings, options, timezone/normalization, missing columns, empty responses,
failed metadata/open-label checks, policy isolation across query methods and database
constraints, preserved duplicates/order/gaps, invalid OHLC/volume, NaN placeholders,
identity, and guarded migration round trips. See final check results in the JSON.
One existing Starlette/AnyIO deprecation warning remains.

Final actual results: **375 tests passed**, no skips (356 previous + 19 new),
15.75 seconds. Ruff passed; Black reported 98 files unchanged; strict mypy passed
63 source files. Alembic current: **0005 (head)**; Alembic check: no drift.
Migration round-trip/guard tests passed. No internet was used by automated tests.

## Hygiene and limitations

No baseline strategy/configuration changes, credentials, `.env`, large dataset,
cache/build artifacts or automatic commit. Existing untracked Phase 5B-2 blocked
reports were preserved. Changes are limited to provider/dependency/policy support,
migration/readiness, tests, pilot script, README link and pilot reports.

Yahoo can return placeholders, omit/revise data, throttle requests and limit intraday
history. Its own preprocessing may remove duplicates before the adapter receives them;
the adapter preserves those it does receive. Calendar authority and price semantics
remain bounded by their documented limitations. This incomplete pilot does not unblock
historical performance evaluation. Do not broaden downloads or run the strategy on it.

Stopped after the RELIANCE pilot. No Phase 5B-2 evaluation or Phase 5C was started.

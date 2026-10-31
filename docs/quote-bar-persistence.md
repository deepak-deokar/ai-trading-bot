# XAUUSD G2B2A — persistent bid/ask research bars

G2B2A persists only the previously verified January 16, 2024 HistData pilot.
No downloads, strategy changes, trading-backtester changes or MT5 work occurred.

## Representation and provenance

Immutable `QuoteBar` has canonical XAUUSD, interval 5minute, aware UTC opening
timestamp, eight Decimal OHLC values (four BID, four ASK), and positive tick count.
Five-minute alignment, finite positive prices, side-specific OHLC ranges and
noncrossed side values are validated. A 10:00 label means `[10:00, 10:05)`;
`closing_timestamp` exposes 10:05. Volume metadata is not converted to bar volume.

The existing HistData parser and stable aggregation are reused unchanged. No
midpoint, forward-fill, interpolation or synthetic price is used. Separate sides
are converted to the dedicated model, never the single-price NSE candle model.
Numeric(28,10) database storage is matched by model precision limits; unsupported
precision is rejected by the application rather than silently rounded.

Migration **0007** creates only `bid_ask_bars`. It stores searchable symbol,
interval, UTC opening timestamp, provider and provider symbol; eight Numeric price
columns; tick count; dataset key; and original successful import run UUID.
Primary identity is `(dataset_key, opening_timestamp)`. The dataset key is a
SHA-256 of canonical JSON selection/provenance: provider, provider symbol,
canonical symbol, archive name/checksum, source month/date/range, timezone,
normalization/aggregation versions and interval. This isolates datasets and
providers; changing a source checksum or version intentionally creates a new
identity, not a silent revision of an existing dataset.

Successful run provenance reuses `system_events` with event type
`quote_bar_dataset_import`. Each run records the full manifest, tick/bar counts,
expected-bin count and every missing opening. Existing stored bars retain their
first run UUID on re-import. There is no new ingestion/versioning platform.

## Import and query rules

Each bounded import is atomic. A PostgreSQL transaction advisory lock serializes
same-dataset imports. Identical rows produce zero new inserts. Changed membership,
provenance counts or bar values raise `QuoteBarConflict`; all writes roll back.
Conflicts are reported to callers and are not silently overwritten. Failed
attempts do not currently create a separately committed failure-audit event.
No update/delete business API is provided; privileged SQL is not prevented.

`QuoteBarRepository.get_bars` requires dataset key, symbol, interval and aware
start/end. It returns typed bars oldest first, filtered by opening time `[start,
end)`. This is a research query, not completion-aware strategy access: a cutoff
inside a bar does not automatically exclude it. No strategy or backtester consumes
this table. `get_run(run_id)` retrieves persisted provenance and gap reporting.

`persist_histdata_pilot.py` accepts only the previously verified archive SHA-256
and analyzes only the fixed January 16 source date. It checks 177,064 valid ticks,
276 bars and zero invalid ticks before persistence. It imports twice, queries
back all bars and checks equality. The compact output artifact records both runs.
The monthly archive remains under `/tmp`, outside Git.

```sh
# DATABASE_URL must already be supplied securely through the environment.
PYTHONPATH=src .venv/bin/python scripts/persist_histdata_pilot.py \
  /tmp/HISTDATA_COM_ASCII_XAUUSD_T_202401.zip
```

## Missing intervals and limitations

The selected fixed-EST day corresponds to 2024-01-16 05:00 UTC through
2024-01-17 05:00 UTC. There are **288 possible bins**, **276 observed bars** and
**12 missing openings, 22:00–22:55 UTC**. All missing openings are persisted in the
run manifest and remain absent from the bar table. No calendar explanation for
the gap is asserted. HistData is a research feed, not the future MT5 broker feed.

The model currently supports only XAUUSD five-minute bars and imports at most one
day. Persistence does not establish broker tradability, adjustment semantics or
execution readiness. Source timezone/version assertions come from the importer.
The checksum-locked demonstration establishes actual provenance for this pilot;
the generic repository does not independently retrieve or hash source files.

Downgrade refuses to drop a nonempty bid/ask table. Migration round trips are
performed only in disposable schemas. The development database keeps the pilot.
G2B2B has not begun.

## Verification actually run

- Real pilot: first import **276 inserted**; second import **0 inserted, 276 existing**.
- Query round trip: all 276 typed bars equal their original aggregates.
- 12 missing bins retained explicitly; 288 = 276 + 12.
- `pytest -q`: **677 passed**, no skips; one existing Starlette/AnyIO warning.
  Includes all 664 existing cases and 13 new cases. Offline synthetic storage
  fixtures are labelled TEST_FIXTURE; actual-pilot evidence is in
  `quote-bar-persistence.json`, not misrepresented as synthetic test data.
- `ruff check .`: passed.
- `black --check .`: passed, 125 files unchanged.
- `mypy`: passed, 76 source files.
- `alembic upgrade head`: succeeded; current **0007 (head)**; check: no drift.
- Disposable schema downgrade to 0006/re-upgrade and nonempty-table downgrade
  rejection passed. Existing NSE/backtester tests remain passing.
- Working/staged Git diffs reviewed; staged diff empty, whitespace check clean.
  No credentials, archive, caches or generated bulk data added. Nothing committed.

Recommended commit: `feat: persist isolated XAUUSD bid ask research bars`.

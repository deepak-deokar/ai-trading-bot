# XAUUSD G2B1B — HistData tick pilot

The bounded pilot verified access, documented parsing and quote validation for
one HistData research day. It does not certify complete market coverage, broker
execution equivalence or profitability. No full ingestion or next phase started.

## Access and provenance

The normal free [January 2024 Generic ASCII tick download page](https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/xauusd/2024/1)
returned HTTP 200 and supplied its download form. Submitting that form to
`https://www.histdata.com/get.php` returned HTTP 200, application/octet-stream,
and a valid ZIP. No access controls were bypassed, credentials supplied, paid
access used or third-party downloader installed.

- Provider: HISTDATA.
- Canonical symbol: XAUUSD; provider label: XAU/USD; filename identifier: XAUUSD.
- Archive: `HISTDATA_COM_ASCII_XAUUSD_T_202401.zip`, **21,433,463 bytes**.
- Member: `DAT_ASCII_XAUUSD_T_202401.csv`, **137,799,900 bytes** uncompressed.
- Archive SHA-256: `5b73733b7e1fcc5f10943602d83e54396338f7e106a2f80f03605eabf37a8990`.
- Selected source date: **Tuesday 2024-01-16**.
- Analyzed UTC interval: **[2024-01-16 05:00, 2024-01-17 05:00)**.

Only one monthly archive was downloaded, to `/tmp`; it is not committed. The CSV
was streamed from the ZIP without extraction. Only selected-date rows were parsed
and analyzed. Other date prefixes were skipped, so this is not a monthly data
audit. Machine-readable provenance/results are in `histdata-pilot.json`.

## Format and validation

The [official specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
defines Generic ASCII ticks as timestamp,bid,ask,volume, with millisecond timestamps
`YYYYMMDD HHMMSSNNN` in EST without DST. The parser attaches **fixed UTC−05:00**
and converts to aware UTC, including during summer. It does not use
America/New_York. Strict fixed-width clock parsing rejects malformed timestamps.

Prices are parsed directly from text to Decimal without divisors or pip scaling.
Existing MarketQuote validation rejects nonfinite, nonpositive or crossed quotes.
Rejected source line numbers are recorded; no quote repair occurs. Valid records
are stably sorted chronologically. Equal timestamps are retained in source order;
the duplicate metric counts excess valid rows sharing timestamps.

The volume field is preserved as its original CSV field text. Every selected
observation contains `"0"`. This is provider-specific/unverified metadata, not
global traded gold volume or a volume available for simulated fills.

## Observed results

| Metric | Result |
| --- | --- |
| Raw selected-day rows | 177,064 |
| Valid quotes | 177,064 |
| Invalid/rejected rows | 0 |
| Duplicate timestamps, excess valid rows | 0 |
| Crossed quotes | 0 |
| Minimum spread | 0.001000 |
| Median spread | 0.327000 |
| Maximum spread | 1.804000 |
| Largest observed inter-tick gap | 3,601,796 ms (1 hour 1.796 seconds) |

First: `2024-01-16T05:00:00.119000Z`, bid **2049.345000**, ask **2049.602000**.
Last: `2024-01-17T04:59:58.799000Z`, bid **2025.355000**, ask **2025.645000**.

The gap is unexplained by this pilot: no claim of verified maintenance or feed
completeness. Spread statistics describe this day's observed feed only.

## Five-minute demonstration

**276 observed bins**, timestamped by UTC opening time, with separate bid OHLC
and ask OHLC. Bins are half-open `[opening, opening + 5 minutes)`. Empty bins are
omitted, not synthesized; there are 12 unobserved bins relative to a 288-bin day.
No volume aggregation or candle persistence is performed. These dictionaries are
a small research demonstration, not a new database candle schema.

The first bin at `2024-01-16T05:00:00Z` contains 466 ticks:

| Side | Open | High | Low | Close |
| --- | --- | --- | --- | --- |
| Bid | 2049.345000 | 2049.435000 | 2048.805000 | 2048.855000 |
| Ask | 2049.602000 | 2049.642000 | 2049.142000 | 2049.205000 |

The offline reproduction command (archive must already be local) is:

```sh
PYTHONPATH=src .venv/bin/python scripts/pilot_histdata.py \
  /tmp/HISTDATA_COM_ASCII_XAUUSD_T_202401.zip
```

The script is intentionally limited to this month/day and caps ZIP/member sizes.
It emits a compact report with first/last aggregate samples; full ticks/bars stay
in memory. The parser is isolated under data/providers and reuses MarketQuote,
without forcing tick data through NSE candle contracts. No generic ingestion
platform, downloader service or PostgreSQL integration was added. HistData is
not necessarily the future MT5 broker feed.

## Verification actually run

- `pytest -q`: **664 passed**, no skips; one existing Starlette/AnyIO warning.
  Includes 649 prior cases and 15 synthetic offline HistData cases; NSE regressions
  passed. Tests never require the archive or internet.
- `ruff check .`: passed.
- `black --check .`: passed, 119 files unchanged.
- `mypy`: passed, 74 source files.
- `alembic current`: **0006 (head)**; `alembic check`: no schema drift.
- Git status/diff reviewed; whitespace check clean. Five new files only, no
  existing files modified. No credentials, monthly archive or extracted CSV in
  commit candidates. No dependency changes, migrations or automatic commit.

Recommended commit: `feat: add bounded HistData XAUUSD tick research pilot`.

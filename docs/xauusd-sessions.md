# XAUUSD G1C — session and time model

XAUUSD research uses a near-24-hour weekday model, separate from the NSE
calendar. The supplied policy opens Monday 00:00 UTC through Saturday 00:00 UTC
and closes Saturday/Sunday. This is a theoretical research approximation, not
an assertion of universal gold or broker hours. It does not model Sunday opening,
holidays, early closes or broker-specific interruptions.

`config/xauusd_sessions.yaml` explicitly defines a versioned schedule identity,
UTC clock basis, trading weekdays, optional daily maintenance and ordered label
windows. It is loaded independently of runtime trading settings:

```python
from pathlib import Path
from trading_bot.domain.sessions import (
    SessionConfig, WeekdaySchedule, ResearchSessionClassifier,
)

config = SessionConfig.load(Path("config/xauusd_sessions.yaml"))
schedule = WeekdaySchedule(config)
labels = ResearchSessionClassifier(config)
# timestamp must be timezone-aware
# schedule.is_theoretically_tradable(timestamp)
# labels.classify(timestamp)
```

All timestamp entry points reject naive datetimes and normalize aware timestamps
to UTC before weekday or clock comparisons. Window endpoints are clock values
in the explicitly declared UTC configuration, not datetime instants; endpoint
offsets are rejected. No NSE session or Asia/Kolkata assumptions are imported.

Maintenance defaults to absent because no broker-specific closure has been
verified. Configure, for example, `maintenance: {start: "22:00", end: "22:30"}`.
Windows are half-open: start is closed, end is open again. A start later than end
crosses midnight, e.g. 23:30–00:30. The daily window applies to each UTC instant,
including the early Monday portion; weekends remain closed independently.
Equal endpoints are rejected rather than interpreted as zero or 24 hours.

Research labels are analytical only and are returned even during weekends or
maintenance. The first matching window in configuration wins; no match returns
OFF_SESSION. The supplied illustrative fixed-UTC definitions are:

| Label | UTC interval |
| --- | --- |
| ASIA | 00:00–08:00 |
| LONDON | 08:00–16:00 |
| NEW_YORK | 13:00–21:00 |
| LONDON_NEW_YORK_OVERLAP | 13:00–16:00, configured first |
| OFF_SESSION | No configured match |

Labels can be disabled with an empty list or redefined explicitly. These are
research conventions, not authoritative local exchange hours. No DST adjustment
is inferred. All endpoints use the same half-open rule.

`MarketSchedule` is a small protocol for theoretical tradability. A future MT5
adapter can supply broker-specific session information through this boundary
without changing the research-label classifier. No such adapter is implemented.
Neither a label nor a true schedule result authorizes execution.

The existing NSE calendar, historical pipeline, journal, strategies, backtester
and database schema are unchanged. No migration is needed. No market data,
trading behavior or G1D work is included.

## Verification actually run

- `pytest -q`: **486 passed**, no skips; one existing Starlette/AnyIO warning.
  All 449 prior cases and 37 new session cases passed, including NSE regressions.
- `ruff check .`: passed.
- `black --check .`: passed, 110 files unchanged.
- `mypy`: passed, 70 source files.
- `alembic current`: **0006 (head)**.
- `alembic check`: no new upgrade operations detected.
- Git status/diff reviewed: four new files, no existing files modified.
  No commit made.

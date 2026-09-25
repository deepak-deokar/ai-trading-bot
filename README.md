# AI Trading Bot

Safety-first infrastructure for personal Indian NSE CASH research. **Phase 3.**
The application cannot submit orders. Live configuration is rejected, including
when explicit enablement flags are present. Paper is a configuration label; no
paper broker is connected.

See [Phase 3 features](docs/features.md) and [verification](docs/phase3-verification.md)
for causal numerical features, persistence and the fixture demonstration.

See [Phase 2.1 hardening](docs/phase21-hardening.md) for multi-year coverage,
explicit Groww semantics, and dataset identities.

Historical data now flows through provider → normalization → validation → calendar-aware
quality checks → audited PostgreSQL storage → chronological queries.
See [Phase 2 data guide](docs/historical-data.md) for exact imports, query examples,
schemas, adjustment policy, calendar limitations, and Groww verification status.

## Implemented

- 29 causal numerical features, versioned registry, batch persistence and point-in-time queries.

- Local CSV ingestion and optional data-only Groww candles adapter (real API UNVERIFIED).
- NSE session calendar, duplicate/conflict auditing, and completed-candle queries.
- Python 3.12 package with pinned dependencies and resolved dependency locks.
- Immutable typed settings, configurable universe and interval, environment-only secrets.
- UTC-normalized domain schemas with decimal prices and validated OHLC values.
- JSON application logs with correlation fields and sanitized exception reporting.
- PostgreSQL, SQLAlchemy transaction factories, and an initial Alembic migration.
- `GET /health` (process liveness) and `GET /ready` (database and schema readiness).
- Unit, decimal regression, and real PostgreSQL integration tests.
- Docker, pre-commit, Ruff, Black, and strict mypy configuration.

## Repository

```text
config/                          development, backtest, paper YAML profiles
src/trading_bot/
  api/app.py                     observation-only API factory
  config/settings.py             typed configuration and live-mode rejection
  domain/models.py               Bar, Prediction, OrderRequest, lifecycle vocabulary
  domain/market.py               exchange, segment, timeframe, adjustment types
  data/                          calendar, providers, normalization, quality, ingestion, query, CLI
  features/                      definitions, calculations, engine, repository, CLI
  database/models.py             instruments, events, bars, ingestion runs, feature sets/values
  database/session.py            bounded engine pool and transaction factory
  monitoring/logging.py          JSON log configuration
migrations/                      explicit, versioned schema changes
tests/{unit,integration,regression}/
docs/                            architecture, security, phase roadmap
pyproject.toml                   package, dependencies, tool configuration
requirements.lock                resolved runtime/build dependencies
requirements-dev.lock            resolved development dependencies
Dockerfile / docker-compose.yml   local services
```

Empty future modules are intentionally not scaffolded. Every included module
has working foundation, historical-data or feature behavior. See [architecture](docs/architecture.md) for the
boundaries that subsequent phases must preserve.

## Setup

Requires Python 3.12+ and Docker Desktop/Engine with Compose. Commands run from
the repository root in a POSIX shell. The `.python-version` selects Python 3.12
for version-manager users; a local Python 3.12.7 interpreter was used initially.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
cp .env.example .env
```

Edit `.env`: replace the placeholder password and both database URLs with matching
values. Percent-encode URL password characters; using a random hexadecimal password
avoids URL/shell quoting ambiguity. `.env` is ignored by Git. No actual credentials
are supplied or created in the repository. Load only your own trusted shell-compatible
file (quote values when necessary):

```sh
set -a
source .env
set +a
docker compose up -d --wait db
alembic upgrade head
alembic check
```

Settings never implicitly read `.env`. Compose reads it for interpolation; local
Python processes receive exported environment variables. Precedence is environment
> selected YAML > model defaults. Select a profile using `CONFIG_FILE`; malformed
or missing explicitly selected files fail startup. Database credentials and live
confirmation values are prohibited in YAML. `UNIVERSE` overrides use a JSON array.

PostgreSQL persists its initialization password in the named volume: changing
`.env` does not rotate an existing database password. Do not delete a volume with
valuable data to resolve a credential mismatch.

## Run

```sh
source .venv/bin/activate
# Export settings as above, then:
uvicorn trading_bot.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

Liveness includes `execution_enabled: false`. Readiness returns 503 if the database
is unavailable, unmigrated, or at an unexpected revision. Health does not claim that
a market feed, broker, or trading strategy is ready. No migrations run implicitly
at application startup.

Optional containerized application (set `DOCKER_DATABASE_URL` with host `db`):

```sh
docker compose --profile app build api
docker compose --profile app run --rm api alembic upgrade head
docker compose --profile app up -d --wait
```

API and PostgreSQL ports bind to loopback. `docker compose stop` stops services
without deleting stored data.

## Tests and quality checks

```sh
source .venv/bin/activate
pytest -q                            # database test skips unless explicitly configured
TEST_DATABASE_URL="$DATABASE_URL" pytest -q  # includes real PostgreSQL integration
ruff check .
black --check --workers 1 .
mypy
python -m pip check
pre-commit install                   # optional; writes a local Git hook
```

Use a migrated development/test database for integration testing. Its writes run
inside a transaction that rolls back; never point tests at a live trading database.
Tests cover invalid/live configurations, environment precedence, UTC handling,
OHLC sanity, nonfinite values, exact decimal roundtrips, unique proposal IDs,
health/readiness, safe exception logs, database constraints, and rollback.

Locks pin the resolved versions, including transitive dependencies. Re-resolve and
review them when upgrading dependencies; pins are reproducibility controls, not a
security certification. No ML framework is installed; pandas supports calendar schedules and NumPy supports
calendar data and numerical feature calculations.

## Scope and next checkpoint

The application has no execution capability. Live mode remains rejected and no
paper orders or broker connections were made. Historical data does not imply a
strategy is profitable or safe to deploy with capital.

Phase 3 adds `feature_sets` and `feature_values` beside the historical tables.
Later phases own models, strategy, risk, accounting and execution. Phase 4 has not
begun; this implementation stops after numerical feature engineering.
See [historical data guide](docs/historical-data.md), [roadmap](docs/roadmap.md),
[security](docs/security.md), and [Phase 2 verification](docs/phase2-verification.md).

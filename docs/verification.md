# Phase 1 verification (historical record)

Current results: [Phase 3 verification](phase3-verification.md). The same local
PostgreSQL instance now runs migration 0003. The credential-loading commands below
still apply; also export `PYTHONPATH="$PWD/src"` for local source execution.

Verified on Python 3.12.7 / macOS with PostgreSQL 17.6 in Docker:

- Initial migration applied successfully; `alembic check` reports no schema drift.
- Unit, regression, and PostgreSQL integration tests pass.
- Ruff, Black, strict mypy, and dependency consistency checks pass.
- API Docker image builds successfully, including Linux dependency installation.
- A real Uvicorn process returned HTTP 200 for `/health` and `/ready`, then shut down.
- Execution remains disabled; no broker connection or order submission occurred.

The test client emits one upstream Starlette/AnyIO deprecation warning. It does not
cause test failures and is not suppressed; review it during dependency upgrades.

## Existing verification database

Docker Desktop and the project's PostgreSQL container were started for verification.
The database remains available, with its initialized named volume. A generated local
password is stored outside the repository in `/tmp/ai-trading-phase1.env` (mode 0600).
No credential-bearing `.env` was created. For this existing database, use:

```sh
source .venv/bin/activate
set -a
source /tmp/ai-trading-phase1.env
set +a
export DATABASE_URL="postgresql+psycopg://trading:${POSTGRES_PASSWORD}@localhost:5432/trading"
export CONFIG_FILE=config/development.yaml
export TRADING_MODE=paper
export LIVE_TRADING_ENABLED=false
export LIVE_TRADING_CONFIRMATION=
alembic current
TEST_DATABASE_URL="$DATABASE_URL" pytest -q
uvicorn trading_bot.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Temporary files may be removed by the operating system. Preserve the local password
in your chosen secret store if retaining this development database. For a new
installation, follow the README. Replacing a password in `.env` does not update
credentials in an initialized PostgreSQL volume.

To stop the verification database without deleting its volume:

```sh
docker compose --env-file /tmp/ai-trading-phase1.env stop db
```

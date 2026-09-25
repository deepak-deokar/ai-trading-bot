# Architecture and assumptions (updated through Phase 3)

The namespaced `src/trading_bot` layout avoids collisions with generic installed
packages such as `models`, `config`, or `data`. Dependency direction is API →
configuration/database/monitoring. Domain schemas have no database or broker dependency.
Explicit factory injection allows tests to control settings and database ownership.

Future trading flow must remain:

Market data → features → prediction → strategy → portfolio → deterministic risk
→ execution → broker adapter. Models never obtain broker access. Before any
simulated or external execution becomes possible, its path must include the risk
engine, persistent lifecycle state, duplicate prevention, reconciliation, and kill switch.
The roadmap sequence does not authorize bypassing risk in earlier backtests.

## Decisions

- Synchronous SQLAlchemy 2 / psycopg with bounded pooling is adequate for the
  observation API. FastAPI synchronous routes execute in its thread pool.
- PostgreSQL is authoritative persistence. No Redis or TimescaleDB is needed yet.
- `instruments` and `system_events` are the initial schema. Migrations, never
  automatic `create_all`, own database schema changes. SystemEvent supports durable
  events; application startup/shutdown currently emit logs only, allowing liveness
  to remain available during a database outage.
- Market bars use **opening timestamps**, normalized to UTC. Phase 2 explicitly
  replaces the unused Phase 1 close-time convention; stored `available_at` carries
  the session-aware close. Queries enforce the completion cutoff. See
  [historical data](historical-data.md) for the NSE calendar policy.
- Financial prices use finite `Decimal`; whole-share positive proposals are the
  initial assumption. No leverage, shorting, or fractional execution is implemented.
- Order proposals are immutable and do not contain a user-settable approval state.
  Status enums do not implement a lifecycle or imply risk approval.
- Every live-related flag is rejected, including flags supplied in another mode.
  Phase 14 requires a reviewed implementation change as well as explicit approval.
- The API owns and disposes only engines it creates. Missing secrets fail startup;
  unavailable databases yield readiness 503 without leaking driver error messages.
- Application logs are JSON; Uvicorn maintains its own server/access logging.
  Context keys are allowlisted; arbitrary messages must still be secret-free.
- Initial migration adds foundation tables; Phase 2 adds market bars and ingestion
  runs. Phase 3 adds feature sets/values via migration 0003. Features use a bounded
  repeatable-read historical snapshot, causal numerical engine, validated batch
  persistence and explicit point-in-time queries. See [feature architecture](features.md).
- Predictions, signals, orders/events/fills, positions/snapshots, risk events, strategy
  runs and model versions remain deferred to their tested owning services.

## References

Settings source behavior follows the [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
Schema versioning follows the [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

## Deferred infrastructure

NumPy is used for Phase 3 features; Polars remains optional and uninstalled.
Scikit-learn and LightGBM or XGBoost for
baselines; controlled Optuna tuning and MLflow tracking follow research validation.
Pandas only for compatibility. No PyTorch until justified. Prometheus/Grafana and
an authenticated operator dashboard follow working risk/execution infrastructure.

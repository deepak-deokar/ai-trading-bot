# Incremental roadmap

1. Foundation: configuration, logging, domain schemas, PostgreSQL, API, tests.
2. Historical ingestion (implemented): provider interface, bars migration, validation, deduplication,
   session-aware missing/gap checks, reproducible ingestion provenance.
3. Deterministic versioned features (implemented): 29 baseline numerical outputs,
   completion-aware queries, gap policy, reproducible identities and persistence.
4. Event-driven backtesting, accounting, costs, execution timing.
5. Deterministic baseline strategy and honest cost-adjusted reports.
6. Chronological ML training, purged labels, validation, model registry.
7. ML signals and walk-forward evaluation with untouched final test data.
8. Independent deterministic risk, sizing, persistent kill switch.
9. Persistent execution lifecycle and simulated broker; risk is mandatory.
10. Paper broker integration and failure/recovery tests.
11. Metrics, alerts, authenticated dashboard.
12. Shadow trading against live data.
13. Security, operational readiness, deployment and recovery review.
14. Explicitly approved, controlled small-capital live deployment.

No phase advances automatically beyond the requested checkpoint. ML cannot control
a broker. Trading and accounting tests are introduced with their implementations;
Phase 1 does not pretend to implement them.

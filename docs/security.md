# Secrets and deployment boundary

Never commit `.env`, credentials, access tokens, production data, or broker keys.
Use environment injection from a secret manager for deployments. The example file
contains placeholders only. Database URL credentials must be URL-encoded.

Do not log configuration objects, raw requests, broker responses, exception strings,
or secrets in log messages. The application formatter only includes known context
fields and exception type; it cannot detect a secret deliberately put in a message.
Database SQL parameters are hidden. Error endpoints return generic readiness failures.

Compose is local development infrastructure. Its initialization user is a database
owner, not a production least-privilege runtime account. Production requires separate
migration/runtime roles, TLS, secret rotation, network isolation, dependency review,
backup/restore verification, access controls, and deployment review in Phase 13.
Containerized API runs as a non-root user. Its health endpoints expose no credentials.
Do not expose this unauthenticated development API to the public internet.

Live mode has no implementation and is unconditionally rejected. Adding a broker
adapter later must not weaken this guard accidentally. Paper mode is not a fallback
for malformed configuration; invalid configuration fails validation.

Phase 2 Groww credentials are optional and environment-only (`GROWW_ACCESS_TOKEN`).
CSV fixtures contain synthetic prices and no credentials. Provider failures and CLI
errors never include raw vendor messages or credential values. Do not place secrets
in CSV/YAML or command-line arguments. Real Groww connectivity is UNVERIFIED.

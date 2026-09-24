# Phase 2 file changes

Compared with the Phase 1 working tree (the repository is not yet committed).

## Created

- `config/calendar_nse.yaml`
- `docs/historical-data.md`
- `docs/phase2-demo.json`
- `docs/phase2-files.md`
- `docs/phase2-verification.md`
- `migrations/versions/0002_historical_data.py`
- `scripts/demonstrate_phase2.py`
- `src/trading_bot/data/__init__.py`
- `src/trading_bot/data/calendar.py`
- `src/trading_bot/data/contracts.py`
- `src/trading_bot/data/import_history.py`
- `src/trading_bot/data/ingestion.py`
- `src/trading_bot/data/normalize.py`
- `src/trading_bot/data/providers/__init__.py`
- `src/trading_bot/data/providers/base.py`
- `src/trading_bot/data/providers/groww.py`
- `src/trading_bot/data/providers/local.py`
- `src/trading_bot/data/quality.py`
- `src/trading_bot/data/query.py`
- `src/trading_bot/domain/market.py`
- `tests/fixtures/reliance_conflict.csv`
- `tests/fixtures/reliance_invalid.csv`
- `tests/fixtures/reliance_valid.csv`
- `tests/fixtures/tcs_gap.csv`
- `tests/fixtures/tcs_overnight.csv`
- `tests/fixtures/tcs_weekend.csv`
- `tests/integration/conftest.py`
- `tests/integration/test_history.py`
- `tests/unit/test_history_calendar.py`
- `tests/unit/test_history_domain.py`
- `tests/unit/test_history_providers.py`

## Modified

- `.env.example`
- `README.md`
- `alembic.ini`
- `config/backtest.yaml`
- `config/development.yaml`
- `config/paper.yaml`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/security.md`
- `docs/verification.md`
- `migrations/env.py`
- `pyproject.toml`
- `requirements-dev.lock`
- `requirements.lock`
- `src/trading_bot/__init__.py`
- `src/trading_bot/api/app.py`
- `src/trading_bot/config/settings.py`
- `src/trading_bot/database/models.py`
- `src/trading_bot/domain/models.py`
- `tests/conftest.py`
- `tests/unit/test_api.py`
- `tests/unit/test_settings.py`

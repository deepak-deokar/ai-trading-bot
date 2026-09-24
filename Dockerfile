FROM python:3.12.11-slim-bookworm
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY config ./config
COPY migrations ./migrations
COPY alembic.ini ./
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation . && useradd --uid 10001 --create-home trader
USER trader
CMD ["uvicorn", "trading_bot.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

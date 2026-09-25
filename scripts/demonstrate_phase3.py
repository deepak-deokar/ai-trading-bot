"""Deterministic fixture demonstration in an automatically removed PostgreSQL schema.

Requires DATABASE_URL and PYTHONPATH=src; writes no market data in public schema.
"""

import json
import os
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.base import RawCandle
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.data.query import HistoryQuery
from trading_bot.domain.market import AdjustmentType
from trading_bot.features.definitions import FeatureConfig
from trading_bot.features.engine import FeatureEngine
from trading_bot.features.repository import FeatureRepository
from trading_bot.features.service import FeatureService

FIXTURE = Path("tests/fixtures/reliance_features.csv")


def demonstrate(engine):
    calendar = NSECalendar()
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=datetime.fromisoformat("2026-01-05T09:15:00+05:30"),
        end=datetime.fromisoformat("2026-01-05T14:15:00+05:30"),
    )
    ingestion = IngestionService(engine, calendar).ingest(
        LocalCSVProvider(FIXTURE), request
    )
    assert ingestion.rows_inserted == 60
    config = FeatureConfig.load(Path("config/features.yaml"))
    service = FeatureService(engine, calendar)
    first = service.generate(request, source="local", config=config)
    second = service.generate(request, source="local", config=config)
    assert first.rows_inserted == 60 and second.rows_inserted == 0
    repository = FeatureRepository(engine)

    def rows(report, cutoff=request.end):
        return repository.get_features(
            feature_set_key=report.feature_set_key,
            symbol="RELIANCE",
            start=request.start,
            end=request.end,
            as_of=cutoff,
        )

    values = rows(first)
    assert values[0].values["ema_20"] is None and values[20].sufficient_history
    early = len(rows(first, request.start + timedelta(minutes=4, seconds=59)))
    complete = len(rows(first, request.start + timedelta(minutes=5)))
    assert (early, complete) == (0, 1)
    snapshot = HistoryQuery(engine).get_snapshot(request, source="local")
    revised = list(snapshot.bars)
    for i in range(35, len(revised)):
        bar = revised[i].bar
        revised[i] = replace(
            revised[i],
            bar=bar.model_copy(
                update={
                    f: getattr(bar, f) * 2 for f in ("open", "high", "low", "close")
                }
                | {"volume": 99999}
            ),
        )
    causal = FeatureEngine(calendar).generate(
        replace(snapshot, bars=tuple(revised)), request, source="local", config=config
    )
    assert list(causal.rows[:35]) == values[:35]
    changed = config.model_copy(
        update={
            "features": tuple(
                (
                    s.model_copy(update={"params": {"period": 10}})
                    if s.name == "rsi"
                    else s
                )
                for s in config.features
            )
        }
    )
    rsi10 = service.generate(request, source="local", config=changed)
    assert rsi10.feature_set_key != first.feature_set_key

    class AdjustedFixture:
        name = "local"

        def fetch_bars(self, request):
            return [
                RawCandle(
                    item.bar.model_dump(mode="json")
                    | {
                        "adjustment_type": "SPLIT_ADJUSTED",
                        **{
                            f: str(getattr(item.bar, f) / 2)
                            for f in ("open", "high", "low", "close")
                        },
                    },
                    i + 1,
                )
                for i, item in enumerate(snapshot.bars)
            ]

    adjusted_request = request.model_copy(
        update={"adjustment_type": AdjustmentType.SPLIT_ADJUSTED}
    )
    IngestionService(engine, calendar).ingest(AdjustedFixture(), adjusted_request)
    adjusted = service.generate(adjusted_request, source="local", config=config)
    assert rows(adjusted)[0].close == values[0].close / 2
    assert adjusted.feature_set_key != first.feature_set_key
    gapped = FeatureEngine(calendar).generate(
        replace(snapshot, bars=snapshot.bars[:25] + snapshot.bars[26:]),
        request,
        source="local",
        config=config,
    )
    assert gapped.rows[25].gap_before
    assert gapped.rows[25].unavailable["ema_20"] == "GAP_WARMUP"
    assert repository.save(gapped) == 59
    sample = []
    for i in (0, 1, 14, 19, 20, 21, 35):
        row = values[i]
        sample.append(
            {
                "timestamp": row.timestamp.isoformat(),
                "available_at": row.available_at.isoformat(),
                "close": str(row.close),
                **{
                    k: row.values[k]
                    for k in (
                        "return_1",
                        "ema_10",
                        "ema_20",
                        "rsi_14",
                        "atr_14",
                        "volume_ratio",
                        "session_progress",
                    )
                },
            }
        )
    return {
        "fixture": "synthetic RELIANCE NSE CASH; not observed exchange prices",
        "baseline": first.model_dump(mode="json"),
        "second_run_inserted": second.rows_inserted,
        "visibility_09_19_59": early,
        "visibility_09_20": complete,
        "future_mutation_earlier_rows_unchanged": 35,
        "rsi_10_key": rsi10.feature_set_key,
        "split_adjusted_key": adjusted.feature_set_key,
        "gap_missing_bars": gapped.missing_bars,
        "gap_affected_rows": sum(
            "GAP_WARMUP" in r.unavailable.values() for r in gapped.rows
        ),
        "gap_first_row": gapped.rows[25].model_dump(mode="json"),
        "sample": sample,
    }


def main():
    url = os.environ["DATABASE_URL"]
    schema = "phase3_demo_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        connect_args={"options": f"-c search_path={schema} -c timezone=UTC"},
        hide_parameters=True,
    )
    try:
        with engine.begin() as conn:
            config = Config("alembic.ini")
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        result = demonstrate(engine)
        output = json.dumps(result, indent=2, allow_nan=False)
        Path("docs/phase3-demonstration.json").write_text(output + "\n")
        print(output)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


if __name__ == "__main__":
    main()

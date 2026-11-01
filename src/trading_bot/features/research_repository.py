"""Atomic per-source-day feature persistence with exact JSON Decimal encoding."""

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from trading_bot.data.gap_policy import ProviderGapPolicy
from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.database.models import BidAskBar, ResearchFeatureBar, SystemEvent
from trading_bot.domain.market import utc
from trading_bot.features.definitions import FeatureError
from trading_bot.features.xauusd import VERSION, XAUUSDFeatureRow, calculate_xauusd


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ResearchFeatureRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def generate(
        self, dataset: QuoteDataset, policy: ProviderGapPolicy
    ) -> dict[str, object]:
        """Lock source bars, recheck approval and compare; never overwrite."""
        with Session(self.engine) as session, session.begin():
            session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": int(dataset.dataset_key[:15], 16)},
            )
            source = tuple(
                session.scalars(
                    select(BidAskBar)
                    .where(BidAskBar.dataset_key == dataset.dataset_key)
                    .order_by(BidAskBar.opening_timestamp)
                    .with_for_update(read=True)
                )
            )
            batch = approved_research_inputs(dataset, source, policy, as_of=dataset.end)
            rows = calculate_xauusd(batch)
            payloads = [r.model_dump(mode="json") for r in rows]
            manifest = {
                "source": dataset.model_dump(mode="json", exclude_none=True),
                "source_dataset_key": dataset.dataset_key,
                "feature_set_version": VERSION,
                "engine_version": VERSION,
                "input_semantics_version": "g2c3a-research-input-v1",
                "source_bar_count": len(source),
                "feature_row_count": len(rows),
                "content_hash": content_hash(payloads),
                "warmup_rows": sum(
                    any(v.value is None for v in r.values) for r in rows
                ),
                "unavailable_counts": dict(
                    Counter(v.name for r in rows for v in r.values if v.value is None)
                ),
                "discontinuity_resets": sum(
                    r.sequence_reset == "DISCONTINUITY" for r in rows
                ),
                "dataset_resets": sum(
                    r.sequence_reset == "DATASET_BOUNDARY" for r in rows
                ),
            }
            key = content_hash(manifest)
            existing = list(
                session.scalars(
                    select(ResearchFeatureBar)
                    .where(
                        ResearchFeatureBar.source_dataset_key == dataset.dataset_key,
                        ResearchFeatureBar.feature_version == VERSION,
                    )
                    .order_by(ResearchFeatureBar.opening_timestamp)
                )
            )
            if existing:
                if len(existing) != len(rows) or any(
                    old.payload != payload
                    or old.feature_dataset_key != key
                    or old.opening_timestamp != row.opening_timestamp
                    or old.available_at != row.available_at
                    or old.canonical_symbol != row.canonical_symbol
                    or old.interval != row.input.interval
                    for old, row, payload in zip(existing, rows, payloads, strict=True)
                ):
                    raise FeatureError(
                        "conflicting or incomplete research feature dataset"
                    )
            else:
                session.add_all(
                    [
                        ResearchFeatureBar(
                            source_dataset_key=dataset.dataset_key,
                            opening_timestamp=row.opening_timestamp,
                            feature_version=VERSION,
                            canonical_symbol=row.canonical_symbol,
                            interval=row.input.interval,
                            available_at=row.available_at,
                            feature_dataset_key=key,
                            payload=payload,
                        )
                        for row, payload in zip(rows, payloads, strict=True)
                    ]
                )
                session.flush()
            run_id = uuid4()
            report = {
                "feature_dataset_key": key,
                "manifest": manifest,
                "inserted": 0 if existing else len(rows),
                "existing": len(existing),
                "generated_at": datetime.now(UTC).isoformat(),
                "run_id": str(run_id),
            }
            session.add(
                SystemEvent(
                    run_id=run_id,
                    event_type="research_feature_import",
                    severity="INFO",
                    message="Policy-approved Decimal research features",
                    details=report,
                )
            )
            return report

    def get_rows(
        self,
        *,
        source_dataset_key: str,
        symbol: str,
        feature_version: str,
        start: datetime,
        end: datetime,
        as_of: datetime,
    ) -> tuple[XAUUSDFeatureRow, ...]:
        start, end, as_of = utc(start), utc(end), utc(as_of)
        if start >= end:
            raise FeatureError("feature query start must precede end")
        with Session(self.engine) as session:
            rows = session.scalars(
                select(ResearchFeatureBar)
                .where(
                    ResearchFeatureBar.source_dataset_key == source_dataset_key,
                    ResearchFeatureBar.canonical_symbol == symbol,
                    ResearchFeatureBar.feature_version == feature_version,
                    ResearchFeatureBar.opening_timestamp >= start,
                    ResearchFeatureBar.opening_timestamp < end,
                    ResearchFeatureBar.available_at <= as_of,
                )
                .order_by(ResearchFeatureBar.opening_timestamp)
            )
            return tuple(
                XAUUSDFeatureRow.model_validate_json(json.dumps(r.payload))
                for r in rows
            )

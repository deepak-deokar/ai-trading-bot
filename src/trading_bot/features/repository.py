"""Atomic batch persistence and mandatory point-in-time feature queries."""

from datetime import datetime

from sqlalchemy import Engine, func, insert, select, text
from sqlalchemy.orm import Session

from trading_bot.data.identity import digest
from trading_bot.database.models import FeatureSet, FeatureValue
from trading_bot.domain.market import utc
from trading_bot.features.definitions import (
    FeatureError,
    FeatureResult,
    FeatureRow,
    FeatureSpec,
)
from trading_bot.features.validation import validate_row


class FeatureRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save(self, result: FeatureResult) -> int:
        """All-or-nothing; serialize identical-key writers, insert in batches."""
        canonical = {
            k: v for k, v in result.manifest.items() if k != "historical_identities"
        }
        if (
            digest(canonical) != result.feature_set_key
            or digest(result.manifest["dataset"]) != result.dataset_key
            or not result.rows
        ):
            raise FeatureError("feature result identity is inconsistent")
        specs = tuple(
            FeatureSpec(name=d["name"], output=d["output"], params=d["parameters"])
            for d in result.manifest["definitions"]
        )
        for row in result.rows:
            validate_row(row, specs)
        with Session(self.engine) as session, session.begin():
            lock = int(result.feature_set_key[:16], 16) - 2**63
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
            existing = session.get(FeatureSet, result.feature_set_key)
            if existing:
                actual = session.scalar(
                    select(func.count())
                    .select_from(FeatureValue)
                    .where(FeatureValue.feature_set_key == result.feature_set_key)
                )
                if actual != len(result.rows) or existing.row_count != actual:
                    raise FeatureError(
                        "incomplete stored feature set; refusing cache reuse"
                    )
                return 0
            session.add(
                FeatureSet(
                    feature_set_key=result.feature_set_key,
                    dataset_key=result.dataset_key,
                    name=result.manifest["feature_config"],
                    manifest=result.manifest,
                    row_count=len(result.rows),
                )
            )
            session.flush()
            for start in range(0, len(result.rows), 1000):
                session.execute(
                    insert(FeatureValue),
                    [
                        {"feature_set_key": result.feature_set_key, **r.model_dump()}
                        for r in result.rows[start : start + 1000]
                    ],
                )
        return len(result.rows)

    def get_features(
        self,
        *,
        feature_set_key: str,
        symbol: str,
        start: datetime,
        end: datetime,
        as_of: datetime,
    ) -> list[FeatureRow]:
        """No default knowledge cutoff. A set key fixes timeframe/source/adjustment."""
        start, end, as_of = utc(start), utc(end), utc(as_of)
        if start >= end:
            raise FeatureError("feature query start must precede end")
        with Session(self.engine) as session:
            rows = session.scalars(
                select(FeatureValue)
                .where(
                    FeatureValue.feature_set_key == feature_set_key,
                    FeatureValue.symbol == symbol,
                    FeatureValue.timestamp >= start,
                    FeatureValue.timestamp < end,
                    FeatureValue.available_at <= min(as_of, end),
                )
                .order_by(FeatureValue.timestamp)
            ).all()
            return [
                FeatureRow.model_validate(
                    {c: getattr(r, c) for c in FeatureRow.model_fields}
                )
                for r in rows
            ]

    def get_manifest(self, feature_set_key: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            value = session.get(FeatureSet, feature_set_key)
            return value.manifest if value else None

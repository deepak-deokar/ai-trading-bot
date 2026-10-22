"""Initial audit commit survives atomic-result rollback; all records are simulated."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, insert, select
from sqlalchemy.orm import Session

from trading_bot.backtesting.orders import BacktestError
from trading_bot.backtesting.results import BacktestResult
from trading_bot.database.models import (
    BacktestEquityPoint,
    BacktestEvent,
    BacktestFill,
    BacktestOrder,
    BacktestRun,
    BacktestTrade,
)


class BacktestRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def start(self, run_id: UUID, manifest: dict[str, Any]) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(
                BacktestRun(
                    run_id=run_id,
                    started_at=datetime.now(UTC),
                    status="RUNNING",
                    manifest=manifest,
                    summary={},
                )
            )

    def fail(self, run_id: UUID, reason: str) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(BacktestRun, run_id)
            if row is None:
                raise BacktestError("audit run not found")
            row.status = "FAILED"
            row.completed_at = datetime.now(UTC)
            row.summary = {"failure": reason}

    def save(self, result: BacktestResult) -> None:
        data = result.model_dump(mode="json")
        with Session(self.engine) as session, session.begin():
            run = session.get(BacktestRun, result.run_id, with_for_update=True)
            if run is None or run.status != "RUNNING":
                raise BacktestError("result requires a RUNNING audit")
            orders = [
                {"run_id": result.run_id, "order_id": r["order_id"], "payload": r}
                for r in data["orders"]
            ]
            if orders:
                session.execute(insert(BacktestOrder), orders)
            for model, key in (
                (BacktestFill, "fills"),
                (BacktestTrade, "trades"),
                (BacktestEquityPoint, "equity"),
                (BacktestEvent, "events"),
            ):
                rows = []
                for index, payload in enumerate(data[key]):
                    row = {
                        "run_id": result.run_id,
                        "sequence": index,
                        "timestamp": datetime.fromisoformat(
                            payload.get("timestamp", payload.get("exit_time"))
                        ),
                        "payload": payload,
                    }
                    if key == "fills":
                        row["order_id"] = payload["order_id"]
                    rows.append(row)
                for index in range(0, len(rows), 1000):
                    session.execute(insert(model), rows[index : index + 1000])
            run.status = result.status
            run.config_key = result.config_key
            run.manifest = data["manifest"]
            run.summary = {"metrics": data["metrics"], "warnings": data["warnings"]}
            run.completed_at = datetime.now(UTC)

    def get_result(self, run_id: UUID) -> BacktestResult | None:
        with Session(self.engine) as session:
            run = session.get(BacktestRun, run_id)
            if run is None or not run.status.startswith("COMPLETED"):
                return None
            data: dict[str, Any] = dict(
                run_id=run_id,
                config_key=run.config_key,
                manifest=run.manifest,
                status=run.status,
                **run.summary,
            )
            data["orders"] = [
                r.payload
                for r in session.scalars(
                    select(BacktestOrder)
                    .where(BacktestOrder.run_id == run_id)
                    .order_by(BacktestOrder.order_id)
                )
            ]
            for model, key in (
                (BacktestFill, "fills"),
                (BacktestTrade, "trades"),
                (BacktestEquityPoint, "equity"),
                (BacktestEvent, "events"),
            ):
                data[key] = [
                    payload
                    for payload in session.scalars(
                        select(model.__table__.c.payload)
                        .where(model.__table__.c.run_id == run_id)
                        .order_by(model.__table__.c.sequence)
                    )
                ]
            return BacktestResult.model_validate(data)

    def get_audit(self, run_id: UUID) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.get(BacktestRun, run_id)
            return (
                {
                    "run_id": str(run_id),
                    "status": row.status,
                    "manifest": row.manifest,
                    "summary": row.summary,
                }
                if row
                else None
            )

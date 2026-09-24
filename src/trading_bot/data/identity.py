"""Canonical metadata identity, not a content snapshot/versioning platform."""

import hashlib
import json
from typing import Any
from uuid import UUID

from pydantic import Field

from trading_bot.data.contracts import HistoryRequest
from trading_bot.domain.models import DomainModel


class DatasetIdentity(DomainModel):
    schema_version: str = "historical-dataset-v1"
    run_id: UUID
    dataset_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest: dict[str, Any]


def digest(value: dict[str, Any]) -> str:
    """Stable across mapping order; no wall-clock times or secrets included."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def dataset_identity(
    request: HistoryRequest,
    provider: str,
    run_id: UUID,
    calendar: dict[str, str],
    provider_semantics: dict[str, Any],
) -> DatasetIdentity:
    """Dataset key describes selection/semantics; run key identifies an import."""
    selection = request.model_dump(mode="json")
    selection["symbols"] = sorted(request.symbols)
    manifest = {
        "schema_version": "historical-dataset-v1",
        "provider": provider,
        "selection": selection,
        "calendar": calendar,
        "timestamp_convention": "open",
        "range_convention": "[start,end)",
        "completion_policy": "available_at <= requested_end",
        "provider_semantics": provider_semantics,
    }
    key = digest(manifest)
    return DatasetIdentity(
        run_id=run_id,
        dataset_key=key,
        run_key=digest({"dataset_key": key, "run_id": str(run_id)}),
        manifest=manifest,
    )

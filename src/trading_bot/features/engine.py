"""Pure causal feature engine over a bounded historical snapshot."""

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime
from typing import Protocol

import numpy as np

from trading_bot.data.calendar import MarketCalendar, Session
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.identity import digest
from trading_bot.data.snapshot import HistorySnapshot, SnapshotBar
from trading_bot.features import price, volume
from trading_bot.features.definitions import (
    FeatureConfig,
    FeatureError,
    FeatureResult,
    FeatureRow,
)
from trading_bot.features.numerics import Array
from trading_bot.features.registry import resolve
from trading_bot.features.validation import validate_row


class FeatureCalendar(MarketCalendar, Protocol):
    def sessions(self, start: datetime, end: datetime) -> tuple[Session, ...]: ...


class FeatureEngine:
    version = "causal-baseline-v1"

    def __init__(self, calendar: FeatureCalendar, *, max_slots: int = 100_000) -> None:
        self.calendar = calendar
        self.max_slots = max_slots

    def generate(
        self,
        snapshot: HistorySnapshot,
        request: HistoryRequest,
        *,
        source: str,
        config: FeatureConfig,
    ) -> FeatureResult:
        definitions = tuple(resolve(s) for s in config.features)
        # Reject oversized ranges before materializing a potentially huge slot map.
        sessions = self.calendar.sessions(request.start, request.end)
        upper_bound = sum(
            max(1, int((s.closes - s.opens) / request.timeframe.duration) + 1)
            for s in sessions
        ) * len(request.symbols)
        if upper_bound > self.max_slots or len(snapshot.bars) > self.max_slots:
            raise FeatureError("feature request exceeds bounded slot/row limit")
        slots = self.calendar.expected_bars(
            request.start, request.end, request.timeframe
        )
        slot_index = {t: i for i, t in enumerate(sorted(slots))}
        openings = [session.opens for session in sessions]
        session_by_time = {t: sessions[bisect_right(openings, t) - 1] for t in slots}
        if any(not s.opens <= t < s.closes for t, s in session_by_time.items()):
            raise FeatureError("calendar slots disagree with sessions")
        calendar = self.calendar.provenance(request.start, request.end)
        identities = {i.run_id: i for i in snapshot.identities}
        if len(identities) != len(snapshot.identities):
            raise FeatureError("ambiguous ingestion identities")
        selections = {}
        for run_id, provenance in identities.items():
            manifest = provenance.manifest
            if (
                digest(manifest) != provenance.dataset_key
                or manifest.get("timestamp_convention") != "open"
            ):
                raise FeatureError("historical dataset identity is inconsistent")
            selections[run_id] = HistoryRequest.model_validate(manifest["selection"])
        groups: dict[str, list[SnapshotBar]] = defaultdict(list)
        for item in snapshot.bars:
            b = item.bar
            if (
                b.symbol not in request.symbols
                or b.exchange != request.exchange
                or b.segment != request.segment
                or b.timeframe != request.timeframe
                or b.source != source
                or b.adjustment_type != request.adjustment_type
            ):
                raise FeatureError("mixed or mismatched historical series")
            if b.timestamp not in slots or item.available_at != slots[b.timestamp]:
                raise FeatureError("candle is not a completed calendar-aligned slot")
            identity = identities.get(item.ingestion_run_id)
            if identity is None:
                raise FeatureError("historical dataset identity required")
            manifest = identity.manifest
            origin = selections[item.ingestion_run_id]
            if (
                b.symbol not in origin.symbols
                or b.exchange != origin.exchange
                or b.segment != origin.segment
                or b.timeframe != origin.timeframe
                or not origin.start <= b.timestamp < origin.end
                or item.available_at > origin.end
            ):
                raise FeatureError("candle lies outside its ingestion identity")
            if (
                manifest.get("calendar", {}).get("version") != self.calendar.version
                or manifest.get("provider") != source
                or manifest.get("selection", {}).get("adjustment_type")
                != request.adjustment_type
            ):
                raise FeatureError(
                    "historical provenance/calendar does not match feature input"
                )
            groups[b.symbol].append(item)
        if set(groups) != set(request.symbols):
            raise FeatureError("no completed bars for one or more requested symbols")
        output: list[FeatureRow] = []
        for symbol in sorted(groups):
            series = sorted(groups[symbol], key=lambda x: x.bar.timestamp)
            if len({x.bar.timestamp for x in series}) != len(series):
                raise FeatureError("duplicate candle in feature input")
            begin = 0
            gap_segment = slot_index[series[0].bar.timestamp] != 0
            for i in range(1, len(series) + 1):
                boundary = i == len(series) or (
                    slot_index[series[i].bar.timestamp]
                    != slot_index[series[i - 1].bar.timestamp] + 1
                )
                if boundary:
                    output.extend(
                        self._segment(
                            series[begin:i], config, session_by_time, gap_segment
                        )
                    )
                    begin, gap_segment = i, True
        output.sort(key=lambda row: (row.timestamp, row.symbol))
        ordered_input = sorted(
            snapshot.bars, key=lambda x: (x.bar.timestamp, x.bar.symbol)
        )
        # Decimal serialization is normalized so storage scale doesn't change identity.
        contents = []
        for item in ordered_input:
            values = item.bar.model_dump(mode="json")
            for name in ("open", "high", "low", "close", "vwap"):
                value = getattr(item.bar, name)
                values[name] = (
                    format(value.normalize(), "f") if value is not None else None
                )
            contents.append(
                {"bar": values, "available_at": item.available_at.isoformat()}
            )
        selection = request.model_dump(mode="json")
        selection["symbols"] = sorted(request.symbols)
        dataset = {
            "selection": selection,
            "source": source,
            "calendar": calendar,
            "historical_datasets": sorted({i.dataset_key for i in snapshot.identities}),
            "input_digest": digest({"candles": contents}),
        }
        manifest = {
            "engine_version": self.version,
            "numeric": "IEEE754-float64/JSON",
            "numpy_version": np.__version__,
            "dataset": dataset,
            "dataset_key": digest(dataset),
            "historical_identities": [
                i.model_dump(mode="json")
                for i in sorted(snapshot.identities, key=lambda i: str(i.run_id))
            ],
            "feature_config": config.name,
            "definitions": [
                d.model_dump(mode="json")
                for d in sorted(definitions, key=lambda d: d.output)
            ],
            "timestamp": "candle_open",
            "availability": "candle_completion",
            "gap_policy": "reset_all_rolling_state",
            "overnight": "continue",
            "warmup": "null; requested range only; no hidden preload",
        }
        # Run IDs are provenance, not numerical input identity.
        key = digest(
            {k: v for k, v in manifest.items() if k != "historical_identities"}
        )
        return FeatureResult(
            feature_set_key=key,
            dataset_key=manifest["dataset_key"],
            manifest=manifest,
            rows=tuple(output),
            missing_bars=len(slots) * len(request.symbols) - len(output),
        )

    @staticmethod
    def _segment(
        series: list[SnapshotBar],
        config: FeatureConfig,
        sessions: dict[datetime, Session],
        gap: bool,
    ) -> list[FeatureRow]:
        close, high, low, volumes = (
            np.asarray([float(getattr(x.bar, field)) for x in series], dtype=np.float64)
            for field in ("close", "high", "low", "volume")
        )
        since = np.asarray(
            [
                (x.bar.timestamp - sessions[x.bar.timestamp].opens).total_seconds() / 60
                for x in series
            ]
        )
        until = np.asarray(
            [
                (sessions[x.bar.timestamp].closes - x.bar.timestamp).total_seconds()
                / 60
                for x in series
            ]
        )
        context = {
            "minutes_since_open": since,
            "minutes_until_close": until,
            "session_progress": since / (since + until),
        }
        arrays: dict[str, Array] = {}
        definitions = {s.output: resolve(s) for s in config.features}
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for spec in config.features:
                if spec.name in context:
                    values = context[spec.name]
                elif spec.name.startswith("volume_"):
                    values = volume.calculate(spec, volumes)
                else:
                    values = price.calculate(spec, close, high, low)
                arrays[spec.output] = values
        rows = []
        for i, item in enumerate(series):
            values_out: dict[str, float | None] = {}
            reasons = {}
            for name, array in arrays.items():
                if i < definitions[name].required_lookback:
                    values_out[name] = None
                    reasons[name] = "GAP_WARMUP" if gap else "WARMUP"
                elif np.isnan(array[i]) and (
                    (definitions[name].name == "volume_change" and volumes[i - 1] == 0)
                    or (
                        definitions[name].name == "volume_ratio"
                        and not np.any(
                            volumes[
                                i - definitions[name].parameters["period"] + 1 : i + 1
                            ]
                        )
                    )
                ):
                    values_out[name] = None
                    reasons[name] = "ZERO_DENOMINATOR"
                elif not np.isfinite(array[i]):
                    raise FeatureError("unexpected non-finite feature calculation")
                else:
                    values_out[name] = float(array[i])
            row = FeatureRow(
                symbol=item.bar.symbol,
                timestamp=item.bar.timestamp,
                available_at=item.available_at,
                close=item.bar.close,
                values=values_out,
                unavailable=reasons,
                sufficient_history=not any(
                    v in {"WARMUP", "GAP_WARMUP"} for v in reasons.values()
                ),
                gap_before=gap and i == 0,
            )
            validate_row(row, config.features)
            rows.append(row)
        return rows

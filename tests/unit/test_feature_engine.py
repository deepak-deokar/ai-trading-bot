from dataclasses import replace
from datetime import timedelta
from math import log

import numpy as np
import pytest
from pydantic import ValidationError

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.snapshot import HistorySnapshot
from trading_bot.features.definitions import FeatureConfig, FeatureError, FeatureSpec
from trading_bot.features.engine import FeatureEngine
from trading_bot.features.registry import resolve
from trading_bot.features.validation import validate_row


def compute(inputs, config=None):
    request, snapshot, default = inputs
    return FeatureEngine(NSECalendar()).generate(
        snapshot, request, source="local", config=config or default
    )


def spec(name, **params):
    return FeatureConfig(
        name="test", features=(FeatureSpec(name=name, output="value", params=params),)
    )


@pytest.mark.parametrize(
    "name,params,index,expected",
    [
        ("return", {"period": 1}, 1, 0.1),
        ("return", {"period": 3}, 3, 0.2),
        ("log_return", {"period": 1}, 1, log(1.1)),
        ("sma", {"period": 3}, 2, 11),
        ("ema", {"period": 3}, 3, 11.5),
        ("momentum", {"period": 3}, 3, 2),
        # Closes [10,11,12,12,10]: Wilder gains/losses seed (1+1+0)/3,0.
        # Next smoothed gain=4/9, loss=2/3 -> RSI 40.
        ("rsi", {"period": 3}, 4, 40),
        ("true_range", {}, 1, 4),
        ("atr", {"period": 3}, 3, 4),
        ("range_pct", {}, 0, 0.4),
        ("volatility", {"period": 2}, 2, abs(0.1 - 1 / 11) / 2),
        ("volume_mean", {"period": 3}, 2, 20),
        ("volume_ratio", {"period": 3}, 2, 1.5),
        ("volume_change", {}, 1, 1),
        ("rolling_high", {"period": 3}, 2, 14),
        ("rolling_low", {"period": 3}, 2, 8),
        ("high_distance", {"period": 3}, 2, 12 / 14 - 1),
        ("low_distance", {"period": 3}, 2, 0.5),
        ("breakout_distance", {"period": 3}, 3, 12 / 14 - 1),
        ("sma_distance", {"period": 3}, 2, 12 / 11 - 1),
        ("ema_spread", {"fast": 2, "slow": 3}, 2, 0.5 / 12),
        ("minutes_since_open", {}, 1, 5),
        ("minutes_until_close", {}, 1, 370),
        ("session_progress", {}, 1, 5 / 375),
    ],
)
def test_independent_small_formulas(feature_inputs, name, params, index, expected):
    result = compute(
        feature_inputs(
            count=5, closes=[10, 11, 12, 12, 10], volumes=[10, 20, 30, 40, 50]
        ),
        spec(name, **params),
    )
    assert result.rows[index].values["value"] == pytest.approx(expected)


def test_baseline_warmup_and_metadata(feature_inputs):
    inputs = feature_inputs()
    result = compute(inputs)
    assert len(inputs[2].features) == 29
    assert result.rows[0].values["return_1"] is None
    assert result.rows[18].values["ema_20"] is None
    assert result.rows[19].values["ema_20"] == 109.5
    assert not result.rows[19].sufficient_history
    assert result.rows[20].sufficient_history
    assert result.rows[13].values["rsi_14"] is None
    assert result.rows[14].values["rsi_14"] == 100
    for definition in result.manifest["definitions"]:
        assert definition["version"] == "1" and definition["input_fields"]
        assert definition["description"] and definition["output_type"] == "float64"


@pytest.mark.parametrize(
    "closes,expected",
    [([10] * 5, 50), ([14, 13, 12, 11, 10], 0), ([10, 11, 12, 13, 14], 100)],
)
def test_rsi_degenerate_cases(feature_inputs, closes, expected):
    rows = compute(feature_inputs(count=5, closes=closes), spec("rsi", period=3)).rows
    assert rows[3].values["value"] == expected


def test_atr_gapped_prices_hand_reference(feature_inputs):
    # TRs at bars 1..3: 12, 4, 11; seed ATR2=8, next=9.5.
    rows = compute(
        feature_inputs(count=4, closes=[10, 20, 19, 10]), spec("atr", period=2)
    ).rows
    assert rows[2].values["value"] == 8
    assert rows[3].values["value"] == 9.5


def test_zero_volume_is_expected_unavailable(feature_inputs):
    result = compute(feature_inputs(count=30, volumes=[0] * 30))
    assert result.rows[25].values["volume_ratio"] is None
    assert result.rows[25].unavailable["volume_ratio"] == "ZERO_DENOMINATOR"
    assert result.rows[25].sufficient_history
    assert result.rows[25].values["volume_mean"] == 0


def test_no_future_leakage_and_input_mutation_changes_identity(feature_inputs):
    request, snapshot, config = feature_inputs()
    original = compute((request, snapshot, config))
    changed = list(snapshot.bars)
    for i in range(25, len(changed)):
        b = changed[i].bar
        b = b.model_copy(
            update={f: getattr(b, f) * 2 for f in ("open", "high", "low", "close")}
            | {"volume": 99999}
        )
        changed[i] = replace(changed[i], bar=b)
    result = compute((request, replace(snapshot, bars=tuple(changed)), config))
    assert result.rows[:25] == original.rows[:25]
    assert result.rows[25:] != original.rows[25:]
    assert result.feature_set_key != original.feature_set_key
    # Truncating at every early cutoff gives identical values, including seeds.
    for count in (1, 10, 15, 20, 25):
        cutoff = snapshot.bars[count - 1].available_at
        truncated = compute(
            (
                request.model_copy(update={"end": cutoff}),
                replace(snapshot, bars=snapshot.bars[:count]),
                config,
            )
        )
        assert truncated.rows == original.rows[:count]


def test_identity_order_parameters_and_exact_decimal_scale(feature_inputs):
    request, snapshot, config = feature_inputs(symbols=("TCS", "RELIANCE"))
    original = compute((request, snapshot, config))
    reordered = compute(
        (
            request.model_copy(update={"symbols": tuple(reversed(request.symbols))}),
            replace(snapshot, bars=tuple(reversed(snapshot.bars))),
            config.model_copy(update={"features": tuple(reversed(config.features))}),
        )
    )
    assert original.feature_set_key == reordered.feature_set_key
    new = config.model_copy(
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
    assert compute((request, snapshot, new)).feature_set_key != original.feature_set_key
    solo = compute(feature_inputs())
    assert [r.values for r in original.rows if r.symbol == "TCS"] == [
        r.values for r in solo.rows
    ]
    assert [r for r in original.rows if r.symbol == "RELIANCE"][0].values[
        "sma_10"
    ] is None


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-01-05T15:20:00+05:30", "2026-01-06T09:30:00+05:30"),
        ("2026-01-09T15:20:00+05:30", "2026-01-12T09:30:00+05:30"),
    ],
)
def test_normal_session_boundary_continues_and_context_resets(
    feature_inputs, start, end
):
    result = compute(feature_inputs(start=start, end=end))
    assert result.missing_bars == 0
    assert not any(r.gap_before for r in result.rows)
    assert result.rows[2].values["return_1"] is not None
    assert result.rows[2].values["minutes_since_open"] == 0
    assert result.rows[2].values["session_progress"] == 0
    assert result.rows[2].values["minutes_until_close"] == 375


def test_gap_resets_state_and_recovers(feature_inputs):
    result = compute(feature_inputs(count=60, missing=(25,)))
    assert result.missing_bars == 1
    after = result.rows[25]
    assert after.gap_before and not after.sufficient_history
    assert after.unavailable["return_1"] == "GAP_WARMUP"
    assert after.values["session_progress"] is not None
    assert result.rows[26].values["return_1"] is not None
    assert result.rows[44].values["ema_20"] == 135.5
    assert result.rows[45].sufficient_history


def test_leading_trailing_missing_slots(feature_inputs):
    result = compute(feature_inputs(count=40, missing=(0, 39)))
    assert result.missing_bars == 2 and result.rows[0].gap_before
    assert result.rows[0].unavailable["return_1"] == "GAP_WARMUP"


def test_timestamp_and_completion(feature_inputs):
    row = compute(feature_inputs()).rows[0]
    assert row.timestamp.isoformat() == "2026-01-05T03:45:00+00:00"
    assert row.available_at - row.timestamp == timedelta(minutes=5)


@pytest.mark.parametrize(
    "name,params",
    [
        ("unknown", {}),
        ("ema", {}),
        ("ema", {"period": 0}),
        ("ema", {"period": 501}),
        ("ema", {"period": 3, "extra": 1}),
        ("ema_spread", {"fast": 20, "slow": 10}),
    ],
)
def test_bad_registry_parameters(name, params):
    with pytest.raises(FeatureError):
        resolve(FeatureSpec(name=name, output="test", params=params))


@pytest.mark.parametrize("value", [True, 2.5, "14"])
def test_no_parameter_coercion(value):
    with pytest.raises(ValidationError):
        FeatureSpec(name="rsi", output="rsi", params={"period": value})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_output_rejected(feature_inputs, bad):
    row = compute(feature_inputs()).rows[0]
    unsafe = row.model_copy(update={"values": row.values | {"session_progress": bad}})
    with pytest.raises(FeatureError):
        validate_row(unsafe, feature_inputs()[2].features)


def test_impossible_session_value_and_unexplained_null(feature_inputs):
    inputs = feature_inputs()
    row = compute(inputs).rows[-1]
    for value in (2, None):
        with pytest.raises(FeatureError):
            validate_row(
                row.model_copy(
                    update={"values": row.values | {"session_progress": value}}
                ),
                inputs[2].features,
            )


@pytest.mark.parametrize(
    "kind",
    [
        "adjustment",
        "source",
        "availability",
        "duplicate",
        "missing_identity",
        "calendar",
    ],
)
def test_reject_unsafe_inputs(feature_inputs, kind):
    request, snapshot, config = feature_inputs()
    items = list(snapshot.bars)
    if kind == "adjustment":
        items[0] = replace(
            items[0],
            bar=items[0].bar.model_copy(update={"adjustment_type": "SPLIT_ADJUSTED"}),
        )
    if kind == "source":
        items[0] = replace(
            items[0], bar=items[0].bar.model_copy(update={"source": "groww"})
        )
    if kind == "availability":
        items[0] = replace(
            items[0], available_at=items[0].available_at + timedelta(minutes=5)
        )
    if kind == "duplicate":
        items.append(items[0])
    identities = snapshot.identities
    if kind == "missing_identity":
        identities = ()
    if kind == "calendar":
        identities = (
            identities[0].model_copy(
                update={
                    "manifest": identities[0].manifest
                    | {"calendar": {"version": "bad"}}
                }
            ),
        )
    with pytest.raises(FeatureError):
        compute((request, HistorySnapshot(tuple(items), identities), config))


def test_limits_empty_and_unexpected_nan(feature_inputs, monkeypatch):
    request, snapshot, config = feature_inputs()
    with pytest.raises(FeatureError, match="limit"):
        FeatureEngine(NSECalendar(), max_slots=10).generate(
            snapshot, request, source="local", config=config
        )
    with pytest.raises(FeatureError, match="no completed"):
        compute((request, replace(snapshot, bars=()), config))
    monkeypatch.setattr(
        "trading_bot.features.price.calculate",
        lambda s, c, h, low: np.full(len(c), np.nan),
    )
    with pytest.raises(FeatureError, match="non-finite"):
        compute((request, snapshot, config))


def test_unexpected_volume_nan_is_not_a_zero_denominator(feature_inputs, monkeypatch):
    monkeypatch.setattr(
        "trading_bot.features.volume.calculate",
        lambda spec, values: np.full(len(values), np.nan),
    )
    with pytest.raises(FeatureError, match="non-finite"):
        compute(feature_inputs())


def test_special_session_uses_scheduled_hours(tmp_path, feature_inputs):
    from datetime import datetime
    from pathlib import Path
    from uuid import uuid4

    import yaml

    from trading_bot.data.identity import dataset_identity
    from trading_bot.data.snapshot import SnapshotBar

    policy = yaml.safe_load(Path("config/calendar_nse.yaml").read_text())
    policy["sessions"].append(
        {
            "date": datetime(2026, 1, 5).date(),
            "open": "18:00",
            "close": "19:00",
            "source": "fixture:test-only",
        }
    )
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(policy))
    calendar = NSECalendar(path)
    request, snapshot, config = feature_inputs(count=1)
    start = datetime.fromisoformat("2026-01-05T18:00:00+05:30")
    request = request.model_copy(
        update={"start": start, "end": start + timedelta(hours=1)}
    )
    run = uuid4()
    identity = dataset_identity(
        request, "local", run, calendar.provenance(request.start, request.end), {}
    )
    bars = tuple(
        SnapshotBar(
            snapshot.bars[0].bar.model_copy(update={"timestamp": t}),
            available,
            snapshot.bars[0].instrument_id,
            run,
        )
        for t, available in calendar.expected_bars(
            request.start, request.end, request.timeframe
        ).items()
    )
    result = FeatureEngine(calendar).generate(
        HistorySnapshot(bars, (identity,)), request, source="local", config=config
    )
    assert result.rows[0].values["minutes_until_close"] == 60
    assert result.rows[-1].values["session_progress"] == 55 / 60


def test_float_conversion_does_not_change_exact_close(feature_inputs):
    from decimal import Decimal

    value = Decimal("1234567890.1234567890")
    result = compute(feature_inputs(count=30, closes=[value] * 30))
    assert result.rows[-1].close == value
    assert isinstance(result.rows[-1].values["sma_20"], float)


@pytest.mark.parametrize("timeframe,count", [("1hour", 7), ("1day", 1)])
def test_session_clipped_availability_other_timeframes(
    feature_inputs, timeframe, count
):
    from datetime import datetime

    from trading_bot.data.identity import dataset_identity
    from trading_bot.data.snapshot import SnapshotBar
    from trading_bot.domain.market import Timeframe
    from trading_bot.domain.models import Bar

    request, snapshot, config = feature_inputs(count=1)
    end = datetime.fromisoformat("2026-01-05T15:30:00+05:30")
    request = request.model_copy(update={"timeframe": Timeframe(timeframe), "end": end})
    calendar = NSECalendar()
    original = snapshot.bars[0]
    identity = dataset_identity(
        request,
        "local",
        original.ingestion_run_id,
        calendar.provenance(request.start, end),
        {},
    )
    bars = tuple(
        SnapshotBar(
            Bar.model_validate(
                original.bar.model_dump()
                | {
                    "timestamp": t,
                    "timeframe": timeframe,
                    "interval_seconds": int(request.timeframe.duration.total_seconds()),
                }
            ),
            available,
            original.instrument_id,
            original.ingestion_run_id,
        )
        for t, available in calendar.expected_bars(
            request.start, end, request.timeframe
        ).items()
    )
    result = FeatureEngine(calendar).generate(
        HistorySnapshot(bars, (identity,)), request, source="local", config=config
    )
    assert len(result.rows) == count and result.rows[-1].available_at == end
    assert result.missing_bars == 0
    if timeframe == "1hour":
        assert result.rows[-1].available_at - result.rows[-1].timestamp == timedelta(
            minutes=15
        )


def test_summary_log_fields_are_allowlisted():
    import json
    import logging

    from trading_bot.monitoring.logging import JsonFormatter

    record = logging.LogRecord(
        "trading_bot.features",
        logging.INFO,
        "",
        0,
        "Feature generation completed",
        (),
        None,
    )
    values = dict(
        feature_run_id="run",
        dataset_key="dataset",
        feature_set_key="features",
        symbols=["RELIANCE"],
        timeframe="5minute",
        range=["start", "end"],
        features_requested=29,
        bars_loaded=60,
        rows_generated=60,
        warmup_rows=20,
        gap_affected_rows=0,
        invalid_outputs=0,
        duration=0.1,
    )
    for key, value in values.items():
        setattr(record, key, value)
    record.private_token = "must-not-appear"
    output = JsonFormatter().format(record)
    parsed = json.loads(output)
    assert all(parsed[k] == v for k, v in values.items())
    assert "must-not-appear" not in output


def test_audit_all_baseline_outputs_and_explicit_warmups(feature_inputs):
    """Linear closes/volumes permit independent expected values for every alias."""
    from statistics import pstdev

    result = compute(feature_inputs())
    expected = {
        "return_1": 1 / 119,
        "return_3": 3 / 117,
        "return_5": 5 / 115,
        "log_return_1": log(120 / 119),
        "sma_10": 115.5,
        "sma_20": 110.5,
        "ema_10": 115.5,
        "ema_20": 110.5,
        "sma_20_distance": 120 / 110.5 - 1,
        "ema_spread": 5 / 120,
        "momentum_3": 3,
        "momentum_5": 5,
        "momentum_10": 10,
        "rsi_14": 100,
        "rolling_volatility": pstdev(1 / previous for previous in range(100, 120)),
        "atr_14": 4,
        "range_pct": 4 / 120,
        "true_range": 4,
        "volume_change": 1 / 119,
        "volume_mean": 110.5,
        "volume_ratio": 120 / 110.5,
        "rolling_high": 122,
        "rolling_low": 99,
        "high_distance": 120 / 122 - 1,
        "low_distance": 120 / 99 - 1,
        "breakout_distance": 120 / 121 - 1,
        "minutes_since_open": 100,
        "minutes_until_close": 275,
        "session_progress": 100 / 375,
    }
    assert result.rows[20].values == pytest.approx(expected)
    for name, first_valid in (("sma_20", 19), ("rsi_14", 14), ("atr_14", 14)):
        for row in result.rows[:first_valid]:
            assert row.values[name] is None
            assert row.unavailable[name] == "WARMUP"
            assert not row.sufficient_history
        assert result.rows[first_valid].values[name] is not None
        assert name not in result.rows[first_valid].unavailable


def test_audit_every_symbol_matches_its_standalone_series(feature_inputs):
    """All outputs match independent computation, including recursive indicators."""
    request, snapshot, config = feature_inputs(symbols=("RELIANCE", "TCS", "INFY"))
    combined = compute((request, snapshot, config))
    for symbol in request.symbols:
        independent = compute(
            (
                request.model_copy(update={"symbols": (symbol,)}),
                replace(
                    snapshot,
                    bars=tuple(x for x in snapshot.bars if x.bar.symbol == symbol),
                ),
                config,
            )
        )
        assert independent.rows == tuple(r for r in combined.rows if r.symbol == symbol)

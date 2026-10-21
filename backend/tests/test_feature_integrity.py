"""Causal prefix invariance, availability propagation, gaps and cross-security isolation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest
from feature_fixtures import observations
from sentientalpha.features.contracts import FeatureError, FeatureSpec, GenerationRequest
from sentientalpha.features.engine import calculate
from sentientalpha.features.registry import CATALOG, Registry
from sentientalpha.features.timing import execution, instant, readiness


def request_for(items, features, tickers=None):
    return GenerationRequest(
        tickers=tickers or ["AAA"],
        start=items[0].bar.session_date,
        end=items[-1].bar.session_date,
        features=features,
    )


@pytest.mark.parametrize("definition", CATALOG, ids=lambda item: item.name)
def test_every_feature_is_prefix_invariant(definition):
    full_a = observations(count=340)
    full_b = observations(
        "BBB", count=340, close=[90 + i * 0.08 + np.sin(i / 7) for i in range(340)]
    )
    full_spy = observations(
        "SPY", count=340, close=[110 + i * 0.05 + np.cos(i / 13) for i in range(340)]
    )
    specs = [FeatureSpec(name=definition.name)]
    resolved = Registry().resolve(specs)
    prefix_sources = {"AAA": full_a[:230], "BBB": full_b[:230], "SPY": full_spy[:230]}
    before = calculate(prefix_sources, request_for(full_a[:230], specs, ["AAA", "BBB"]), resolved)
    after = calculate(
        {"AAA": full_a, "BBB": full_b, "SPY": full_spy},
        request_for(full_a, specs, ["AAA", "BBB"]),
        resolved,
    )
    later = {(row["ticker"], row["session_date"]): row for row in after.rows}
    for row in before.rows:
        old = later[row["ticker"], row["session_date"]]
        assert old["values"] == row["values"]
        assert old["reasons"] == row["reasons"]
        assert old["timing"] == row["timing"]


def test_extended_fixture_warms_up_sma_200_and_retains_warmup_nulls():
    data = observations(count=320)
    specs = [FeatureSpec(name="sma", parameters={"window": 200})]
    result = calculate({"AAA": data}, request_for(data, specs), Registry().resolve(specs))
    name = result.columns[0]
    assert all(row["values"][name] is None for row in result.rows[:199])
    assert result.rows[199]["values"][name] == pytest.approx(
        np.mean([float(x.bar.close) for x in data[:200]])
    )


def test_recursive_revision_clock_differs_from_short_window_clock():
    data = observations(count=80)
    late = datetime(2026, 6, 1, tzinfo=UTC)
    data[0] = replace(
        data[0],
        bar=replace(data[0].bar, available_at=late),
        ingested_at=late + timedelta(seconds=1),
    )
    specs = [
        FeatureSpec(name="sma", parameters={"window": 5}),
        FeatureSpec(name="ema", parameters={"window": 5}),
    ]
    result = calculate({"AAA": data}, request_for(data, specs), Registry().resolve(specs))
    row = result.rows[-1]
    assert instant(row["timing"]["ema__window_5"][0]) == late
    assert instant(row["timing"]["sma__window_5"][0]) == data[-1].bar.available_at
    assert row["timing"]["ema__window_5"][2] == 0
    assert row["timing"]["sma__window_5"][2] == len(data) - 5


def test_rank_availability_uses_all_cohort_members():
    a, b = observations(count=30), observations("BBB", count=30)
    late = datetime(2026, 5, 1, tzinfo=UTC)
    b[-1] = replace(
        b[-1], bar=replace(b[-1].bar, available_at=late), ingested_at=late + timedelta(seconds=1)
    )
    specs = [FeatureSpec(name="cross_sectional_momentum_rank", parameters={"window": 5})]
    result = calculate(
        {"AAA": a, "BBB": b}, request_for(a, specs, ["AAA", "BBB"]), Registry().resolve(specs)
    )
    for row in result.rows:
        if row["session_date"] == a[-1].bar.session_date:
            assert instant(row["timing"][result.columns[0]][0]) == late


def test_no_cross_asset_contamination_in_local_indicators():
    a, b = observations(count=80), observations("BBB", count=80)
    specs = [FeatureSpec(name="ema"), FeatureSpec(name="rsi"), FeatureSpec(name="obv")]
    req = request_for(a, specs, ["AAA", "BBB"])
    base = calculate({"AAA": a, "BBB": b}, req, Registry().resolve(specs))
    changed = [
        replace(
            item,
            bar=replace(
                item.bar,
                close=item.bar.close * 5,
                open=item.bar.open * 5,
                high=item.bar.high * 5,
                low=item.bar.low * 5,
            ),
        )
        for item in b
    ]
    new = calculate({"AAA": a, "BBB": changed}, req, Registry().resolve(specs))
    assert [row["values"] for row in base.rows if row["ticker"] == "AAA"] == [
        row["values"] for row in new.rows if row["ticker"] == "AAA"
    ]


def test_gap_nulls_recursive_state_and_prevents_momentum_bridging():
    full = observations(count=40)
    data = full[:20] + full[21:]
    specs = [
        FeatureSpec(name="ema", parameters={"window": 5}),
        FeatureSpec(name="trailing_return", parameters={"window": 5}),
    ]
    result = calculate({"AAA": data}, request_for(full, specs), Registry().resolve(specs))
    assert result.rows[20]["values"]["ema__window_5"] is None
    assert result.rows[24]["values"]["ema__window_5"] is None
    assert result.rows[25]["values"]["ema__window_5"] is not None
    assert result.rows[25]["values"]["trailing_return__window_5"] is None
    assert result.rows[26]["values"]["trailing_return__window_5"] is not None
    req = request_for(full, specs).model_copy(update={"gap_policy": "reject"})
    with pytest.raises(FeatureError, match="Missing"):
        calculate({"AAA": data}, req, Registry().resolve(specs))


def test_unsorted_inputs_sort_but_duplicate_sessions_fail():
    data = observations(count=30)
    specs = [FeatureSpec(name="sma", parameters={"window": 5})]
    req = request_for(data, specs)
    left = calculate({"AAA": data}, req, Registry().resolve(specs))
    right = calculate({"AAA": list(reversed(data))}, req, Registry().resolve(specs))
    assert left.rows == right.rows
    with pytest.raises(FeatureError, match="revisions"):
        calculate({"AAA": data + [data[0]]}, req, Registry().resolve(specs))


def test_missing_benchmark_is_never_zero_beta():
    data = observations(count=30)
    specs = [FeatureSpec(name="rolling_beta", parameters={"window": 5})]
    result = calculate({"AAA": data}, request_for(data, specs), Registry().resolve(specs))
    assert result.rows[-1]["values"][result.columns[0]] is None
    assert result.rows[-1]["reasons"][result.columns[0]] == "missing_benchmark"


def test_no_same_close_execution_or_duplicated_value_shift():
    data = observations(count=10)
    specs = [FeatureSpec(name="return")]
    result = calculate({"AAA": data}, request_for(data, specs), Registry().resolve(specs))
    row = result.rows[-1]
    assert row["values"]["return"] == pytest.approx(
        float(data[-1].bar.close / data[-2].bar.close - 1)
    )
    available, ingested, _ = row["timing"]["return"]
    ready = readiness(row["market_at"], available, 1)
    filled_after = execution("weekday", ready, ingested, datetime(2026, 1, 1, tzinfo=UTC))
    assert ready >= instant(available) and ready > row["market_at"]
    assert filled_after > ready and filled_after > instant(ingested)


def test_raw_and_adjusted_values_are_not_mixed():
    data = observations(count=20)
    with_adjusted = [
        replace(
            item, bar=replace(item.bar, adjusted_close=Decimal("1"), adjustment_status="supplied")
        )
        for item in data
    ]
    specs = [FeatureSpec(name="sma", parameters={"window": 5}), FeatureSpec(name="return")]
    req = request_for(data, specs)
    before = calculate({"AAA": data}, req, Registry().resolve(specs))
    after = calculate({"AAA": with_adjusted}, req, Registry().resolve(specs))
    assert [row["values"] for row in before.rows] == [row["values"] for row in after.rows]
    with pytest.raises(ValueError):
        GenerationRequest(tickers=["AAA"], start=req.start, end=req.end, price_basis="adjusted")


@pytest.mark.parametrize(
    "parameters",
    [{"window": 0}, {"window": 505}, {"window": 5.0}, {"window": float("nan")}, {"wrong": 5}],
)
def test_invalid_parameters_rejected(parameters):
    with pytest.raises((FeatureError, ValueError)):
        Registry().resolve([FeatureSpec(name="sma", parameters=parameters)])


def test_future_labels_cannot_be_selected_as_features():
    for name in ["future_return", "target", "next_day_direction"]:
        with pytest.raises(FeatureError, match="labels"):
            Registry().resolve([FeatureSpec(name=name)])


def test_point_in_time_snapshot_rejects_future_available_inputs():
    data = observations(count=30)
    specs = [FeatureSpec(name="sma")]
    cutoff = datetime(2025, 1, 1, tzinfo=UTC)
    req = request_for(data, specs).model_copy(update={"as_of": cutoff})
    with pytest.raises(FeatureError, match="visible"):
        calculate({"AAA": data}, req, Registry().resolve(specs))


def test_benchmark_gap_cannot_be_filled_or_bridged():
    own = observations(count=50)
    benchmark = observations("SPY", count=50)
    specs = [
        FeatureSpec(name="relative_strength", parameters={"window": 5}),
        FeatureSpec(name="rolling_beta", parameters={"window": 5}),
    ]
    result = calculate(
        {"AAA": own, "SPY": benchmark[:30] + benchmark[31:]},
        request_for(own, specs),
        Registry().resolve(specs),
    )
    assert all(value is None for row in result.rows[30:36] for value in row["values"].values())
    assert all(value is not None for value in result.rows[36]["values"].values())


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_source_prices_rejected_before_feature_calculation(value):
    from dataclasses import replace
    from decimal import Decimal

    with pytest.raises(ValueError):
        replace(observations(count=1)[0].bar, close=Decimal(str(value)))


def test_flagged_and_gap_rejection_require_explicit_policy():
    from dataclasses import replace

    own = observations(count=30)
    specs = [FeatureSpec(name="sma", parameters={"window": 5})]
    flagged = [replace(item, quality_flags=("unexplained_jump",)) for item in own]
    req = request_for(own, specs)
    with pytest.raises(FeatureError, match="quality flags"):
        calculate({"AAA": flagged}, req, Registry().resolve(specs))
    allowed = calculate(
        {"AAA": flagged},
        req.model_copy(update={"quality_policy": "allow_flagged"}),
        Registry().resolve(specs),
    )
    assert allowed.diagnostics["source_quality_flags"]["unexplained_jump"] == 30
    with pytest.raises(FeatureError, match="Missing trading sessions"):
        calculate(
            {"AAA": own[:20] + own[21:]},
            req.model_copy(update={"gap_policy": "reject"}),
            Registry().resolve(specs),
        )

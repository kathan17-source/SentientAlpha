"""Explicit synthetic statistical fixtures; no genuine sentiment-alpha evidence."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest
from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.optimization.contracts import (
    Estimator,
    Objective,
    OptimizationRequest,
    ResearchRequest,
    Sentiment,
)
from sentientalpha.optimization.estimation import OptimizationError, Panel, ReturnRow
from sentientalpha.optimization.inputs import Inputs
from sentientalpha.optimization.research import compare, optimize
from sentientalpha.optimization.sentiment import SentimentCell, adjustment, fit

DATASET = "a" * 36
COLUMN = "sent_mean__min_articles_1__window_1"
CUTOFF = datetime(2026, 10, 14, tzinfo=UTC)


def fixture():
    days = sessions_in_range("weekday", date(2024, 1, 2), date(2024, 6, 28))
    bars = []
    cells = []
    rows = []
    previous_close = 100.0
    for i, day in enumerate(days):
        signal = ((i % 5) - 2) / 3
        prior = (((i - 1) % 5) - 2) / 3
        closing = 100 * (1 + 0.001 - 0.002 * prior)
        available = session_close("weekday", day) + timedelta(seconds=1)
        bars.append(
            Bar(
                "AAA",
                day,
                Decimal(100),
                Decimal(str(closing)),
                100000,
                available,
                CUTOFF,
                "synthetic-fixture-" + str(day),
            )
        )
        cells.append(
            SentimentCell("AAA", day, signal, available, "complete", None, DATASET, COLUMN)
        )
        rows.append(ReturnRow(day, (closing / previous_close - 1,), (available,)))
        previous_close = closing
    spec = Sentiment(
        dataset_id=DATASET,
        column=COLUMN,
        train_start=days[0],
        train_end=date(2024, 3, 29),
        minimum_samples=30,
        provenance="synthetic_fixture",
    )
    cfg = OptimizationRequest(
        price_dataset_id="b" * 36,
        tickers=["AAA"],
        history_start=days[0],
        estimation_end=date(2024, 4, 1),
        decision_at=datetime(2024, 4, 2, tzinfo=UTC),
        source_as_of=CUTOFF,
        information_policy="research_replay",
        estimator=Estimator(lookback=60, minimum_observations=10),
        objective=Objective(method="mean_variance"),
        sentiment=spec,
    )
    inputs = Inputs(
        Panel(("AAA",), tuple(rows), "weekday"),
        Snapshot(tuple(bars)),
        tuple(cells),
        {
            "provider": "synthetic",
            "warnings": ["Mathematical synthetic fixture, not market news or investment evidence"],
        },
    )
    return cfg, inputs


def test_negative_lambda_training_reference_and_annual_units():
    cfg, inputs = fixture()
    model = fit(
        cfg.sentiment,
        inputs.sentiments,
        inputs.prices,
        "weekday",
        cfg.decision_at,
        "research_replay",
    )
    samples = [
        s.value
        for s in inputs.sentiments
        if cfg.sentiment.train_start <= s.day < cfg.sentiment.train_end
    ]
    expected = -0.002 * np.std(samples, ddof=1)
    assert model["lambda_daily"] == pytest.approx(expected, abs=1e-14)
    assert model["lambda_annual"] == pytest.approx(expected * 252)
    assert model["samples"] == len(samples) and model["lambda_daily"] < 0
    delta, details = adjustment(
        cfg.sentiment, model, inputs.sentiments, ("AAA",), cfg.decision_at, cfg.estimation_end
    )
    s = next(s for s in inputs.sentiments if s.day == cfg.estimation_end)
    z = (s.value - np.mean(samples)) / np.std(samples, ddof=1)
    assert delta[0] == pytest.approx(z * expected * 252)
    assert details["AAA"]["coverage"] == "complete"


@pytest.mark.parametrize("change", ["future_prices", "future_sentiment", "late_training_label"])
def test_future_evaluation_and_late_labels_cannot_fit_lambda(change):
    cfg, inputs = fixture()
    model = fit(
        cfg.sentiment,
        inputs.sentiments,
        inputs.prices,
        "weekday",
        cfg.decision_at,
        "research_replay",
    )
    if change == "future_prices":
        prices = replace(
            inputs.prices,
            bars=tuple(
                replace(b, close=Decimal(999)) if b.day > cfg.sentiment.train_end else b
                for b in inputs.prices.bars
            ),
        )
        changed = fit(
            cfg.sentiment, inputs.sentiments, prices, "weekday", cfg.decision_at, "research_replay"
        )
        assert changed == model
    elif change == "future_sentiment":
        cells = tuple(
            replace(s, value=999) if s.day > cfg.sentiment.train_end else s
            for s in inputs.sentiments
        )
        changed = fit(
            cfg.sentiment, cells, inputs.prices, "weekday", cfg.decision_at, "research_replay"
        )
        assert changed == model
    else:
        prices = replace(
            inputs.prices, bars=tuple(replace(b, available=CUTOFF) for b in inputs.prices.bars)
        )
        with pytest.raises(OptimizationError, match="Insufficient"):
            fit(
                cfg.sentiment,
                inputs.sentiments,
                prices,
                "weekday",
                cfg.decision_at,
                "research_replay",
            )


@pytest.mark.parametrize(
    "state,reason",
    [
        ("missing_provider_coverage", "missing_provider_coverage"),
        ("complete", "no_news_observed"),
        ("complete", "inference_failure_or_unsupported_text"),
        ("partial_observed", None),
    ],
)
def test_missing_not_zero_and_coverage_distinctions(state, reason):
    cfg, inputs = fixture()
    cells = tuple(
        replace(s, value=None if reason else s.value, coverage=state, reason=reason)
        for s in inputs.sentiments
    )
    with pytest.raises(OptimizationError, match="Insufficient"):
        fit(cfg.sentiment, cells, inputs.prices, "weekday", cfg.decision_at, "research_replay")
    assert cells[0].reason == reason


def test_neutral_is_valid_but_constant_signal_has_no_estimable_slope():
    cfg, inputs = fixture()
    neutral = tuple(replace(s, value=0) for s in inputs.sentiments)
    with pytest.raises(OptimizationError, match="Constant"):
        fit(cfg.sentiment, neutral, inputs.prices, "weekday", cfg.decision_at, "research_replay")


def test_missing_prediction_can_use_only_explicit_price_only_fallback():
    cfg, inputs = fixture()
    missing = replace(inputs, sentiments=())
    unavailable = optimize(cfg, missing)
    assert unavailable["status"] == "insufficient_sentiment" and unavailable["weights"] is None
    cfg = cfg.model_copy(
        update={"sentiment": cfg.sentiment.model_copy(update={"fallback": "price_only"})}
    )
    fallback = optimize(cfg, missing)
    price = optimize(cfg.model_copy(update={"sentiment": None}), missing)
    assert fallback["status"] == "price_only_fallback" and fallback["weights"] == price["weights"]
    assert fallback["sentiment"]["status"] == "unavailable"


def test_after_hours_or_revised_signal_cannot_retroactively_enter_training():
    cfg, inputs = fixture()
    late = tuple(replace(s, ready=CUTOFF) for s in inputs.sentiments)
    with pytest.raises(OptimizationError, match="Insufficient"):
        fit(cfg.sentiment, late, inputs.prices, "weekday", cfg.decision_at, "research_replay")
    before = fit(
        cfg.sentiment,
        inputs.sentiments,
        inputs.prices,
        "weekday",
        cfg.decision_at,
        "research_replay",
    )
    # A later correction is a distinct frozen snapshot, never an in-place update.
    revised = inputs.sentiments + (
        replace(inputs.sentiments[0], value=50, ready=CUTOFF, dataset_id="c" * 36),
    )
    after = fit(
        cfg.sentiment, revised, inputs.prices, "weekday", cfg.decision_at, "research_replay"
    )
    assert before == after


def test_heldout_sentiment_changes_cannot_change_earlier_allocation():
    cfg, inputs = fixture()
    original = optimize(cfg, inputs)
    changed = replace(
        inputs,
        sentiments=tuple(
            replace(s, value=50) if s.day > cfg.estimation_end else s for s in inputs.sentiments
        ),
    )
    result = optimize(cfg, changed)
    assert (
        result["weights"] == original["weights"]
        and result["expected_returns_used"] == original["expected_returns_used"]
    )


def test_ablation_comparison_infrastructure_keeps_all_variants_and_ledger():
    cfg, inputs = fixture()
    b = BacktestRequest(
        tickers=["AAA"],
        start=date(2024, 4, 3),
        end=date(2024, 6, 28),
        source_as_of=CUTOFF,
        information_policy="research_replay",
    )
    req = ResearchRequest(
        optimization=cfg,
        backtest=b,
        methods=["mean_variance"],
        include_sentiment=True,
        sentiment_ablations=[cfg.sentiment.model_copy(update={"fallback": "price_only"})],
    )
    result = compare(req, inputs)
    assert [m["method"] for m in result["methods"]] == [
        "mean_variance",
        "sentiment_adjusted",
        "ablation:" + COLUMN,
    ]
    assert result["methods"][1]["sentiment_model"]["lambda_daily"] < 0
    assert all(m["fills"] > 0 for m in result["methods"])
    assert result["sentiment_claim"].startswith("No empirical alpha")

"""Synthetic statistical experiment ONLY: these signals are NOT news or FinBERT outputs."""

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.storage import build_id, digest
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.optimization.contracts import (
    Constraints,
    Estimator,
    Objective,
    OptimizationRequest,
    ResearchRequest,
    Sentiment,
)
from sentientalpha.optimization.estimation import Panel, ReturnRow
from sentientalpha.optimization.inputs import Inputs, freeze, thaw
from sentientalpha.optimization.research import compare
from sentientalpha.optimization.storage import numerical


def synthetic_inputs():
    days = sessions_in_range("weekday", date(2024, 1, 2), date(2024, 6, 28))
    names = ("TOYA", "TOYB")
    source_id = "a" * 36
    from sentientalpha.optimization.sentiment import SentimentCell

    bars = []
    cells = []
    rows = []
    previous = np.array([100.0, 100.0])
    values = np.array(
        [[0.7 * np.sin(i * 0.6), 0.6 * np.cos(i * 0.45)] for i in range(-1, len(days))]
    )
    columns = [
        "sent_mean__min_articles_1__window_1",
        "sent_momentum__min_articles_1__window_1",
        "sent_surprise__baseline_5__min_articles_1__min_history_3__window_1",
    ]
    for i, day in enumerate(days):
        signal = values[i + 1]
        returns = 0.0004 - 0.002 * values[i] + 0.0002 * np.sin(i * 2.37)
        close = previous * (1 + returns)
        at = session_close("weekday", day) + timedelta(seconds=1)
        for j, ticker in enumerate(names):
            bars.append(
                Bar(
                    ticker,
                    day,
                    Decimal(str(previous[j])),
                    Decimal(str(close[j])),
                    1000000,
                    at,
                    at,
                    f"STATISTICAL-FIXTURE-{ticker}-{day}",
                )
            )
            transformed = [
                signal[j],
                signal[j] - values[i, j],
                signal[j] - float(values[max(0, i - 4) : i + 1, j].mean()),
            ]
            for column, value in zip(columns, transformed, strict=True):
                cells.append(
                    SentimentCell(
                        ticker, day, float(value), at, "complete", None, source_id, column
                    )
                )
        rows.append(ReturnRow(day, tuple(returns.tolist()), (at, at)))
        previous = close
    inputs = Inputs(
        Panel(names, tuple(rows), "weekday"),
        Snapshot(tuple(bars)),
        tuple(cells),
        {
            "provider": "synthetic",
            "warnings": [
                "Pure synthetic statistical fixture. Signals are fabricated test "
                "variables, NOT observed news or FinBERT outputs; no investment "
                "evidence."
            ],
            "fixture_only": True,
        },
    )
    configs = [
        Sentiment(
            dataset_id=source_id,
            column=c,
            train_start=days[0],
            train_end=date(2024, 3, 29),
            minimum_samples=30,
            provenance="synthetic_fixture",
        )
        for c in columns
    ]
    cfg = OptimizationRequest(
        price_dataset_id="b" * 36,
        tickers=list(names),
        history_start=days[0],
        estimation_end=date(2024, 4, 1),
        decision_at=datetime(2024, 4, 2, tzinfo=UTC),
        source_as_of=datetime(2024, 7, 1, tzinfo=UTC),
        information_policy="research_replay",
        sentiment=configs[0],
        estimator=Estimator(lookback=60, minimum_observations=20),
        objective=Objective(method="mean_variance"),
        constraints=Constraints(cash_maximum=1, concentration=0.8),
    )
    b = BacktestRequest(
        tickers=list(names),
        start=date(2024, 4, 3),
        end=date(2024, 6, 28),
        source_as_of=cfg.source_as_of,
        information_policy="research_replay",
    )
    request = ResearchRequest(
        optimization=cfg,
        backtest=b,
        methods=["mean_variance"],
        include_sentiment=True,
        sentiment_ablations=configs[1:],
    )
    return request, inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    args = parser.parse_args()
    request, inputs = synthetic_inputs()
    result = compare(request, inputs)
    frozen = freeze(inputs)
    args.inputs.write_text(
        json.dumps(
            {
                "configuration": request.model_dump(mode="json"),
                "inputs": frozen,
                "input_hash": digest(frozen),
                "build_id": build_id(),
                "provenance": "PURE_SYNTHETIC_STATISTICAL_FIXTURE_NO_MARKET_OR_NEWS_EVIDENCE",
            },
            indent=2,
        )
        + "\n"
    )
    saved = json.loads(args.inputs.read_text())
    repeated = compare(
        ResearchRequest.model_validate(saved["configuration"]), thaw(saved["inputs"])
    )
    assert digest(numerical(result)) == digest(numerical(repeated))
    for before, after in zip(result["_backtests"], repeated["_backtests"], strict=True):
        for kind in ("orders", "fills", "equity", "actions"):
            assert before["result"][kind] == after["result"][kind]
    methods = []
    for m in result["methods"]:
        model = m["sentiment_model"]
        forecast_errors = []
        base_errors = []
        direction = []
        if model:
            source = {(b.ticker, b.day): b for b in inputs.prices.bars}
            days = sessions_in_range("weekday", request.backtest.start, request.backtest.end)
            for decision in m["decisions"]:
                d = date.fromisoformat(decision["day"])
                later = next((t for t in days if t > d), None)
                if later is None or not decision["decision"].get("weights"):
                    continue
                for j, ticker in enumerate(inputs.panel.tickers):
                    b = source[(ticker, later)]
                    realized = float(b.close / b.opening - 1)
                    predicted = decision["decision"]["expected_returns_used"][j] / 252
                    base = decision["decision"]["expected_returns_base"][j] / 252
                    forecast_errors.append((realized - predicted) ** 2)
                    base_errors.append((realized - base) ** 2)
                    direction.append(float(np.sign(predicted) == np.sign(realized)))
        methods.append(
            {
                "method": m["method"],
                "status": m["status"],
                "lambda_daily": model["lambda_daily"] if model else None,
                "samples": model["samples"] if model else None,
                "synthetic_OOS_forecast_quality": {
                    "targets": len(forecast_errors),
                    "adjusted_mse": float(np.mean(forecast_errors)) if forecast_errors else None,
                    "price_only_mse_same_targets": float(np.mean(base_errors))
                    if base_errors
                    else None,
                    "direction_accuracy": float(np.mean(direction)) if direction else None,
                    "warning": (
                        "Tiny generated sample; no empirical significance or market "
                        "prediction claim"
                    ),
                },
                "metrics": {
                    k: v
                    for k, v in m["metrics"].items()
                    if k not in {"daily_returns", "monthly_returns", "drawdown", "rolling"}
                },
                "decision_statuses": m["decision_statuses"],
                "mean_realized_concentration_hhi": m[
                    "mean_realized_concentration_hhi_including_cash"
                ],
            }
        )
    report = {
        "status": "VERIFIED_SYNTHETIC_STATISTICAL_INFRASTRUCTURE_ONLY",
        "warning": (
            "Generated mathematical test signals are NOT real sentiment, news,"
            " FinBERT predictions or evidence of alpha. All variants are "
            "reported without selecting a winner."
        ),
        "training_end": "2024-03-29",
        "evaluation_start": "2024-04-03",
        "evaluation_end": "2024-06-28",
        "methods": methods,
        "equivalent_saved_manifest_replay": True,
        "equivalent_M4_execution_artifacts": True,
        "input_hash": digest(frozen),
        "hypothesis_search_history": (
            "predeclared price-only, level, momentum and surprise; separate "
            "univariate coefficients; no combination or held-out tuning"
        ),
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

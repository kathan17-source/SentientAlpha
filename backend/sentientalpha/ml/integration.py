"""Forecast adapters reuse M4 execution and M5 estimation/constraint contracts."""

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast

import numpy as np

from sentientalpha.backtesting.contracts import Costs, Feature, Request, Snapshot, StrategySpec
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.strategies import Context
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.ml.contracts import MLException, ResearchRequest
from sentientalpha.ml.dataset import Dataset
from sentientalpha.optimization.estimation import Estimates


class ForecastStrategy:
    def __init__(self, forecasts: list[dict[str, Any]], tickers: list[str], threshold: float):
        self.forecasts, self.tickers, self.threshold = forecasts, tickers, threshold
        self.used: set[tuple[str, str]] = set()

    def targets(self, context: Context) -> dict[str, Decimal]:
        candidates = [
            p
            for p in self.forecasts
            if p["day"] == str(context.day)
            and datetime.fromisoformat(p["decision_at"]) <= context.at
        ]
        if not candidates:
            return {}
        if any(
            p["prediction_type"] != "direction" or p["target_convention"] != "next_open_to_close"
            for p in candidates
        ):
            raise MLException("Directional adapter requires eligible next-open direction forecasts")
        current = {p["ticker"]: p for p in candidates}
        # No stale signal carry: absent assets explicitly target cash at each eligible decision.
        return {
            t: Decimal(str(1 / len(self.tickers)))
            if t in current and current[t]["value"] >= self.threshold
            else Decimal(0)
            for t in self.tickers
        }


def economic(
    request: ResearchRequest, ds: Dataset, predictions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if request.target.task != "direction" or request.target.convention != "next_open_to_close":
        raise MLException("Economic adapter only supports next-open directional forecasts")
    outputs = []
    for i, w in enumerate(request.windows):
        forecasts = [p for p in predictions if p["fold"] == i]
        if not forecasts:
            outputs.append({"fold": i, "status": "insufficient_data"})
            continue
        # Retrospective mode deliberately models original bar publication; preserve acquisition
        # lineage in the parent snapshot and never claim verified execution.
        bars = tuple(
            replace(b, available=session_close(ds.calendar, b.day) + timedelta(seconds=1))
            if request.information_policy == "retrospective"
            else b
            for b in ds.prices.bars
        )
        features = tuple(
            Feature(
                p["ticker"],
                datetime.fromisoformat(p["decision_at"]).date() - timedelta(days=1)
                if ds.calendar == "weekday"
                else datetime.fromisoformat(p["day"]).date(),
                Decimal(str(p["value"])),
                datetime.fromisoformat(p["decision_at"]),
                datetime.fromisoformat(p["decision_at"]),
                p["model_hash"],
            )
            for p in forecasts
        )
        snapshot = Snapshot(bars, features)
        cfg = Request(
            tickers=request.tickers,
            provider="synthetic"
            if ds.metadata["datasets"][0]["provider"] == "synthetic"
            else "alphavantage",
            start=w.test_start,
            end=w.test_end,
            source_as_of=request.source_as_of,
            calendar=cast(Literal["weekday", "XNYS"], ds.calendar),
            information_policy="research_replay"
            if request.information_policy == "retrospective"
            else request.information_policy,
            strategy=StrategySpec(name="equal_weight", rebalance="daily"),
        )
        net = simulate(
            cfg, snapshot, ForecastStrategy(forecasts, request.tickers, request.threshold)
        )
        gross_cfg = cfg.model_copy(
            update={"costs": Costs(fixed=Decimal(0), slippage_bps=Decimal(0))}
        )
        gross = simulate(
            gross_cfg, snapshot, ForecastStrategy(forecasts, request.tickers, request.threshold)
        )
        benchmarks = {}
        for name in ("buy_hold", "equal_weight"):
            bcfg = cfg.model_copy(
                update={
                    "strategy": StrategySpec(
                        name=name, rebalance="once" if name == "buy_hold" else "monthly"
                    )
                }
            )
            benchmarks[name] = simulate(bcfg, Snapshot(bars))
        outputs.append(
            {
                "fold": i,
                "status": net["status"],
                "request": cfg.model_dump(mode="json"),
                "snapshot": snapshot,
                "net": net,
                "gross": gross,
                "benchmarks": benchmarks,
                "holding_policy": (
                    "Daily updated long/cash; horizon labels are predictive targets, "
                    "not isolated overlapping trade returns."
                ),
            }
        )
    return outputs


def forecast_estimates(
    base: Estimates,
    forecasts: list[dict[str, Any]],
    at: datetime,
    horizon: int,
    maximum_age_sessions: int = 1,
    sentiment_adjustment: bool = False,
) -> Estimates:
    if base.units != "annual" or horizon not in {1, 5, 10} or not 1 <= maximum_age_sessions <= 10:
        raise MLException("Incompatible estimator units, horizon or freshness bound")
    if sentiment_adjustment:
        raise MLException(
            "ML expected returns replace means; additional sentiment adjustment refused"
        )
    values = []
    for ticker in base.tickers:
        eligible = [
            p
            for p in forecasts
            if p["ticker"] == ticker and datetime.fromisoformat(p["decision_at"]) <= at
        ]
        if not eligible:
            raise MLException("Missing forecast", "insufficient_data")
        p = max(eligible, key=lambda item: item["decision_at"])
        if (
            p["prediction_type"] != "return"
            or p.get("units") != "simple_return_horizon"
            or p["horizon"] != horizon
            or p["target_convention"] != "next_open_to_close"
            or p.get("inference_status") != "completed"
            or len(
                sessions_in_range(
                    base.metadata.get("calendar", "weekday"),
                    datetime.fromisoformat(p["decision_at"]).date() + timedelta(days=1),
                    at.date(),
                )
            )
            > maximum_age_sessions
            or datetime.fromisoformat(p["training_cutoff"])
            >= datetime.fromisoformat(p["decision_at"])
            or not np.isfinite(p["value"])
            or p["value"] <= -1
        ):
            raise MLException("Incompatible, stale or incorrectly scaled expected-return forecast")
        # Explicit arithmetic horizon conversion, no probability-to-magnitude inference.
        values.append(float(p["value"]) * 252 / horizon)
    return Estimates(
        base.tickers,
        np.array(values),
        base.covariance.copy(),
        {
            **base.metadata,
            "mean_estimator": "ml_expected_return",
            "forecast_horizon": horizon,
            "conversion": "arithmetic annual proxy = horizon simple return * 252/h",
            "warning": (
                "Next-open drift and close-close covariance are a research approximation; "
                "calibration of magnitude unverified."
            ),
        },
    )

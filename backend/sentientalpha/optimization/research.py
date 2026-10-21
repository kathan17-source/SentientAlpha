"""Point-in-time optimization callback driving the existing M4 simulator and ledger."""

from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from time import monotonic
from typing import Any

import numpy as np

from sentientalpha.backtesting.analytics import analytics
from sentientalpha.backtesting.contracts import BacktestError, StrategySpec
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.evaluation import WalkRequest
from sentientalpha.backtesting.strategies import Context
from sentientalpha.features.timing import next_open
from sentientalpha.optimization.contracts import (
    FrontierRequest,
    OptimizationRequest,
    ResearchRequest,
    WalkResearch,
)
from sentientalpha.optimization.estimation import Estimates, OptimizationError, estimate
from sentientalpha.optimization.inputs import Inputs
from sentientalpha.optimization.sentiment import adjustment, fit
from sentientalpha.optimization.solver import residuals, solve


def optimize(
    request: OptimizationRequest, inputs: Inputs, model: dict[str, Any] | None = None
) -> dict[str, Any]:
    try:
        estimates = estimate(
            inputs.panel,
            request.decision_at,
            request.history_start,
            request.estimation_end,
            request.estimator,
        )
    except OptimizationError as exc:
        if exc.code != "insufficient_data":
            raise
        return {"status": "insufficient_data", "weights": None, "reason": str(exc)}
    base = estimates.mean.copy()
    sent: dict[str, Any] = {"status": "not_requested"}
    if request.sentiment:
        try:
            model = model or fit(
                request.sentiment,
                inputs.sentiments,
                inputs.prices,
                inputs.panel.calendar,
                request.decision_at,
                request.information_policy,
            )
            delta, details = adjustment(
                request.sentiment,
                model,
                inputs.sentiments,
                estimates.tickers,
                request.decision_at,
                request.estimation_end,
            )
            estimates = Estimates(
                estimates.tickers, base + delta, estimates.covariance, estimates.metadata
            )
            sent = {"status": "adjusted", "model": model, "signals": details}
        except OptimizationError as exc:
            sent = {"status": "unavailable", "reason": str(exc), "code": exc.code}
            if request.sentiment.fallback == "unavailable":
                return {
                    "status": "insufficient_sentiment",
                    "weights": None,
                    "sentiment": sent,
                    "estimation": estimates.metadata,
                }
    result = solve(estimates, request.constraints, request.objective, request.current_weights)
    result.update(
        asset_order=list(estimates.tickers),
        expected_returns_base=base.tolist(),
        expected_returns_used=estimates.mean.tolist(),
        covariance=estimates.covariance.tolist(),
        estimation=estimates.metadata,
        sentiment=sent,
        current_weights=request.current_weights,
        units="annual arithmetic return and annual covariance",
        warnings=result.get("warnings", [])
        + estimates.metadata["warnings"]
        + inputs.metadata["warnings"],
    )
    if sent["status"] == "unavailable" and result.get("weights") is not None:
        result["status"] = "price_only_fallback"
    if result.get("weights") is not None:
        result["explanation"] = {
            "method": request.objective.method,
            "binding_constraints": result["diagnostics"].get("binding_constraints", []),
            "weight_changes": {
                t: result["weights"][t] - request.current_weights.get(t, 0)
                for t in estimates.tickers
            },
            "risk_contribution_interpretation": (
                "Marginal covariance exposure times capital weight; a small "
                "capital weight can dominate risk. These are model attributions, "
                "not causal return claims."
            ),
            "sentiment_adjustment": sent.get("signals", {}),
            "estimated_costs_are_not_ledger_entries": True,
        }
    return result


def frontier(request: FrontierRequest, inputs: Inputs) -> dict[str, Any]:
    # Estimate once, then freeze exact common inputs for all frontier QPs.
    base = optimize(
        request.optimization.model_copy(
            update={
                "objective": request.optimization.objective.model_copy(
                    update={"method": "mean_variance"}
                )
            }
        ),
        inputs,
    )
    if "covariance" not in base:
        return {"status": base["status"], "points": [], "estimation": base}
    e = Estimates(
        tuple(base["asset_order"]),
        np.array(base["expected_returns_used"]),
        np.array(base["covariance"]),
        base["estimation"],
    )
    started = monotonic()
    points = []
    for gamma in request.risk_aversions:
        if monotonic() - started > request.optimization.objective.seconds:
            raise OptimizationError("Frontier cooperative time budget exceeded", "time_budget", 429)
        objective = request.optimization.objective.model_copy(
            update={"method": "mean_variance", "risk_aversion": gamma}
        )
        points.append(
            {
                "risk_aversion": gamma,
                **solve(
                    e,
                    request.optimization.constraints,
                    objective,
                    request.optimization.current_weights,
                ),
            }
        )
    return {
        "status": "completed",
        "points": points,
        "asset_order": list(e.tickers),
        "expected_returns": e.mean.tolist(),
        "covariance": e.covariance.tolist(),
        "estimation": e.metadata,
        "sentiment": base["sentiment"],
        "note": (
            "Each point is an independently solved feasible utility problem on"
            " the same estimates; costs/constraints may prevent a classical "
            "smooth frontier."
        ),
    }


class OptimizedStrategy:
    def __init__(self, request: ResearchRequest, inputs: Inputs, optimization: OptimizationRequest):
        self.request, self.inputs, self.config = request, inputs, optimization
        self.previous: date | None = None
        self.decisions: list[dict[str, Any]] = []
        self.model = None
        self.model_error = None
        if optimization.sentiment:
            try:
                self.model = fit(
                    optimization.sentiment,
                    inputs.sentiments,
                    inputs.prices,
                    inputs.panel.calendar,
                    optimization.decision_at,
                    optimization.information_policy,
                )
            except OptimizationError as exc:
                self.model_error = str(exc)

    def targets(self, context: Context) -> dict[str, Decimal]:
        day = context.day
        previous = self.previous
        due = (
            day in self.request.rebalance_dates
            if self.request.rebalance == "explicit"
            else previous is None
            or (
                (
                    day.year,
                    (day.month - 1) // 3 if self.request.rebalance == "quarterly" else day.month,
                )
                != (
                    previous.year,
                    (previous.month - 1) // 3
                    if self.request.rebalance == "quarterly"
                    else previous.month,
                )
            )
        )
        if not due:
            return {}
        if len(self.decisions) >= self.request.maximum_rebalances:
            raise OptimizationError("Rebalance budget exceeded", "workload_limit")
        self.previous = day
        prices = dict(context.prices)
        quantities = dict(context.quantities)
        value = context.cash + sum((q * prices[t] for t, q in quantities.items()), Decimal(0))
        current = {
            t: float(quantities.get(t, Decimal(0)) * prices[t] / value)
            for t in self.config.tickers
            if t in prices
        }
        config = self.config.model_copy(
            update={"decision_at": context.at, "estimation_end": day, "current_weights": current}
        )
        if (
            self.model_error
            and self.config.sentiment
            and self.config.sentiment.fallback == "unavailable"
        ):
            result: dict[str, Any] = {
                "status": "insufficient_sentiment",
                "weights": None,
                "reason": self.model_error,
            }
        else:
            result = optimize(config, self.inputs, self.model)
        if result.get("sentiment", {}).get("model"):
            self.model = result["sentiment"]["model"]
            result["sentiment"] = {
                **result["sentiment"],
                "model": {k: v for k, v in self.model.items() if k != "lineage"},
            }
        self.decisions.append({"at": context.at.isoformat(), "day": str(day), "decision": result})
        weights = result.get("weights")
        if weights is None:
            return {}
        return {
            t: Decimal(str(w)).quantize(Decimal("0.000000000001"), rounding=ROUND_FLOOR)
            for t, w in weights.items()
        }


def compare(request: ResearchRequest, inputs: Inputs) -> dict[str, Any]:
    if (
        inputs.panel.calendar != request.backtest.calendar
        or inputs.metadata["provider"] != request.backtest.provider
    ):
        raise OptimizationError("Return panel and execution calendar/provider differ")
    if inputs.panel.rows[-1].day < request.backtest.end:
        raise OptimizationError(
            "Frozen return snapshot does not cover evaluation range", "insufficient_data"
        )
    strategies: list[tuple[str, OptimizationRequest]] = [
        (
            method,
            request.optimization.model_copy(
                update={
                    "objective": request.optimization.objective.model_copy(
                        update={"method": method}
                    ),
                    "sentiment": None,
                }
            ),
        )
        for method in request.methods
    ]
    if request.include_sentiment:
        if request.optimization.sentiment is None:
            raise OptimizationError(
                "Sentiment comparison requires an explicit snapshot/training configuration"
            )
        strategies.append(("sentiment_adjusted", request.optimization))
    for spec in request.sentiment_ablations:
        strategies.append(
            ("ablation:" + spec.column, request.optimization.model_copy(update={"sentiment": spec}))
        )
    started = monotonic()
    results: list[dict[str, Any]] = []
    backtests: list[dict[str, Any]] = []
    for name, config in strategies:
        if monotonic() - started > request.backtest.seconds:
            raise OptimizationError(
                "Comparison cooperative time budget exceeded", "time_budget", 429
            )
        strategy = OptimizedStrategy(request, inputs, config)
        simulated = simulate(request.backtest, inputs.prices, strategy)
        # Attach auditable theoretical decisions to existing M4 artifacts; no
        # execution/accounting bypass.
        for order in simulated["orders"]:
            order["strategy"] = "optimization:" + name
        for item in strategy.decisions:
            decision = item["decision"]
            eligible_open = next_open(request.backtest.calendar, datetime.fromisoformat(item["at"]))
            after = next(
                (
                    r
                    for r in simulated["equity"]
                    if datetime.fromisoformat(r["at"]) >= eligible_open
                ),
                None,
            )
            item["first_subsequent_closing_at"] = after["at"] if after else None
            item["first_subsequent_closing_weights"] = (
                {t: p["weight"] for t, p in after["positions"].items()} if after else None
            )
            if after and decision.get("weights"):
                e = Estimates(
                    tuple(decision["asset_order"]),
                    np.array(decision["expected_returns_used"]),
                    np.array(decision["covariance"]),
                    decision["estimation"],
                )
                actual = np.array(
                    [after["positions"].get(t, {}).get("weight", 0) for t in e.tickers]
                )
                previous = np.array([decision["current_weights"].get(t, 0) for t in e.tickers])
                item["actual_constraint_slack_at_subsequent_close"] = residuals(
                    actual, e, config.constraints, previous, config.objective.target_return_annual
                )
        statuses = [d["decision"]["status"] for d in strategy.decisions]
        summary = {
            "method": name,
            "status": simulated["status"],
            "metrics": simulated["metrics"],
            "decisions": strategy.decisions,
            "decision_statuses": statuses,
            "sentiment_model": strategy.model,
            "fills": len(simulated["fills"]),
            "warnings": simulated["warnings"],
        }
        if not any(d["decision"].get("weights") is not None for d in strategy.decisions):
            summary["status"] = "unavailable"
        equity = simulated["equity"]
        if equity:
            summary["mean_realized_concentration_hhi_including_cash"] = float(
                np.mean(
                    [
                        sum(float(p["weight"]) ** 2 for p in r["positions"].values())
                        + (float(r["cash"]) / float(r["equity"])) ** 2
                        for r in equity
                    ]
                )
            )
        targets = [
            d["decision"]["weights"]
            for d in strategy.decisions
            if d["decision"].get("weights") is not None
        ]
        summary["mean_target_weight_change"] = (
            float(
                np.mean(
                    [
                        sum(abs(b[t] - a[t]) for t in a)
                        for a, b in zip(targets, targets[1:], strict=False)
                    ]
                )
            )
            if len(targets) > 1
            else None
        )
        results.append(summary)
        backtests.append(
            {
                "method": name,
                "request": request.backtest.model_dump(mode="json"),
                "result": simulated,
            }
        )
    spy: dict[str, Any] = {
        "status": "insufficient_data",
        "reason": "No compatible genuine SPY snapshot; no synthetic market proxy.",
    }
    if inputs.metadata["provider"] == "alphavantage" and any(
        b.ticker == "SPY" for b in inputs.prices.bars
    ):
        try:
            spy_config = request.backtest.model_copy(
                update={"tickers": ["SPY"], "strategy": StrategySpec(), "benchmarks": []}
            )
            simulation = simulate(spy_config, inputs.prices)
            spy = {
                "status": simulation["status"],
                "method": "SPY_buy_hold",
                "metrics": simulation["metrics"],
            }
            backtests.append(
                {
                    "method": "SPY_buy_hold",
                    "request": spy_config.model_dump(mode="json"),
                    "result": simulation,
                }
            )
        except BacktestError as exc:
            spy = {"status": "insufficient_data", "reason": str(exc), "code": exc.code}
    reference = next(
        (
            b
            for b in backtests
            if b["method"] == "SPY_buy_hold" and b["result"]["status"] == "completed"
        ),
        None,
    )
    reference = reference or next(
        (
            b
            for b in backtests
            if b["method"] == "equal_weight" and b["result"]["status"] == "completed"
        ),
        None,
    )
    if reference:
        for summary, bt in zip(results, backtests, strict=False):
            relative = analytics(
                bt["result"]["equity"],
                float(request.backtest.capital),
                bt["result"]["fills"],
                bt["result"]["closed_pnl"],
                reference["result"]["equity"],
            )
            for key in (
                "alpha",
                "beta",
                "tracking_error",
                "information_ratio",
                "excess_return",
                "rolling",
            ):
                if key in relative:
                    summary["metrics"][key] = relative[key]
            summary["metrics"]["relative_benchmark"] = reference["method"]
    return {
        "status": "completed"
        if any(r["status"] == "completed" for r in results)
        else "insufficient_data",
        "methods": results,
        "_backtests": backtests,
        "selection_policy": (
            "all predeclared methods reported; no held-out ranking or parameter selection"
        ),
        "sentiment_claim": "No empirical alpha claim; incomplete genuine history is unavailable",
        "spy": spy,
    }


def walk(request: WalkResearch, inputs: Inputs) -> dict[str, Any]:
    started = monotonic()
    base = request.research
    wr = WalkRequest(
        backtest=base.backtest,
        train_sessions=request.train_sessions,
        validation_sessions=request.validation_sessions,
        test_sessions=request.test_sessions,
        step_sessions=request.step_sessions,
        mode=request.mode,
        maximum_folds=request.maximum_folds,
    )
    from sentientalpha.data.calendar import session_open, sessions_in_range

    splits = wr.folds(
        sessions_in_range(base.backtest.calendar, base.backtest.start, base.backtest.end)
    )
    folds = []
    all_backtests = []
    indices: dict[str, list[dict[str, Any]]] = {}
    capitals: dict[str, float] = {}
    for i, split in enumerate(splits):
        if monotonic() - started > base.backtest.seconds:
            raise OptimizationError(
                "Walk-forward cooperative time budget exceeded", "time_budget", 429
            )
        config = base.optimization.model_copy(
            update={
                "history_start": split.train_start,
                "estimation_end": split.validation_end,
                "decision_at": session_open(base.backtest.calendar, split.test_start)
                - timedelta(microseconds=1),
            }
        )
        # Fixed sentiment coefficients must come from the declared pre-evaluation training interval.
        # No tuning/model selection uses held-out test performance.
        fold = base.model_copy(
            update={
                "optimization": config,
                "backtest": base.backtest.model_copy(
                    update={"start": split.test_start, "end": split.test_end}
                ),
                "rebalance_dates": [
                    d for d in base.rebalance_dates if split.test_start <= d <= split.test_end
                ],
            }
        )
        result = compare(fold, inputs)
        for bt in result.pop("_backtests"):
            method = bt["method"]
            bt["fold"] = i
            capital = capitals.get(method, float(base.backtest.capital))
            previous = float(base.backtest.capital)
            for row in bt["result"]["equity"]:
                current = float(row["equity"])
                capital *= current / previous
                previous = current
                indices.setdefault(method, []).append(
                    {
                        "day": row["day"],
                        "equity": str(capital),
                        "gross_exposure": row["gross_exposure"],
                        "fold": i,
                    }
                )
            capitals[method] = capital
            all_backtests.append(bt)
        folds.append(
            {"index": i, "split": split.model_dump(mode="json"), "methods": result["methods"]}
        )
    aggregate = {}
    for method, curve in indices.items():
        metrics = analytics(curve, float(base.backtest.capital), [], [])
        for key in (
            "turnover",
            "average_exposure",
            "commissions",
            "slippage",
            "trade_count",
            "closed_lot_count",
            "win_rate",
            "profit_factor",
            "average_trade_pnl",
        ):
            metrics[key] = None
        aggregate[method] = {
            "metrics": metrics,
            "index": [{"day": r["day"], "equity": r["equity"], "fold": r["fold"]} for r in curve],
        }
    return {
        "status": "completed",
        "folds": folds,
        "aggregate": aggregate,
        "_backtests": all_backtests,
        "selection_policy": (
            "predeclared fixed hyperparameters; rolling/expanding past-only "
            "moments; independent fold cash; linked OOS index, no portfolio "
            "carry"
        ),
    }

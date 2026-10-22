"""Committee targets for the authoritative M4 simulator; no accounting or artificial fills."""

from datetime import datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, cast

from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.contracts import StrategySpec
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.strategies import Context
from sentientalpha.committee.adapters import quant, strategy
from sentientalpha.committee.agents import heuristic, unavailable
from sentientalpha.committee.aggregation import aggregate
from sentientalpha.committee.contracts import AgentRecommendation, Evidence
from sentientalpha.committee.requests import Request
from sentientalpha.committee.risk import allocate
from sentientalpha.features.timing import next_open
from sentientalpha.optimization.estimation import OptimizationError, Panel, ReturnRow, estimate
from sentientalpha.strategies.contracts import Definition
from sentientalpha.strategies.contracts import Request as DiscoveryRequest
from sentientalpha.strategies.evaluation import RuleStrategy
from sentientalpha.strategies.evaluation import snapshot as execution_snapshot
from sentientalpha.strategies.inputs import Inputs, Signal


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in {"solve_seconds"}}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class CommitteeStrategy:
    def __init__(self, request: Request, inputs: Inputs, metadata: dict[str, Any]):
        self.request, self.inputs, self.metadata = request, inputs, metadata
        self.trace: list[dict[str, Any]] = []
        self.timings = {"agents": 0.0, "aggregation": 0.0, "optimization_and_risk": 0.0}
        self.last: tuple[Any, ...] | None = None
        from sentientalpha.risk.controller import RiskController

        self.risk_control = (
            RiskController(request, inputs, metadata, self) if request.risk_policy else None
        )
        days = sorted({d for d, _ in inputs.signals})
        self.panel = Panel(
            tuple(request.tickers),
            tuple(
                ReturnRow(
                    d,
                    tuple(
                        inputs.signals.get((d, t), {})
                        .get("return", Signal(None, None, "missing"))
                        .value
                        for t in request.tickers
                    ),
                    tuple(
                        inputs.signals.get((d, t), {})
                        .get("return", Signal(None, None, "missing"))
                        .ready
                        for t in request.tickers
                    ),
                )
                for d in days
            ),
            inputs.calendar,
        )
        self.rule = (
            RuleStrategy(
                Definition.model_validate(metadata["strategy"]["definition"]),
                inputs,
                request.tickers,
            )
            if metadata["strategy"]
            else None
        )

    def recommendations(self, context: Context) -> list[AgentRecommendation]:
        q = self.request
        raw_targets = self.rule.targets(context) if self.rule else {}
        rows = []
        for ticker in q.tickers:
            cells = self.inputs.signals.get((context.day, ticker), {})
            for agent in q.agents:
                if agent in {"fundamental", "macro"}:
                    rows.append(
                        unavailable(
                            agent,
                            ticker,
                            context.at,
                            "No genuine PIT statements/vintages configured",
                        )
                    )
                elif agent == "quant":
                    rows.append(
                        quant(q, self.metadata["quant"], ticker, context.at, str(context.day))
                    )
                elif agent == "strategy":
                    trace = (
                        next(
                            (
                                v
                                for v in reversed(self.rule.trace)
                                if v["ticker"] == ticker and v["day"] == str(context.day)
                            ),
                            None,
                        )
                        if self.rule
                        else None
                    )
                    feature_times = (
                        [
                            datetime.fromisoformat(v["available_at"])
                            for v in trace["features"].values()
                            if v["available_at"]
                        ]
                        if trace
                        else []
                    )
                    complete = trace and all(
                        v["value"] is not None for v in trace["features"].values()
                    )
                    # Unchanged M7 target on a non-rebalance day follows actual holdings.
                    target = float(
                        raw_targets.get(
                            ticker,
                            Decimal(1)
                            if dict(context.quantities).get(ticker, 0) > 0
                            else Decimal(0),
                        )
                    )
                    rows.append(
                        strategy(
                            q,
                            self.metadata["strategy"],
                            ticker,
                            context.at,
                            target if complete else None,
                            max(feature_times) if feature_times else None,
                        )
                    )
                else:
                    name = q.technical_column if agent == "technical" else q.sentiment_column
                    item = cells.get(name) if name else None
                    ev = None
                    if item and item.ready and item.ready <= context.at and item.value is not None:
                        ev = Evidence(
                            reference=item.source + ":" + str(context.day) + ":" + ticker,
                            version=self.metadata["feature_version"],
                            available_at=item.ready,
                            observed_at=item.ready,
                            ingested_at=item.ready,
                            kind="feature",
                            provenance="retrospective"
                            if q.information_policy == "retrospective"
                            else self.metadata["provenance"],
                            dependencies=(
                                ("market_prices:" if agent == "technical" else "news:") + ticker,
                            ),
                        )
                    rows.append(
                        heuristic(
                            agent,
                            ticker,
                            context.at,
                            item.value if item else None,
                            ev,
                            scale=q.technical_scale if agent == "technical" else 1,
                            neutral_region=q.policy.neutral_region,
                        )
                    )
        return rows

    def targets(self, context: Context) -> dict[str, Decimal]:
        q = self.request
        if self.last is not None and context.day <= self.last[0]:
            return {}
        self.last = (context.day, context.at)
        if len(self.trace) >= 13000:
            raise OptimizationError("Committee decision budget exceeded", "time_budget", 429)
        started = perf_counter()
        rows = self.recommendations(context)
        self.timings["agents"] += perf_counter() - started
        started = perf_counter()
        policy = q.policy.model_copy(update={"experimental_forecast_votes": q.experimental_quant})
        voting = aggregate(rows, policy, context.at)
        self.timings["aggregation"] += perf_counter() - started
        prices, quantities = dict(context.prices), dict(context.quantities)
        equity = context.cash + sum(
            quantities.get(t, Decimal(0)) * prices.get(t, Decimal(0)) for t in q.tickers
        )
        previous = (
            {
                t: float(quantities.get(t, Decimal(0)) * prices.get(t, Decimal(0)) / equity)
                for t in q.tickers
            }
            if equity > 0
            else {}
        )
        started = perf_counter()
        try:
            moments = estimate(self.panel, context.at, q.history_start, context.day, q.estimator)
            constraints = q.constraints
            experimental_only = not any(
                r.signal is not None and r.agent_id != "quant" for r in rows
            )
            if (
                q.allocation_policy == "committee"
                and experimental_only
                and any(r.agent_id == "quant" and r.prediction is not None for r in rows)
            ):
                constraints = constraints.model_copy(
                    update={"invested_maximum": min(0.1, constraints.invested_maximum)}
                )
            allocation = allocate(
                {
                    t: (q.allocation_policy == "m5_equal_weight_baseline" or voting[t]["active"])
                    for t in q.tickers
                },
                moments,
                constraints,
                previous,
                context.at,
                datetime.fromisoformat(moments.metadata["earliest_availability"]),
                timings=self.timings,
            )
            estimates_metadata = moments.metadata
        except OptimizationError as exc:
            allocation = {
                "action": "abstain",
                "proposal": None,
                "risk_review": None,
                "final_allocation": None,
                "reason": str(exc),
            }
            estimates_metadata = {"status": "insufficient_data"}
        self.timings["optimization_and_risk"] += perf_counter() - started
        final = allocation["final_allocation"]
        final_action = allocation["action"]
        if final is not None:
            current_total = sum(previous.values())
            proposed_total = sum(final.values())
            if all(abs(final.get(t, 0) - previous.get(t, 0)) <= 2e-7 for t in q.tickers):
                final_action = "maintain"
            elif proposed_total <= 2e-7 and current_total > 2e-7:
                final_action = "more_cash"
            elif proposed_total < current_total - 2e-7:
                final_action = "reduce"
        self.trace.append(
            clean(
                {
                    "decision_at": context.at.isoformat(),
                    "day": str(context.day),
                    "recommendations": [r.model_dump(mode="json") for r in rows],
                    "aggregation": voting,
                    "allocation": allocation,
                    "risk_inputs": estimates_metadata,
                    "actual_quantities_before": {t: str(v) for t, v in context.quantities},
                    "actual_weights_before": previous,
                    "cash_before": str(context.cash),
                    "execution_eligible_at": next_open(
                        self.inputs.calendar, context.at
                    ).isoformat(),
                    "information_policy": q.information_policy,
                    "final_action": final_action,
                }
            )
        )
        # A veto emits no targets, hence no orders for that decision. Never bypass risk.
        return {t: Decimal(str(v)) for t, v in final.items()} if final is not None else {}


def backtest_config(request: Request, inputs: Inputs) -> BacktestRequest:
    return BacktestRequest(
        tickers=request.tickers,
        provider=inputs.metadata["provider"],
        start=request.start,
        end=request.end,
        source_as_of=request.source_as_of,
        capital=Decimal(str(request.capital)),
        calendar=cast(Literal["weekday", "XNYS"], inputs.calendar),
        information_policy="online"
        if request.information_policy == "online"
        else "research_replay",
        costs=request.costs,
        seconds=request.seconds,
        strategy=StrategySpec(name="equal_weight", rebalance="daily"),
    )


def run(
    request: Request, inputs: Inputs, metadata: dict[str, Any]
) -> tuple[dict[str, Any], CommitteeStrategy]:
    adapter = CommitteeStrategy(request, inputs, metadata)
    config = backtest_config(request, inputs)
    # Reuse M7's explicitly labeled retrospective daily-bar clock adapter and M4 ledger.
    source = execution_snapshot(
        DiscoveryRequest.model_validate(metadata["source_configuration"]),
        inputs,
        request.start,
        request.end,
    )
    result = simulate(config, source, strategy=adapter, risk_control=adapter.risk_control)
    return result, adapter

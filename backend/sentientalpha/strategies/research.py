"""Train/validation-only search, explicit selection freeze and locked OOS execution."""

from collections.abc import Callable
from decimal import Decimal
from time import monotonic
from typing import Any

from sentientalpha.backtesting.contracts import (
    BacktestError,
    Costs,
    Feature,
    Snapshot,
    StrategySpec,
)
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.storage import digest
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.strategies.contracts import Definition, DiscoveryError, Request, Rule
from sentientalpha.strategies.evaluation import (
    config,
    evaluate,
    fitness,
    fragility,
    snapshot,
    summary,
)
from sentientalpha.strategies.grammar import complexity, identity, normalized, validate
from sentientalpha.strategies.inputs import Inputs
from sentientalpha.strategies.search import generate


class Budget:
    def __init__(self, request: Request):
        self.request, self.started, self.count, self.events = request, monotonic(), 0, 0

    def check(self) -> None:
        if (
            self.count >= self.request.maximum_simulations
            or monotonic() - self.started > self.request.seconds
        ):
            raise DiscoveryError(
                "Discovery cooperative simulation/time budget exceeded", "discovery_budget", 429
            )
        self.count += 1


def prepare(request: Request, inputs: Inputs) -> dict[str, Any]:
    budget = Budget(request)
    folds: list[dict[str, Any]] = []
    for i, w in enumerate(request.windows):
        definitions, history = generate(request, i)
        days = sessions_in_range(inputs.calendar, w.train_start, w.test_end)
        indices = w.indices(days)
        candidates = []
        for definition in definitions:
            candidate: dict[str, Any] = {
                "rule_hash": identity(definition),
                "definition": normalized(definition),
                "complexity": complexity(definition),
                "fold": i,
            }
            candidates.append(candidate)
            try:
                validate(definition, set(inputs.available))
                for phase in ("train", "validation"):
                    values = indices[phase]
                    if not values:
                        raise DiscoveryError("Empty purged research interval", "insufficient_data")
                    budget.check()
                    result, diagnostics = evaluate(
                        request, inputs, definition, days[values[0]], days[values[-1]]
                    )
                    budget.events += result["events_processed"]
                    candidate[phase] = {
                        "metrics": summary(result),
                        "fitness": fitness(result, diagnostics, definition, request.fitness),
                        "coverage": diagnostics["signal_coverage"],
                        "fragility": fragility(result),
                    }
                eligible = (
                    candidate["train"]["fitness"]["eligible"]
                    and candidate["validation"]["fitness"]["eligible"]
                )
                candidate["status"] = "eligible" if eligible else "rejected"
                if (
                    eligible
                    and candidate["validation"]["fitness"]["score"]
                    < request.fitness.minimum_validation_score
                ):
                    candidate["status"] = "validation_weakness"
                candidate["training_validation_gap"] = (
                    candidate["train"]["metrics"].get("sharpe") or 0
                ) - (candidate["validation"]["metrics"].get("sharpe") or 0)
            except (DiscoveryError, BacktestError) as exc:
                if isinstance(exc, DiscoveryError) and exc.code == "discovery_budget":
                    candidate.update(status="budget_interrupted", error_code=exc.code)
                    exc.partial_history = {
                        "completed_folds": folds,
                        "current_fold": i,
                        "candidates": candidates,
                    }
                    raise
                candidate.update(status="failed", error_code=exc.code)
        eligible = [c for c in candidates if c["status"] == "eligible"]
        ranked = sorted(
            eligible,
            key=lambda c: (
                -c["validation"]["fitness"]["score"],
                c["complexity"]["normalized"],
                c["rule_hash"],
            ),
        )
        selected = None
        if ranked:
            best = ranked[0]["validation"]["fitness"]["score"]
            selected = min(
                [
                    c
                    for c in ranked
                    if c["validation"]["fitness"]["score"]
                    >= best - request.fitness.selection_tolerance
                ],
                key=lambda c: (
                    c["complexity"]["normalized"],
                    -c["validation"]["fitness"]["score"],
                    c["rule_hash"],
                ),
            )["rule_hash"]
        folds.append(
            {
                "fold": i,
                "window": w.model_dump(mode="json"),
                "history": history,
                "candidates": candidates,
                "selected": selected,
                "ranking": [c["rule_hash"] for c in ranked],
                "status": "selected" if selected else "no_eligible_strategy",
            }
        )
    # No held-out simulation or data-dependent parameter generation above this line.
    frozen = {
        "folds": [
            {
                "fold": f["fold"],
                "selected": f["selected"],
                "ranking": f["ranking"],
                "window": f["window"],
                "candidate_hashes": [c["rule_hash"] for c in f["candidates"]],
            }
            for f in folds
        ],
        "search_configuration_hash": digest(request.model_dump(mode="json")),
        "selection_uses": "validation_fitness_only",
    }
    return {
        "folds": folds,
        "selection_lock": frozen,
        "selection_hash": digest(frozen),
        "search_simulations": budget.count,
        "events_processed": budget.events,
        "status": "ready_for_test" if any(f["selected"] for f in folds) else "no_eligible_strategy",
    }


def perturb(rule: Rule, sign: float = 1.0) -> Rule:
    if rule.kind == "compare":
        if rule.threshold is None:
            return rule
        value = rule.threshold
        return rule.model_copy(update={"threshold": value + sign * max(abs(value) * 0.1, 0.001)})
    return rule.model_copy(update={"children": [perturb(c, sign) for c in rule.children]})


def final_evaluation(
    request: Request,
    inputs: Inputs,
    prepared: dict[str, Any],
    record: Callable[[int, str, Any, Any, Any], str] | None = None,
) -> dict[str, Any]:
    if digest(prepared["selection_lock"]) != prepared["selection_hash"]:
        raise DiscoveryError("Locked selection was altered", "selection_lock_mismatch", 409)
    # Detect mutable changes to selection, rank, candidate definitions or declared windows.
    expected = prepare_lock(request, prepared)
    if digest(expected) != prepared["selection_hash"]:
        raise DiscoveryError(
            "Candidate or evaluation manifest differs from lock", "selection_lock_mismatch", 409
        )
    budget = Budget(request)
    folds: list[dict[str, Any]] = []
    series: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    def save(i: int, name: str, cfg: Any, snap: Any, result: Any) -> str | None:
        value = record(i, name, cfg, snap, result) if record else None
        if value:
            links.append({"fold": i, "kind": name, "run_id": value})
        return value

    for f, w in zip(prepared["folds"], request.windows, strict=True):
        if not f["selected"]:
            folds.append({"fold": f["fold"], "status": "no_eligible_strategy"})
            continue
        c = next(c for c in f["candidates"] if c["rule_hash"] == f["selected"])
        definition = Definition.model_validate(c["definition"])
        days = sessions_in_range(inputs.calendar, w.train_start, w.test_end)
        indices = w.indices(days)
        bounds = {k: (days[v[0]], days[v[-1]]) for k, v in indices.items() if v}
        fold: dict[str, Any] = {
            "fold": f["fold"],
            "rule_hash": f["selected"],
            "selection_hash": prepared["selection_hash"],
        }
        folds.append(fold)
        for phase, first, last in [
            ("train", w.train_start, w.train_end),
            ("validation", w.validation_start, w.validation_end),
            ("test", w.test_start, w.test_end),
        ]:
            first, last = bounds[phase]
            budget.check()
            result, diagnostic = evaluate(
                request, inputs, definition, first, last, audit=phase == "test"
            )
            cfg, snap = config(request, inputs, first, last), snapshot(request, inputs, first, last)
            save(f["fold"], phase, cfg, snap, result)
            if phase == "test":
                fold.update(
                    test=summary(result),
                    fragility=fragility(result),
                    trace=diagnostic["trace"],
                    test_fitness=fitness(result, diagnostic, definition, request.fitness),
                    validation_test_sharpe_gap=(c["validation"]["metrics"].get("sharpe") or 0)
                    - (result["metrics"].get("sharpe") or 0),
                )
                series.extend({"fold": f["fold"], **r} for r in result["metrics"]["daily_returns"])
        # Fixed benchmark policies. All use the same independent capital and raw-price convention.
        benchmarks = {}
        for name in ("buy_hold", "equal_weight", "cash", "moving_average"):
            budget.check()
            cfg = config(request, inputs, w.test_start, w.test_end)
            snap = snapshot(request, inputs, w.test_start, w.test_end)
            if name == "cash":
                cfg = cfg.model_copy(
                    update={
                        "strategy": StrategySpec(
                            allocation={t: Decimal(0) for t in request.tickers}
                        )
                    }
                )
                result = simulate(cfg, snap)
            elif name == "moving_average":
                sma = next(
                    (v for v in sorted(inputs.available) if v.startswith("sma__window_")), None
                )
                if sma is None:
                    benchmarks[name] = {"status": "unavailable", "reason": "No retained SMA"}
                    continue
                features = []
                for (day, ticker), values in inputs.signals.items():
                    if w.test_start <= day <= w.test_end and ticker in request.tickers:
                        signal = values.get(sma)
                        if signal is not None and signal.ready is not None:
                            features.append(
                                Feature(
                                    ticker,
                                    day,
                                    Decimal(str(signal.value))
                                    if signal.value is not None
                                    else None,
                                    signal.ready,
                                    signal.ready,
                                    signal.source,
                                )
                            )
                cfg = cfg.model_copy(
                    update={
                        "strategy": StrategySpec(
                            name="moving_average",
                            rebalance="daily",
                            feature_dataset_id=request.dataset_id,
                            feature_column=sma,
                        )
                    }
                )
                snap = Snapshot(snap.bars, tuple(features))
                result = simulate(cfg, snap)
            else:
                cfg = cfg.model_copy(
                    update={
                        "strategy": StrategySpec.model_validate(
                            {"name": name, "rebalance": "once" if name == "buy_hold" else "monthly"}
                        )
                    }
                )
                result = simulate(cfg, snap)
            benchmarks[name] = summary(result)
            save(f["fold"], "benchmark_" + name, cfg, snap, result)
        fold["benchmarks"] = benchmarks
        if request.robustness:
            stresses: list[dict[str, Any]] = []
            higher = request.costs.model_copy(
                update={
                    "fixed": min(request.costs.fixed * 2 + DecimalOne, DecimalThousand),
                    "slippage_bps": min(
                        request.costs.slippage_bps * 2 + DecimalFive, DecimalThousand
                    ),
                }
            )
            zero = Costs.model_validate(
                {
                    **request.costs.model_dump(),
                    "fixed": 0,
                    "per_share": 0,
                    "percentage": 0,
                    "slippage_bps": 0,
                }
            )
            for name, req, rule, delay in [
                (
                    "higher_cost_validation",
                    request.model_copy(update={"costs": higher}),
                    definition,
                    0,
                ),
                (
                    "nearby_threshold_validation",
                    request,
                    definition.model_copy(update={"entry": perturb(definition.entry)}),
                    0,
                ),
                (
                    "lower_threshold_validation",
                    request,
                    definition.model_copy(update={"entry": perturb(definition.entry, -1.0)}),
                    0,
                ),
                ("extra_session_delay_validation", request, definition, 1),
                (
                    "weekly_validation",
                    request,
                    definition.model_copy(update={"rebalance": "weekly"}),
                    0,
                ),
                (
                    "reduced_universe_validation",
                    request.model_copy(update={"tickers": request.tickers[:-1] or request.tickers}),
                    definition,
                    0,
                ),
                ("gross_test", request.model_copy(update={"costs": zero}), definition, 0),
            ]:
                budget.check()
                first, last = (
                    (w.test_start, w.test_end) if name == "gross_test" else bounds["validation"]
                )
                result, _ = evaluate(req, inputs, rule, first, last, delay=delay)
                stresses.append({"name": name, "metrics": summary(result)})
                save(
                    f["fold"],
                    name,
                    config(req, inputs, first, last),
                    snapshot(req, inputs, first, last),
                    result,
                )
            fold["robustness"] = stresses
            validation_stresses = [r["metrics"] for r in stresses if r["name"] != "gross_test"]
            sharpes = [v["sharpe"] for v in validation_stresses if v.get("sharpe") is not None]
            fold["robustness_flags"] = {
                "high_parameter_or_execution_sensitivity": bool(
                    (sharpes and max(sharpes) - min(sharpes) > 1)
                    or any(v.get("sharpe") is None for v in validation_stresses)
                ),
                "cost_profit_reversal": c["validation"]["metrics"]["total_return"] > 0
                and stresses[0]["metrics"]["total_return"] <= 0,
                "selection_changed_after_stress": False,
            }
        cash = benchmarks.get("cash", {}).get("total_return", 0)
        eq = benchmarks.get("equal_weight", {}).get("total_return")
        test = fold["test"]
        fold["outcome"] = (
            "no_out_of_sample_advantage"
            if test.get("total_return", 0) <= max(cash, eq or 0)
            else "eligible_for_further_research"
        )
        if not fold["test_fitness"]["eligible"]:
            fold["outcome"] = "insufficient_test_evidence"
        fold["warnings"] = [
            "Selected among all logged trials; no significance or alpha claim.",
            "Stress checks are assumptions, not calibrated execution models.",
        ]
    wealth = 1.0
    index = []
    for row in series:
        wealth *= 1 + row["return"]
        index.append({"day": row["day"], "fold": row["fold"], "return_index": wealth})
    frequency: dict[str, int] = {}
    for f in folds:
        if "rule_hash" in f:
            frequency[f["rule_hash"]] = frequency.get(f["rule_hash"], 0) + 1
    return {
        "folds": folds,
        "ledger_links": links,
        "selection_frequency": frequency,
        "oos_return_index": index,
        "capital_policy": "Independent fold ledgers; linked return index, no carried holdings",
        "status": "evaluated",
        "alpha_established": False,
    }


def prepare_lock(request: Request, prepared: dict[str, Any]) -> dict[str, Any]:
    for f in prepared["folds"]:
        if any(
            identity(Definition.model_validate(c["definition"])) != c["rule_hash"]
            for c in f["candidates"]
        ):
            raise DiscoveryError(
                "Candidate definition hash mismatch", "selection_lock_mismatch", 409
            )
    return {
        "folds": [
            {
                "fold": f["fold"],
                "selected": f["selected"],
                "ranking": f["ranking"],
                "window": f["window"],
                "candidate_hashes": [c["rule_hash"] for c in f["candidates"]],
            }
            for f in prepared["folds"]
        ],
        "search_configuration_hash": digest(request.model_dump(mode="json")),
        "selection_uses": "validation_fitness_only",
    }


DecimalOne, DecimalFive, DecimalThousand = Decimal(1), Decimal(5), Decimal(1000)

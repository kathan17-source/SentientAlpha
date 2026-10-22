"""One independent authority: M5 hard constraints, data gates and complete M9 revalidation."""

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from math import isfinite
from time import perf_counter
from typing import Any, cast

import numpy as np

from sentientalpha.backtesting.execution import commission
from sentientalpha.backtesting.storage import digest
from sentientalpha.optimization.contracts import Constraints
from sentientalpha.optimization.estimation import Estimates, OptimizationError, estimate
from sentientalpha.risk.analytics import analyse, matrix
from sentientalpha.risk.contracts import EvaluationRequest, Order
from sentientalpha.risk.legacy import review


def merged(base: Constraints, extra: Constraints) -> Constraints:
    a, b = base.model_dump(), extra.model_dump()
    out = {**a}
    for name in ["minimum"]:
        out[name] = {
            t: max(a[name].get(t, 0), b[name].get(t, 0)) for t in set(a[name]) | set(b[name])
        }
    for name in ["maximum", "sector_maximum"]:
        out[name] = {
            t: min(a[name].get(t, 1), b[name].get(t, 1)) for t in set(a[name]) | set(b[name])
        }
    for name in ["concentration", "cash_maximum", "invested_maximum"]:
        out[name] = min(a[name], b[name])
    out["cash_minimum"] = max(a["cash_minimum"], b["cash_minimum"])
    out["restricted"] = sorted(set(a["restricted"]) | set(b["restricted"]))
    for name in ["sectors", "groups"]:
        if any(k in a[name] and a[name][k] != v for k, v in b[name].items()):
            raise OptimizationError("Conflicting risk constraint definitions")
        out[name] = {**a[name], **b[name]}
    for name in [
        "volatility_maximum",
        "variance_maximum",
        "turnover_maximum",
        "tracking_error_maximum",
    ]:
        vals = [x for x in [a[name], b[name]] if x is not None]
        out[name] = min(vals) if vals else None
    if (
        a["benchmark_weights"] is not None
        and b["benchmark_weights"] is not None
        and a["benchmark_weights"] != b["benchmark_weights"]
    ):
        raise OptimizationError("Conflicting benchmark risk definitions")
    out["benchmark_weights"] = (
        a["benchmark_weights"] if a["benchmark_weights"] is not None else b["benchmark_weights"]
    )
    return Constraints.model_validate(out)


def control(request: EvaluationRequest) -> dict[str, Any]:
    p = request.policy
    history = [(e.at, float(e.value)) for e in request.state.equity_history]
    if not history or history[-1][0] < request.state.at:
        history.append((request.state.at, float(request.state.equity)))
    peak = history[0][1]
    halted = False
    good = 0
    transitions = []
    for at, value in history:
        peak = max(peak, value)
        dd = 1 - value / peak
        if p.drawdown_maximum is not None and dd > p.drawdown_maximum + 1e-12:
            if not halted:
                transitions.append({"at": at.isoformat(), "state": "HALTED", "drawdown": dd})
            halted = True
            good = 0
        elif halted and p.recovery_observations:
            good = good + 1 if dd <= p.recovery_drawdown else 0
            if good >= p.recovery_observations:
                halted = False
                good = 0
                transitions.append({"at": at.isoformat(), "state": "ACTIVE", "drawdown": dd})
    return {
        "state": "HALTED" if halted else "ACTIVE",
        "mode": p.drawdown_mode,
        "peak": peak,
        "recovery_observations": good,
        "transitions": transitions,
    }


def plan(
    request: EvaluationRequest,
    targets: dict[str, float] | None = None,
    orders: list[Order] | None = None,
) -> dict[str, Any]:
    state = request.state
    prices = {p.ticker: p.value for p in state.prices}
    names = sorted(prices)
    targets = request.targets if targets is None else targets
    orders = request.orders if orders is None else orders
    quantities = {t: state.quantities.get(t, Decimal(0)) for t in names}
    original = quantities.copy()
    cash = state.cash
    cost = Decimal(0)
    deltas = {}
    if targets is not None:
        if any(not isfinite(v) or v < 0 for v in targets.values()) or set(targets) - set(names):
            return {"status": "INVALID", "reason": "Invalid target weights/universe"}
        for t in names:
            if t not in targets:
                continue
            if targets.get(t, 0) and prices[t] is None:
                return {"status": "UNAVAILABLE", "reason": "Missing target price:" + t}
            desired = (
                (
                    state.equity * Decimal(str(targets.get(t, 0))) / cast(Decimal, prices[t])
                ).to_integral_value(rounding=ROUND_FLOOR)
                if prices[t]
                else Decimal(0)
            )
            delta = desired - original[t]
            if abs(delta) >= request.costs.minimum_quantity:
                deltas[t] = delta
    else:
        for order in orders:
            if order.ticker not in names:
                return {"status": "INVALID", "reason": "Unsupported order security"}
            deltas[order.ticker] = deltas.get(order.ticker, Decimal(0)) + order.quantity * (
                1 if order.side == "buy" else -1
            )
    for t, delta in sorted(deltas.items(), key=lambda v: (v[1] > 0, v[0])):
        price = prices[t]
        if price is None:
            return {"status": "UNAVAILABLE", "reason": "Missing trading price:" + t}
        execution_price = price * (
            1 + (1 if delta > 0 else -1) * request.costs.slippage_bps / 10000
        )
        fee = commission(request.costs, abs(delta), execution_price)
        cost += fee + abs(delta) * abs(execution_price - price)
        cash -= delta * execution_price + fee
        quantities[t] += delta
    liquidity_deltas = dict(deltas)
    pending_reserve = Decimal(0)
    for pending in state.pending_orders:
        if pending.side != "buy" or targets is not None and pending.ticker in deltas:
            continue
        price = prices[pending.ticker]
        if price is None:
            return {"status": "UNAVAILABLE", "reason": "Missing pending-order price"}
        execution_price = price * (1 + request.costs.slippage_bps / 10000)
        fee = commission(request.costs, pending.quantity, execution_price)
        commitment = pending.quantity * execution_price + fee
        pending_reserve += commitment
        cash -= commitment
        cost += fee + pending.quantity * abs(execution_price - price)
        quantities[pending.ticker] += pending.quantity
        liquidity_deltas[pending.ticker] = (
            liquidity_deltas.get(pending.ticker, Decimal(0)) + pending.quantity
        )
    equity = state.equity - cost
    if equity <= 0:
        return {"status": "INVALID", "reason": "Costs consume portfolio equity"}
    weights = {t: float(quantities[t] * (prices[t] or Decimal(0)) / equity) for t in names}
    return {
        "status": "PLANNED",
        "quantities": {t: str(v) for t, v in quantities.items()},
        "deltas": {t: str(v) for t, v in deltas.items()},
        "weights": weights,
        "cash": str(cash),
        "equity": str(equity),
        "costs": str(cost),
        "pending_buy_reserve": "0",
        "pending_commitment_included": str(pending_reserve),
        "liquidity_deltas": {t: str(v) for t, v in liquidity_deltas.items()},
        "assumption": "Indicative full fills with M4 costs; not an executed ledger",
    }


def evaluate(request: EvaluationRequest, timings: dict[str, float] | None = None) -> dict[str, Any]:
    request = EvaluationRequest.model_validate(request.model_dump())
    p = request.policy
    started = perf_counter()
    cache = None
    moments = None
    try:
        panel, x, meta = matrix(request)
        moments = estimate(
            panel,
            request.state.at,
            min(r.day for r in request.returns),
            request.state.at.date(),
            p.estimator,
        )
        cache = (moments, x, meta)
    except OptimizationError:
        pass
    if timings is not None:
        timings["covariance"] = timings.get("covariance", 0.0) + perf_counter() - started
    current = analyse(request, cached=cache, timings=timings)
    fsm = control(request)
    previous = current.get("exposure", {}).get("weights", {})
    names = tuple(sorted(v.ticker for v in request.state.prices))
    violations: list[dict[str, Any]] = []

    def check(candidate: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        bad = []

        def fail(metric: str, observed: Any, limit: Any, kind: str = "HARD_LIMIT") -> None:
            bad.append(
                {
                    "metric": metric,
                    "observed": observed,
                    "limit": limit,
                    "kind": kind,
                    "explanation": f"{metric}: observed {observed}; required {limit}",
                }
            )

        if candidate["status"] != "PLANNED":
            fail(
                "planning",
                candidate.get("reason"),
                "Valid available portfolio",
                "MISSING_DATA" if candidate["status"] == "UNAVAILABLE" else "INVALID",
            )
            return bad, {}
        weights = candidate["weights"]
        proposed = analyse(
            request,
            weights,
            cached=cache,
            timings=timings,
            equity_override=float(candidate["equity"]),
        )
        if proposed.get("exposure", {}).get("status") != "CALCULATED":
            fail("exposure", "unavailable", "Complete current valuations", "MISSING_DATA")
            return bad, proposed
        for warning in sorted(
            set(proposed.get("quality_violations", []) + current.get("quality_violations", []))
        ):
            fail("market_data", warning, "Eligible raw observed price", "MISSING_DATA")
        if current.get("status") == "UNAVAILABLE":
            fail("current_state", "unavailable", "Known actual holdings", "MISSING_DATA")
        if Decimal(candidate["cash"]) - Decimal(candidate["pending_buy_reserve"]) < 0:
            fail("cash", candidate["cash"], "Cash covers full orders and pending buys")
        if any(Decimal(v) < 0 for v in candidate["quantities"].values()):
            fail("short_position", candidate["quantities"], "Long-only")
        if moments is not None:
            legacy = review(
                weights,
                moments,
                p.constraints,
                previous,
                request.state.at,
                datetime.fromisoformat(moments.metadata["earliest_availability"]),
            )
            for key, value in legacy["violations"].items():
                fail("M5:" + key, value, "Constraint residual >= -2e-7")
        elif any(weights.values()) or p.constraints.tracking_error_maximum is not None:
            fail("covariance", "unavailable", "Required past M5 risk data", "MISSING_DATA")
        else:
            exact = Estimates(
                names,
                np.zeros(len(names)),
                np.zeros((len(names), len(names))),
                {"scope": "Exact zero target exposure, not estimated market covariance"},
            )
            legacy = review(
                weights, exact, p.constraints, previous, request.state.at, request.state.at
            )
            for key, value in legacy["violations"].items():
                fail("M5:" + key, value, "Constraint residual >= -2e-7")
        v = proposed.get("volatility", {})
        if (
            (
                p.constraints.volatility_maximum is not None
                or p.constraints.variance_maximum is not None
            )
            and any(weights.values())
            and not v.get("raw_covariance_reliable", False)
        ):
            fail(
                "covariance_reliability",
                v.get("raw_condition_number"),
                "Reliable unregularized support",
                "MISSING_DATA",
            )
        tail = proposed.get("tail", {})
        for key, limit in [
            ("var_loss_fraction", p.var_maximum),
            ("cvar_loss_fraction", p.cvar_maximum),
        ]:
            if limit is not None:
                if tail.get("status") not in {"CALCULATED", "EXACT_ZERO_EXPOSURE"}:
                    fail(key, tail.get("status"), "Adequate effective tail sample", "MISSING_DATA")
                elif tail[key] > limit + 1e-10:
                    fail(key, tail[key], limit)
        if (
            p.constraints.sector_maximum
            and proposed["exposure"]["sectors"].get("UNKNOWN", 0) > 1e-10
        ):
            fail("sector_classification", "missing", "Known eligible sector", "MISSING_DATA")
        if p.industry_maximum and proposed["exposure"]["industries"].get("UNKNOWN", 0) > 1e-10:
            fail("industry_classification", "missing", "Known eligible industry", "MISSING_DATA")
        for industry, cap in p.industry_maximum.items():
            value = proposed["exposure"]["industries"].get(industry, 0)
            if value > cap + 1e-10:
                fail("industry:" + industry, value, cap)
        if p.correlation_maximum is not None:
            corr = v.get("raw_correlation", v.get("correlation"))
            if corr is None and any(weights.values()):
                fail("correlation", "unavailable", "Known correlation", "MISSING_DATA")
            elif corr:
                for i, t in enumerate(names):
                    for j, u in enumerate(names[:i]):
                        if (
                            weights[t] > 0
                            and weights[u] > 0
                            and abs(corr[i][j]) > p.correlation_maximum
                        ):
                            fail("correlation:" + t + ":" + u, corr[i][j], p.correlation_maximum)
        if fsm["state"] == "HALTED":
            buys = any(
                Decimal(candidate["quantities"][t]) > request.state.quantities.get(t, 0)
                for t in names
            )
            must_cash = (
                p.drawdown_mode == "cash"
                and request.targets is not None
                and any(Decimal(v) > 0 for v in candidate["quantities"].values())
            )
            if buys or must_cash:
                fail("drawdown_state", fsm["state"], p.drawdown_mode)
        if p.cost_fraction_maximum is not None:
            cost = float(candidate["costs"]) / float(request.state.equity)
            if cost > p.cost_fraction_maximum:
                fail("execution_cost_fraction", cost, p.cost_fraction_maximum)
        for t, delta_text in candidate["liquidity_deltas"].items():
            delta = abs(float(delta_text))
            liq = proposed.get("liquidity", {}).get(t, {})
            if p.participation_maximum is not None or p.minimum_dollar_volume is not None:
                if liq.get("status") != "DAILY_VOLUME_PROXY":
                    fail(
                        "liquidity:" + t,
                        liq.get("status"),
                        "Verified daily volume proxy",
                        "MISSING_DATA",
                    )
                else:
                    if (
                        p.participation_maximum is not None
                        and delta / liq["average_volume"] > p.participation_maximum + 1e-12
                    ):
                        fail(
                            "participation:" + t,
                            delta / liq["average_volume"],
                            p.participation_maximum,
                        )
                    if (
                        p.minimum_dollar_volume is not None
                        and liq["average_dollar_volume"] < p.minimum_dollar_volume
                    ):
                        fail(
                            "dollar_volume:" + t,
                            liq["average_dollar_volume"],
                            p.minimum_dollar_volume,
                        )
        if p.stress_loss_maximum is not None:
            for s in proposed.get("stress", []):
                if s["status"] != "CALCULATED":
                    fail("stress:" + s["id"], s.get("reason"), "Eligible scenario", "MISSING_DATA")
                elif s["loss_fraction"] > p.stress_loss_maximum + 1e-12:
                    fail("stress:" + s["id"], s["loss_fraction"], p.stress_loss_maximum)
        return bad, proposed

    started = perf_counter()
    original = plan(request)
    violations, proposed = check(original)
    accepted = original if not violations else None
    approved_report = proposed
    attempts = []
    if (
        violations
        and p.adjustment == "scale_to_cash"
        and not any(v["kind"] == "INVALID" for v in violations)
    ):
        for i in range(1, p.adjustment_steps + 1):
            scale = 1 - i / p.adjustment_steps
            if request.targets is not None:
                target = {t: max(0.0, value) * scale for t, value in request.targets.items()}
                candidate = plan(request, targets=target)
                candidate["target_weights"] = target
            else:
                orders = [
                    o.model_copy(
                        update={
                            "quantity": (o.quantity * Decimal(str(scale))).to_integral_value(
                                rounding=ROUND_FLOOR
                            )
                        }
                    )
                    for o in request.orders
                ]
                orders = [o for o in orders if o.quantity >= request.costs.minimum_quantity]
                candidate = plan(request, orders=orders)
            bad, report = check(candidate)
            attempts.append({"scale": scale, "violations": bad})
            if not bad:
                accepted = candidate
                approved_report = report
                break
    if timings is not None:
        timings["policy_validation"] = (
            timings.get("policy_validation", 0.0) + perf_counter() - started
        )
    status = (
        "APPROVED"
        if not violations
        else "APPROVED_WITH_REDUCTION"
        if accepted
        else "INSUFFICIENT_RISK_DATA"
        if any(v["kind"] == "MISSING_DATA" for v in violations)
        else "REJECTED"
    )
    if not accepted and fsm["state"] == "HALTED":
        status = "NO_NEW_RISK"
    final_targets = None
    if accepted is not None:
        final_targets = accepted.get("target_weights", request.targets)
        if final_targets is None:
            final_targets = accepted["weights"]
    payload: dict[str, Any] = {
        "status": status,
        "policy_id": p.id,
        "policy_version": p.version,
        "policy_hash": digest(p.model_dump(mode="json")),
        "at": request.state.at.isoformat(),
        "portfolio_id": request.state.portfolio_id,
        "current": current,
        "proposed": proposed,
        "approved": approved_report if accepted else None,
        "proposal": original,
        "approved_plan": accepted,
        "approved_targets": final_targets,
        "violations": violations,
        "adjustment_attempts": attempts,
        "control": fsm,
        "executable": accepted is not None,
        "override_permitted": False,
        "exposure_change": {
            t: proposed.get("exposure", {}).get("weights", {}).get(t, 0) - previous.get(t, 0)
            for t in names
        },
        "methodology": "9.0.0; M5 residual authority + empirical tails and independent M9 policies",
    }
    payload["alerts"] = list(violations)
    if fsm["state"] == "HALTED":
        payload["alerts"].append(
            {
                "metric": "realized_drawdown_latch",
                "observed": current.get("drawdown", {}).get("current"),
                "limit": p.drawdown_maximum,
                "kind": "REALIZED_STATE",
                "explanation": "Past drawdown breach; explicit recovery required",
            }
        )
    payload["decision_id"] = digest(
        {"request": request.model_dump(mode="json", exclude={"idempotency_key"}), "outcome": status}
    )
    return payload

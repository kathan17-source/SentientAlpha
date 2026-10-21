"""Constrained deterministic SciPy SLSQP with independent feasibility validation."""

from time import perf_counter
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sentientalpha.optimization.contracts import Constraints, Objective
from sentientalpha.optimization.estimation import Estimates, OptimizationError, covariance_checked

TOLERANCE = 2e-7


def bounds(estimates: Estimates, c: Constraints) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    names = estimates.tickers
    lo = np.array([c.minimum.get(t, 0) for t in names], dtype=float)
    hi = np.array(
        [0 if t in c.restricted else min(c.concentration, c.maximum.get(t, 1)) for t in names],
        dtype=float,
    )
    return lo, hi


def residuals(
    w: NDArray[np.float64],
    e: Estimates,
    c: Constraints,
    previous: NDArray[np.float64],
    target: float | None = None,
    risk_free_annual: float = 0,
) -> dict[str, float]:
    lo, hi = bounds(e, c)
    cash = 1 - float(w.sum())
    result = {
        "minimum_asset_weight": float(np.min(w - lo)),
        "maximum_asset_weight": float(np.min(hi - w)),
        "cash_minimum": cash - c.cash_minimum,
        "cash_maximum": c.cash_maximum - cash,
        "invested_exposure": c.invested_maximum - float(w.sum()),
    }
    for name, g in c.groups.items():
        amount = float(sum(w[e.tickers.index(t)] for t in g.members))
        result["group_minimum:" + name] = amount - g.minimum
        result["group_maximum:" + name] = g.maximum - amount
    for sector, limit in c.sector_maximum.items():
        result["sector:" + sector] = limit - float(
            sum(w[i] for i, t in enumerate(e.tickers) if c.sectors.get(t) == sector)
        )
    variance = float(w @ e.covariance @ w)
    if c.volatility_maximum is not None:
        result["volatility"] = (c.volatility_maximum**2 - variance) / c.volatility_maximum**2
    if c.variance_maximum is not None:
        result["variance"] = (c.variance_maximum - variance) / c.variance_maximum
    turnover = 0.5 * (float(np.abs(w - previous).sum()) + abs(float(w.sum() - previous.sum())))
    if c.turnover_maximum is not None:
        result["turnover"] = c.turnover_maximum - turnover
    if c.tracking_error_maximum is not None:
        benchmark = np.array([(c.benchmark_weights or {}).get(t, 0) for t in e.tickers])
        active = w - benchmark
        result["tracking_error"] = (
            c.tracking_error_maximum**2 - float(active @ e.covariance @ active)
        ) / c.tracking_error_maximum**2
    if target is not None:
        result["target_return"] = float(w @ e.mean) + cash * risk_free_annual - target
    return result


def risk(
    w: NDArray[np.float64],
    e: Estimates,
    previous: NDArray[np.float64],
    objective: Objective,
    c: Constraints,
) -> dict[str, Any]:
    variance = max(0, float(w @ e.covariance @ w))
    volatility = float(np.sqrt(variance))
    cash = 1 - float(w.sum())
    expected = float(w @ e.mean) + cash * objective.risk_free_annual
    contribution = w * (e.covariance @ w) / volatility if volatility > 1e-14 else np.zeros(len(w))
    pct = w * (e.covariance @ w) / variance if variance > 1e-14 else None
    delta = np.abs(w - previous)
    cost = float(
        sum(objective.asset_cost_rates.get(t, 0) * delta[i] for i, t in enumerate(e.tickers))
    )
    diag = np.sqrt(np.maximum(np.diag(e.covariance), 0))
    denom = np.outer(diag, diag)
    correlation = np.divide(e.covariance, denom, out=np.zeros_like(e.covariance), where=denom > 0)
    invested = float(w.sum())
    benchmark = np.array([(c.benchmark_weights or {}).get(t, 0) for t in e.tickers])
    return {
        "units": "annual expected arithmetic risk/return; costs one rebalance fraction of equity",
        "expected_return": expected,
        "variance": variance,
        "volatility": volatility,
        "sharpe": (expected - objective.risk_free_annual) / volatility
        if volatility > 1e-14
        else None,
        "risk_contributions": dict(zip(e.tickers, contribution.tolist(), strict=True))
        if volatility > 1e-14
        else None,
        "percentage_risk_contributions": dict(zip(e.tickers, pct.tolist(), strict=True))
        if pct is not None
        else None,
        "risk_parity_residual": float(np.max(np.abs(pct - 1 / len(w))))
        if pct is not None
        else None,
        "cash_weight": cash,
        "invested_weight": invested,
        "turnover": 0.5 * (float(delta.sum()) + abs(float(w.sum() - previous.sum()))),
        "estimated_cost_fraction": cost,
        "concentration_hhi_including_cash": float(w @ w) + cash**2,
        "maximum_asset_weight": float(np.max(w)),
        "sector_exposure": {
            s: float(sum(w[i] for i, t in enumerate(e.tickers) if c.sectors.get(t) == s))
            for s in sorted(set(c.sectors.values()))
        },
        "correlation_matrix": correlation.tolist(),
        "weighted_pair_correlation": float(w @ correlation @ w) / (invested**2)
        if invested > 0
        else None,
        "tracking_error": float(
            np.sqrt(max(0, float((w - benchmark) @ e.covariance @ (w - benchmark))))
        )
        if c.benchmark_weights is not None
        else None,
    }


def solve(e: Estimates, c: Constraints, o: Objective, current: dict[str, float]) -> dict[str, Any]:
    try:
        from scipy.optimize import linprog, minimize
    except ImportError as exc:
        raise OptimizationError(
            "SciPy solver dependency unavailable", "solver_unavailable", 503
        ) from exc
    if e.units != "annual":
        raise OptimizationError("Expected return/covariance units must both be annual")
    n = len(e.tickers)
    if not n or e.mean.shape != (n,) or not np.all(np.isfinite(e.mean)) or len(set(e.tickers)) != n:
        raise OptimizationError("Invalid expected-return vector or ordering")
    if e.covariance.shape != (n, n):
        raise OptimizationError("Covariance and asset ordering dimensions differ")
    if o.method in {"risk_parity", "maximum_sharpe"} and (
        c.cash_minimum >= 1
        or np.any(np.diag(e.covariance) <= 1e-16)
        or e.metadata.get("covariance_audit", {}).get("zero_variance_assets", 0) > 0
        or np.max(np.diag(e.covariance)) <= 1e-16
        or e.metadata.get("covariance_audit", {}).get("zero_variance_assets") == n
    ):
        return {
            "status": "insufficient_data",
            "weights": None,
            "diagnostics": {"reason": "Zero empirical covariance makes risk objective undefined"},
        }
    if e.covariance.shape != (n, n):
        raise OptimizationError("Covariance and asset ordering dimensions differ")
    requested = (
        set(c.minimum)
        | set(c.maximum)
        | set(c.sectors)
        | set(c.restricted)
        | set(current)
        | set(o.asset_cost_rates)
        | set(c.benchmark_weights or {})
    )
    for group in c.groups.values():
        requested.update(group.members)
    if requested - set(e.tickers):
        raise OptimizationError("Constraint/current asset absent from estimated universe")
    if (
        any(not np.isfinite(v) or v < 0 or v > 1 for v in current.values())
        or sum(current.values()) > 1 + TOLERANCE
    ):
        raise OptimizationError("Invalid current holdings")
    covariance, solver_covariance_audit = covariance_checked(e.covariance, 0)
    e = Estimates(e.tickers, e.mean, covariance, e.metadata)
    if (
        o.method in {"maximum_sharpe", "risk_parity"}
        and abs(c.cash_minimum - c.cash_maximum) > 1e-12
    ):
        raise OptimizationError(
            "Sharpe and risk parity require a fixed invested exposure; "
            "variable cash ranges unsupported"
        )
    lo, hi = bounds(e, c)
    previous = np.array([current.get(t, 0) for t in e.tickers], dtype=float)
    if (
        (1 - c.cash_maximum) > c.invested_maximum + TOLERANCE
        or np.any(lo > hi)
        or lo.sum() > min(1 - c.cash_minimum, c.invested_maximum) + TOLERANCE
        or hi.sum() < 1 - c.cash_maximum - TOLERANCE
    ):
        return {
            "status": "infeasible",
            "weights": None,
            "diagnostics": {"reason": "asset/cash/exposure bounds conflict"},
        }
    # Variables w, nonnegative absolute asset changes, absolute cash change.
    m = 2 * n + 1
    inequalities = []
    limits = []

    def linear(coeff: NDArray[np.float64], limit: float) -> None:
        inequalities.append(coeff)
        limits.append(limit)

    row = np.zeros(m)
    row[:n] = 1
    equality = row.copy() if c.cash_minimum == c.cash_maximum else None
    if equality is None:
        linear(row.copy(), min(1 - c.cash_minimum, c.invested_maximum))
        linear(-row.copy(), -(1 - c.cash_maximum))
    for i in range(n):
        row = np.zeros(m)
        row[i] = 1
        row[n + i] = -1
        linear(row.copy(), previous[i])
        row[i] = -1
        linear(row.copy(), -previous[i])
    row = np.zeros(m)
    row[:n] = 1
    row[-1] = -1
    linear(row.copy(), float(previous.sum()))
    row[:n] = -1
    linear(row.copy(), -float(previous.sum()))
    if c.turnover_maximum is not None:
        row = np.zeros(m)
        row[n:] = 0.5
        linear(row, c.turnover_maximum)
    for g in c.groups.values():
        row = np.zeros(m)
        for t in g.members:
            row[e.tickers.index(t)] = 1
        linear(row.copy(), g.maximum)
        linear(-row.copy(), -g.minimum)
    for sector, cap in c.sector_maximum.items():
        row = np.zeros(m)
        for i, t in enumerate(e.tickers):
            row[i] = int(c.sectors.get(t) == sector)
        linear(row, cap)
    if o.target_return_annual is not None:
        row = np.zeros(m)
        row[:n] = -(e.mean - o.risk_free_annual)
        linear(row, o.risk_free_annual - o.target_return_annual)
    a = np.array(inequalities)
    b = np.array(limits)
    variable_bounds = list(zip(lo, hi, strict=True)) + [(0.0, 1.0)] * (n + 1)
    start = perf_counter()
    feasible = linprog(
        np.zeros(m),
        A_ub=a,
        b_ub=b,
        A_eq=np.array([equality]) if equality is not None else None,
        b_eq=np.array([1 - c.cash_minimum]) if equality is not None else None,
        bounds=variable_bounds,
        method="highs",
        options={"time_limit": 5.0},
    )
    if not feasible.success:
        return {
            "status": "infeasible" if feasible.status == 2 else "solver_failed",
            "weights": None,
            "diagnostics": {
                "solver": "HiGHS feasibility",
                "status": int(feasible.status),
                "message": str(feasible.message),
            },
        }
    constraints: list[dict[str, Any]] = [
        {"type": "ineq", "fun": lambda x: b - a @ x, "jac": lambda x: -a}
    ]
    if equality is not None:
        constraints.append(
            {
                "type": "eq",
                "fun": lambda x: float(equality @ x) - (1 - c.cash_minimum),
                "jac": lambda x: equality,
            }
        )
    nonlinear = (
        c.volatility_maximum is not None
        or c.variance_maximum is not None
        or c.tracking_error_maximum is not None
    )
    if nonlinear:

        def nonlinear_slack(x: NDArray[np.float64]) -> NDArray[np.float64]:
            r = residuals(x[:n], e, c, previous)
            return np.array(
                [v for k, v in r.items() if k in {"volatility", "variance", "tracking_error"}]
            )

        constraints.append({"type": "ineq", "fun": nonlinear_slack})
    rates = np.array([o.asset_cost_rates.get(t, 0) for t in e.tickers])
    eligible = hi > 0
    equal = np.where(
        eligible, min(1 - c.cash_minimum, c.invested_maximum) / max(1, int(eligible.sum())), 0.0
    )
    equal = np.minimum(equal, hi)
    h = o.horizon_sessions / 252
    covariance_scale = max(float(np.max(np.diag(e.covariance))), 1e-8)

    def value(x: NDArray[np.float64]) -> float:
        w = x[:n]
        cost = float(rates @ x[n : 2 * n])
        turn = 0.5 * float(x[n:].sum())
        var = float(w @ e.covariance @ w)
        if o.method == "equal_weight":
            base = float(np.sum((w - equal) ** 2))
        elif o.method == "minimum_variance":
            base = var
        elif o.method == "mean_variance":
            base = h * (
                o.risk_aversion * var
                - float(w @ e.mean)
                - (1 - float(w.sum())) * o.risk_free_annual
            )
        elif o.method == "maximum_sharpe":
            base = -(float(w @ e.mean) - float(w.sum()) * o.risk_free_annual - cost / h) / np.sqrt(
                max(var, 1e-20)
            )
        else:
            pct = w * (e.covariance @ w) / max(var, 1e-20)
            base = float(np.sum((pct - 1 / n) ** 2))
        return (
            base + o.turnover_penalty * turn + (0 if o.method == "maximum_sharpe" else cost)
        ) / (covariance_scale if o.method == "minimum_variance" else 1)

    def gradient(x: NDArray[np.float64]) -> NDArray[np.float64]:
        w = x[:n]
        a = e.covariance @ w
        v = max(float(w @ a), 1e-20)
        out = np.zeros(m)
        if o.method == "equal_weight":
            out[:n] = 2 * (w - equal)
        elif o.method == "minimum_variance":
            out[:n] = 2 * a
        elif o.method == "mean_variance":
            out[:n] = h * (2 * o.risk_aversion * a - e.mean + o.risk_free_annual)
        elif o.method == "maximum_sharpe":
            numerator = (
                float(w @ e.mean)
                - float(w.sum()) * o.risk_free_annual
                - float(rates @ x[n : 2 * n]) / h
            )
            out[:n] = -(e.mean - o.risk_free_annual) / np.sqrt(v) + numerator * a / (v**1.5)
            out[n : 2 * n] = rates / (h * np.sqrt(v))
        else:
            contribution = w * a / v
            jacobian = (
                np.diag(a) / v + np.diag(w) @ e.covariance / v - 2 * np.outer(w * a, a) / (v * v)
            )
            out[:n] = 2 * jacobian.T @ (contribution - 1 / n)
        out[n:] += 0.5 * o.turnover_penalty
        if o.method != "maximum_sharpe":
            out[n : 2 * n] += rates
        return out / (covariance_scale if o.method == "minimum_variance" else 1)

    starts = [feasible.x]
    # Equal-weight projected start helps nonconvex methods; deterministic, never selected
    # by held-out returns.
    if o.method in {"risk_parity", "maximum_sharpe"}:
        for candidate in (np.ones(n) / n, 1 / np.sqrt(np.maximum(np.diag(e.covariance), 1e-12))):
            candidate = candidate / candidate.sum() * (1 - c.cash_minimum)
            x = np.r_[
                candidate,
                np.abs(candidate - previous),
                abs(float(candidate.sum() - previous.sum())),
            ]
            if (
                min(
                    residuals(
                        candidate, e, c, previous, o.target_return_annual, o.risk_free_annual
                    ).values()
                )
                >= -TOLERANCE
            ):
                starts.append(x)

    def checkpoint(x: NDArray[np.float64]) -> None:
        if perf_counter() - start > o.seconds:
            raise OptimizationError("Solver cooperative time budget exceeded", "time_budget", 429)

    attempts = []
    accepted = []
    for x0 in starts:
        result = minimize(
            value,
            x0,
            method="SLSQP",
            jac=gradient,
            bounds=variable_bounds,
            constraints=constraints,
            callback=checkpoint,
            options={"ftol": o.tolerance, "maxiter": o.maximum_iterations},
        )
        w = result.x[:n]
        finite = bool(np.all(np.isfinite(result.x)))
        slack = (
            residuals(w, e, c, previous, o.target_return_annual, o.risk_free_annual)
            if finite
            else {"nonfinite": -1.0}
        )
        violation = max(0.0, -min(slack.values()))
        attempts.append(
            {
                "status": int(result.status),
                "success": bool(result.success),
                "message": str(result.message),
                "iterations": int(result.nit),
                "objective": float(result.fun) if np.isfinite(result.fun) else None,
                "maximum_constraint_violation": violation,
            }
        )
        if result.success and finite and violation <= TOLERANCE:
            accepted.append((float(result.fun), w.copy(), slack))
    diagnostics: dict[str, Any] = {
        "solver": "scipy.optimize.SLSQP",
        "input_covariance_audit": solver_covariance_audit,
        "objective": o.method,
        "tolerance": o.tolerance,
        "feasibility_tolerance": TOLERANCE,
        "attempts": attempts,
        "solve_seconds": perf_counter() - start,
        "global_optimum_claimed": False,
        "covariance_scale_for_minimum_variance": covariance_scale,
    }
    if not accepted:
        if o.fallback == "equal_weight" and o.method != "equal_weight":
            fallback = solve(
                e, c, o.model_copy(update={"method": "equal_weight", "fallback": "none"}), current
            )
            if fallback["weights"] is not None:
                fallback.update(
                    status="fallback", requested_method=o.method, fallback_reason=diagnostics
                )
                return fallback
        return {"status": "solver_failed", "weights": None, "diagnostics": diagnostics}
    objective, w, slack = min(accepted, key=lambda item: item[0])
    if (
        o.rebalance_threshold
        and 0.5 * (np.abs(w - previous).sum() + abs(w.sum() - previous.sum()))
        < o.rebalance_threshold
        and min(
            residuals(previous, e, c, previous, o.target_return_annual, o.risk_free_annual).values()
        )
        >= -TOLERANCE
    ):
        w = previous.copy()
        slack = residuals(w, e, c, previous, o.target_return_annual, o.risk_free_annual)
        diagnostics["threshold_no_trade"] = True
    # Tiny negative solver noise is not allowed into long-only execution; revalidate after clipping.
    w = np.maximum(w, 0)
    if w.sum() > 1 and w.sum() <= 1 + TOLERANCE:
        w = w / w.sum()
    slack = residuals(w, e, c, previous, o.target_return_annual, o.risk_free_annual)
    if min(slack.values()) < -TOLERANCE:
        return {"status": "invalid_solution", "weights": None, "diagnostics": diagnostics}
    diagnostics.update(
        objective_value=objective,
        constraint_slack=slack,
        binding_constraints=[k for k, v in slack.items() if abs(v) <= TOLERANCE],
        maximum_constraint_violation=max(0.0, -min(slack.values())),
    )
    return {
        "status": "completed",
        "weights": dict(zip(e.tickers, w.tolist(), strict=True)),
        "cash_weight": 1 - float(w.sum()),
        "risk": risk(w, e, previous, o, c),
        "diagnostics": diagnostics,
        "warnings": ["Local nonlinear solve; no guaranteed global optimum for Sharpe/risk parity."]
        if o.method in {"maximum_sharpe", "risk_parity"}
        else [],
    }

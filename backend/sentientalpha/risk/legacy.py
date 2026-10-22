"""Authoritative existing M5 residual veto, shared by M8 compatibility and M9."""

from datetime import datetime, timedelta
from math import isfinite
from typing import Any

import numpy as np

from sentientalpha.data.contracts import utc
from sentientalpha.optimization.contracts import Constraints
from sentientalpha.optimization.estimation import Estimates, OptimizationError, covariance_checked
from sentientalpha.optimization.solver import TOLERANCE, residuals


def review(
    proposal: dict[str, float],
    estimates: Estimates,
    constraints: Constraints,
    previous: dict[str, float],
    decision_at: datetime,
    available_at: datetime,
    *,
    simulation_only: bool = True,
) -> dict[str, Any]:
    violations: dict[str, float | str] = {}
    utc(decision_at)
    utc(available_at)
    Constraints.model_validate(constraints.model_dump())
    if available_at > decision_at:
        violations["availability"] = "Risk estimates unavailable at decision"
    elif decision_at - available_at > timedelta(days=7):
        violations["staleness"] = "Risk input availability is older than seven calendar days"
    try:
        covariance_checked(estimates.covariance, 0)
        if estimates.covariance.shape != (len(estimates.tickers), len(estimates.tickers)):
            raise OptimizationError("Risk universe shape mismatch")
        if (
            estimates.units != "annual"
            or not np.all(np.isfinite(estimates.mean))
            or estimates.mean.shape != (len(estimates.tickers),)
            or len(set(estimates.tickers)) != len(estimates.tickers)
        ):
            raise OptimizationError("Invalid risk units or means")
    except (OptimizationError, IndexError, ValueError) as exc:
        violations["risk_estimates"] = str(exc)
    if not simulation_only:
        violations["simulation_only"] = "Live execution is unsupported"
    if set(proposal) != set(estimates.tickers) or set(previous) - set(estimates.tickers):
        violations["universe"] = "Proposal/holdings differ from frozen risk universe"
    if (
        any(not isfinite(v) or v < 0 or v > 1 for v in previous.values())
        or sum(previous.values()) > 1 + TOLERANCE
    ):
        violations["previous"] = "Invalid actual portfolio weights"
    if any(not isfinite(v) or v < 0 for v in proposal.values()):
        violations["weights"] = "Nonfinite or negative allocation"
    names = set(estimates.tickers)
    mappings: list[dict[str, Any]] = [
        constraints.minimum,
        constraints.maximum,
        constraints.sectors,
        constraints.benchmark_weights or {},
    ]
    if (
        any(set(m) - names for m in mappings)
        or set(constraints.restricted) - names
        or any(set(g.members) - names for g in constraints.groups.values())
    ):
        violations["constraint_universe"] = "Constraint references unknown assets"
    if not violations:
        weights = np.array([proposal[t] for t in estimates.tickers], dtype=float)
        prior = np.array([previous.get(t, 0) for t in estimates.tickers], dtype=float)
        slacks = residuals(weights, estimates, constraints, prior)
        violations.update({k: v for k, v in slacks.items() if not isfinite(v) or v < -TOLERANCE})
    else:
        slacks = {}
    return {
        "status": "vetoed" if violations else "approved",
        "original_proposal": proposal,
        "constraint_slack": slacks,
        "violations": violations,
        "adjustment": None,
        "final_allocation": None if violations else proposal,
        "override_permitted": False,
    }

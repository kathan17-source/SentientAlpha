"""Independent M5 constraint recheck; a veto is terminal for this proposal."""

from datetime import datetime
from time import perf_counter
from typing import Any

from sentientalpha.data.contracts import utc
from sentientalpha.optimization.contracts import Constraints, Objective
from sentientalpha.optimization.estimation import Estimates
from sentientalpha.optimization.solver import solve
from sentientalpha.risk.legacy import review as review


def allocate(
    active: dict[str, bool],
    estimates: Estimates,
    constraints: Constraints,
    previous: dict[str, float],
    decision_at: datetime,
    available_at: datetime,
    timings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Reuse M5 equal-weight projection with genuine past-estimated covariance."""
    utc(decision_at)
    utc(available_at)
    if available_at > decision_at or set(active) != set(estimates.tickers):
        raise ValueError("Unavailable estimates or incompatible active universe")
    constrained = Constraints.model_validate(
        {
            **constraints.model_dump(),
            "restricted": sorted(
                set(constraints.restricted) | {t for t, flag in active.items() if not flag}
            ),
        }
    )
    started = perf_counter()
    proposal = solve(estimates, constrained, Objective(method="equal_weight"), previous)
    if timings is not None:
        timings["optimization"] = timings.get("optimization", 0.0) + perf_counter() - started
    if proposal.get("weights") is None:
        return {
            "action": "reject",
            "proposal": proposal,
            "risk_review": None,
            "final_allocation": None,
        }
    started = perf_counter()
    risk = review(proposal["weights"], estimates, constrained, previous, decision_at, available_at)
    if timings is not None:
        timings["risk_validation"] = timings.get("risk_validation", 0.0) + perf_counter() - started
    return {
        "action": "approve" if risk["status"] == "approved" else "reject",
        "proposal": proposal,
        "risk_review": risk,
        "final_allocation": risk["final_allocation"],
    }

"""Optional M5 projection boundary for downstream consumers of validated rule signals."""

from dataclasses import replace
from datetime import datetime
from typing import Any

from sentientalpha.optimization.contracts import Constraints, Objective
from sentientalpha.optimization.estimation import Estimates
from sentientalpha.optimization.solver import solve
from sentientalpha.strategies.contracts import DiscoveryError


def project_active(
    estimates: Estimates,
    active: dict[str, bool | None],
    constraints: Constraints,
    decision_at: datetime,
    estimates_available_at: datetime,
    previous: dict[str, float] | None = None,
) -> dict[str, Any]:
    if estimates_available_at > decision_at or set(active) != set(estimates.tickers):
        raise DiscoveryError("Allocation estimates/signals are unavailable or incompatible")
    restricted = sorted(
        set(constraints.restricted) | {t for t, value in active.items() if value is not True}
    )
    constrained = constraints.model_copy(update={"restricted": restricted})
    result = solve(
        replace(
            estimates, metadata={**estimates.metadata, "source": "strategy_active_set_projection"}
        ),
        constrained,
        Objective(method="equal_weight"),
        previous or {},
    )
    return {
        **result,
        "active_signals": active,
        "decision_at": decision_at.isoformat(),
        "scope": "Optional M5 constrained proposal; discovery backtests use declared fixed weights",
    }

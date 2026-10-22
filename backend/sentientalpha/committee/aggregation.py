"""Conservative dependency-aware voting; agreement is not independent probability."""

from datetime import datetime
from typing import Any

from sentientalpha.committee.contracts import AgentRecommendation, Policy


def aggregate(
    recommendations: list[AgentRecommendation],
    policy: Policy,
    at: datetime,
) -> dict[str, Any]:
    if not recommendations or len(recommendations) > 300:
        raise ValueError("Committee needs one to 300 bounded recommendations")
    Policy.model_validate(policy.model_dump())
    if policy.effective_at > at:
        raise ValueError("Future policy cannot determine current weights")
    seen: set[tuple[str, str]] = set()
    for rec in recommendations:
        key = (rec.agent_id, rec.ticker)
        if key in seen:
            raise ValueError("Duplicate/conflicting recommendation; agents cannot submit orders")
        seen.add(key)
        if rec.decision_at != at:
            raise ValueError("Recommendations must share exact decision clock")
        # Revalidate even instances produced through unchecked Pydantic model_copy/construct.
        AgentRecommendation.model_validate(rec.model_dump())
    result: dict[str, Any] = {}
    for ticker in sorted({r.ticker for r in recommendations}):
        rows = sorted([r for r in recommendations if r.ticker == ticker], key=lambda r: r.agent_id)
        eligible = [
            r
            for r in rows
            if r.signal is not None
            and policy.weights.get(r.agent_id, 0) > 0
            and (
                (r.interpretation == "heuristic" and r.prediction is None)
                or (
                    policy.experimental_forecast_votes
                    and r.agent_id == "quant"
                    and r.interpretation == "forecast"
                )
            )
        ]
        # Connected components: shared dependencies are counted as a single evidence family.
        groups: list[list[AgentRecommendation]] = []
        for row in eligible:
            deps = {d for e in row.evidence for d in e.dependencies}
            matching = [
                g
                for g in groups
                if deps & {d for r in g for e in r.evidence for d in e.dependencies}
            ]
            merged = [row]
            for group in matching:
                merged.extend(group)
                groups.remove(group)
            groups.append(merged)
        contributions: list[dict[str, Any]] = []
        for group in groups:
            weights = [
                min(policy.weights[r.agent_id], 0.1)
                if r.agent_id == "quant"
                else policy.weights[r.agent_id]
                for r in group
            ]
            # Cap the entire overlapping family at its largest constituent prior.
            contribution = sum(
                w * float(r.signal or 0) for w, r in zip(weights, group, strict=True)
            ) / sum(weights)
            contributions.append(
                {
                    "agents": sorted(r.agent_id for r in group),
                    "signal": contribution,
                    "weight": max(weights),
                    "dependencies": sorted(
                        {d for r in group for e in r.evidence for d in e.dependencies}
                    ),
                }
            )
        denominator = sum(g["weight"] for g in contributions)
        score = (
            sum(g["weight"] * g["signal"] for g in contributions) / denominator
            if denominator
            else None
        )
        disagreement = bool(
            any(float(r.signal or 0) > 0 for r in eligible)
            and any(float(r.signal or 0) < 0 for r in eligible)
        )
        sufficient = len(groups) >= policy.minimum_independent_groups
        # Conflicting signs and insufficient independent evidence both withhold additions.
        active = (
            sufficient and not disagreement and score is not None and score > policy.neutral_region
        )
        result[ticker] = {
            "participating": len(eligible),
            "abstaining": len(rows) - len(eligible),
            "independent_groups": len(groups),
            "groups": contributions,
            "disagreement": disagreement,
            "aggregate_heuristic": score,
            "active": active,
            "action": "propose" if active else "abstain",
            "confidence": None,
            "expected_return": None,
            "reason": "Fixed-prior evidence groups; no estimated skill. "
            + (
                "Conflicting directions."
                if disagreement
                else "Insufficient groups."
                if not sufficient
                else "Eligible evidence."
            ),
            "policy_version": policy.version,
        }
    return result

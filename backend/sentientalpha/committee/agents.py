"""Deterministic adapters; source extraction remains the existing engines' responsibility."""

from datetime import datetime
from math import isfinite

from sentientalpha.committee.contracts import Agent, AgentRecommendation, Evidence, Status


def unavailable(
    agent: Agent,
    ticker: str,
    at: datetime,
    reason: str,
    status: Status = "insufficient_data",
) -> AgentRecommendation:
    if status in {"positive", "negative", "neutral"}:
        raise ValueError("Unavailable adapter needs an abstaining status")
    return AgentRecommendation(
        agent_id=agent,
        ticker=ticker,
        decision_at=at,
        data_cutoff=at,
        status=status,
        interpretation="unavailable",
        coverage=0,
        limitations=(reason,),
        reasoning=reason,
    )


def heuristic(
    agent: Agent,
    ticker: str,
    at: datetime,
    value: float | None,
    evidence: Evidence | None,
    *,
    scale: float,
    neutral_region: float,
    coverage: float = 1,
) -> AgentRecommendation:
    """Declared clipped linear transform of an existing feature, not a return estimate."""
    if agent not in {"technical", "sentiment"}:
        raise ValueError("Heuristic adapter only supports technical/sentiment features")
    if not isfinite(scale) or scale <= 0 or not 0 <= neutral_region < 1:
        raise ValueError("Invalid prior-configured transform")
    if value is None or evidence is None:
        return unavailable(agent, ticker, at, "No eligible cached feature")
    if not isfinite(value):
        return unavailable(agent, ticker, at, "Nonfinite source feature", "invalid")
    if max(evidence.available_at, evidence.ingested_at) > at:
        return unavailable(agent, ticker, at, "Source feature unavailable at decision", "invalid")
    if agent == "sentiment" and coverage != 1:
        return unavailable(agent, ticker, at, "Sentiment requires complete eligible news coverage")
    if evidence.kind != "feature":
        raise ValueError("Heuristic adapter consumes existing feature cells only")
    signal = max(-1.0, min(1.0, value / scale))
    if abs(signal) <= neutral_region:
        signal = 0.0
    return AgentRecommendation(
        agent_id=agent,
        ticker=ticker,
        decision_at=at,
        data_cutoff=at,
        status="positive" if signal > 0 else "negative" if signal < 0 else "neutral",
        signal=signal,
        strength=abs(signal),
        interpretation="heuristic",
        coverage=coverage,
        evidence=(evidence,),
        limitations=("Configured heuristic; no empirical confidence or expected return",),
        reasoning=f"Existing feature={value}; clip(value/{scale},-1,1); "
        f"neutral region={neutral_region}. Article text is passive data.",
    )

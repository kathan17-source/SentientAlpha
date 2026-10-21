"""Past-matured directional diagnostics; this does not learn portfolio weights."""

from datetime import datetime

from pydantic import Field, model_validator

from sentientalpha.backtesting.contracts import Frozen
from sentientalpha.committee.contracts import AgentRecommendation
from sentientalpha.data.contracts import utc


class Outcome(Frozen):
    recommendation: AgentRecommendation
    execution_at: datetime
    matured_at: datetime
    available_at: datetime
    realized_return: float = Field(gt=-1)
    out_of_sample: bool
    horizon_sessions: int = Field(ge=1, le=252, strict=True)

    @model_validator(mode="after")
    def chronological(self) -> "Outcome":
        for value in (self.execution_at, self.matured_at, self.available_at):
            utc(value)
        if (
            not self.recommendation.decision_at
            < self.execution_at
            <= self.matured_at
            <= self.available_at
        ):
            raise ValueError("Outcome must follow next-open execution and maturity")
        if self.recommendation.horizon_sessions != self.horizon_sessions:
            raise ValueError("Incompatible forecast and realized outcome horizons")
        return self


def evaluate(history: list[Outcome], at: datetime, minimum_samples: int = 60) -> dict[str, object]:
    utc(at)
    if minimum_samples < 30 or len(history) > 100_000:
        raise ValueError("Invalid bounded performance evaluation")
    eligible = [
        o
        for o in history
        if o.out_of_sample and o.available_at <= at and o.recommendation.signal not in {None, 0}
    ]
    keys = [
        (
            o.recommendation.agent_id,
            o.recommendation.agent_version,
            o.recommendation.ticker,
            o.recommendation.decision_at,
            o.horizon_sessions,
        )
        for o in eligible
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate recommendation outcomes")
    if (
        len(
            {
                (o.recommendation.agent_id, o.recommendation.agent_version, o.horizon_sessions)
                for o in eligible
            }
        )
        > 1
    ):
        raise ValueError("Evaluate one versioned agent and horizon at a time")
    count = len(eligible)
    accuracy = (
        sum(float(o.recommendation.signal or 0) * o.realized_return > 0 for o in eligible) / count
        if count
        else None
    )
    return {
        "status": "descriptive_only" if count >= minimum_samples else "insufficient_data",
        "samples": count,
        "excluded": len(history) - count,
        "direction_accuracy": accuracy,
        "confidence": None,
        "adaptive_weights": None,
        "calibration": None,
        "information_coefficient": None,
        "period_start": min((o.execution_at for o in eligible), default=None),
        "period_end": max((o.matured_at for o in eligible), default=None),
        "limitation": (
            "Overlapping outcomes may be dependent; no skill significance "
            "or adaptive weights claimed"
        ),
    }

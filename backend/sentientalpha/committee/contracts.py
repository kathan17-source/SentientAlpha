"""Versioned evidence with explicit clocks, units and abstention semantics."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Frozen
from sentientalpha.data.contracts import ticker_symbol, utc

Agent = Literal["fundamental", "technical", "sentiment", "macro", "quant", "strategy"]
Status = Literal[
    "positive", "negative", "neutral", "abstain", "insufficient_data", "invalid", "model_failure"
]


class Evidence(Frozen):
    reference: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=160)
    available_at: datetime
    observed_at: datetime
    ingested_at: datetime
    kind: Literal["feature", "article", "filing", "macro_vintage", "forecast", "strategy"]
    provenance: Literal["genuine", "synthetic_fixture", "retrospective"]
    dependencies: tuple[str, ...] = Field(min_length=1, max_length=16)

    @field_validator("available_at", "observed_at", "ingested_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def clocks(self) -> "Evidence":
        if self.observed_at > self.available_at:
            raise ValueError("Observation cannot follow evidence availability")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("Duplicate dependencies")
        return self


class AgentRecommendation(Frozen):
    agent_id: Agent
    agent_version: Literal["8.0.0"] = "8.0.0"
    ticker: str
    decision_at: datetime
    data_cutoff: datetime
    status: Status
    signal: float | None = Field(default=None, ge=-1, le=1)
    strength: float | None = Field(default=None, ge=0, le=1)
    interpretation: Literal["heuristic", "description", "forecast", "unavailable"]
    horizon_sessions: int | None = Field(default=None, ge=1, le=252, strict=True)
    prediction: float | None = None
    prediction_units: (
        Literal["probability", "simple_return_horizon", "annualized_volatility"] | None
    ) = None
    # Empirical confidence is intentionally unsupported until calibration evidence is integrated.
    diagnostics: dict[str, Any] = Field(default_factory=dict, max_length=20)
    confidence: None = None
    expected_return: None = None
    coverage: float = Field(ge=0, le=1)
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=128)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=32)
    reasoning: str = Field(min_length=1, max_length=4000)

    @field_validator("ticker")
    @classmethod
    def symbol(cls, value: str) -> str:
        return ticker_symbol(value)

    @field_validator("decision_at", "data_cutoff")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def coherent(self) -> "AgentRecommendation":
        if self.data_cutoff > self.decision_at:
            raise ValueError("Data cutoff follows decision")
        for item in self.evidence:
            if max(item.available_at, item.ingested_at) > self.data_cutoff:
                raise ValueError("Future evidence is ineligible")
        participating = self.status in {"positive", "negative", "neutral"}
        if participating:
            if self.signal is None or self.strength is None or not self.evidence:
                raise ValueError("Participating agents need signals, strength and evidence")
            if self.strength != abs(self.signal):
                raise ValueError("Strength is signal magnitude, never confidence")
            if (
                (self.status == "positive" and self.signal <= 0)
                or (self.status == "negative" and self.signal >= 0)
                or (self.status == "neutral" and self.signal != 0)
            ):
                raise ValueError("Direction contradicts signal")
            if self.interpretation == "unavailable" or self.coverage == 0:
                raise ValueError("Unavailable evidence cannot participate")
        elif self.signal is not None or self.strength is not None:
            raise ValueError("Abstentions must not masquerade as neutral signals")
        if (self.prediction is None) != (self.prediction_units is None):
            raise ValueError("Prediction requires explicit units")
        if self.prediction_units == "probability" and not 0 <= self.prediction <= 1:  # type: ignore[operator]
            raise ValueError("Probability outside zero to one")
        if self.prediction is not None and self.horizon_sessions is None:
            raise ValueError("Forecast requires explicit horizon")
        if not participating and self.prediction is not None:
            raise ValueError("Unavailable forecasts cannot carry predictions")
        return self


class Policy(Frozen):
    version: Literal["committee-fixed-8.0.0"] = "committee-fixed-8.0.0"
    effective_at: datetime
    neutral_region: float = Field(default=0.05, ge=0, lt=1)
    minimum_independent_groups: int = Field(default=2, ge=1, le=6, strict=True)
    experimental_forecast_votes: bool = False
    # Fixed priors are declared preferences, not estimated skill or probabilities.
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "fundamental": 1 / 6,
            "technical": 1 / 6,
            "sentiment": 1 / 6,
            "macro": 1 / 6,
            "quant": 1 / 6,
            "strategy": 1 / 6,
        },
        min_length=1,
        max_length=6,
    )

    @field_validator("effective_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def normalized(self) -> "Policy":
        if set(self.weights) - {
            "fundamental",
            "technical",
            "sentiment",
            "macro",
            "quant",
            "strategy",
        }:
            raise ValueError("Unknown agent weight")
        if any(v < 0 for v in self.weights.values()) or abs(sum(self.weights.values()) - 1) > 1e-10:
            raise ValueError("Weights must be nonnegative and normalized")
        return self

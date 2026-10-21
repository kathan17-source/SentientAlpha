"""Bounded committee research configuration; no implicit training or discovery."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Costs, Frozen
from sentientalpha.committee.contracts import Agent, Policy
from sentientalpha.data.contracts import ticker_symbol, utc
from sentientalpha.optimization.contracts import Constraints, Estimator
from sentientalpha.risk.contracts import Policy as RiskPolicy


def default_agents() -> list[Agent]:
    return ["technical", "sentiment", "quant", "strategy", "fundamental", "macro"]


class Request(Frozen):
    dataset_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    sentiment_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    sentiment_column: str | None = Field(default=None, max_length=160)
    sentiment_provenance: Literal["genuine", "synthetic_fixture"] = "genuine"
    model_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    strategy_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    horizon: Literal[1, 5, 10] = 1
    tickers: list[str] = Field(min_length=1, max_length=50)
    history_start: date
    start: date
    end: date
    source_as_of: datetime
    information_policy: Literal["online", "research_replay", "retrospective"] = "online"
    technical_column: str = Field(default="return", max_length=160)
    technical_scale: float = Field(default=0.02, gt=0, le=10)
    agents: list[Agent] = Field(default_factory=default_agents, min_length=1, max_length=6)
    policy: Policy
    allocation_policy: Literal["committee", "m5_equal_weight_baseline"] = "committee"
    experimental_quant: bool = False
    risk_policy: RiskPolicy | None = None
    estimator: Estimator = Field(default_factory=Estimator)
    constraints: Constraints = Field(default_factory=lambda: Constraints(cash_maximum=1))
    costs: Costs = Field(default_factory=Costs)
    capital: float = Field(default=100000.0, gt=0, le=1e12)
    seconds: int = Field(default=120, ge=1, le=300, strict=True)
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")

    @field_validator("source_as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, values: list[str]) -> list[str]:
        result = sorted(ticker_symbol(v) for v in values)
        if len(result) != len(set(result)):
            raise ValueError("Duplicate assets")
        return result

    @model_validator(mode="after")
    def valid(self) -> "Request":
        if (
            not date(2000, 1, 1)
            <= self.history_start
            < self.start
            <= self.end
            <= date(2034, 12, 31)
        ):
            raise ValueError("Chronological bounded history required")
        if (self.end - self.history_start).days > 3660 or (self.end - self.start).days > 366:
            raise ValueError("At most ten years of history and one evaluation year")
        if self.end > self.source_as_of.date() or self.policy.effective_at.date() >= self.start:
            raise ValueError("Source cutoff and pre-evaluation policy are incompatible")
        if len(set(self.agents)) != len(self.agents):
            raise ValueError("Duplicate agents")
        if self.technical_column != "return" and not self.technical_column.startswith(
            "price_to_sma__"
        ):
            raise ValueError("Technical adapter accepts existing return/price-to-SMA features")
        if bool(self.sentiment_dataset_id) != bool(self.sentiment_column):
            raise ValueError("Sentiment needs a dataset and column")
        if self.sentiment_column and not self.sentiment_column.startswith("sent_mean__"):
            raise ValueError("Only descriptive cached sentiment means are supported")
        if self.risk_policy is not None and self.risk_policy.effective_at.date() >= self.start:
            raise ValueError("Risk policy must precede evaluation")
        c = self.constraints
        mappings: list[dict[str, Any]] = [
            c.minimum,
            c.maximum,
            c.sectors,
            c.benchmark_weights or {},
        ]
        if (
            any(set(m) - set(self.tickers) for m in mappings)
            or set(c.restricted) - set(self.tickers)
            or any(set(g.members) - set(self.tickers) for g in c.groups.values())
        ):
            raise ValueError("Constraint outside universe")
        if c.concentration > float(self.costs.position_limit):
            raise ValueError("Risk concentration exceeds M4 position limit")
        return self

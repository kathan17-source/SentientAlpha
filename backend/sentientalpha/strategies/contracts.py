"""Closed strategy grammar and predeclared chronological research configurations."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Costs, Frozen
from sentientalpha.backtesting.evaluation import Split
from sentientalpha.data.contracts import ticker_symbol, utc
from sentientalpha.optimization.estimation import OptimizationError


class DiscoveryError(OptimizationError):
    partial_history: dict | None = None


class Rule(Frozen):
    kind: Literal["compare", "all", "any"] = "compare"
    feature: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.]{0,119}$")
    operator: Literal["lt", "le", "gt", "ge", "eq"] | None = None
    threshold: float | None = Field(default=None, ge=-1e9, le=1e9)
    other_feature: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.]{0,119}$")
    children: list["Rule"] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def valid(self) -> "Rule":
        if self.kind == "compare":
            if (
                not self.feature
                or not self.operator
                or self.children
                or ((self.threshold is None) == (self.other_feature is None))
            ):
                raise ValueError("Comparison requires one feature, operator and exactly one RHS")
        elif len(self.children) < 2 or any(
            v is not None for v in (self.feature, self.operator, self.threshold, self.other_feature)
        ):
            raise ValueError("Boolean rules require 2–4 children and no comparison fields")
        if self.depth() > 3 or self.leaves() > 6:
            raise ValueError("Rule depth/condition budget exceeded")
        return self

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)

    def leaves(self) -> int:
        return 1 if self.kind == "compare" else sum(c.leaves() for c in self.children)

    def features(self) -> set[str]:
        return {x for x in (self.feature, self.other_feature) if x} | set().union(
            *(c.features() for c in self.children)
        )


class Definition(Frozen):
    entry: Rule
    exit: Rule | None = None
    exposure: float = Field(default=1.0, gt=0, le=1)
    holding_sessions: int | None = Field(default=None, ge=1, le=252, strict=True)
    rebalance: Literal["daily", "weekly", "monthly"] = "daily"
    missing_policy: Literal["hold", "cash"] = "cash"
    version: Literal["7.0.0"] = "7.0.0"

    @model_validator(mode="after")
    def limited(self) -> "Definition":
        if self.entry.leaves() + (self.exit.leaves() if self.exit else 0) > 8:
            raise ValueError("Strategy condition budget exceeded")
        return self


class Axis(Frozen):
    feature: str = Field(pattern=r"^[a-z][a-z0-9_.]{0,119}$")
    operator: Literal["lt", "le", "gt", "ge", "eq"] = "gt"
    thresholds: list[float] = Field(default_factory=list, max_length=20)
    other_features: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def valid(self) -> "Axis":
        if bool(self.thresholds) == bool(self.other_features):
            raise ValueError("Declare numeric thresholds or feature comparisons")
        for value in self.thresholds:
            Rule(feature=self.feature, operator=self.operator, threshold=value)
        for other in self.other_features:
            Rule(feature=self.feature, operator=self.operator, other_feature=other)
        return self


class Space(Frozen):
    axes: list[Axis] = Field(min_length=1, max_length=24)
    maximum_conditions: int = Field(default=2, ge=1, le=3, strict=True)
    joins: list[Literal["all", "any"]] = Field(default=["all"], min_length=1, max_length=2)
    holdings: list[int | None] = Field(
        default_factory=lambda: [None, 10], min_length=1, max_length=4
    )
    schedules: list[Literal["daily", "weekly", "monthly"]] = Field(
        default=["daily"], min_length=1, max_length=3
    )
    exposure: float = Field(default=1.0, gt=0, le=1)
    include_exit: bool = True

    @field_validator("holdings")
    @classmethod
    def periods(cls, values: list[int | None]) -> list[int | None]:
        if any(v is not None and (type(v) is not int or not 1 <= v <= 252) for v in values):
            raise ValueError("Invalid holding period")
        return values


class Fitness(Frozen):
    minimum_validation_score: float = Field(default=0.0, ge=-5, le=5)
    minimum_sessions: int = Field(default=40, ge=5, le=1260, strict=True)
    minimum_closed_lots: int = Field(default=5, ge=1, le=1000, strict=True)
    minimum_signal_coverage: float = Field(default=0.7, ge=0, le=1)
    drawdown_weight: float = Field(default=0.2, ge=0, le=10)
    turnover_weight: float = Field(default=0.1, ge=0, le=10)
    complexity_weight: float = Field(default=0.1, ge=0, le=10)
    instability_weight: float = Field(default=0.1, ge=0, le=10)
    turnover_scale: float = Field(default=5.0, gt=0, le=100)
    maximum_turnover: float = Field(default=20.0, gt=0, le=10000)
    selection_tolerance: float = Field(default=0.01, ge=0, le=0.2)


class Request(Frozen):
    dataset_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    sentiment_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    ml_model_ids: list[str] = Field(default_factory=list, max_length=12)
    ml_horizon: Literal[1, 5, 10] = 1
    tickers: list[str] = Field(min_length=1, max_length=50)
    source_as_of: datetime
    information_policy: Literal["online", "research_replay", "retrospective"] = "online"
    sentiment_provenance: Literal["genuine", "synthetic_fixture"] = "genuine"
    windows: list[Split] = Field(min_length=1, max_length=8)
    training_mode: Literal["rolling", "expanding"] = "rolling"
    space: Space
    algorithm: Literal["random", "grid"] = "random"
    candidates: int = Field(default=100, ge=1, le=1000, strict=True)
    seed: int = Field(default=71, ge=0, le=2**31 - 1, strict=True)
    costs: Costs = Field(default_factory=Costs)
    fitness: Fitness = Field(default_factory=Fitness)
    capital: float = Field(default=100000.0, gt=0, le=1e12)
    seconds: int = Field(default=120, ge=1, le=600, strict=True)
    maximum_simulations: int = Field(default=2500, ge=10, le=5000, strict=True)
    robustness: bool = True
    holdout_history: Literal["new_reservation", "previously_inspected"] = "new_reservation"
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")

    @field_validator("source_as_of")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, v: list[str]) -> list[str]:
        result = sorted(ticker_symbol(t) for t in v)
        if len(set(result)) != len(result):
            raise ValueError("Duplicate securities")
        return result

    @model_validator(mode="after")
    def bounded(self) -> "Request":
        for i, w in enumerate(self.windows):
            if (
                not date(2000, 1, 1) <= w.train_start < w.test_end <= date(2034, 12, 31)
                or (w.test_end - self.windows[0].train_start).days > 3660
            ):
                raise ValueError("At most ten years within supported calendars")
            if i and (
                w.test_start <= self.windows[i - 1].test_end
                or w.train_end <= self.windows[i - 1].train_end
            ):
                raise ValueError("Test windows must be disjoint and training must advance")
        if self.training_mode == "expanding" and any(
            w.train_start != self.windows[0].train_start for w in self.windows
        ):
            raise ValueError("Expanding history retains its start")
        if (
            2 * self.candidates * len(self.windows) + 20 * len(self.windows)
            > self.maximum_simulations
        ):
            raise ValueError("Declared candidate/fold workload exceeds simulation budget")
        if self.space.exposure / len(self.tickers) > float(self.costs.position_limit):
            raise ValueError("Requested target exceeds the per-position execution limit")
        return self

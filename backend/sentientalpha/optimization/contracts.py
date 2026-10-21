"""Validated estimator, constraint and research configurations."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Frozen
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.data.calendar import session_open, sessions_in_range
from sentientalpha.data.contracts import ticker_symbol, utc

Method = Literal[
    "equal_weight", "minimum_variance", "mean_variance", "maximum_sharpe", "risk_parity"
]


class Group(Frozen):
    members: list[str] = Field(min_length=1, max_length=50)
    minimum: float = Field(default=0, ge=0, le=1)
    maximum: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def valid(self) -> "Group":
        if self.minimum > self.maximum or len(set(self.members)) != len(self.members):
            raise ValueError("Invalid group bound or duplicated members")
        return self


class Constraints(Frozen):
    minimum: dict[str, float] = Field(default_factory=dict, max_length=50)
    maximum: dict[str, float] = Field(default_factory=dict, max_length=50)
    concentration: float = Field(default=1, gt=0, le=1)
    cash_minimum: float = Field(default=0, ge=0, le=1)
    cash_maximum: float = Field(default=0, ge=0, le=1)
    invested_maximum: float = Field(default=1, gt=0, le=1)
    restricted: list[str] = Field(default_factory=list, max_length=50)
    groups: dict[str, Group] = Field(default_factory=dict, max_length=20)
    sectors: dict[str, str] = Field(default_factory=dict, max_length=50)
    sector_maximum: dict[str, float] = Field(default_factory=dict, max_length=20)
    volatility_maximum: float | None = Field(default=None, ge=1e-6, le=10)
    variance_maximum: float | None = Field(default=None, ge=1e-12, le=100)
    turnover_maximum: float | None = Field(default=None, ge=0, le=1)
    benchmark_weights: dict[str, float] | None = None
    tracking_error_maximum: float | None = Field(default=None, ge=1e-6, le=10)

    @model_validator(mode="after")
    def valid(self) -> "Constraints":
        for mapping in (
            self.minimum,
            self.maximum,
            self.sector_maximum,
            self.benchmark_weights or {},
        ):
            if any(v < 0 or v > 1 for v in mapping.values()):
                raise ValueError("Invalid allocation bounds")
        if self.cash_minimum > self.cash_maximum:
            raise ValueError("Conflicting cash bounds")
        if self.tracking_error_maximum is not None and self.benchmark_weights is None:
            raise ValueError("Tracking error requires compatible benchmark weights")
        if self.benchmark_weights is not None and sum(self.benchmark_weights.values()) > 1 + 1e-10:
            raise ValueError("Benchmark leverage is unsupported")
        if set(self.sector_maximum) - set(self.sectors.values()):
            raise ValueError("Sector cap has no declared members")
        return self


class Estimator(Frozen):
    mean: Literal["historical", "exponential", "shrinkage"] = "shrinkage"
    covariance: Literal["sample", "exponential", "diagonal_shrinkage"] = "diagonal_shrinkage"
    lookback: int = Field(default=252, ge=10, le=1260, strict=True)
    minimum_observations: int = Field(default=60, ge=5, le=1260, strict=True)
    decay: float = Field(default=0.97, gt=0, lt=1)
    shrinkage: float = Field(default=0.25, ge=0, le=1)
    prior_annual_return: float = Field(default=0, ge=-1, le=2)
    eigenvalue_floor: float = Field(default=1e-10, ge=0, le=0.01)
    history: Literal["rolling", "expanding"] = "rolling"

    @model_validator(mode="after")
    def valid(self) -> "Estimator":
        if self.minimum_observations > self.lookback:
            raise ValueError("Minimum observations exceeds bounded history")
        return self


class Objective(Frozen):
    method: Method = "minimum_variance"
    risk_aversion: float = Field(default=5, gt=0, le=10000)
    risk_free_annual: float = Field(default=0, ge=-0.2, le=0.5)
    horizon_sessions: int = Field(default=21, ge=1, le=252, strict=True)
    turnover_penalty: float = Field(default=0, ge=0, le=1)
    asset_cost_rates: dict[str, float] = Field(default_factory=dict, max_length=50)
    rebalance_threshold: float = Field(default=0, ge=0, le=1)
    target_return_annual: float | None = Field(default=None, ge=-2, le=5)
    maximum_iterations: int = Field(default=500, ge=1, le=1000, strict=True)
    tolerance: float = Field(default=1e-9, ge=1e-12, le=1e-6)
    fallback: Literal["none", "equal_weight"] = "none"
    seconds: int = Field(default=10, ge=1, le=60, strict=True)

    @field_validator("asset_cost_rates")
    @classmethod
    def rates(cls, value: dict[str, float]) -> dict[str, float]:
        if any(v < 0 or v > 0.1 for v in value.values()):
            raise ValueError("Cost rates must be fractions of traded notional, within 0..0.1")
        return value


class Sentiment(Frozen):
    dataset_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    column: str = Field(min_length=1, max_length=160)
    train_start: date
    train_end: date
    minimum_samples: int = Field(default=60, ge=10, le=5000, strict=True)
    fallback: Literal["unavailable", "price_only"] = "unavailable"
    provenance: Literal["verified_history", "synthetic_fixture"] = "verified_history"

    @model_validator(mode="after")
    def valid(self) -> "Sentiment":
        if self.train_start >= self.train_end or not self.column.startswith(
            ("sent_mean__", "sent_momentum__", "sent_surprise__")
        ):
            raise ValueError(
                "Choose one registered level/momentum/surprise and a chronological"
                " training interval"
            )
        return self


class OptimizationRequest(Frozen):
    price_dataset_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    tickers: list[str] = Field(min_length=1, max_length=50)
    history_start: date
    estimation_end: date
    decision_at: datetime
    source_as_of: datetime
    information_policy: Literal["online", "research_replay"] = "online"
    estimator: Estimator = Field(default_factory=Estimator)
    objective: Objective = Field(default_factory=Objective)
    constraints: Constraints = Field(default_factory=Constraints)
    current_weights: dict[str, float] = Field(default_factory=dict, max_length=50)
    sentiment: Sentiment | None = None

    @field_validator("decision_at", "source_as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, values: list[str]) -> list[str]:
        result = sorted(ticker_symbol(v) for v in values)
        if len(set(result)) != len(result):
            raise ValueError("Duplicate assets")
        return result

    @model_validator(mode="after")
    def valid(self) -> "OptimizationRequest":
        if (
            not date(2000, 1, 1)
            <= self.history_start
            <= self.estimation_end
            <= self.decision_at.date()
            <= date(2034, 12, 31)
            or (self.estimation_end - self.history_start).days > 3660
        ):
            raise ValueError("Estimation must precede decision and remain within ten-year coverage")
        if self.decision_at > self.source_as_of:
            raise ValueError("Decision cannot exceed frozen source cutoff")
        c = self.constraints
        mappings: list[dict[str, Any]] = [
            c.minimum,
            c.maximum,
            c.sectors,
            self.current_weights,
            self.objective.asset_cost_rates,
            c.benchmark_weights or {},
        ]
        if (
            any(set(m) - set(self.tickers) for m in mappings)
            or set(c.restricted) - set(self.tickers)
            or any(set(g.members) - set(self.tickers) for g in c.groups.values())
        ):
            raise ValueError("Constraint/holding outside fixed universe")
        if (
            any(v < 0 or v > 1 for v in self.current_weights.values())
            or sum(self.current_weights.values()) > 1 + 1e-10
        ):
            raise ValueError("Invalid current long-only weights")
        if self.sentiment and self.sentiment.train_end >= self.estimation_end:
            raise ValueError(
                "Sentiment fitting interval must end before estimation/evaluation boundary"
            )
        return self


class FrontierRequest(Frozen):
    optimization: OptimizationRequest
    risk_aversions: list[float] = Field(
        default_factory=lambda: [0.5, 1, 2, 5, 10, 25], min_length=1, max_length=25
    )

    @field_validator("risk_aversions")
    @classmethod
    def values(cls, values: list[float]) -> list[float]:
        if any(v <= 0 or v > 10000 for v in values) or len(set(values)) != len(values):
            raise ValueError("Invalid frontier grid")
        return sorted(values)


def default_methods() -> list[Method]:
    return ["equal_weight", "minimum_variance", "mean_variance", "maximum_sharpe", "risk_parity"]


class ResearchRequest(Frozen):
    optimization: OptimizationRequest
    backtest: BacktestRequest
    methods: list[Method] = Field(default_factory=default_methods, min_length=1, max_length=5)
    rebalance: Literal["monthly", "quarterly", "explicit"] = "monthly"
    rebalance_dates: list[date] = Field(default_factory=list, max_length=60)
    maximum_rebalances: int = Field(default=60, ge=1, le=60, strict=True)
    include_sentiment: bool = False
    sentiment_ablations: list[Sentiment] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def causal(self) -> "ResearchRequest":
        o, b = self.optimization, self.backtest
        if (
            o.tickers != b.tickers
            or o.information_policy != b.information_policy
            or o.source_as_of != b.source_as_of
        ):
            raise ValueError("Research inputs must share universe, policy and source cutoff")
        if (
            o.estimation_end >= b.start
            or not (sessions := sessions_in_range(b.calendar, b.start, b.end))
            or o.decision_at >= session_open(b.calendar, sessions[0])
        ):
            raise ValueError("Pre-evaluation estimates must end before untouched evaluation begins")
        if o.objective.risk_free_annual != 0:
            raise ValueError(
                "M4 historical cash has zero yield; nonzero risk-free return is "
                "static optimization only"
            )
        if o.constraints.concentration > b.costs.position_limit:
            raise ValueError("Optimizer concentration cannot exceed execution position limit")
        if any(
            a.train_end >= o.estimation_end or a.train_start < o.history_start
            for a in self.sentiment_ablations
        ):
            raise ValueError("Ablation training must be inside pre-evaluation history")
        if len({(a.dataset_id, a.column) for a in self.sentiment_ablations}) != len(
            self.sentiment_ablations
        ):
            raise ValueError("Duplicate ablations")
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("Duplicated methods")
        if self.rebalance == "explicit" and not self.rebalance_dates:
            raise ValueError("Explicit schedule requires dates")
        if self.rebalance != "explicit" and self.rebalance_dates:
            raise ValueError("Dates require explicit schedule")
        if any(d < b.start or d > b.end for d in self.rebalance_dates) or len(
            set(self.rebalance_dates)
        ) != len(self.rebalance_dates):
            raise ValueError("Invalid rebalance dates")
        if b.strategy.feature_dataset_id or set(b.benchmarks) - {"SPY"} or b.actions:
            raise ValueError(
                "Research uses its frozen return snapshot; nested M4 "
                "baselines/actions are unsupported"
            )
        return self


class WalkResearch(Frozen):
    research: ResearchRequest
    train_sessions: int = Field(default=126, ge=10, le=1260, strict=True)
    validation_sessions: int = Field(default=21, ge=1, le=252, strict=True)
    test_sessions: int = Field(default=63, ge=5, le=252, strict=True)
    step_sessions: int = Field(default=63, ge=5, le=252, strict=True)
    mode: Literal["rolling", "expanding"] = "rolling"
    maximum_folds: int = Field(default=10, ge=1, le=20, strict=True)

    @model_validator(mode="after")
    def disjoint(self) -> "WalkResearch":
        if self.step_sessions < self.test_sessions:
            raise ValueError("Overlapping OOS windows refused")
        return self

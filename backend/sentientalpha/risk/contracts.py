"""Strict portfolio/market clocks and immutable, opt-in simulation risk policy."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Costs, Frozen
from sentientalpha.data.contracts import ticker_symbol, utc
from sentientalpha.optimization.contracts import Constraints, Estimator


class Price(Frozen):
    ticker: str
    asset_id: str = Field(min_length=1, max_length=80)
    value: Decimal | None = Field(default=None, gt=0)
    observed_at: datetime
    available_at: datetime
    basis: Literal["raw", "adjusted", "unknown"] = "raw"
    currency: Literal["USD"] = "USD"
    asset_type: Literal["equity"] = "equity"
    suspended: bool = False
    source: str = Field(min_length=1, max_length=240)

    @field_validator("ticker")
    @classmethod
    def symbol(cls, v: str) -> str:
        return ticker_symbol(v)

    @field_validator("observed_at", "available_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @model_validator(mode="after")
    def valid(self) -> "Price":
        if self.observed_at > self.available_at:
            raise ValueError("Observation follows availability")
        return self


class Equity(Frozen):
    kind: Literal["opening", "closing", "valuation"] = "valuation"
    at: datetime
    value: Decimal = Field(gt=0)

    @field_validator("at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)


class Order(Frozen):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def symbol(cls, value: str) -> str:
        return ticker_symbol(value)


class PortfolioState(Frozen):
    portfolio_id: str = Field(min_length=1, max_length=80)
    at: datetime
    valuation_at: datetime
    cash: Decimal = Field(ge=0)
    equity: Decimal = Field(gt=0)
    quantities: dict[str, Decimal] = Field(max_length=50)
    prices: list[Price] = Field(max_length=50)
    equity_history: list[Equity] = Field(default_factory=list, max_length=2520)
    pending_orders: list[Order] = Field(default_factory=list, max_length=100)
    calendar: Literal["weekday", "XNYS"] = "XNYS"
    provenance: Literal["online", "research_replay", "retrospective", "synthetic_fixture"]

    @field_validator("at", "valuation_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @model_validator(mode="after")
    def valid(self) -> "PortfolioState":
        if self.valuation_at > self.at:
            raise ValueError("Future valuation")
        if len({p.ticker for p in self.prices}) != len(self.prices):
            raise ValueError("Duplicate prices")
        if any(q < 0 for q in self.quantities.values()):
            raise ValueError("Shorts and margin unsupported")
        if any(e.at > self.at for e in self.equity_history):
            raise ValueError("Future equity contaminates drawdown")
        if any(
            a.at >= b.at for a, b in zip(self.equity_history, self.equity_history[1:], strict=False)
        ):
            raise ValueError("Equity history must be unique chronological snapshots")
        mapping = {p.ticker: p for p in self.prices}
        if set(self.quantities) - set(mapping):
            raise ValueError("Position missing asset identity")
        if any(o.ticker not in mapping for o in self.pending_orders):
            raise ValueError("Pending order references an unsupported security")
        if len({p.asset_id for p in self.prices}) != len(self.prices):
            raise ValueError("Conflicting security identifiers")
        if all(mapping[t].value is not None for t, q in self.quantities.items() if q):
            expected = self.cash + sum(
                q * (mapping[t].value or Decimal(0)) for t, q in self.quantities.items()
            )
            if abs(expected - self.equity) > Decimal(".000001"):
                raise ValueError("Portfolio equity does not reconcile")
        return self


class ReturnObservation(Frozen):
    basis: Literal["raw", "adjusted"] = "raw"
    day: date
    available_at: datetime
    values: dict[str, float | None] = Field(max_length=50)
    source: str = Field(min_length=1, max_length=240)

    @field_validator("available_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @model_validator(mode="after")
    def valid(self) -> "ReturnObservation":
        if self.day > self.available_at.date():
            raise ValueError("Return available before observation")
        if any(v is not None and v <= -1 for v in self.values.values()):
            raise ValueError("Invalid simple return")
        return self


class VolumeObservation(Frozen):
    ticker: str
    day: date
    available_at: datetime
    volume: int | None = Field(default=None, ge=0, strict=True)
    close: float = Field(gt=0)
    source: str = Field(min_length=1, max_length=240)

    @field_validator("available_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @field_validator("ticker")
    @classmethod
    def symbol(cls, value: str) -> str:
        return ticker_symbol(value)

    @model_validator(mode="after")
    def valid(self) -> "VolumeObservation":
        if self.day > self.available_at.date():
            raise ValueError("Volume available before observation")
        return self


class Scenario(Frozen):
    id: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    effective_at: datetime
    kind: Literal["hypothetical", "historical"] = "hypothetical"
    broad_shock: float = Field(default=0.0, ge=-1, le=3)
    assets: dict[str, float] = Field(default_factory=dict, max_length=50)
    sectors: dict[str, float] = Field(default_factory=dict, max_length=30)
    start: date | None = None
    end: date | None = None

    @field_validator("effective_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @model_validator(mode="after")
    def valid(self) -> "Scenario":
        if any(not -1 <= v <= 3 for v in [*self.assets.values(), *self.sectors.values()]):
            raise ValueError("Finite linear-equity shocks must be within -100% and +300%")
        if self.kind == "historical":
            if (
                self.start is None
                or self.end is None
                or self.start > self.end
                or self.assets
                or self.sectors
                or self.broad_shock
            ):
                raise ValueError(
                    "Historical scenario needs only a chronological actual return window"
                )
        elif self.start is not None or self.end is not None:
            raise ValueError("Hypothetical shock has no observed historical window")
        return self


class Policy(Frozen):
    id: str = Field(default="baseline_simulation", min_length=1, max_length=80)
    version: str = Field(default="1", min_length=1, max_length=80)
    portfolio_id: str = Field(default="*", min_length=1, max_length=80)
    parent_definition_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    effective_at: datetime
    constraints: Constraints = Field(default_factory=lambda: Constraints(cash_maximum=1))
    estimator: Estimator = Field(default_factory=Estimator)
    confidence: float = Field(default=0.95, ge=0.5, lt=1)
    minimum_tail_mass: float = Field(default=5.0, ge=1, le=100)
    var_maximum: float | None = Field(default=None, ge=0, le=1)
    cvar_maximum: float | None = Field(default=None, ge=0, le=1)
    drawdown_maximum: float | None = Field(default=None, gt=0, le=1)
    drawdown_mode: Literal["no_new_risk", "cash"] = "no_new_risk"
    recovery_observations: int = Field(default=0, ge=0, le=252, strict=True)
    recovery_drawdown: float = Field(default=0.0, ge=0, lt=1)
    participation_maximum: float | None = Field(default=None, gt=0, le=1)
    minimum_dollar_volume: float | None = Field(default=None, ge=0)
    cost_fraction_maximum: float | None = Field(default=None, ge=0, le=1)
    volume_lookback: int = Field(default=20, ge=1, le=252, strict=True)
    minimum_volume_observations: int = Field(default=5, ge=1, le=252, strict=True)
    stale_days: int = Field(default=7, ge=1, le=30, strict=True)
    covariance_condition_maximum: float = Field(default=1e12, ge=1, le=1e16)
    correlation_maximum: float | None = Field(default=None, ge=0, le=1)
    stress_loss_maximum: float | None = Field(default=None, ge=0, le=1)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=12)
    industries: dict[str, str] = Field(default_factory=dict, max_length=50)
    industry_maximum: dict[str, float] = Field(default_factory=dict, max_length=30)
    missing_required: Literal["reject"] = "reject"
    adjustment: Literal["reject", "scale_to_cash"] = "reject"
    adjustment_steps: int = Field(default=20, ge=1, le=40, strict=True)

    @field_validator("effective_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @model_validator(mode="after")
    def valid(self) -> "Policy":
        if any(
            v > self.constraints.maximum.get(t, 1) or v > self.constraints.concentration
            for t, v in self.constraints.minimum.items()
        ):
            raise ValueError("Conflicting explicit asset bounds")
        if self.minimum_volume_observations > self.volume_lookback:
            raise ValueError("Conflicting volume sample bounds")
        if any(not 0 <= v <= 1 for v in self.industry_maximum.values()):
            raise ValueError("Invalid industry cap")
        if set(self.industry_maximum) - set(self.industries.values()):
            raise ValueError("Industry cap without classification")
        if self.stress_loss_maximum is not None and not self.scenarios:
            raise ValueError("Stress limit needs configured scenarios")
        if self.recovery_observations and (
            self.drawdown_maximum is None or self.recovery_drawdown >= self.drawdown_maximum
        ):
            raise ValueError("Explicit recovery threshold must precede drawdown breach")
        if len({s.id for s in self.scenarios}) != len(self.scenarios):
            raise ValueError("Duplicate scenario identity")
        if any(s.effective_at > self.effective_at for s in self.scenarios):
            raise ValueError("Scenario introduced after policy effective time")
        return self


class EvaluationRequest(Frozen):
    state: PortfolioState
    policy: Policy
    targets: dict[str, float] | None = Field(default=None, max_length=50)
    orders: list[Order] = Field(default_factory=list, max_length=50)
    returns: list[ReturnObservation] = Field(default_factory=list, max_length=1260)
    volumes: list[VolumeObservation] = Field(default_factory=list, max_length=12600)
    costs: Costs = Field(default_factory=Costs)
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")

    @model_validator(mode="after")
    def valid(self) -> "EvaluationRequest":
        if self.targets is not None and self.orders:
            raise ValueError("Choose targets or explicit orders")
        if any(r.basis != "raw" for r in self.returns):
            raise ValueError("Adjusted returns incompatible with raw simulation prices")
        universe = {p.ticker for p in self.state.prices}
        c = self.policy.constraints
        if (
            any(set(r.values) - universe for r in self.returns)
            or any(v.ticker not in universe for v in self.volumes)
            or any(set(m) - universe for m in [c.minimum, c.maximum, c.benchmark_weights or {}])
            or set(c.restricted) - universe
            or any(set(g.members) - universe for g in c.groups.values())
        ):
            raise ValueError("Risk inputs/constraints contain unsupported security references")
        if len({r.day for r in self.returns}) != len(self.returns):
            raise ValueError("Duplicate return dates")
        for scenario in self.policy.scenarios:
            if scenario.kind == "historical":
                assert scenario.start is not None and scenario.end is not None
                if (scenario.end - scenario.start).days > 1827:
                    raise ValueError("Historical scenario exceeds five-year calculation budget")
                if self.state.calendar == "XNYS" and not (
                    date(2000, 1, 1) <= scenario.start <= scenario.end <= date(2035, 12, 31)
                ):
                    raise ValueError("Historical scenario outside supported XNYS calendar")
        if self.policy.portfolio_id not in {"*", self.state.portfolio_id}:
            raise ValueError("Wrong portfolio policy")
        if self.policy.effective_at > self.state.at:
            raise ValueError("Future policy is unavailable")
        if len({(v.ticker, v.day) for v in self.volumes}) != len(self.volumes):
            raise ValueError("Duplicate volume observations")
        return self

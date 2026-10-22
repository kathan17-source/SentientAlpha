"""Bounded immutable requests and executable event records."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sentientalpha.data.contracts import ticker_symbol, utc


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Costs(Frozen):
    fixed: Decimal = Field(default=Decimal("1"), ge=0, le=1000)
    per_share: Decimal = Field(default=Decimal("0"), ge=0, le=10)
    percentage: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.1"))
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0, le=1000)
    participation: Decimal = Field(default=Decimal("0.01"), gt=0, le=1)
    minimum_volume: int = Field(default=1, ge=0, le=10**12, strict=True)
    unknown_volume: Literal["reject", "unlimited_approximation"] = "reject"
    minimum_quantity: int = Field(default=1, ge=1, le=10**6, strict=True)
    position_limit: Decimal = Field(default=Decimal("1"), gt=0, le=1)


class StrategySpec(Frozen):
    name: Literal["buy_hold", "equal_weight", "moving_average"] = "buy_hold"
    version: Literal["1.0.0"] = "1.0.0"
    rebalance: Literal["once", "daily", "weekly", "monthly", "signal"] = "once"
    allocation: dict[str, Decimal] | None = None
    feature_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    feature_column: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def safe_features(self) -> "StrategySpec":
        if self.name == "moving_average":
            if not self.feature_dataset_id or not self.feature_column:
                raise ValueError("Moving average requires an existing M2 snapshot and SMA column")
            if not self.feature_column.startswith("sma__window_"):
                raise ValueError("Only the existing SMA input is accepted; no prediction targets")
        elif self.feature_dataset_id or self.feature_column:
            raise ValueError("Feature inputs are only permitted for the moving average strategy")
        if self.allocation is not None:
            if len(self.allocation) > 50 or any(
                not v.is_finite() or v < 0 or v > 1 for v in self.allocation.values()
            ):
                raise ValueError("Invalid long-only allocation")
            if sum(self.allocation.values()) > 1:
                raise ValueError("Allocation cannot use leverage")
        return self


class Action(Frozen):
    ticker: str
    day: date
    kind: Literal["split", "dividend"]
    value: Decimal = Field(gt=0, le=1000000)
    known_at: datetime
    source: str = Field(min_length=1, max_length=160)

    @field_validator("known_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("ticker")
    @classmethod
    def symbol(cls, value: str) -> str:
        return ticker_symbol(value)


class Request(Frozen):
    tickers: list[str] = Field(min_length=1, max_length=50)
    provider: Literal["synthetic", "alphavantage"] = "synthetic"
    start: date
    end: date
    source_as_of: datetime
    capital: Decimal = Field(default=Decimal("100000"), gt=0, le=10**12)
    calendar: Literal["weekday", "XNYS"] = "weekday"
    information_policy: Literal["online", "research_replay"] = "online"
    price_convention: Literal["raw_daily_research_approximation"] = (
        "raw_daily_research_approximation"
    )
    strategy: StrategySpec = Field(default_factory=StrategySpec)
    costs: Costs = Field(default_factory=Costs)
    actions: list[Action] = Field(default_factory=list, max_length=1000)
    benchmarks: list[Literal["buy_hold", "equal_weight", "moving_average", "SPY"]] = Field(
        default_factory=list, max_length=4
    )
    seconds: int = Field(default=120, ge=1, le=300, strict=True)

    @field_validator("source_as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, values: list[str]) -> list[str]:
        result = sorted(ticker_symbol(v) for v in values)
        if len(set(result)) != len(result):
            raise ValueError("Duplicate universe members")
        return result

    @model_validator(mode="after")
    def valid(self) -> "Request":
        if (
            not date(2000, 1, 1) <= self.start <= self.end <= date(2034, 12, 31)
            or (self.end - self.start).days > 366 * 10
        ):
            raise ValueError(
                "Backtest range must be within calendar coverage and at most ten years"
            )
        if self.strategy.allocation is not None and set(self.strategy.allocation) - set(
            self.tickers
        ):
            raise ValueError("Allocation outside declared fixed universe")
        if len(set(self.benchmarks)) != len(self.benchmarks):
            raise ValueError("Duplicate benchmarks")
        if any(a.ticker not in self.tickers for a in self.actions):
            raise ValueError("Corporate action outside universe")
        if len({(a.ticker, a.day, a.kind) for a in self.actions}) != len(self.actions):
            raise ValueError("Duplicate corporate action")
        return self


@dataclass(frozen=True, slots=True)
class Bar:
    ticker: str
    day: date
    opening: Decimal | None
    close: Decimal | None
    volume: int | None
    available: datetime
    ingested: datetime
    source_id: str
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "available", utc(self.available))
        object.__setattr__(self, "ingested", utc(self.ingested))
        if self.available > self.ingested or self.revision < 1 or not self.source_id:
            raise ValueError("Invalid source clocks or identity")
        if any(v is not None and (not v.is_finite() or v <= 0) for v in (self.opening, self.close)):
            raise ValueError("Invalid raw executable price")
        if self.volume is not None and (type(self.volume) is not int or self.volume < 0):
            raise ValueError("Invalid tradable volume")


@dataclass(frozen=True, slots=True)
class Feature:
    ticker: str
    day: date
    value: Decimal | None
    ready: datetime
    online: datetime
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ready", utc(self.ready))
        object.__setattr__(self, "online", utc(self.online))
        if self.online < self.ready or self.value is not None and not self.value.is_finite():
            raise ValueError("Invalid feature timing/value")


@dataclass(frozen=True, slots=True)
class Snapshot:
    bars: tuple[Bar, ...]
    features: tuple[Feature, ...] = ()
    definitions: tuple[str, ...] = ()


class BacktestError(ValueError):
    def __init__(self, message: str, code: str = "invalid_backtest", status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status

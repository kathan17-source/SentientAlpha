"""Immutable operating modes and bounded, retry-safe commands."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Costs, Frozen
from sentientalpha.committee.contracts import Policy as CommitteePolicy
from sentientalpha.data.contracts import ticker_symbol, utc
from sentientalpha.optimization.contracts import Estimator
from sentientalpha.risk.contracts import Policy

Mode = Literal["forward_paper", "synthetic_demo", "historical_replay"]
Status = Literal["CREATED", "READY", "RUNNING", "PAUSED", "STOPPED", "FAILED"]


class Command(Frozen):
    key: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class Create(Command):
    mode: Mode
    tickers: list[str] = Field(min_length=1, max_length=50)
    capital: Decimal = Field(default=Decimal("100000"), gt=0, le=Decimal("1000000000"))
    provider: Literal["synthetic", "alphavantage"]
    history_start: date
    simulation_start: date | None = None
    historical_run_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    committee_policy: CommitteePolicy
    risk_policy: Policy
    costs: Costs = Field(default_factory=Costs)
    estimator: Estimator = Field(default_factory=lambda: Estimator(minimum_observations=20))
    strategy_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    model_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    sentiment_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    sentiment_column: str | None = Field(default=None, max_length=160)
    stale_hours: int = Field(default=48, ge=1, le=168, strict=True)
    maximum_reception_delay_hours: int = Field(default=36, ge=1, le=72, strict=True)
    execution_convention: Literal["next_observed_close_ioc"] = "next_observed_close_ioc"
    corporate_action_policy: Literal["pause_on_quality_warning_raw_prices"] = (
        "pause_on_quality_warning_raw_prices"
    )

    @field_validator("tickers")
    @classmethod
    def symbols(cls, values: list[str]) -> list[str]:
        result = sorted(ticker_symbol(v) for v in values)
        if len(set(result)) != len(result):
            raise ValueError("Duplicate tickers")
        return result

    @model_validator(mode="after")
    def compatible(self) -> "Create":
        if (self.mode == "synthetic_demo" and self.provider != "synthetic") or (
            self.mode == "forward_paper" and self.provider == "synthetic"
        ):
            raise ValueError("Synthetic provider and demo mode must be paired")
        if (self.simulation_start is not None) != (self.mode == "synthetic_demo"):
            raise ValueError("Only synthetic demonstrations accept a virtual start")
        if (self.historical_run_id is not None) != (self.mode == "historical_replay"):
            raise ValueError("Historical mode requires an existing M4 research run")
        if self.simulation_start and self.history_start >= self.simulation_start:
            raise ValueError("History must precede virtual start")
        if self.history_start < date(2000, 1, 1):
            raise ValueError("Unsupported history")
        if self.risk_policy.constraints.concentration > float(self.costs.position_limit):
            raise ValueError("Risk and execution position limits differ")
        if bool(self.sentiment_dataset_id) != bool(self.sentiment_column):
            raise ValueError("Sentiment requires dataset and column")
        return self


class Advance(Command):
    maximum_events: int = Field(default=1, ge=1, le=20, strict=True)
    through: date | None = None


class Update(Command):
    start: date
    end: date

    @model_validator(mode="after")
    def bounded(self) -> "Update":
        if self.start > self.end or (self.end - self.start).days > 14:
            raise ValueError("Provider update limited to fourteen days")
        return self


class Reconcile(Command):
    backtest_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")


def aware(value: datetime) -> datetime:
    return utc(value)

"""Public API contracts; decimals serialize as strings without losing precision."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sentientalpha.data.contracts import ticker_symbol, validate_range

ProviderName = Literal["synthetic", "alphavantage"]


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    provider: ProviderName = "synthetic"
    start: date
    end: date
    seed: int = Field(default=42, ge=0, le=2**31 - 1, strict=True)

    @field_validator("ticker")
    @classmethod
    def valid_ticker(cls, value: str) -> str:
        return ticker_symbol(value)

    @model_validator(mode="after")
    def chronological(self) -> "IngestRequest":
        validate_range(self.start, self.end)
        if self.provider != "synthetic" and self.seed != 42:
            raise ValueError("Seed only applies to synthetic data")
        return self


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ticker: str
    name: str
    sector: str
    currency: str


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    provider: str
    ticker: str
    requested_start: date
    requested_end: date
    status: str
    started_at: datetime
    completed_at: datetime | None
    inserted: int
    deduplicated: int
    error_code: str | None
    quality_report: dict[str, Any] | None
    parameters: dict[str, str | int]


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int
    available_at: datetime
    ingested_at: datetime
    availability_kind: str
    provider: str
    is_synthetic: bool
    checksum: str
    revision_no: int
    observed_at: datetime | None
    session_close_at: datetime | None
    calendar: str
    adjustment_status: str
    currency: str
    quality_flags: list[str]


class MarketResponse(BaseModel):
    ticker: str
    provider: ProviderName
    as_of: datetime
    prices: list[PriceResponse]
    next_offset: int | None
    price_basis: Literal["raw"] = "raw"
    currency: Literal["USD"] = "USD"
    availability_policy: str = "strict: available_at and ingested_at <= as_of"


class HealthResponse(BaseModel):
    status: str
    mode: str
    version: str
    real_trading_enabled: Literal[False] = False


class ErrorDetail(BaseModel):
    code: str
    message: str
    run_id: str | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail

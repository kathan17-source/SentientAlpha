"""Validated requests, pure input observations and bounded research contracts."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sentientalpha.data.contracts import PriceBar, ticker_symbol, utc, validate_range

MAX_INPUT_ROWS = 300_000
MAX_OUTPUT_CELLS = 5_000_000
MAX_COLUMNS = 128
MAX_WINDOW = 504


class FeatureError(Exception):
    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class FeatureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    parameters: dict[str, int | float] = Field(default_factory=dict, max_length=8)

    @field_validator("parameters", mode="before")
    @classmethod
    def numeric_parameters(cls, value: Any) -> Any:
        if not isinstance(value, dict) or any(type(v) not in {int, float} for v in value.values()):
            raise ValueError("Feature parameters must be numeric, never executable values")
        return value


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tickers: list[str] = Field(min_length=1, max_length=50)
    provider: Literal["synthetic", "alphavantage"] = "synthetic"
    start: date
    end: date
    as_of: datetime | None = None
    benchmark: str = "SPY"
    features: list[FeatureSpec] = Field(default_factory=list, max_length=64)
    groups: list[Literal["trend", "momentum", "volatility", "volume", "statistics", "relative"]] = (
        Field(default_factory=list, max_length=6)
    )
    price_basis: Literal["raw"] = "raw"
    gap_policy: Literal["reset", "reject"] = "reset"
    quality_policy: Literal["reject_flagged", "allow_flagged"] = "reject_flagged"
    processing_delay_seconds: int = Field(default=1, ge=1, le=3600, strict=True)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, values: list[str]) -> list[str]:
        normalized = [ticker_symbol(value) for value in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate tickers are not allowed")
        return sorted(normalized)

    @field_validator("benchmark")
    @classmethod
    def benchmark_symbol(cls, value: str) -> str:
        return ticker_symbol(value)

    @field_validator("as_of")
    @classmethod
    def cutoff(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc(value)

    @model_validator(mode="after")
    def dates(self) -> "GenerationRequest":
        validate_range(self.start, self.end)
        if self.features and self.groups:
            raise ValueError("Choose explicit features or groups, not both")
        return self


@dataclass(frozen=True)
class Observation:
    price_id: str
    asset_id: str
    bar: PriceBar
    ingested_at: datetime
    revision_no: int
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ingested_at", utc(self.ingested_at))
        if self.ingested_at < self.bar.available_at:
            raise FeatureError("invalid_timestamps", "Ingestion precedes source availability")
        if self.bar.calendar == "unknown" or self.bar.session_close_at is None:
            raise FeatureError(
                "unknown_metadata", "Re-ingest prices with known calendar/close metadata"
            )

    def fingerprint(self) -> dict[str, Any]:
        return {
            "id": self.price_id,
            "asset": self.asset_id,
            "content": self.bar.checksum,
            "ingested_at": self.ingested_at.isoformat(),
            "revision": self.revision_no,
            "quality_flags": self.quality_flags,
            "available_at": self.bar.available_at.isoformat(),
        }

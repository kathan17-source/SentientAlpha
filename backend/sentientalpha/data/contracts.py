"""Validated domain records. All prices are raw USD prices unless explicitly adjusted."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Protocol

AvailabilityKind = Literal["observed", "modeled", "verified"]
PRICE_UNIT = Decimal("0.00000001")


def ticker_symbol(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", value):
        raise ValueError("Invalid ticker; use 1–12 letters, digits, dots or hyphens")
    return value


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(UTC)


def price(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not Decimal("0") < result < Decimal("1e12"):
            raise ValueError("Prices must be finite, positive and below 1e12")
        rounded = result.quantize(PRICE_UNIT)
        if rounded <= 0 or rounded >= Decimal("1e12"):
            raise ValueError("Rounded price is outside supported precision or range")
        return rounded
    except InvalidOperation as exc:
        raise ValueError("Invalid price") from exc


@dataclass(frozen=True)
class PriceBar:
    ticker: str
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    available_at: datetime
    provider: str
    is_synthetic: bool
    availability_kind: AvailabilityKind
    adjusted_close: Decimal | None = None
    session_close_at: datetime | None = None
    calendar: str = "unknown"
    adjustment_status: Literal["not_supplied", "supplied", "unknown"] = "unknown"
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.session_date, date) or isinstance(self.session_date, datetime):
            raise ValueError("session_date must be a date, not a timestamp")
        if type(self.is_synthetic) is not bool:
            raise ValueError("is_synthetic must be a boolean")
        if self.currency != "USD":
            raise ValueError("Only USD observations are supported")
        if self.calendar not in {"unknown", "weekday", "XNYS"}:
            raise ValueError("Unsupported calendar")
        if self.adjustment_status not in {"unknown", "not_supplied", "supplied"}:
            raise ValueError("Invalid adjustment status")
        if self.adjustment_status == "supplied" and self.adjusted_close is None:
            raise ValueError("Supplied adjustment requires adjusted_close")
        if self.adjustment_status == "not_supplied" and self.adjusted_close is not None:
            raise ValueError("Adjusted close contradicts adjustment status")
        object.__setattr__(self, "ticker", ticker_symbol(self.ticker))
        for name in ("open", "high", "low", "close"):
            object.__setattr__(self, name, price(getattr(self, name)))
        if self.adjusted_close is not None:
            object.__setattr__(self, "adjusted_close", price(self.adjusted_close))
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("OHLC prices violate low/open/close/high ordering")
        if isinstance(self.volume, bool) or not isinstance(self.volume, int):
            raise ValueError("Volume must be an integer")
        if not 0 <= self.volume <= 9_223_372_036_854_775_807:
            raise ValueError("Volume must be a nonnegative signed 64-bit integer")
        object.__setattr__(self, "available_at", utc(self.available_at))
        if self.available_at.date() < self.session_date:
            raise ValueError("A daily bar cannot be available before its session")
        if self.session_close_at is not None:
            close_at = utc(self.session_close_at)
            object.__setattr__(self, "session_close_at", close_at)
            if close_at.date() != self.session_date or close_at > self.available_at:
                raise ValueError("Session close must match the session and precede availability")
        if self.availability_kind not in {"observed", "modeled", "verified"}:
            raise ValueError("Invalid availability kind")
        if not re.fullmatch(r"[a-z][a-z0-9_\-]{0,39}", self.provider):
            raise ValueError("Invalid provider identifier")
        if self.is_synthetic != (self.provider == "synthetic"):
            raise ValueError("Synthetic provenance must use the synthetic provider")
        if self.is_synthetic != (self.availability_kind == "modeled"):
            raise ValueError("Modeled availability is reserved for synthetic data")

    @property
    def checksum(self) -> str:
        """Economic content hash; fetch time is excluded to make repeat imports idempotent."""
        payload = {
            "ticker": self.ticker,
            "date": self.session_date.isoformat(),
            "ohlc": [str(self.open), str(self.high), str(self.low), str(self.close)],
            "adjusted_close": str(self.adjusted_close),
            "volume": self.volume,
            "provider": self.provider,
            "calendar": self.calendar,
            "session_close_at": self.session_close_at.isoformat()
            if self.session_close_at
            else None,
            "adjustment_status": self.adjustment_status,
            "currency": self.currency,
            "schema_version": 2,
            "synthetic": self.is_synthetic,
            "availability_kind": self.availability_kind,
            "asserted_available_at": (
                self.available_at.isoformat() if self.availability_kind != "observed" else None
            ),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class ProviderError(Exception):
    """Sanitized provider failure: never contains request URLs or API keys."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MarketDataProvider(Protocol):
    name: str

    @property
    def parameters(self) -> Mapping[str, str | int]: ...

    def fetch(self, ticker: str, start: date, end: date) -> list[PriceBar]: ...


def validate_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("Start date must not be after end date")
    if start < date(2000, 1, 1):
        raise ValueError("Dates before 2000 are outside the initial supported scope")
    if (end - start).days > 366 * 30:
        raise ValueError("A request may span at most 30 years")

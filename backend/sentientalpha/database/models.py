"""Core normalized storage. Content revisions are retained rather than overwritten."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, TypeEngine

from sentientalpha.data.contracts import PRICE_UNIT, price
from sentientalpha.database.base import Base as Base
from sentientalpha.database.base import UTCDateTime as UTCDateTime
from sentientalpha.database.base import new_id as new_id
from sentientalpha.database.base import now as now

EXPECTED_SCHEMA_REVISION = "0012_paper_operations"


class ExactPrice(TypeDecorator[Decimal]):
    """PostgreSQL NUMERIC; SQLite fixed-width decimal text for exact round trips/order."""

    impl = Numeric(20, 8)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        return dialect.type_descriptor(String(21) if dialect.name == "sqlite" else Numeric(20, 8))

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> Decimal | str | None:
        if value is None:
            return None
        normalized = price(value)
        return f"{normalized:021.8f}" if dialect.name == "sqlite" else normalized

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(str(value)).quantize(PRICE_UNIT)


SQLITE_PRICE_PATTERN = "[0-9]" * 12 + "." + "[0-9]" * 8
SQLITE_PRICE_ENCODING = (
    " AND ".join(
        f"{name} GLOB '{SQLITE_PRICE_PATTERN}'" for name in ("open", "high", "low", "close")
    )
    + f" AND (adjusted_close IS NULL OR adjusted_close GLOB '{SQLITE_PRICE_PATTERN}')"
)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticker: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    sector: Mapped[str] = mapped_column(String(80), default="Unclassified")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint("requested_start <= requested_end", name="valid_run_dates"),
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="valid_run_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(40))
    ticker: Mapped[str] = mapped_column(String(12))
    requested_start: Mapped[date] = mapped_column(Date)
    requested_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    deduplicated: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    parameters: Mapped[dict[str, str | int]] = mapped_column(JSON, default=dict)
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "provider", "session_date", "ingestion_run_id", name="uq_price_run"
        ),
        CheckConstraint(
            "CAST(low AS NUMERIC) > 0 AND low <= open AND low <= close", name="valid_low"
        ),
        CheckConstraint("high >= open AND high >= close", name="valid_high"),
        CheckConstraint("volume >= 0", name="valid_volume"),
        CheckConstraint(
            "open <= '999999999999.99999999' AND high <= '999999999999.99999999' "
            "AND low <= '999999999999.99999999' AND close <= '999999999999.99999999' "
            "AND (adjusted_close IS NULL OR adjusted_close <= '999999999999.99999999')",
            name="finite_price_bounds",
        ),
        UniqueConstraint(
            "asset_id", "provider", "session_date", "revision_no", name="uq_price_revision"
        ),
        CheckConstraint("revision_no > 0", name="valid_revision"),
        CheckConstraint("available_at <= ingested_at", name="availability_before_ingestion"),
        CheckConstraint(
            "observed_at IS NULL OR observed_at <= ingested_at", name="observation_before_ingestion"
        ),
        CheckConstraint(
            "session_close_at IS NULL OR session_close_at <= available_at",
            name="close_before_availability",
        ),
        CheckConstraint("calendar IN ('unknown', 'weekday', 'XNYS')", name="valid_calendar"),
        CheckConstraint(
            "adjustment_status IN ('unknown', 'not_supplied', 'supplied')",
            name="valid_adjustment_status",
        ),
        CheckConstraint(
            "adjustment_status != 'supplied' OR adjusted_close IS NOT NULL",
            name="supplied_adjustment",
        ),
        CheckConstraint(
            "adjustment_status != 'not_supplied' OR adjusted_close IS NULL",
            name="absent_adjustment",
        ),
        CheckConstraint("currency = 'USD'", name="supported_currency"),
        CheckConstraint(
            "(is_synthetic AND provider = 'synthetic' AND availability_kind = 'modeled') OR "
            "(NOT is_synthetic AND provider != 'synthetic' AND availability_kind != 'modeled')",
            name="consistent_provenance",
        ),
        CheckConstraint(
            "adjusted_close IS NULL OR CAST(adjusted_close AS NUMERIC) > 0", name="valid_adjusted"
        ),
        CheckConstraint(
            "availability_kind IN ('observed', 'modeled', 'verified')", name="valid_availability"
        ),
        CheckConstraint(SQLITE_PRICE_ENCODING, name="valid_decimal_encoding").ddl_if(
            dialect="sqlite"
        ),
        Index("ix_price_asof", "asset_id", "provider", "session_date", "ingested_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    ingestion_run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"))
    session_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal] = mapped_column(ExactPrice())
    high: Mapped[Decimal] = mapped_column(ExactPrice())
    low: Mapped[Decimal] = mapped_column(ExactPrice())
    close: Mapped[Decimal] = mapped_column(ExactPrice())
    adjusted_close: Mapped[Decimal | None] = mapped_column(ExactPrice())
    volume: Mapped[int] = mapped_column(BigInteger)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    availability_kind: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    checksum: Mapped[str] = mapped_column(String(64))
    revision_no: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    session_close_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    calendar: Mapped[str] = mapped_column(String(16), server_default="unknown")
    adjustment_status: Mapped[str] = mapped_column(String(16), server_default="unknown")
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")


# Register feature metadata on Base without widening the market-data model module.
from sentientalpha.database import backtest_models as backtest_models  # noqa: E402
from sentientalpha.database import committee_models as committee_models  # noqa: E402
from sentientalpha.database import ml_models as ml_models  # noqa: E402
from sentientalpha.database import optimization_models as optimization_models  # noqa: E402
from sentientalpha.database import paper_models as paper_models  # noqa: E402
from sentientalpha.database import risk_models as risk_models  # noqa: E402
from sentientalpha.database import sentiment_models as sentiment_models  # noqa: E402
from sentientalpha.database import strategy_models as strategy_models  # noqa: E402
from sentientalpha.database.feature_models import FeatureDataset as FeatureDataset  # noqa: E402
from sentientalpha.database.feature_models import FeatureInput as FeatureInput  # noqa: E402
from sentientalpha.database.feature_models import FeatureRow as FeatureRow  # noqa: E402
from sentientalpha.database.feature_models import FeatureSourceAsset as FeatureSourceAsset  # noqa: E402

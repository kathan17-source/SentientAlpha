"""Immutable feature snapshots with relational source lineage and explicit staleness."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class FeatureDataset(Base):
    __tablename__ = "feature_datasets"
    __table_args__ = (
        CheckConstraint("status IN ('current', 'stale')", name="valid_feature_status"),
        CheckConstraint("start_date <= end_date", name="valid_feature_dates"),
        Index("ix_feature_configuration", "configuration_key", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True)
    configuration_key: Mapped[str] = mapped_column(String(64))
    source_hash: Mapped[str] = mapped_column(String(64))
    definition_hash: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(40))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    source_as_of: Mapped[datetime] = mapped_column(UTCDateTime())
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(16), default="current")
    invalidated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invalidation_reason: Mapped[str | None] = mapped_column(String(100))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    definitions: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    columns: Mapped[list[str]] = mapped_column(JSON)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer)


class FeatureSourceAsset(Base):
    __tablename__ = "feature_source_assets"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("feature_datasets.id"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12))
    role: Mapped[str] = mapped_column(String(16))
    __table_args__ = (Index("ix_feature_source_asset", "asset_id", "dataset_id"),)


class FeatureInput(Base):
    __tablename__ = "feature_inputs"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("feature_datasets.id"), primary_key=True)
    price_id: Mapped[str] = mapped_column(ForeignKey("market_prices.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("position >= 0", name="valid_feature_input_position"),)


class FeatureRow(Base):
    __tablename__ = "feature_rows"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("feature_datasets.id"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    market_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    values: Mapped[dict[str, float | None]] = mapped_column(JSON)
    reasons: Mapped[dict[str, str]] = mapped_column(JSON)
    timing: Mapped[dict[str, list[int]]] = mapped_column(JSON)
    __table_args__ = (
        CheckConstraint("position >= 0", name="valid_feature_row_position"),
        Index("ix_feature_rows_date", "dataset_id", "session_date", "asset_id"),
    )

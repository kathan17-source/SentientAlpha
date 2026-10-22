"""Versioned research, numeric artifacts and append-only application forecast records."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class MLExperiment(Base):
    __tablename__ = "ml_experiments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(32))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class MLModel(Base):
    __tablename__ = "ml_models"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("ml_experiments.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        UniqueConstraint("model_id", "ticker", "decision_at", name="uq_ml_forecast_version"),
        Index("ix_ml_ticker_time", "ticker", "decision_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    model_id: Mapped[str] = mapped_column(ForeignKey("ml_models.id"))
    ticker: Mapped[str] = mapped_column(String(12))
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime())
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

"""Audited discovery state, canonical candidates and persistent holdout-use records."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class DiscoveryRun(Base):
    __tablename__ = "strategy_discoveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(32))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class StrategyCandidate(Base):
    __tablename__ = "strategy_candidates"
    __table_args__ = (
        UniqueConstraint("discovery_id", "fold", "rule_hash", name="uq_discovery_rule"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    discovery_id: Mapped[str] = mapped_column(ForeignKey("strategy_discoveries.id"))
    fold: Mapped[int] = mapped_column(Integer)
    rule_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    validation_score: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class HoldoutUse(Base):
    __tablename__ = "strategy_holdouts"
    __table_args__ = (UniqueConstraint("discovery_id", "fold", name="uq_discovery_holdout"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    discovery_id: Mapped[str] = mapped_column(ForeignKey("strategy_discoveries.id"))
    fold: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(40))
    start: Mapped[date] = mapped_column(Date)
    end: Mapped[date] = mapped_column(Date)
    tickers: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24))

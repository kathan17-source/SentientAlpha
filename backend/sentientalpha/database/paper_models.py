"""Operational identities only; financial artifacts reuse M4 tables."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class PaperSession(Base):
    __tablename__ = "paper_sessions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('forward_paper','synthetic_demo','historical_replay')", name="paper_mode"
        ),
        CheckConstraint(
            "status IN ('CREATED','READY','RUNNING','PAUSED','STOPPED','FAILED')",
            name="paper_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    mode: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    ledger_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.id"), unique=True)
    last_day: Mapped[date | None] = mapped_column(Date())
    last_processing_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    warning: Mapped[str | None] = mapped_column(String(240))


class PaperEvent(Base):
    __tablename__ = "paper_events"
    __table_args__ = (
        UniqueConstraint("session_id", "key", name="uq_paper_command"),
        UniqueConstraint("session_id", "sequence", name="uq_paper_sequence"),
        UniqueConstraint("session_id", "market_day", name="uq_paper_market_day"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("paper_sessions.id"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    market_day: Mapped[date | None] = mapped_column(Date())
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    previous_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class PaperOrder(Base):
    __tablename__ = "paper_order_states"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("paper_sessions.id"), index=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("backtest_artifacts.id"), unique=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("committee_decisions.id"))


class PaperFillReceipt(Base):
    __tablename__ = "paper_fill_receipts"
    order_id: Mapped[str] = mapped_column(ForeignKey("paper_order_states.id"), primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("backtest_artifacts.id"), unique=True)

"""Durable committee audit records; execution artifacts remain in the M4 ledger."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class CommitteeRun(Base):
    __tablename__ = "committee_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(32))
    backtest_id: Mapped[str | None] = mapped_column(ForeignKey("backtest_runs.id"))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class CommitteeDecision(Base):
    __tablename__ = "committee_decisions"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_committee_decision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("committee_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime())
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

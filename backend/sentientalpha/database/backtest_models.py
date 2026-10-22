"""Immutable simulation manifests and ordered, paginated run artifacts."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed','insufficient_data','failed')", name="valid_backtest_status"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(24))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON)


class BacktestArtifact(Base):
    __tablename__ = "backtest_artifacts"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", "sequence", name="uq_backtest_artifact"),
        CheckConstraint("sequence >= 0", name="valid_artifact_sequence"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    sequence: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

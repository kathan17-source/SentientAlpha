"""Frozen optimization experiments reuse M4 run/artifact ledgers through explicit links."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('optimization','frontier','comparison','walk_forward')",
            name="valid_optimization_kind",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)

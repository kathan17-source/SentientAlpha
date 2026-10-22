"""Immutable policy versions and source-linked risk assessments/alerts, not a second ledger."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, now


class RiskPolicyVersion(Base):
    __tablename__ = "risk_policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version", name="uq_risk_policy_version"),)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(80))
    effective_at: Mapped[datetime] = mapped_column(UTCDateTime())
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (UniqueConstraint("committee_id", "sequence", name="uq_risk_committee_event"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    policy_key: Mapped[str] = mapped_column(ForeignKey("risk_policy_versions.key"))
    portfolio_id: Mapped[str] = mapped_column(String(80), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(40))
    phase: Mapped[str] = mapped_column(String(24))
    committee_id: Mapped[str | None] = mapped_column(ForeignKey("committee_runs.id"), index=True)
    backtest_id: Mapped[str | None] = mapped_column(ForeignKey("backtest_runs.id"))
    sequence: Mapped[int | None] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class RiskAlert(Base):
    __tablename__ = "risk_alerts"
    __table_args__ = (UniqueConstraint("assessment_id", "metric", name="uq_risk_alert"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("risk_assessments.id"), index=True)
    metric: Mapped[str] = mapped_column(String(240))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

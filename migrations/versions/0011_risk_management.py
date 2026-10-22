"""Immutable risk policies, portfolio assessments and idempotent source-linked alerts."""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0011_risk_management"
down_revision = "0010_investment_committee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_policy_versions",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("policy_id", sa.String(80), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("effective_at", UTCDateTime(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.UniqueConstraint("policy_id", "version", name="uq_risk_policy_version"),
    )
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("request_key", sa.String(80), unique=True),
        sa.Column(
            "policy_key", sa.String(64), sa.ForeignKey("risk_policy_versions.key"), nullable=False
        ),
        sa.Column("portfolio_id", sa.String(80), nullable=False),
        sa.Column("at", UTCDateTime(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(24), nullable=False),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("committee_runs.id")),
        sa.Column("backtest_id", sa.String(36), sa.ForeignKey("backtest_runs.id")),
        sa.Column("sequence", sa.Integer()),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("committee_id", "sequence", name="uq_risk_committee_event"),
    )
    for name in ["portfolio_id", "at", "committee_id"]:
        op.create_index("ix_risk_assessments_" + name, "risk_assessments", [name])
    op.create_table(
        "risk_alerts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "assessment_id", sa.String(64), sa.ForeignKey("risk_assessments.id"), nullable=False
        ),
        sa.Column("metric", sa.String(240), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("assessment_id", "metric", name="uq_risk_alert"),
    )
    op.create_index("ix_risk_alerts_assessment_id", "risk_alerts", ["assessment_id"])


def downgrade() -> None:
    op.drop_index("ix_risk_alerts_assessment_id", table_name="risk_alerts")
    op.drop_table("risk_alerts")
    for name in ["portfolio_id", "at", "committee_id"]:
        op.drop_index("ix_risk_assessments_" + name, table_name="risk_assessments")
    op.drop_table("risk_assessments")
    op.drop_table("risk_policy_versions")

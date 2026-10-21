"""Persistent local paper operations around existing M4 financial artifacts."""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0012_paper_operations"
down_revision = "0011_risk_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(80), unique=True, nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime()),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column(
            "ledger_id",
            sa.String(36),
            sa.ForeignKey("backtest_runs.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("last_day", sa.Date()),
        sa.Column("last_processing_at", UTCDateTime()),
        sa.Column("warning", sa.String(240)),
        sa.CheckConstraint(
            "mode IN ('forward_paper','synthetic_demo','historical_replay')", name="paper_mode"
        ),
        sa.CheckConstraint(
            "status IN ('CREATED','READY','RUNNING','PAUSED','STOPPED','FAILED')",
            name="paper_status",
        ),
    )
    op.create_table(
        "paper_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("paper_sessions.id"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("market_day", sa.Date()),
        sa.Column("processed_at", UTCDateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("session_id", "key", name="uq_paper_command"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_paper_sequence"),
        sa.UniqueConstraint("session_id", "market_day", name="uq_paper_market_day"),
    )
    op.create_index("ix_paper_events_session_id", "paper_events", ["session_id"])
    op.create_table(
        "paper_order_states",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("paper_sessions.id"), nullable=False),
        sa.Column(
            "artifact_id",
            sa.Integer(),
            sa.ForeignKey("backtest_artifacts.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "decision_id", sa.String(36), sa.ForeignKey("committee_decisions.id"), nullable=False
        ),
    )
    op.create_index("ix_paper_order_states_session_id", "paper_order_states", ["session_id"])
    op.create_table(
        "paper_fill_receipts",
        sa.Column(
            "order_id", sa.String(64), sa.ForeignKey("paper_order_states.id"), primary_key=True
        ),
        sa.Column(
            "artifact_id",
            sa.Integer(),
            sa.ForeignKey("backtest_artifacts.id"),
            unique=True,
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("paper_fill_receipts")
    op.drop_table("paper_order_states")
    op.drop_table("paper_events")
    op.drop_table("paper_sessions")

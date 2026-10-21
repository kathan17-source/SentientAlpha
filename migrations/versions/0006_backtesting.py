"""Persist immutable backtesting manifests and bounded artifacts.
Revision ID: 0006_backtesting
Revises: 0005_sentiment
"""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0006_backtesting"
down_revision = "0005_sentiment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("started_at", UTCDateTime(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed','insufficient_data','failed')", name="valid_backtest_status"
        ),
    )
    op.create_table(
        "backtest_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "kind", "sequence", name="uq_backtest_artifact"),
        sa.CheckConstraint("sequence >= 0", name="valid_artifact_sequence"),
    )
    op.create_index("ix_backtest_artifacts_run_id", "backtest_artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_backtest_artifacts_run_id", table_name="backtest_artifacts")
    op.drop_table("backtest_artifacts")
    op.drop_table("backtest_runs")

"""Committee parent and ordered decision audit; authoritative M4 child references."""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0010_investment_committee"
down_revision = "0009_strategy_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "committee_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False, unique=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("backtest_id", sa.String(36), sa.ForeignKey("backtest_runs.id")),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.create_table(
        "committee_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("committee_runs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("decision_at", UTCDateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_committee_decision"),
    )
    op.create_index("ix_committee_decisions_run_id", "committee_decisions", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_committee_decisions_run_id", table_name="committee_decisions")
    op.drop_table("committee_decisions")
    op.drop_table("committee_runs")

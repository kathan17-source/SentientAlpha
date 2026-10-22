"""Immutable optimization/research experiments.
Revision ID: 0007_optimization
Revises: 0006_backtesting
"""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0007_optimization"
down_revision = "0006_backtesting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('optimization','frontier','comparison','walk_forward')",
            name="valid_optimization_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("optimization_runs")

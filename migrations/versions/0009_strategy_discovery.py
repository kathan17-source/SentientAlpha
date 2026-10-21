"""Discovery registries and auditable holdout reservation/consumption."""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0009_strategy_discovery"
down_revision = "0008_machine_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_discoveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False, unique=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.create_table(
        "strategy_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "discovery_id", sa.String(36), sa.ForeignKey("strategy_discoveries.id"), nullable=False
        ),
        sa.Column("fold", sa.Integer(), nullable=False),
        sa.Column("rule_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("validation_score", sa.String(64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("discovery_id", "fold", "rule_hash", name="uq_discovery_rule"),
    )
    op.create_table(
        "strategy_holdouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "discovery_id", sa.String(36), sa.ForeignKey("strategy_discoveries.id"), nullable=False
        ),
        sa.Column("fold", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("start", sa.Date(), nullable=False),
        sa.Column("end", sa.Date(), nullable=False),
        sa.Column("tickers", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.UniqueConstraint("discovery_id", "fold", name="uq_discovery_holdout"),
    )


def downgrade() -> None:
    op.drop_table("strategy_holdouts")
    op.drop_table("strategy_candidates")
    op.drop_table("strategy_discoveries")

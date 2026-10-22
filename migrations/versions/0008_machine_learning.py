"""Financial ML research snapshots, numeric models and versioned forecasts."""

import sqlalchemy as sa
from alembic import op
from sentientalpha.database.base import UTCDateTime

revision = "0008_machine_learning"
down_revision = "0007_optimization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.create_table(
        "ml_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "experiment_id", sa.String(36), sa.ForeignKey("ml_experiments.id"), nullable=False
        ),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "ml_predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("ticker", sa.String(12), nullable=False),
        sa.Column("decision_at", UTCDateTime(), nullable=False),
        sa.Column("generated_at", UTCDateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("model_id", "ticker", "decision_at", name="uq_ml_forecast_version"),
    )
    op.create_index("ix_ml_ticker_time", "ml_predictions", ["ticker", "decision_at"])


def downgrade() -> None:
    op.drop_index("ix_ml_ticker_time", table_name="ml_predictions")
    op.drop_table("ml_predictions")
    op.drop_table("ml_models")
    op.drop_table("ml_experiments")

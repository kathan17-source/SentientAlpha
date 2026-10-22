"""Feature snapshots, selected assets, relational input lineage and wide output rows."""

import sqlalchemy as sa
from alembic import op

revision = "0004_feature_engine"
down_revision = "0003_exact_sqlite_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False, unique=True),
        sa.Column("configuration_key", sa.String(64), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("definition_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("source_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("invalidation_reason", sa.String(100)),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("definitions", sa.JSON(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('current', 'stale')", name="valid_feature_status"),
        sa.CheckConstraint("start_date <= end_date", name="valid_feature_dates"),
    )
    op.create_index("ix_feature_configuration", "feature_datasets", ["configuration_key", "status"])
    op.create_table(
        "feature_source_assets",
        sa.Column(
            "dataset_id", sa.String(36), sa.ForeignKey("feature_datasets.id"), primary_key=True
        ),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("ticker", sa.String(12), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
    )
    op.create_index("ix_feature_source_asset", "feature_source_assets", ["asset_id", "dataset_id"])
    op.create_table(
        "feature_inputs",
        sa.Column(
            "dataset_id", sa.String(36), sa.ForeignKey("feature_datasets.id"), primary_key=True
        ),
        sa.Column("price_id", sa.String(36), sa.ForeignKey("market_prices.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="valid_feature_input_position"),
    )
    op.create_table(
        "feature_rows",
        sa.Column(
            "dataset_id", sa.String(36), sa.ForeignKey("feature_datasets.id"), primary_key=True
        ),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("session_date", sa.Date(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("market_at", sa.DateTime(timezone=True)),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("timing", sa.JSON(), nullable=False),
        sa.CheckConstraint("position >= 0", name="valid_feature_row_position"),
    )
    op.create_index(
        "ix_feature_rows_date", "feature_rows", ["dataset_id", "session_date", "asset_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_feature_rows_date", table_name="feature_rows")
    op.drop_table("feature_rows")
    op.drop_table("feature_inputs")
    op.drop_index("ix_feature_source_asset", table_name="feature_source_assets")
    op.drop_table("feature_source_assets")
    op.drop_index("ix_feature_configuration", table_name="feature_datasets")
    op.drop_table("feature_datasets")

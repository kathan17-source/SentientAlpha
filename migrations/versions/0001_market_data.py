"""Create assets, ingestion audit and immutable price revisions."""

import sqlalchemy as sa
from alembic import op

revision = "0001_market_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(12), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("sector", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("ticker", sa.String(12), nullable=False),
        sa.Column("requested_start", sa.Date(), nullable=False),
        sa.Column("requested_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("deduplicated", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.CheckConstraint("requested_start <= requested_end", name="valid_run_dates"),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="valid_run_status"),
    )
    op.create_table(
        "market_prices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column(
            "ingestion_run_id", sa.String(36), sa.ForeignKey("ingestion_runs.id"), nullable=False
        ),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(20, 8)),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "asset_id", "provider", "session_date", "ingestion_run_id", name="uq_price_run"
        ),
        sa.CheckConstraint("low > 0 AND low <= open AND low <= close", name="valid_low"),
        sa.CheckConstraint("high >= open AND high >= close", name="valid_high"),
        sa.CheckConstraint("volume >= 0", name="valid_volume"),
        sa.CheckConstraint("adjusted_close IS NULL OR adjusted_close > 0", name="valid_adjusted"),
        sa.CheckConstraint(
            "availability_kind IN ('observed', 'modeled', 'verified')", name="valid_availability"
        ),
    )
    op.create_index(
        "ix_price_asof",
        "market_prices",
        [
            "asset_id",
            "provider",
            "session_date",
            "ingested_at",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_price_asof", table_name="market_prices")
    op.drop_table("market_prices")
    op.drop_table("ingestion_runs")
    op.drop_table("assets")

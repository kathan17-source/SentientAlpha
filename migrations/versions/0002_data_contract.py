"""Add auditable market timestamps, quality metadata and deterministic revisions.

Legacy rows retain their original content/checksum. Unknown metadata is explicitly unknown.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_data_contract"
down_revision = "0001_market_data"
branch_labels = None
depends_on = None

CONSTRAINTS = {
    "finite_price_bounds": (
        "open < 1000000000000 AND high < 1000000000000 AND low < 1000000000000 AND "
        "close < 1000000000000 AND (adjusted_close IS NULL OR adjusted_close < 1000000000000)"
    ),
    "valid_revision": "revision_no > 0",
    "availability_before_ingestion": "available_at <= ingested_at",
    "observation_before_ingestion": "observed_at IS NULL OR observed_at <= ingested_at",
    "close_before_availability": "session_close_at IS NULL OR session_close_at <= available_at",
    "valid_calendar": "calendar IN ('unknown', 'weekday', 'XNYS')",
    "valid_adjustment_status": "adjustment_status IN ('unknown', 'not_supplied', 'supplied')",
    "supplied_adjustment": "adjustment_status != 'supplied' OR adjusted_close IS NOT NULL",
    "absent_adjustment": "adjustment_status != 'not_supplied' OR adjusted_close IS NULL",
    "supported_currency": "currency = 'USD'",
    "consistent_provenance": (
        "(is_synthetic AND provider = 'synthetic' AND availability_kind = 'modeled') OR "
        "(NOT is_synthetic AND provider != 'synthetic' AND availability_kind != 'modeled')"
    ),
}


def upgrade() -> None:
    # Refuse invalid existing timestamps; do not silently rewrite research evidence.
    invalid = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM market_prices WHERE available_at > ingested_at")
    )
    if invalid:
        raise ValueError(
            "Legacy timestamp violations require an explicit data review before upgrade"
        )
    op.add_column("ingestion_runs", sa.Column("quality_report", sa.JSON(), nullable=True))
    op.add_column("market_prices", sa.Column("revision_no", sa.Integer(), nullable=True))
    op.get_bind().execute(
        sa.text(
            "WITH ranked AS (SELECT id, ROW_NUMBER() OVER (PARTITION BY asset_id, provider, "
            "session_date ORDER BY ingested_at, id) AS n FROM market_prices) "
            "UPDATE market_prices SET revision_no = "
            "(SELECT n FROM ranked WHERE ranked.id = market_prices.id)"
        )
    )
    with op.batch_alter_table("market_prices") as batch:
        batch.alter_column("revision_no", existing_type=sa.Integer(), nullable=False)
        batch.add_column(sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("session_close_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("calendar", sa.String(16), nullable=False, server_default="unknown")
        )
        batch.add_column(
            sa.Column("adjustment_status", sa.String(16), nullable=False, server_default="unknown")
        )
        batch.add_column(sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
        batch.add_column(sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"))
        batch.create_unique_constraint(
            "uq_price_revision", ["asset_id", "provider", "session_date", "revision_no"]
        )
        for name, expression in CONSTRAINTS.items():
            batch.create_check_constraint(name, expression)


def downgrade() -> None:
    with op.batch_alter_table("market_prices") as batch:
        for name in CONSTRAINTS:
            batch.drop_constraint(name, type_="check")
        batch.drop_constraint("uq_price_revision", type_="unique")
        for name in (
            "quality_flags",
            "currency",
            "adjustment_status",
            "calendar",
            "session_close_at",
            "observed_at",
            "revision_no",
        ):
            batch.drop_column(name)
    op.drop_column("ingestion_runs", "quality_report")

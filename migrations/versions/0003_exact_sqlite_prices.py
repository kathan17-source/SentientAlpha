"""Remove SQLite floating-point price storage; retain PostgreSQL NUMERIC.

Legacy conversion is recorded; digits lost by earlier numeric storage cannot be recovered.
"""

import json
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = "0003_exact_sqlite_prices"
down_revision = "0002_data_contract"
branch_labels = None
depends_on = None

FIELDS = ("open", "high", "low", "close", "adjusted_close")
UNIT = Decimal("0.00000001")
PATTERN = "[0-9]" * 12 + "." + "[0-9]" * 8
ENCODING = " AND ".join(f"{name} GLOB '{PATTERN}'" for name in FIELDS[:-1]) + (
    f" AND (adjusted_close IS NULL OR adjusted_close GLOB '{PATTERN}')"
)
NEW = {
    "valid_low": "CAST(low AS NUMERIC) > 0 AND low <= open AND low <= close",
    "valid_high": "high >= open AND high >= close",
    "valid_adjusted": "adjusted_close IS NULL OR CAST(adjusted_close AS NUMERIC) > 0",
    "finite_price_bounds": (
        "open <= '999999999999.99999999' AND high <= '999999999999.99999999' "
        "AND low <= '999999999999.99999999' AND close <= '999999999999.99999999' "
        "AND (adjusted_close IS NULL OR adjusted_close <= '999999999999.99999999')"
    ),
}
OLD = {
    "valid_low": "low > 0 AND low <= open AND low <= close",
    "valid_high": NEW["valid_high"],
    "valid_adjusted": "adjusted_close IS NULL OR adjusted_close > 0",
    "finite_price_bounds": (
        "open < 1000000000000 AND high < 1000000000000 AND low < 1000000000000 AND "
        "close < 1000000000000 AND (adjusted_close IS NULL OR adjusted_close < 1000000000000)"
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    legacy_rows = (
        list(bind.execute(sa.text("SELECT * FROM market_prices")).mappings()) if sqlite else []
    )
    with op.batch_alter_table("market_prices") as batch:
        for name in OLD:
            batch.drop_constraint(name, type_="check")
        if sqlite:
            for name in FIELDS:
                batch.alter_column(name, existing_type=sa.Numeric(20, 8), type_=sa.String(21))
    if sqlite:
        affected_runs: set[str] = set()

        def legacy_decimal(value: object) -> Decimal:
            # Match the old NUMERIC result adapter's 8-place interpretation of SQLite floats.
            return (Decimal(value) if isinstance(value, float) else Decimal(str(value))).quantize(
                UNIT
            )

        for row in legacy_rows:
            values = {
                name: None if row[name] is None else f"{legacy_decimal(row[name]):021.8f}"
                for name in FIELDS
            }
            flags = (
                json.loads(row["quality_flags"])
                if isinstance(row["quality_flags"], str)
                else row["quality_flags"]
            )
            values["quality_flags"] = json.dumps(
                sorted(set(flags + ["legacy_numeric_precision_unknown"]))
            )
            values["id"] = row["id"]
            bind.execute(
                sa.text(
                    "UPDATE market_prices SET "
                    + ", ".join(f"{name} = :{name}" for name in FIELDS)
                    + ", quality_flags = :quality_flags WHERE id = :id"
                ),
                values,
            )
            affected_runs.add(row["ingestion_run_id"])
        for run_id in affected_runs:
            raw = bind.scalar(
                sa.text("SELECT quality_report FROM ingestion_runs WHERE id = :id"), {"id": run_id}
            )
            report = json.loads(raw) if isinstance(raw, str) else raw
            report = report or {"state": "legacy_unverified", "transformations": []}
            report.setdefault("transformations", []).append(
                {
                    "migration": revision,
                    "operation": "legacy SQLite NUMERIC to decimal text",
                    "original_precision": "unknown; no reconstruction of lost digits",
                }
            )
            bind.execute(
                sa.text("UPDATE ingestion_runs SET quality_report = :report WHERE id = :id"),
                {"report": json.dumps(report), "id": run_id},
            )
    with op.batch_alter_table("market_prices") as batch:
        for name, expression in NEW.items():
            batch.create_check_constraint(name, expression)
        if sqlite:
            batch.create_check_constraint("valid_decimal_encoding", ENCODING)


def downgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        for row in bind.execute(
            sa.text("SELECT open, high, low, close, adjusted_close FROM market_prices")
        ):
            for value in row:
                if value is not None and Decimal(str(float(value))).quantize(UNIT) != Decimal(
                    value
                ):
                    raise ValueError(
                        "Lossy SQLite price downgrade refused; preserve exact-price data"
                    )
    with op.batch_alter_table("market_prices") as batch:
        for name in NEW:
            batch.drop_constraint(name, type_="check")
        if sqlite:
            batch.drop_constraint("valid_decimal_encoding", type_="check")
            for name in FIELDS:
                batch.alter_column(name, existing_type=sa.String(21), type_=sa.Numeric(20, 8))
        for name, expression in OLD.items():
            batch.create_check_constraint(name, expression)

"""Chronologically ordered ML inputs. No target/label columns are created or accepted."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.data.contracts import ticker_symbol, utc, validate_range
from sentientalpha.database.models import FeatureDataset, FeatureRow, FeatureSourceAsset
from sentientalpha.features.contracts import FeatureError
from sentientalpha.features.storage import get_dataset
from sentientalpha.features.timing import execution, instant, readiness


class MatrixRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    sentiment_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    tickers: list[str] | None = Field(default=None, max_length=50, min_length=1)
    columns: list[str] | None = Field(default=None, max_length=128, min_length=1)
    start: date
    end: date
    missing_policy: Literal["preserve", "drop_row", "raise"] = "preserve"
    decision_at: datetime | None = None
    availability_mode: Literal["online", "research"] = "online"
    allow_stale: bool = False
    limit: int = Field(default=500, ge=1, le=2000, strict=True)
    offset: int = Field(default=0, ge=0, le=1_000_000, strict=True)

    @field_validator("tickers")
    @classmethod
    def valid_symbols(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        result = [ticker_symbol(value) for value in values]
        if len(set(result)) != len(result):
            raise ValueError("Duplicate tickers")
        return sorted(result)

    @field_validator("decision_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc(value)

    @model_validator(mode="after")
    def chronological(self) -> "MatrixRequest":
        validate_range(self.start, self.end)
        if self.columns and len(set(self.columns)) != len(self.columns):
            raise ValueError("Duplicate feature columns")
        return self


def cell(dataset: FeatureDataset, row: FeatureRow, name: str) -> dict[str, Any]:
    value = row.values[name]
    ticker = next(
        (
            ticker
            for ticker, info in dataset.diagnostics.get("entity_mapping", {}).items()
            if info["asset_id"] == row.asset_id
        ),
        dataset.configuration["tickers"][0] if len(dataset.configuration["tickers"]) == 1 else "",
    )
    coverage = (
        dataset.diagnostics.get("coverage_states", {})
        .get(ticker + ":" + str(row.session_date), {})
        .get(name)
    )
    result: dict[str, Any] = {
        "name": name,
        "coverage_state": coverage,
        "value": value,
        "missing_reason": row.reasons.get(name),
        "observation_at": row.market_at,
        "calculated_at": dataset.calculated_at,
        "inputs_available_at": None,
        "inputs_ingested_at": None,
        "decision_ready_at": None,
        "online_ready_at": None,
        "earliest_execution_at": None,
        "dependency_start_position": None,
        "dependency_end_position": row.position,
    }
    if value is None:
        return result
    available, ingested, first = row.timing[name]
    if row.market_at is None or not 0 <= first <= row.position:
        raise FeatureError("invalid_lineage", "Stored feature timing is inconsistent", 500)
    decision = readiness(
        row.market_at, available, int(dataset.configuration["processing_delay_seconds"])
    )
    result.update(
        {
            "inputs_available_at": instant(available),
            "inputs_ingested_at": instant(ingested),
            "decision_ready_at": decision,
            "online_ready_at": max(decision, instant(ingested), dataset.calculated_at),
            "earliest_execution_at": execution(
                dataset.diagnostics["calendar"], decision, ingested, dataset.calculated_at
            ),
            "dependency_start_position": first,
        }
    )
    return result


@dataclass(frozen=True)
class Matrix:
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    next_offset: int | None
    missing_policy: str
    availability_mode: str
    sentiment_dataset_id: str | None = None

    def to_numpy(self) -> NDArray[np.float64]:
        """Ordered numeric inputs only. Missing cells remain NaN; no labels or scaling."""
        return np.array(
            [
                [np.nan if value is None else value for value in row["features"]]
                for row in self.rows
            ],
            dtype=np.float64,
        ).reshape(len(self.rows), len(self.columns))


def assemble(session: Session, request: MatrixRequest) -> Matrix:
    if request.sentiment_dataset_id is not None:
        from sentientalpha.sentiment.matrices import combined

        return combined(session, request)
    dataset = get_dataset(session, request.dataset_id, request.allow_stale)
    columns = sorted(request.columns or dataset.columns)
    if set(columns) - set(dataset.columns):
        raise FeatureError("unknown_column", "Only persisted input features can enter a matrix")
    if request.limit * len(columns) > 100_000:
        raise FeatureError("response_limit", "Reduce row limit or selected feature columns")
    symbols = request.tickers or dataset.configuration["tickers"]
    if set(symbols) - set(dataset.configuration["tickers"]):
        raise FeatureError("unknown_dataset_asset", "Ticker is not in this feature dataset")
    statement = (
        select(FeatureRow, FeatureSourceAsset.ticker)
        .join(
            FeatureSourceAsset,
            (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
            & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
        )
        .where(
            FeatureRow.dataset_id == dataset.id,
            FeatureSourceAsset.ticker.in_(symbols),
            FeatureRow.session_date.between(request.start, request.end),
        )
        .order_by(FeatureRow.session_date, FeatureSourceAsset.ticker)
        .offset(request.offset)
        .limit(request.limit + 1)
    )
    stored = list(session.execute(statement))
    rows: list[dict[str, Any]] = []
    for record, ticker in stored[: request.limit]:
        cells = [cell(dataset, record, name) for name in columns]
        values = []
        reasons = {}
        ready_times = []
        for item in cells:
            value, reason = item["value"], item["missing_reason"]
            ready_at = item["decision_ready_at"]
            if value is not None:
                if request.availability_mode == "online":
                    ready_at = max(ready_at, item["inputs_ingested_at"], dataset.calculated_at)
                if request.decision_at is not None and ready_at > request.decision_at:
                    value, reason = None, "not_available_at_decision"
            if value is not None:
                ready_times.append(ready_at)
            else:
                reasons[item["name"]] = reason
            values.append(value)
        if reasons and request.missing_policy == "raise":
            raise FeatureError(
                "missing_features", "Selected matrix cells contain unavailable/undefined values"
            )
        if reasons and request.missing_policy == "drop_row":
            continue
        rows.append(
            {
                "ticker": ticker,
                "session_date": record.session_date,
                "observation_at": record.market_at,
                "decision_ready_at": max(ready_times) if ready_times else None,
                "calculated_at": dataset.calculated_at,
                "features": values,
                "missing_reasons": reasons,
            }
        )
    # Cursor advances across scanned source rows, including explicitly dropped rows.
    return Matrix(
        dataset.id,
        columns,
        rows,
        request.offset + request.limit if len(stored) > request.limit else None,
        request.missing_policy,
        request.availability_mode,
    )

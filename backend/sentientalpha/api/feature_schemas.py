"""Typed feature responses; nulls and provenance are explicit."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class DefinitionResponse(BaseModel):
    name: str
    group: str
    description: str
    parameters: dict[str, int | float]
    inputs: list[str]
    calculation_version: str
    lookback: str
    warmup_sessions: dict[str, int]
    outputs: list[str]
    dtype: str
    availability: str
    missing_policy: str
    price_basis: str
    parameter_defaults: dict[str, int | float]
    maximum_session_parameter: int


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    engine_version: str
    provider: str
    status: str
    start_date: date
    end_date: date
    source_as_of: datetime
    calculated_at: datetime
    columns: list[str]
    definitions: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    row_count: int
    configuration: dict[str, Any]
    configuration_key: str
    source_hash: str
    definition_hash: str
    invalidated_at: datetime | None
    invalidation_reason: str | None

    @field_validator("diagnostics")
    @classmethod
    def bounded_diagnostics(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Large internal evidence maps are accessed through bounded contributor/history endpoints.
        internal = {"cell_lineage", "contribution_sets", "coverage_states"}
        return {
            **{k: v for k, v in value.items() if k not in internal},
            **({"sentiment_lineage_available": True} if "cell_lineage" in value else {}),
        }


class GenerationResponse(BaseModel):
    dataset: DatasetResponse
    reused: bool
    elapsed_seconds: float


class CellResponse(BaseModel):
    coverage_state: str | None = None
    name: str
    value: float | None
    missing_reason: str | None
    observation_at: datetime | None
    calculated_at: datetime
    inputs_available_at: datetime | None
    inputs_ingested_at: datetime | None
    decision_ready_at: datetime | None
    online_ready_at: datetime | None
    earliest_execution_at: datetime | None
    dependency_start_position: int | None
    dependency_end_position: int


class FeatureRecord(BaseModel):
    session_date: date
    ticker: str
    features: list[CellResponse]


class RetrievalResponse(BaseModel):
    dataset_id: str
    status: str
    records: list[FeatureRecord]
    next_offset: int | None


class MatrixRowResponse(BaseModel):
    ticker: str
    session_date: date
    observation_at: datetime | None
    decision_ready_at: datetime | None
    calculated_at: datetime
    features: list[float | None]
    missing_reasons: dict[str, str]


class MatrixResponse(BaseModel):
    sentiment_dataset_id: str | None = None
    dataset_id: str
    columns: list[str]
    rows: list[MatrixRowResponse]
    next_offset: int | None
    missing_policy: str
    availability_mode: str


class LineageItem(BaseModel):
    price_id: str
    asset_id: str
    ticker: str
    session_date: date
    revision_no: int
    checksum: str
    position: int
    available_at: datetime
    ingested_at: datetime
    is_synthetic: bool
    provider: str


class LineageResponse(BaseModel):
    dataset_id: str
    inputs: list[LineageItem]
    next_offset: int | None

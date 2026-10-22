"""Explicit bounded feature generation; read endpoints never trigger calculations."""

from dataclasses import asdict
from datetime import date
from threading import BoundedSemaphore
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.api.feature_schemas import (
    CellResponse,
    DatasetResponse,
    DefinitionResponse,
    FeatureRecord,
    GenerationResponse,
    LineageItem,
    LineageResponse,
    MatrixResponse,
    RetrievalResponse,
)
from sentientalpha.data.contracts import ticker_symbol, validate_range
from sentientalpha.database.models import FeatureInput, FeatureRow, FeatureSourceAsset, MarketPrice
from sentientalpha.features.contracts import FeatureError, GenerationRequest
from sentientalpha.features.matrices import MatrixRequest, assemble, cell
from sentientalpha.features.registry import Registry
from sentientalpha.features.storage import generate, get_dataset


def feature_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(tags=["features"])
    generation_slot = BoundedSemaphore(1)

    @router.get("/api/features/definitions", response_model=list[DefinitionResponse])
    def definitions() -> list[DefinitionResponse]:
        return [
            DefinitionResponse.model_validate(item) for item in Registry().definitions_metadata()
        ]

    @router.get("/api/features/all-definitions", response_model=list[DefinitionResponse])
    def all_definitions() -> list[DefinitionResponse]:
        from sentientalpha.sentiment.registry import UnifiedRegistry

        return [
            DefinitionResponse.model_validate(m) for m in UnifiedRegistry().definitions_metadata()
        ]

    @router.post("/api/features/generate", response_model=GenerationResponse, status_code=201)
    def generate_features(request: GenerationRequest) -> GenerationResponse:
        if not generation_slot.acquire(blocking=False):
            raise FeatureError(
                "generation_busy", "One generation is already running; retry later", 429
            )
        try:
            result = generate(sessions, request)
        finally:
            generation_slot.release()
        return GenerationResponse(
            dataset=DatasetResponse.model_validate(result.dataset),
            reused=result.reused,
            elapsed_seconds=result.elapsed_seconds,
        )

    @router.post("/api/features/matrix", response_model=MatrixResponse)
    def matrix(request: MatrixRequest) -> MatrixResponse:
        with sessions() as session:
            return MatrixResponse.model_validate(asdict(assemble(session, request)))

    @router.get("/api/feature-datasets/{dataset_id}", response_model=DatasetResponse)
    def dataset_info(dataset_id: UUID) -> DatasetResponse:
        with sessions() as session:
            return DatasetResponse.model_validate(
                get_dataset(session, str(dataset_id), allow_stale=True)
            )

    @router.get("/api/feature-datasets/{dataset_id}/lineage", response_model=LineageResponse)
    def lineage(
        dataset_id: UUID,
        limit: int = Query(default=500, ge=1, le=2000),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ) -> LineageResponse:
        with sessions() as session:
            get_dataset(session, str(dataset_id), allow_stale=True)
            stored = list(
                session.execute(
                    select(FeatureInput, MarketPrice, FeatureSourceAsset.ticker)
                    .join(MarketPrice, MarketPrice.id == FeatureInput.price_id)
                    .join(
                        FeatureSourceAsset,
                        (FeatureSourceAsset.dataset_id == FeatureInput.dataset_id)
                        & (FeatureSourceAsset.asset_id == MarketPrice.asset_id),
                    )
                    .where(FeatureInput.dataset_id == str(dataset_id))
                    .order_by(FeatureSourceAsset.ticker, FeatureInput.position)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            inputs = [
                LineageItem(
                    price_id=row.id,
                    asset_id=row.asset_id,
                    ticker=ticker,
                    session_date=row.session_date,
                    revision_no=row.revision_no,
                    checksum=row.checksum,
                    position=link.position,
                    available_at=row.available_at,
                    ingested_at=row.ingested_at,
                    is_synthetic=row.is_synthetic,
                    provider=row.provider,
                )
                for link, row, ticker in stored[:limit]
            ]
            return LineageResponse(
                dataset_id=str(dataset_id),
                inputs=inputs,
                next_offset=offset + limit if len(stored) > limit else None,
            )

    @router.get("/api/features/{ticker}", response_model=RetrievalResponse)
    def historical(
        ticker: str,
        dataset_id: UUID,
        start: date,
        end: date,
        allow_stale: bool = False,
        limit: int = Query(default=500, ge=1, le=2000),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ) -> RetrievalResponse:
        try:
            ticker = ticker_symbol(ticker)
            validate_range(start, end)
        except ValueError:
            raise FeatureError("invalid_request", "Invalid ticker or chronological range") from None
        with sessions() as session:
            dataset = get_dataset(session, str(dataset_id), allow_stale)
            if ticker not in dataset.configuration["tickers"]:
                raise FeatureError("unknown_dataset_asset", "Ticker is not in this dataset", 404)
            if limit * len(dataset.columns) > 100_000:
                raise FeatureError("response_limit", "Reduce the row limit for this feature set")
            rows = list(
                session.scalars(
                    select(FeatureRow)
                    .join(
                        FeatureSourceAsset,
                        (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
                        & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
                    )
                    .where(
                        FeatureRow.dataset_id == dataset.id,
                        FeatureSourceAsset.ticker == ticker,
                        FeatureRow.session_date.between(start, end),
                    )
                    .order_by(FeatureRow.session_date)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            records = [
                FeatureRecord(
                    session_date=row.session_date,
                    ticker=ticker,
                    features=[
                        CellResponse.model_validate(cell(dataset, row, name))
                        for name in dataset.columns
                    ],
                )
                for row in rows[:limit]
            ]
            return RetrievalResponse(
                dataset_id=dataset.id,
                status=dataset.status,
                records=records,
                next_offset=offset + limit if len(rows) > limit else None,
            )

    return router

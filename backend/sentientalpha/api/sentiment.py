"""Explicit bounded financial-news operations; no copyrighted full-text response fields."""

from datetime import datetime
from threading import BoundedSemaphore
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.api.feature_schemas import (
    DatasetResponse,
    DefinitionResponse,
    GenerationResponse,
)
from sentientalpha.config import Settings
from sentientalpha.data.contracts import ticker_symbol
from sentientalpha.database.models import Asset, now
from sentientalpha.database.sentiment_models import (
    ArticleAssociation,
    NewsArticle,
    NewsVersion,
    SentimentInference,
    SentimentRun,
)
from sentientalpha.features.contracts import FeatureError
from sentientalpha.features.storage import get_dataset
from sentientalpha.sentiment.contracts import NewsRequest
from sentientalpha.sentiment.datasets import SentimentGenerationRequest, generate_sentiment
from sentientalpha.sentiment.inference import infer
from sentientalpha.sentiment.ingestion import ingest_news
from sentientalpha.sentiment.model import FinBERT
from sentientalpha.sentiment.providers import AlphaVantageNewsProvider, FederalReserveProvider
from sentientalpha.sentiment.registry import SentimentRegistry


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    provider: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    inserted: int
    reused: int
    error_code: str | None
    configuration: dict[str, Any]
    diagnostics: dict[str, Any]


class ArticleResponse(BaseModel):
    headline: str | None
    content_hash: str
    event_at: datetime | None
    version_id: str
    article_id: str
    story_id: str
    provider: str
    publisher: str
    url: str
    canonical_url: str
    revision_no: int
    published_at: datetime
    updated_at: datetime | None
    first_seen_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    is_synthetic: bool
    language: str
    text_rights: str
    quality_flags: list[str]
    relevance_status: str | None
    # Headline/text deliberately omitted; internal inference uses rights-controlled stored text.


class InferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    version_id: str
    context_key: str
    attempt: int
    model_key: str
    model_metadata: dict[str, Any]
    input_hash: str
    inferred_at: datetime
    status: str
    positive: float | None
    negative: float | None
    neutral: float | None
    score: float | None
    tokens: int
    truncated: bool


class InitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tokens: int = Field(default=512, ge=8, le=512)
    threads: int = Field(default=2, ge=1, le=8)


class InferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern=r"^(federal_reserve|alphavantage_news|synthetic_news)$")
    max_items: int = Field(default=100, ge=1, le=1000)
    batch_size: int = Field(default=16, ge=1, le=32)
    seconds: int = Field(default=120, ge=1, le=300)


class ContributionResponse(BaseModel):
    dataset_id: str
    ticker: str
    session_date: str
    feature: str
    inferences: list[InferenceResponse]


def sentiment_router(sessions: sessionmaker[Session], settings: Settings) -> APIRouter:
    router = APIRouter(tags=["sentiment"])
    slot = BoundedSemaphore(1)
    model: FinBERT | None = None

    def acquire() -> None:
        if not slot.acquire(blocking=False):
            raise FeatureError(
                "sentiment_busy", "Another sentiment operation is running; retry later", 429
            )

    @router.get("/api/sentiment/definitions", response_model=list[DefinitionResponse])
    def definitions() -> list[DefinitionResponse]:
        return [
            DefinitionResponse.model_validate(m) for m in SentimentRegistry().definitions_metadata()
        ]

    @router.post("/api/news/ingest", response_model=RunResponse, status_code=201)
    def ingestion(request: NewsRequest) -> RunResponse:
        acquire()
        try:
            provider = (
                FederalReserveProvider()
                if request.provider == "federal_reserve"
                else AlphaVantageNewsProvider(settings.alpha_vantage_api_key)
            )
            return RunResponse.model_validate(
                ingest_news(
                    sessions,
                    provider,
                    request.start,
                    request.end,
                    request.tickers,
                    request.max_articles,
                )
            )
        finally:
            slot.release()

    @router.get("/api/sentiment/runs/{run_id}", response_model=RunResponse)
    def run_info(run_id: UUID) -> RunResponse:
        with sessions() as session:
            run = session.get(SentimentRun, str(run_id))
            if run is None:
                raise FeatureError("unknown_run", "Sentiment run not found", 404)
            return RunResponse.model_validate(run)

    @router.post("/api/sentiment/model/initialize")
    def initialize(request: InitRequest) -> dict[str, Any]:
        nonlocal model
        if not settings.finbert_cache_dir:
            raise FeatureError(
                "model_cache_required",
                "Configure FINBERT_CACHE_DIR; API initialization is local-only",
                503,
            )
        acquire()
        try:
            if model is None:
                model = FinBERT(
                    settings.finbert_cache_dir,
                    local_only=True,
                    max_tokens=request.max_tokens,
                    threads=request.threads,
                )
            elif model.max_tokens != request.max_tokens or model.threads != request.threads:
                raise FeatureError(
                    "model_config_conflict",
                    "Restart application to change loaded model configuration",
                    409,
                )
            return {"model_key": model.key, "metadata": model.metadata}
        finally:
            slot.release()

    @router.post("/api/sentiment/infer", response_model=RunResponse, status_code=201)
    def inference(request: InferRequest) -> RunResponse:
        if model is None:
            raise FeatureError(
                "model_not_initialized", "Initialize the pinned local model explicitly first", 503
            )
        acquire()
        try:
            return RunResponse.model_validate(
                infer(
                    sessions,
                    model,
                    request.provider,
                    request.max_items,
                    request.batch_size,
                    request.seconds,
                )
            )
        finally:
            slot.release()

    @router.post("/api/sentiment/generate", response_model=GenerationResponse, status_code=201)
    def generate(request: SentimentGenerationRequest) -> GenerationResponse:
        acquire()
        try:
            result = generate_sentiment(sessions, request)
            return GenerationResponse(
                dataset=DatasetResponse.model_validate(result.dataset),
                reused=result.reused,
                elapsed_seconds=result.elapsed_seconds,
            )
        finally:
            slot.release()

    @router.get("/api/news/{ticker}", response_model=list[ArticleResponse])
    def news(
        ticker: str,
        as_of: datetime | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0, le=100000),
    ) -> list[ArticleResponse]:
        from sentientalpha.data.contracts import utc

        try:
            ticker = ticker_symbol(ticker)
            cutoff = now() if as_of is None else utc(as_of)
        except ValueError:
            raise FeatureError("invalid_news_request", "Invalid ticker or aware cutoff") from None
        with sessions() as session:
            statement = (
                select(NewsVersion, NewsArticle, ArticleAssociation.status)
                .join(NewsArticle)
                .outerjoin(ArticleAssociation, ArticleAssociation.version_id == NewsVersion.id)
                .outerjoin(Asset, Asset.id == ArticleAssociation.asset_id)
                .where(NewsVersion.observed_at <= cutoff, NewsVersion.ingested_at <= cutoff)
            )
            statement = (
                statement.where(NewsVersion.scope == "broad_market")
                if ticker == "SENT.MKT"
                else statement.where(Asset.ticker == ticker)
            )
            rows = session.execute(
                statement.order_by(NewsVersion.published_at, NewsVersion.id)
                .offset(offset)
                .limit(limit)
            )
            return [
                ArticleResponse(
                    headline=v.headline
                    if v.text_rights in {"synthetic", "public_domain_feed"}
                    else None,
                    content_hash=v.content_hash,
                    event_at=v.event_at,
                    version_id=v.id,
                    article_id=a.id,
                    story_id=a.story_id,
                    provider=a.provider,
                    publisher=v.publisher,
                    url=v.source_metadata.get("original_url", a.original_url),
                    canonical_url=v.source_metadata.get("canonical_url", a.canonical_url),
                    revision_no=v.revision_no,
                    published_at=v.published_at,
                    updated_at=v.updated_at,
                    first_seen_at=v.first_seen_at,
                    observed_at=v.observed_at,
                    ingested_at=v.ingested_at,
                    is_synthetic=v.is_synthetic,
                    language=v.language,
                    text_rights=v.text_rights,
                    quality_flags=v.quality_flags,
                    relevance_status=status,
                )
                for v, a, status in rows
            ]

    @router.get("/api/sentiment/articles/{version_id}", response_model=list[InferenceResponse])
    def article_sentiment(
        version_id: UUID, limit: int = Query(default=100, ge=1, le=500)
    ) -> list[InferenceResponse]:
        with sessions() as session:
            return [
                InferenceResponse.model_validate(p)
                for p in session.scalars(
                    select(SentimentInference)
                    .where(SentimentInference.version_id == str(version_id))
                    .limit(limit)
                )
            ]

    @router.get("/api/sentiment/{dataset_id}/contributors", response_model=ContributionResponse)
    def contributors(
        dataset_id: UUID, ticker: str, session_date: str, feature: str
    ) -> ContributionResponse:
        with sessions() as session:
            dataset = get_dataset(session, str(dataset_id), True)
            key = ticker + ":" + session_date + ":" + feature
            set_key = dataset.diagnostics.get("cell_lineage", {}).get(key)
            if set_key is None:
                raise FeatureError("unknown_sentiment_cell", "No such sentiment feature cell", 404)
            ids = dataset.diagnostics["contribution_sets"][set_key]
            if len(ids) > 500:
                raise FeatureError(
                    "lineage_limit", "Cell has over 500 contributors; narrow aggregation window"
                )
            predictions = session.scalars(
                select(SentimentInference)
                .where(SentimentInference.id.in_(ids))
                .order_by(SentimentInference.id)
            )
            return ContributionResponse(
                dataset_id=str(dataset_id),
                ticker=ticker,
                session_date=session_date,
                feature=feature,
                inferences=[InferenceResponse.model_validate(p) for p in predictions],
            )

    return router

"""Loopback-only research API. Data acquisition is explicit and never triggered by reads."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from sentientalpha import __version__
from sentientalpha.api.backtesting import backtest_router
from sentientalpha.api.committee import committee_router
from sentientalpha.api.features import feature_router
from sentientalpha.api.ml import ml_router
from sentientalpha.api.paper import paper_router
from sentientalpha.api.portfolio import portfolio_router
from sentientalpha.api.research import research_router
from sentientalpha.api.risk import risk_router
from sentientalpha.api.schemas import (
    AssetResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    IngestRequest,
    MarketResponse,
    PriceResponse,
    ProviderName,
    RunResponse,
)
from sentientalpha.api.sentiment import sentiment_router
from sentientalpha.api.strategies import strategies_router
from sentientalpha.backtesting.contracts import BacktestError
from sentientalpha.config import Settings
from sentientalpha.data.alphavantage import AlphaVantageProvider
from sentientalpha.data.contracts import (
    MarketDataProvider,
    ProviderError,
    ticker_symbol,
    utc,
    validate_range,
)
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import EXPECTED_SCHEMA_REVISION, Asset, IngestionRun, now
from sentientalpha.database.repository import prices_as_of
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureError
from sentientalpha.logging import configure_logging
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.services.ingestion import IngestionError, ingest


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging()
    engine = make_engine(settings.database_url)
    sessions = session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="SentientAlpha",
        version=__version__,
        lifespan=lifespan,
        description=(
            "Simulation-only research infrastructure. "
            "M1–2: market data, provenance and financial features."
        ),
        responses={code: {"model": ErrorResponse} for code in (404, 409, 422, 429, 500, 502, 503)},
    )
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    from sentientalpha.api.security import LocalBoundary

    app.add_middleware(LocalBoundary, origins=settings.trusted_origins)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
    app.state.engine = engine

    def failure(status: int, code: str, message: str, run_id: str | None = None) -> JSONResponse:
        body = ErrorResponse(detail=ErrorDetail(code=code, message=message, run_id=run_id))
        return JSONResponse(status_code=status, content=body.model_dump())

    @app.exception_handler(OptimizationError)
    async def optimization_failure(request: Request, exc: OptimizationError) -> JSONResponse:
        return failure(exc.status, exc.code, str(exc))

    @app.exception_handler(BacktestError)
    async def backtest_failure(request: Request, exc: BacktestError) -> JSONResponse:
        return failure(exc.status, exc.code, str(exc))

    @app.exception_handler(FeatureError)
    async def feature_failure(request: Request, exc: FeatureError) -> JSONResponse:
        return failure(exc.status, exc.code, str(exc))

    @app.exception_handler(SQLAlchemyError)
    async def database_failure(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return failure(503, "database_unavailable", "Database unavailable or unmigrated")

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's default response echoes rejected input, which may contain credentials.
        return failure(422, "invalid_request", "Request failed input validation")

    @app.exception_handler(StarletteHTTPException)
    async def http_failure(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return failure(
                exc.status_code,
                exc.detail.get("code", "request_failed"),
                exc.detail.get("message", "Request failed"),
                exc.detail.get("run_id"),
            )
        return failure(exc.status_code, "request_failed", str(exc.detail))

    @app.exception_handler(Exception)
    async def internal_failure(request: Request, exc: Exception) -> JSONResponse:
        return failure(500, "internal_error", "Internal request failure")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", mode=settings.mode, version=__version__)

    @app.get("/ready", response_model=HealthResponse)
    def ready() -> HealthResponse:
        with sessions() as session:
            revision = session.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != EXPECTED_SCHEMA_REVISION:
                raise HTTPException(503, "Database schema is not at the expected revision")
            session.execute(select(Asset.id).limit(1))
        return HealthResponse(status="ready", mode=settings.mode, version=__version__)

    @app.get("/api/assets", response_model=list[AssetResponse])
    def assets(
        limit: int = Query(default=200, ge=1, le=2000),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ) -> list[Asset]:
        with sessions() as session:
            return list(
                session.scalars(select(Asset).order_by(Asset.ticker).limit(limit).offset(offset))
            )

    @app.post("/api/market/ingest", response_model=RunResponse, status_code=201)
    def import_prices(request: IngestRequest) -> IngestionRun:
        try:
            provider: MarketDataProvider = (
                SyntheticProvider(request.seed)
                if request.provider == "synthetic"
                else AlphaVantageProvider(settings.alpha_vantage_api_key)
            )
            return ingest(sessions, provider, request.ticker, request.start, request.end)
        except ProviderError as exc:
            raise HTTPException(503, {"code": exc.code, "message": str(exc)}) from None
        except IngestionError as exc:
            status = {
                "concurrent_conflict": 409,
                "currency_conflict": 409,
                "database_error": 503,
                "internal_error": 500,
                "empty_range": 422,
                "insufficient_coverage": 422,
                "unsupported_market": 422,
                "provider_rejected": 404,
            }.get(exc.code, 502)
            raise HTTPException(status, {"code": exc.code, "run_id": exc.run_id}) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/ingestions/{run_id}", response_model=RunResponse)
    def ingestion_status(run_id: UUID) -> IngestionRun:
        with sessions() as session:
            run = session.get(IngestionRun, str(run_id))
            if run is None:
                raise HTTPException(404, "Ingestion run not found")
            return run

    @app.get("/api/market/{ticker}", response_model=MarketResponse)
    def market(
        ticker: str,
        start: date,
        end: date,
        provider: ProviderName = "synthetic",
        as_of: datetime | None = None,
        limit: int = Query(default=500, ge=1, le=2000),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ) -> MarketResponse:
        try:
            ticker = ticker_symbol(ticker)
            validate_range(start, end)
            cutoff = utc(as_of) if as_of is not None else now()
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        with sessions() as session:
            if session.scalar(select(Asset.id).where(Asset.ticker == ticker)) is None:
                raise HTTPException(404, "Asset not found; ingest prices first")
            rows = prices_as_of(session, ticker, provider, start, end, cutoff, limit + 1, offset)
            return MarketResponse(
                ticker=ticker,
                provider=provider,
                as_of=cutoff,
                prices=[PriceResponse.model_validate(row) for row in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    app.include_router(paper_router(sessions, settings))
    app.include_router(research_router(sessions))
    app.include_router(risk_router(sessions))
    app.include_router(committee_router(sessions))
    app.include_router(strategies_router(sessions))
    app.include_router(ml_router(sessions))
    app.include_router(portfolio_router(sessions))
    app.include_router(backtest_router(sessions))
    app.include_router(feature_router(sessions))
    app.include_router(sentiment_router(sessions, settings))
    return app

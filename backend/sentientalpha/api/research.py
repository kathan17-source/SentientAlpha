"""Small read-only catalog for discovering existing research IDs, never new calculations."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, load_only, sessionmaker

from sentientalpha.database.backtest_models import BacktestRun
from sentientalpha.database.committee_models import CommitteeRun
from sentientalpha.database.feature_models import FeatureDataset
from sentientalpha.database.ml_models import MLExperiment
from sentientalpha.database.models import Asset, MarketPrice
from sentientalpha.database.optimization_models import OptimizationRun
from sentientalpha.database.paper_models import PaperSession
from sentientalpha.database.sentiment_models import SentimentRun
from sentientalpha.database.strategy_models import DiscoveryRun

Kind = Literal["backtest", "optimization", "ml", "strategy", "committee", "features", "sentiment"]


class CatalogItem(BaseModel):
    id: str
    kind: Kind
    status: str
    created_at: datetime
    label: str
    configuration: dict[str, Any]
    links: dict[str, str]


class CatalogPage(BaseModel):
    items: list[CatalogItem]
    next_offset: int | None


class CoveragePage(BaseModel):
    items: list[dict[str, Any]]


def research_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/research", tags=["research catalog"])
    models: dict[str, Any] = {
        "backtest": (BacktestRun, BacktestRun.started_at),
        "optimization": (OptimizationRun, OptimizationRun.created_at),
        "ml": (MLExperiment, MLExperiment.created_at),
        "strategy": (DiscoveryRun, DiscoveryRun.created_at),
        "committee": (CommitteeRun, CommitteeRun.created_at),
        "features": (FeatureDataset, FeatureDataset.calculated_at),
        "sentiment": (SentimentRun, SentimentRun.started_at),
    }
    paths = {
        "backtest": "/api/backtest/",
        "optimization": "/api/portfolio/optimization/",
        "ml": "/api/ml/experiments/",
        "strategy": "/api/strategies/discovery/",
        "committee": "/api/investment-committee/",
        "features": "/api/feature-datasets/",
        "sentiment": "/api/sentiment/runs/",
    }

    @router.get("/catalog", response_model=CatalogPage)
    def catalog(
        kind: Kind, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
    ) -> CatalogPage:
        model, clock = models[kind]
        public_columns = [model.id, model.status, clock]
        for name in ["manifest", "configuration", "idempotency_key", "kind", "backtest_id"]:
            if hasattr(model, name):
                public_columns.append(getattr(model, name))
        excluded = []
        if kind == "backtest":
            excluded = [~exists(select(PaperSession.id).where(PaperSession.ledger_id == model.id))]
        elif kind == "committee":
            excluded = [
                ~exists(select(PaperSession.id).where(PaperSession.ledger_id == model.backtest_id))
            ]
        with sessions() as session:
            rows = list(
                session.scalars(
                    select(model)
                    .options(load_only(*public_columns))
                    .where(*excluded)
                    .order_by(clock.desc(), model.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            items = []
            for row in rows[:limit]:
                manifest = getattr(row, "manifest", {})
                config = manifest.get("configuration", getattr(row, "configuration", {}))
                # Return only bounded public research fields, never raw model/source artifacts.
                allowed = {
                    k: v
                    for k, v in config.items()
                    if k
                    in {
                        "tickers",
                        "provider",
                        "start",
                        "end",
                        "history_start",
                        "dataset_id",
                        "information_policy",
                        "strategy",
                        "objective",
                        "estimator",
                        "split",
                        "splits",
                        "source_as_of",
                        "agents",
                        "risk_policy",
                        "model_id",
                        "strategy_id",
                    }
                }
                label = getattr(row, "idempotency_key", None) or getattr(row, "kind", kind)
                links = {"detail": paths[kind] + row.id}
                if kind == "committee" and row.backtest_id:
                    links["backtest"] = "/api/backtest/" + row.backtest_id
                items.append(
                    CatalogItem(
                        id=row.id,
                        kind=kind,
                        status=row.status,
                        created_at=getattr(row, clock.key),
                        label=str(label),
                        configuration=allowed,
                        links=links,
                    )
                )
            return CatalogPage(
                items=items, next_offset=offset + limit if len(rows) > limit else None
            )

    @router.get("/coverage", response_model=CoveragePage)
    def coverage(
        limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0, le=100000)
    ) -> CoveragePage:
        with sessions() as session:
            rows = session.execute(
                select(
                    Asset.ticker,
                    MarketPrice.provider,
                    func.min(MarketPrice.session_date),
                    func.max(MarketPrice.session_date),
                    func.max(MarketPrice.available_at),
                    func.max(MarketPrice.ingested_at),
                    func.count(MarketPrice.id),
                )
                .join(Asset, Asset.id == MarketPrice.asset_id)
                .group_by(Asset.ticker, MarketPrice.provider)
                .order_by(Asset.ticker, MarketPrice.provider)
                .offset(offset)
                .limit(limit)
            )
            return CoveragePage(
                items=[
                    dict(
                        ticker=t,
                        provider=p,
                        start=str(a),
                        end=str(b),
                        latest_available_at=c.isoformat(),
                        latest_ingested_at=d.isoformat(),
                        retained_versions=n,
                        provenance="synthetic" if p == "synthetic" else "provider_observations",
                        limitation="Retained range, not full coverage or live quotes",
                    )
                    for t, p, a, b, c, d, n in rows
                ]
            )

    return router

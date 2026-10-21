"""Typed bounded ML research routes; one training/replay/backtest job per process."""

from threading import Semaphore
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.database.ml_models import MLModel, MLPrediction
from sentientalpha.ml.contracts import PredictRequest, ResearchRequest
from sentientalpha.ml.storage import backtest, get, predict, replay, run


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    manifest: dict[str, Any]


class Page(BaseModel):
    items: list[dict[str, Any]]


def ml_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/ml", tags=["ML research"])
    gate = Semaphore(1)

    @router.post("/train", response_model=ExperimentResponse, status_code=201)
    @router.post("/walk-forward", response_model=ExperimentResponse, status_code=201)
    def train(request: ResearchRequest) -> Any:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "ML job already active")
        try:
            return run(sessions, request)
        finally:
            gate.release()

    @router.get("/models", response_model=Page)
    def models(
        limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)
    ) -> Page:
        with sessions() as session:
            items = list(
                session.scalars(
                    select(MLModel)
                    .order_by(MLModel.created_at, MLModel.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            return Page(
                items=[
                    {
                        "id": m.id,
                        "experiment_id": m.experiment_id,
                        "version": m.version,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in items
                ]
            )

    @router.get("/models/{model_id}", response_model=Page)
    def model(model_id: UUID) -> Page:
        with sessions() as session:
            m = session.get(MLModel, str(model_id))
            if m is None:
                raise HTTPException(404, "Model not found")
            return Page(
                items=[
                    {
                        "id": m.id,
                        "version": m.version,
                        **{k: v for k, v in m.payload.items() if k != "artifact"},
                    }
                ]
            )

    @router.post("/predict", response_model=Page)
    def inference(request: PredictRequest) -> Page:
        with sessions() as session:
            return Page(items=predict(session, request))

    @router.get("/predictions/{ticker}", response_model=Page)
    def forecasts(
        ticker: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=1000000)
    ) -> Page:
        with sessions() as session:
            rows = session.scalars(
                select(MLPrediction)
                .where(MLPrediction.ticker == ticker)
                .order_by(MLPrediction.decision_at, MLPrediction.id)
                .limit(limit)
                .offset(offset)
            )
            return Page(
                items=[
                    {
                        "id": r.id,
                        "model_id": r.model_id,
                        "generated_at": r.generated_at.isoformat(),
                        **r.payload,
                    }
                    for r in rows
                ]
            )

    @router.get("/experiments/{run_id}", response_model=ExperimentResponse)
    def experiment(run_id: UUID) -> Any:
        with sessions() as session:
            return get(session, str(run_id))

    @router.get("/experiments/{run_id}/metrics", response_model=Page)
    def scores(run_id: UUID) -> Page:
        with sessions() as session:
            saved = get(session, str(run_id))
            return Page(
                items=[
                    {
                        k: v
                        for k, v in f.items()
                        if k not in {"native_importance", "permutation_importance"}
                    }
                    for f in saved.result.get("folds", [])
                ]
            )

    @router.get("/experiments/{run_id}/feature-importance", response_model=Page)
    def importance(run_id: UUID) -> Page:
        with sessions() as session:
            saved = get(session, str(run_id))
            return Page(
                items=[
                    {
                        "fold": f["fold"],
                        "native": f.get("native_importance", []),
                        "held_out_permutation": f.get("permutation_importance", []),
                    }
                    for f in saved.result.get("folds", [])
                ]
            )

    @router.post("/experiments/{run_id}/replay")
    def reproduce(run_id: UUID) -> dict[str, Any]:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "ML job already active")
        try:
            with sessions() as session:
                return replay(session, str(run_id))
        finally:
            gate.release()

    @router.post("/experiments/{run_id}/backtest")
    def economic_test(run_id: UUID) -> dict[str, Any]:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "ML job already active")
        try:
            return backtest(sessions, str(run_id))
        finally:
            gate.release()

    return router

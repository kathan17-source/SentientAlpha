"""Simulation-only bounded synchronous API; one research job per application."""

from threading import Semaphore
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.contracts import BacktestError, Request
from sentientalpha.backtesting.evaluation import WalkRequest
from sentientalpha.backtesting.storage import get_run, replay, run_backtest, walk_forward
from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    manifest: dict[str, Any]
    diagnostics: dict[str, Any]


class ArtifactPage(BaseModel):
    run_id: str
    kind: str
    items: list[dict[str, Any]]
    next_offset: int | None


class MetricsResponse(BaseModel):
    run_id: str
    metrics: dict[str, Any]


def backtest_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/backtest", tags=["backtesting"])
    gate = Semaphore(1)

    def job(request: Request | WalkRequest) -> BacktestRun:
        if not gate.acquire(blocking=False):
            raise HTTPException(
                429, {"code": "backtest_busy", "message": "One research job is already active"}
            )
        try:
            return (
                walk_forward(sessions, request)
                if isinstance(request, WalkRequest)
                else run_backtest(sessions, request)
            )
        except BacktestError as exc:
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
        except ValueError as exc:
            raise HTTPException(422, {"code": "invalid_evaluation", "message": str(exc)}) from None
        finally:
            gate.release()

    @router.post("", response_model=RunResponse, status_code=201)
    def create(request: Request) -> BacktestRun:
        return job(request)

    @router.post("/walk-forward", response_model=RunResponse, status_code=201)
    def walk(request: WalkRequest) -> BacktestRun:
        return job(request)

    @router.get("/{run_id}", response_model=RunResponse)
    def retrieve(run_id: UUID) -> BacktestRun:
        with sessions() as session:
            return get_run(session, str(run_id))

    @router.get("/{run_id}/metrics", response_model=MetricsResponse)
    def metrics(run_id: UUID) -> MetricsResponse:
        with sessions() as session:
            return MetricsResponse(
                run_id=str(run_id), metrics=get_run(session, str(run_id)).metrics
            )

    def page(run_id: UUID, kind: str, limit: int, offset: int) -> ArtifactPage:
        with sessions() as session:
            get_run(session, str(run_id))
            rows = list(
                session.scalars(
                    select(BacktestArtifact)
                    .where(BacktestArtifact.run_id == str(run_id), BacktestArtifact.kind == kind)
                    .order_by(BacktestArtifact.sequence)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return ArtifactPage(
                run_id=str(run_id),
                kind=kind,
                items=[r.payload for r in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    @router.get("/{run_id}/equity", response_model=ArtifactPage)
    def equity(
        run_id: UUID,
        limit: int = Query(500, ge=1, le=2000),
        offset: int = Query(0, ge=0, le=300000),
        benchmark: str | None = Query(None, pattern="^(buy_hold|equal_weight|moving_average|SPY)$"),
    ) -> ArtifactPage:
        return page(run_id, "bench_" + benchmark if benchmark else "equity", limit, offset)

    @router.get("/{run_id}/trades", response_model=ArtifactPage)
    def trades(
        run_id: UUID,
        kind: str = Query("fills", pattern="^(fills|orders|actions)$"),
        limit: int = Query(500, ge=1, le=2000),
        offset: int = Query(0, ge=0, le=300000),
    ) -> ArtifactPage:
        return page(run_id, kind, limit, offset)

    @router.get("/{run_id}/drawdown", response_model=ArtifactPage)
    def drawdown(
        run_id: UUID,
        limit: int = Query(500, ge=1, le=2000),
        offset: int = Query(0, ge=0, le=300000),
    ) -> ArtifactPage:
        with sessions() as session:
            rows = get_run(session, str(run_id)).metrics.get("drawdown", [])
            return ArtifactPage(
                run_id=str(run_id),
                kind="drawdown",
                items=rows[offset : offset + limit],
                next_offset=offset + limit if len(rows) > offset + limit else None,
            )

    @router.get("/{run_id}/report", response_model=dict[str, Any])
    def report(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            run = get_run(session, str(run_id))
            return {
                "run": RunResponse.model_validate(run).model_dump(mode="json"),
                "metrics": run.metrics,
                "benchmarks": page(run_id, "benchmarks", 4, 0).model_dump(),
                "folds": page(run_id, "folds", 50, 0).model_dump(),
            }

    @router.post("/{run_id}/replay", response_model=dict[str, Any])
    def rerun(run_id: UUID) -> dict[str, Any]:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Backtest busy")
        try:
            with sessions() as session:
                result = replay(session, str(run_id))
            return {
                "run_id": result["run_id"],
                "equivalent_metrics": result["equivalent_metrics"],
                "equivalent_artifacts": result["equivalent_artifacts"],
            }
        finally:
            gate.release()

    return router

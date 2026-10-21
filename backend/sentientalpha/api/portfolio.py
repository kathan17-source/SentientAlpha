"""Bounded numerical research API; no arbitrary code and no trading connection."""

import json
from threading import Semaphore
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.database.optimization_models import OptimizationRun
from sentientalpha.optimization.contracts import (
    FrontierRequest,
    OptimizationRequest,
    ResearchRequest,
    WalkResearch,
)
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.optimization.storage import get_run, replay, run


class OptimizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    status: str
    manifest: dict[str, Any]


class AllocationResponse(BaseModel):
    run_id: str
    status: str
    weights: dict[str, float] | None
    cash_weight: float | None


class ResultResponse(BaseModel):
    run_id: str
    status: str
    result: dict[str, Any]


def bounded(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: bounded(v) for k, v in value.items() if k != "lineage"}
    if isinstance(value, list):
        return [bounded(v) for v in value]
    return value


def portfolio_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio optimization"])
    gate = Semaphore(1)

    def job(
        request: OptimizationRequest | FrontierRequest | ResearchRequest | WalkResearch,
    ) -> OptimizationRun:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Optimization job already active")
        try:
            return run(sessions, request)
        finally:
            gate.release()

    @router.post("/optimize", response_model=OptimizationResponse, status_code=201)
    def optimize(request: OptimizationRequest) -> OptimizationRun:
        return job(request)

    @router.post("/efficient-frontier", response_model=OptimizationResponse, status_code=201)
    def frontier(request: FrontierRequest) -> OptimizationRun:
        return job(request)

    @router.post("/compare", response_model=OptimizationResponse, status_code=201)
    def compare(request: ResearchRequest) -> OptimizationRun:
        return job(request)

    @router.post("/walk-forward", response_model=OptimizationResponse, status_code=201)
    def walk(request: WalkResearch) -> OptimizationRun:
        return job(request)

    @router.get("/optimization/{run_id}", response_model=OptimizationResponse)
    def retrieve(run_id: UUID) -> OptimizationRun:
        with sessions() as session:
            return get_run(session, str(run_id))

    @router.get("/optimization/{run_id}/weights", response_model=AllocationResponse)
    def weights(run_id: UUID) -> AllocationResponse:
        with sessions() as session:
            r = get_run(session, str(run_id))
            return AllocationResponse(
                run_id=r.id,
                status=r.status,
                weights=r.result.get("weights"),
                cash_weight=r.result.get("cash_weight"),
            )

    @router.get("/optimization/{run_id}/risk", response_model=ResultResponse)
    def risk(run_id: UUID) -> ResultResponse:
        with sessions() as session:
            r = get_run(session, str(run_id))
            return ResultResponse(run_id=r.id, status=r.status, result=r.result.get("risk", {}))

    @router.get("/optimization/{run_id}/explanation", response_model=ResultResponse)
    def explain(run_id: UUID) -> ResultResponse:
        with sessions() as session:
            r = get_run(session, str(run_id))
            return ResultResponse(
                run_id=r.id,
                status=r.status,
                result=bounded(
                    {
                        k: v
                        for k, v in r.result.items()
                        if k
                        in {
                            "explanation",
                            "estimation",
                            "expected_returns_base",
                            "expected_returns_used",
                            "sentiment",
                            "diagnostics",
                            "warnings",
                            "reason",
                        }
                    }
                ),
            )

    @router.get("/optimization/{run_id}/result", response_model=ResultResponse)
    def result(
        run_id: UUID,
        section: str = Query("summary", pattern="^(summary|points|methods|folds|aggregate)$"),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0, le=10000),
        decision_limit: int = Query(5, ge=1, le=60),
        decision_offset: int = Query(0, ge=0, le=60),
    ) -> ResultResponse:
        with sessions() as session:
            r = get_run(session, str(run_id))
            value = (
                r.result.get(section)
                if section != "summary"
                else {
                    k: v
                    for k, v in r.result.items()
                    if k not in {"methods", "folds", "points", "aggregate"}
                }
            )
            if isinstance(value, list):
                value = value[offset : offset + limit]
            value = bounded(value)

            def trim(item: Any) -> None:
                if isinstance(item, dict):
                    if isinstance(item.get("decisions"), list):
                        item["decision_count"] = len(item["decisions"])
                        item["decisions"] = item["decisions"][
                            decision_offset : decision_offset + decision_limit
                        ]
                    for v in item.values():
                        trim(v)
                elif isinstance(item, list):
                    for v in item:
                        trim(v)

            trim(value)
            if len(json.dumps(value)) > 2 * 1024 * 1024:
                raise OptimizationError("Reduce result/decision page size", "response_budget")
            return ResultResponse(
                run_id=r.id, status=r.status, result={"section": section, "data": value}
            )

    @router.get("/optimization/{run_id}/training-lineage", response_model=ResultResponse)
    def lineage(
        run_id: UUID,
        method: str | None = Query(None, max_length=180),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0, le=140000),
    ) -> ResultResponse:
        with sessions() as session:
            r = get_run(session, str(run_id))
            model = r.result.get("sentiment", {}).get("model", {})
            if method:
                model = next(
                    (
                        m.get("sentiment_model") or {}
                        for m in r.result.get("methods", [])
                        if m["method"] == method
                    ),
                    {},
                )
            rows = model.get("lineage", [])
            return ResultResponse(
                run_id=r.id,
                status=r.status,
                result={"total": len(rows), "items": rows[offset : offset + limit]},
            )

    @router.post("/optimization/{run_id}/replay", response_model=dict[str, Any])
    def rerun(run_id: UUID) -> dict[str, Any]:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Optimization job already active")
        try:
            with sessions() as session:
                return replay(session, str(run_id))
        finally:
            gate.release()

    return router

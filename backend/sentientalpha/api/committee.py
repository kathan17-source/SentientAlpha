"""Typed bounded investment committee services; no fitting, discovery or live execution."""

from threading import Semaphore
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.committee.contracts import AgentRecommendation
from sentientalpha.committee.requests import Request
from sentientalpha.committee.storage import execute, get, replay
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun

AGENTS = {
    "technical": "Existing M2 feature heuristic",
    "sentiment": "Complete eligible cached M3 sentiment mean",
    "quant": "Immutable M6 forecast; experimental, capped influence",
    "strategy": "Locked M7 validation-selected stateful rule",
    "fundamental": "Abstains without genuine point-in-time statements",
    "macro": "Abstains without genuine historical vintages",
}


class AgentInfo(BaseModel):
    id: str
    version: str = "8.0.0"
    description: str


class AgentList(BaseModel):
    items: list[AgentInfo]


class RunResponse(BaseModel):
    id: str
    status: str
    backtest_id: str | None
    manifest: dict[str, Any]
    result: dict[str, Any]


class RunPage(BaseModel):
    items: list[RunResponse]


class DecisionPage(BaseModel):
    items: list[dict[str, Any]]
    next_offset: int | None


class RecommendationPage(BaseModel):
    items: list[AgentRecommendation]


class ReplayResponse(BaseModel):
    run_id: str
    equivalent_decisions: bool
    equivalent_ledger: bool
    equivalent_metrics: bool
    numeric_tolerance: dict[str, float]
    decimal_strings: str
    scope: str


def present(saved: CommitteeRun) -> RunResponse:
    return RunResponse(
        id=saved.id,
        status=saved.status,
        backtest_id=saved.backtest_id,
        manifest=saved.manifest,
        result=saved.result,
    )


def committee_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(tags=["investment committee"])
    gate = Semaphore(1)

    def job(request: Request, execution: bool) -> RunResponse:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Committee job active")
        try:
            return present(execute(sessions, request, execution))
        finally:
            gate.release()

    @router.get("/api/agents", response_model=AgentList)
    def agents() -> AgentList:
        return AgentList(items=[AgentInfo(id=k, description=v) for k, v in AGENTS.items()])

    @router.get("/api/agents/{agent_id}", response_model=AgentInfo)
    def agent(agent_id: str) -> AgentInfo:
        if agent_id not in AGENTS:
            raise HTTPException(404, "Agent not found")
        return AgentInfo(id=agent_id, description=AGENTS[agent_id])

    @router.get("/api/agents/{agent_id}/performance", response_model=DecisionPage)
    def performance(
        agent_id: str, limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=100000)
    ) -> DecisionPage:
        agent(agent_id)
        with sessions() as session:
            rows = list(
                session.scalars(
                    select(CommitteeDecision)
                    .order_by(CommitteeDecision.decision_at, CommitteeDecision.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            items = [
                {
                    "run_id": d.run_id,
                    "decision_at": d.decision_at.isoformat(),
                    "recommendations": [
                        r for r in d.payload["recommendations"] if r["agent_id"] == agent_id
                    ],
                    "skill_status": "insufficient_data",
                    "confidence": None,
                    "limitation": "No source-authenticated matured-outcome attribution attached",
                }
                for d in rows[:limit]
            ]
            return DecisionPage(
                items=items, next_offset=offset + limit if len(rows) > limit else None
            )

    @router.post("/api/agents/analyze", response_model=RunResponse, status_code=201)
    @router.post("/api/investment-committee/analyze", response_model=RunResponse, status_code=201)
    def analyze(request: Request) -> RunResponse:
        return job(request, False)

    @router.post("/api/investment-committee/backtest", response_model=RunResponse, status_code=201)
    def backtest(request: Request) -> RunResponse:
        return job(request, True)

    @router.get("/api/investment-committee", response_model=RunPage)
    def runs(
        limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=100000)
    ) -> RunPage:
        with sessions() as session:
            return RunPage(
                items=[
                    present(r)
                    for r in session.scalars(
                        select(CommitteeRun)
                        .order_by(CommitteeRun.created_at, CommitteeRun.id)
                        .offset(offset)
                        .limit(limit)
                    )
                ]
            )

    @router.get("/api/investment-committee/{run_id}", response_model=RunResponse)
    def run(run_id: UUID) -> RunResponse:
        with sessions() as session:
            return present(get(session, str(run_id)))

    def page(run_id: str, limit: int, offset: int) -> DecisionPage:
        with sessions() as session:
            get(session, run_id)
            rows = list(
                session.scalars(
                    select(CommitteeDecision)
                    .where(CommitteeDecision.run_id == run_id)
                    .order_by(CommitteeDecision.sequence)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return DecisionPage(
                items=[{"id": r.id, "sequence": r.sequence, **r.payload} for r in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    @router.get("/api/investment-committee/{run_id}/decisions", response_model=DecisionPage)
    def audit(
        run_id: UUID, limit: int = Query(5, ge=1, le=10), offset: int = Query(0, ge=0, le=13000)
    ) -> DecisionPage:
        return page(str(run_id), limit, offset)

    @router.get("/api/investment-committee/{run_id}/agents", response_model=RecommendationPage)
    def recommendations(
        run_id: UUID, limit: int = Query(1, ge=1, le=5), offset: int = Query(0, ge=0, le=13000)
    ) -> RecommendationPage:
        rows = page(str(run_id), limit, offset).items
        return RecommendationPage(
            items=[
                AgentRecommendation.model_validate(r) for d in rows for r in d["recommendations"]
            ]
        )

    @router.get("/api/investment-committee/{run_id}/{section}", response_model=DecisionPage)
    def section(
        run_id: UUID,
        section: Literal["evidence", "allocation", "risk-review", "execution"],
        limit: int = Query(5, ge=1, le=10),
        offset: int = Query(0, ge=0, le=13000),
        kind: Literal["orders", "fills", "equity"] = "fills",
    ) -> DecisionPage:
        if section == "execution":
            with sessions() as session:
                saved = get(session, str(run_id))
                items = (
                    list(
                        session.scalars(
                            select(BacktestArtifact)
                            .where(
                                BacktestArtifact.run_id == saved.backtest_id,
                                BacktestArtifact.kind == kind,
                            )
                            .order_by(BacktestArtifact.sequence)
                            .offset(offset)
                            .limit(limit + 1)
                        )
                    )
                    if saved.backtest_id
                    else []
                )
                return DecisionPage(
                    items=[
                        {"backtest_id": saved.backtest_id, "kind": kind, **a.payload}
                        for a in items[:limit]
                    ],
                    next_offset=offset + limit if len(items) > limit else None,
                )
        rows = page(str(run_id), limit, offset)
        key = (
            "allocation"
            if section == "allocation"
            else "aggregation"
            if section == "evidence"
            else "risk_review"
        )
        return DecisionPage(
            items=[
                {
                    "decision_at": d["decision_at"],
                    key: d["allocation"].get("risk_review") if section == "risk-review" else d[key],
                    **({"recommendations": d["recommendations"]} if section == "evidence" else {}),
                }
                for d in rows.items
            ],
            next_offset=rows.next_offset,
        )

    @router.post("/api/investment-committee/{run_id}/replay", response_model=ReplayResponse)
    def reproduce(run_id: UUID) -> ReplayResponse:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Committee job active")
        try:
            with sessions() as session:
                return ReplayResponse.model_validate(replay(session, str(run_id)))
        finally:
            gate.release()

    return router

"""Typed bounded risk services backed by immutable calculated assessments."""

from datetime import datetime
from threading import Semaphore
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.data.contracts import utc
from sentientalpha.database.risk_models import RiskAlert, RiskAssessment, RiskPolicyVersion
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.risk.contracts import EvaluationRequest
from sentientalpha.risk.storage import execute, get, replay


class AssessmentResponse(BaseModel):
    id: str
    portfolio_id: str
    at: datetime
    status: str
    phase: str
    policy_key: str
    committee_id: str | None
    backtest_id: str | None
    payload: dict[str, Any]


class Page(BaseModel):
    items: list[dict[str, Any]]
    next_offset: int | None = None


class ReplayResponse(BaseModel):
    assessment_id: str
    equivalent_risk: bool
    numeric_tolerance: dict[str, float]
    scope: str


def present(row: RiskAssessment) -> AssessmentResponse:
    return AssessmentResponse(
        id=row.id,
        portfolio_id=row.portfolio_id,
        at=row.at,
        status=row.status,
        phase=row.phase,
        policy_key=row.policy_key,
        committee_id=row.committee_id,
        backtest_id=row.backtest_id,
        payload=row.payload,
    )


def risk_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/risk", tags=["independent risk management"])
    gate = Semaphore(1)

    @router.get("", response_model=Page)
    def summary() -> Page:
        with sessions() as session:
            return Page(
                items=[
                    {
                        "version": "9.0.0",
                        "simulation_only": True,
                        "assessments": session.scalar(
                            select(func.count()).select_from(RiskAssessment)
                        ),
                        "alerts": session.scalar(select(func.count()).select_from(RiskAlert)),
                        "risk_estimates_are_not_loss_guarantees": True,
                    }
                ]
            )

    def job(request: EvaluationRequest) -> AssessmentResponse:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Risk assessment active")
        try:
            return present(execute(sessions, request))
        finally:
            gate.release()

    @router.post("/evaluate", response_model=AssessmentResponse, status_code=201)
    def evaluate(request: EvaluationRequest) -> AssessmentResponse:
        return job(request)

    @router.post("/stress-test", response_model=AssessmentResponse, status_code=201)
    def stress(request: EvaluationRequest) -> AssessmentResponse:
        if not request.policy.scenarios:
            raise HTTPException(422, "Supply explicit versioned scenarios")
        return job(request)

    @router.get("/policies", response_model=Page)
    def policies(
        limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
    ) -> Page:
        with sessions() as session:
            rows = list(
                session.scalars(
                    select(RiskPolicyVersion)
                    .order_by(RiskPolicyVersion.policy_id, RiskPolicyVersion.version)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[{"key": r.key, **r.definition} for r in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    @router.get("/policies/{policy_id}", response_model=Page)
    def policy(
        policy_id: str,
        version: str | None = Query(None, max_length=80),
        limit: int = Query(20, ge=1, le=100),
    ) -> Page:
        with sessions() as session:
            query = select(RiskPolicyVersion).where(RiskPolicyVersion.policy_id == policy_id)
            if version is not None:
                query = query.where(RiskPolicyVersion.version == version)
            rows = list(
                session.scalars(query.order_by(RiskPolicyVersion.effective_at).limit(limit))
            )
            if not rows:
                raise HTTPException(404, "Risk policy not found")
            return Page(items=[{"key": r.key, **r.definition} for r in rows])

    @router.get("/decisions/{assessment_id}", response_model=AssessmentResponse)
    def assessment(assessment_id: str) -> AssessmentResponse:
        with sessions() as session:
            return present(get(session, assessment_id))

    @router.post("/decisions/{assessment_id}/replay", response_model=ReplayResponse)
    def reproduce(assessment_id: str) -> ReplayResponse:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Risk replay active")
        try:
            with sessions() as session:
                return ReplayResponse.model_validate(replay(session, assessment_id))
        finally:
            gate.release()

    def portfolio(
        session: Session, id: str, assessment_id: str | None, as_of: datetime | None
    ) -> RiskAssessment:
        if as_of is not None:
            try:
                as_of = utc(as_of)
            except ValueError as exc:
                raise OptimizationError("Aware as_of required") from exc
        if assessment_id:
            row = get(session, assessment_id)
            if row.portfolio_id != id:
                raise HTTPException(404, "Assessment does not belong to portfolio")
            if as_of is not None and row.at > utc(as_of):
                raise HTTPException(404, "Assessment unavailable at requested time")
            return row
        query = select(RiskAssessment).where(RiskAssessment.portfolio_id == id)
        if as_of is not None:
            try:
                cutoff = utc(as_of)
            except ValueError as exc:
                raise OptimizationError("Aware as_of required") from exc
            query = query.where(RiskAssessment.at <= cutoff)
        selected = session.scalar(
            query.order_by(
                RiskAssessment.at.desc(),
                RiskAssessment.sequence.desc(),
                RiskAssessment.created_at.desc(),
            ).limit(1)
        )
        if selected is None:
            raise HTTPException(404, "No portfolio risk snapshot at requested cutoff")
        return selected

    @router.get("/portfolio/{portfolio_id}", response_model=AssessmentResponse)
    def state(
        portfolio_id: str, assessment_id: str | None = None, as_of: datetime | None = None
    ) -> AssessmentResponse:
        with sessions() as session:
            return present(portfolio(session, portfolio_id, assessment_id, as_of))

    @router.get("/portfolio/{portfolio_id}/{section}", response_model=Page)
    def metric(
        portfolio_id: str,
        section: Literal[
            "exposure", "var", "cvar", "drawdown", "concentration", "volatility", "stress"
        ],
        assessment_id: str | None = None,
        as_of: datetime | None = None,
        snapshot: Literal["current", "proposed", "approved"] = "current",
    ) -> Page:
        with sessions() as session:
            row = portfolio(session, portfolio_id, assessment_id, as_of)
            data = row.payload.get(snapshot)
            if data and data.get("same_as"):
                data = row.payload[data["same_as"]]
            key = (
                "tail"
                if section in {"var", "cvar"}
                else "exposure"
                if section in {"exposure", "concentration"}
                else section
            )
            return Page(
                items=[
                    {
                        "assessment_id": row.id,
                        "snapshot": snapshot,
                        "at": row.at.isoformat(),
                        key: data.get(key) if data else None,
                        "status": row.status,
                        "policy_key": row.policy_key,
                    }
                ]
            )

    @router.get("/history", response_model=Page)
    def history(
        portfolio_id: str | None = Query(None, max_length=80),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
    ) -> Page:
        with sessions() as session:
            query = select(RiskAssessment)
            if portfolio_id:
                query = query.where(RiskAssessment.portfolio_id == portfolio_id)
            rows = list(
                session.scalars(
                    query.order_by(RiskAssessment.at, RiskAssessment.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[present(r).model_dump(mode="json") for r in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    @router.get("/alerts", response_model=Page)
    def alerts(
        limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
    ) -> Page:
        with sessions() as session:
            rows = list(
                session.scalars(
                    select(RiskAlert).order_by(RiskAlert.id).offset(offset).limit(limit + 1)
                )
            )
            return Page(
                items=[
                    {"id": r.id, "assessment_id": r.assessment_id, **r.payload}
                    for r in rows[:limit]
                ],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    return router

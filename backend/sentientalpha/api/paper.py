"""Typed local-user operational API; no arbitrary orders or brokerage capability."""

from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.config import Settings
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun
from sentientalpha.database.paper_models import PaperEvent, PaperSession
from sentientalpha.database.risk_models import RiskAssessment
from sentientalpha.paper import storage
from sentientalpha.paper.contracts import Advance, Command, Create, Reconcile, Update
from sentientalpha.paper.worker import update


class SessionResponse(BaseModel):
    id: str
    mode: Literal["forward_paper", "synthetic_demo", "historical_replay"]
    status: Literal["CREATED", "READY", "RUNNING", "PAUSED", "STOPPED", "FAILED"]
    configuration: dict[str, Any]
    portfolio: dict[str, Any]
    ledger_id: str
    warning: str | None
    created_at: str
    started_at: str | None
    last_processed_observation: str | None
    last_processing_at: str | None
    pending_orders: int
    reserved_cash: str
    reservation_policy: str
    valuation_stale: bool
    simulation_only: bool
    synthetic: bool
    latest_decision: dict[str, Any] | None
    last_provider_update: dict[str, Any] | None
    continuous_availability: bool


class Page(BaseModel):
    items: list[dict[str, Any]]
    next_offset: int | None = None


class Result(BaseModel):
    data: dict[str, Any]


def paper_router(sessions: sessionmaker[Session], settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/paper/sessions", tags=["persistent simulated paper operations"])

    def response(id: str) -> SessionResponse:
        with sessions() as s:
            return SessionResponse.model_validate(storage.present(s, storage.get(s, id)))

    @router.post("", response_model=SessionResponse, status_code=201)
    def create(q: Create) -> SessionResponse:
        return response(storage.create(sessions, q).id)

    @router.get("", response_model=Page)
    def listing(
        limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
    ) -> Page:
        with sessions() as s:
            rows = list(
                s.scalars(
                    select(PaperSession)
                    .order_by(PaperSession.created_at.desc())
                    .limit(limit + 1)
                    .offset(offset)
                )
            )
            return Page(
                items=[storage.present(s, row) for row in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    @router.get("/{id}", response_model=SessionResponse)
    def detail(id: str) -> SessionResponse:
        return response(id)

    @router.post("/{id}/advance", response_model=Result)
    def advance(id: str, q: Advance) -> Result:
        return Result(data=storage.advance(sessions, id, q))

    @router.post("/{id}/update", response_model=Result)
    def market_update(id: str, q: Update) -> Result:
        return Result(data=update(sessions, id, q, settings))

    @router.post("/{id}/orders/{order_id}/cancel", response_model=Result)
    def cancel(id: str, order_id: str, q: Command) -> Result:
        return Result(data=storage.cancel(sessions, id, order_id, q))

    @router.post("/{id}/reconcile", response_model=Result)
    def reconcile(id: str, q: Reconcile) -> Result:
        with sessions() as s:
            row = storage.get(s, id)
            data = storage.replay(s, row)
            if q.backtest_id:
                from sentientalpha.database.backtest_models import BacktestRun

                other = s.get(BacktestRun, q.backtest_id)
                if other is None:
                    raise storage.error("Comparison backtest not found", "not_found", 404)
                data["comparison"] = {
                    "backtest_id": other.id,
                    "backtest_metrics": other.metrics,
                    "paper_metrics": storage.performance(s, row)["metrics"],
                    "equal_not_assumed": True,
                    "differences_to_inspect": [
                        "mode",
                        "actual receipt/decision clocks",
                        "provider revisions",
                        "model versions",
                        "missed observations",
                        "risk state",
                        "execution price convention and costs",
                    ],
                }
            return Result(data=data)

    @router.get("/{id}/portfolio", response_model=Result)
    def portfolio(id: str) -> Result:
        return Result(data=response(id).model_dump()["portfolio"])

    @router.get("/{id}/performance", response_model=Result)
    def performance(id: str) -> Result:
        with sessions() as s:
            return Result(data=storage.performance(s, storage.get(s, id)))

    @router.get("/{id}/{kind}", response_model=Page)
    def records(
        id: str,
        kind: Literal["orders", "fills", "decisions", "risk", "events"],
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
    ) -> Page:
        with sessions() as s:
            row = storage.get(s, id)
            if kind in {"orders", "fills"}:
                rows = s.scalars(
                    select(BacktestArtifact)
                    .where(BacktestArtifact.run_id == row.ledger_id, BacktestArtifact.kind == kind)
                    .order_by(BacktestArtifact.sequence)
                    .offset(offset)
                    .limit(limit + 1)
                )
                items = [a.payload for a in rows]
            elif kind == "events":
                event_rows = s.scalars(
                    select(PaperEvent)
                    .where(PaperEvent.session_id == id)
                    .order_by(PaperEvent.sequence)
                    .offset(offset)
                    .limit(limit + 1)
                )
                items = [
                    {
                        "id": e.id,
                        "sequence": e.sequence,
                        "kind": e.kind,
                        "market_day": str(e.market_day) if e.market_day else None,
                        "processed_at": e.processed_at.isoformat(),
                        "hash": e.hash,
                        "summary": {
                            k: v
                            for k, v in e.payload.items()
                            if k not in {"decision", "risks", "operations"}
                        },
                        "decision_id": (e.payload.get("decision") or {}).get("decision_id"),
                    }
                    for e in event_rows
                ]
            elif kind == "decisions":
                items = [
                    {
                        "id": d.id,
                        "committee_id": c.id,
                        "at": d.decision_at.isoformat(),
                        "payload": d.payload,
                    }
                    for d, c in s.execute(
                        select(CommitteeDecision, CommitteeRun)
                        .join(CommitteeRun, CommitteeRun.id == CommitteeDecision.run_id)
                        .where(CommitteeRun.backtest_id == row.ledger_id)
                        .order_by(CommitteeDecision.decision_at)
                        .offset(offset)
                        .limit(limit + 1)
                    )
                ]
            else:
                items = [
                    {
                        "id": r.id,
                        "at": r.at.isoformat(),
                        "phase": r.phase,
                        "status": r.status,
                        "payload": r.payload,
                    }
                    for r in s.scalars(
                        select(RiskAssessment)
                        .where(RiskAssessment.backtest_id == row.ledger_id)
                        .order_by(RiskAssessment.at)
                        .offset(offset)
                        .limit(limit + 1)
                    )
                ]
            return Page(
                items=items[:limit], next_offset=offset + limit if len(items) > limit else None
            )

    @router.post("/{id}/{action}", response_model=SessionResponse)
    def lifecycle(
        id: str, action: Literal["ready", "start", "pause", "resume", "stop"], q: Command
    ) -> SessionResponse:
        return response(storage.transition(sessions, id, action, q).id)

    return router

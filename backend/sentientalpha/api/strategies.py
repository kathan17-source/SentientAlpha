"""Bounded strategy discovery and immutable validation-ranked research inspection."""

from threading import Semaphore
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.strategy_models import StrategyCandidate
from sentientalpha.strategies.contracts import Definition, Request
from sentientalpha.strategies.grammar import describe, requirements
from sentientalpha.strategies.storage import discover, evaluate_locked, get, replay


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    manifest: dict[str, Any]


class CandidateResponse(BaseModel):
    id: str
    discovery_id: str
    fold: int
    version: str
    status: str
    rule: str
    definition: dict[str, Any]
    requirements: list[str]
    performance: dict[str, Any]
    selected: bool


class CandidatePage(BaseModel):
    items: list[CandidateResponse]


def strategies_router(sessions: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/strategies", tags=["strategy discovery"])
    gate = Semaphore(1)

    def candidate(session: Session, value: str) -> StrategyCandidate:
        c = session.get(StrategyCandidate, value)
        if c is None:
            raise HTTPException(404, "Strategy not found")
        return c

    def present(session: Session, c: StrategyCandidate) -> CandidateResponse:
        run = get(session, c.discovery_id)
        prepared = run.result.get("prepared", run.result)
        selected = prepared["folds"][c.fold]["selected"] == c.rule_hash
        data = dict(c.payload)
        # Test results are disclosed separately, never used to order the leaderboard.
        data["test"] = (
            next(
                (
                    f.get("test")
                    for f in run.result.get("evaluation", {}).get("folds", [])
                    if f.get("fold") == c.fold
                ),
                None,
            )
            if selected
            else None
        )
        definition = Definition.model_validate(c.payload["definition"])
        return CandidateResponse(
            id=c.id,
            discovery_id=c.discovery_id,
            fold=c.fold,
            version=c.rule_hash,
            status=c.status,
            rule=describe(definition.entry),
            definition=c.payload["definition"],
            requirements=sorted(requirements(definition)),
            performance=data,
            selected=selected,
        )

    @router.post("/discover", response_model=RunResponse, status_code=201)
    def search(request: Request) -> Any:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Discovery job already active")
        try:
            return discover(sessions, request)
        finally:
            gate.release()

    @router.get("", response_model=CandidatePage)
    def history(
        run_id: UUID | None = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1000000),
    ) -> CandidatePage:
        with sessions() as session:
            q = select(StrategyCandidate)
            if run_id:
                q = q.where(StrategyCandidate.discovery_id == str(run_id))
            rows = session.scalars(
                q.order_by(
                    StrategyCandidate.discovery_id,
                    StrategyCandidate.fold,
                    StrategyCandidate.rule_hash,
                )
                .limit(limit)
                .offset(offset)
            )
            return CandidatePage(items=[present(session, c) for c in rows])

    @router.get("/leaderboard", response_model=CandidatePage)
    def leaderboard(
        run_id: UUID, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)
    ) -> CandidatePage:
        with sessions() as session:
            saved = get(session, str(run_id))
            prepared = saved.result.get("prepared", saved.result)
            ranks = [(f["fold"], h) for f in prepared.get("folds", []) for h in f["ranking"]]
            items = []
            for fold, h in ranks[offset : offset + limit]:
                c = session.scalar(
                    select(StrategyCandidate).where(
                        StrategyCandidate.discovery_id == str(run_id),
                        StrategyCandidate.fold == fold,
                        StrategyCandidate.rule_hash == h,
                    )
                )
                if c:
                    items.append(present(session, c))
            return CandidatePage(items=items)

    @router.get("/discovery/{run_id}", response_model=RunResponse)
    def retrieve(run_id: UUID) -> Any:
        with sessions() as session:
            return get(session, str(run_id))

    @router.get("/discovery/{run_id}/history")
    def search_history(
        run_id: UUID,
        fold: int = Query(0, ge=0, le=7),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0, le=1000000),
    ) -> dict[str, Any]:
        with sessions() as session:
            saved = get(session, str(run_id))
            prepared = saved.result.get("prepared", saved.result)
            folds = prepared.get("folds", [])
            rows: list[dict[str, Any]]
            if folds:
                rows = next((f["candidates"] for f in folds if f["fold"] == fold), [])
            else:
                partial = saved.result.get("partial_search_history") or {}
                rows = (
                    partial.get("candidates", [])
                    if partial.get("current_fold") == fold
                    else next(
                        (
                            f["candidates"]
                            for f in partial.get("completed_folds", [])
                            if f["fold"] == fold
                        ),
                        [],
                    )
                )
            return {
                "status": saved.status,
                "fold": fold,
                "items": rows[offset : offset + limit],
                "total": len(rows),
                "error_code": saved.result.get("error_code"),
            }

    @router.post("/discovery/{run_id}/evaluate", response_model=RunResponse)
    def final(run_id: UUID) -> Any:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Discovery job already active")
        try:
            return evaluate_locked(sessions, str(run_id))
        finally:
            gate.release()

    @router.post("/discovery/{run_id}/replay")
    def reproduce(run_id: UUID) -> dict[str, bool]:
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Discovery job already active")
        try:
            with sessions() as session:
                return replay(session, str(run_id))
        finally:
            gate.release()

    @router.get("/{strategy_id}", response_model=CandidateResponse)
    @router.get("/{strategy_id}/rules", response_model=CandidateResponse)
    @router.get("/{strategy_id}/performance", response_model=CandidateResponse)
    def detail(strategy_id: UUID) -> CandidateResponse:
        with sessions() as session:
            return present(session, candidate(session, str(strategy_id)))

    @router.post("/{strategy_id}/evaluate", response_model=RunResponse)
    def evaluate_strategy(strategy_id: UUID) -> Any:
        with sessions() as session:
            c = candidate(session, str(strategy_id))
            run = get(session, c.discovery_id)
            prepared = run.result.get("prepared", run.result)
            if prepared["folds"][c.fold]["selected"] != c.rule_hash:
                raise HTTPException(409, "Only the frozen selected strategy may use the final test")
            run_id = c.discovery_id
        return final(UUID(run_id))

    @router.get("/{strategy_id}/robustness")
    def robustness(strategy_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            c = candidate(session, str(strategy_id))
            run = get(session, c.discovery_id)
            fold: dict[str, Any] = next(
                (
                    f
                    for f in run.result.get("evaluation", {}).get("folds", [])
                    if f.get("rule_hash") == c.rule_hash and f["fold"] == c.fold
                ),
                {},
            )
            return {
                "strategy_id": c.id,
                "status": run.status,
                "robustness": fold.get("robustness", []),
                "warnings": fold.get("warnings", []),
            }

    @router.get("/{strategy_id}/trades")
    def trades(
        strategy_id: UUID,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0, le=1000000),
    ) -> dict[str, Any]:
        with sessions() as session:
            c = candidate(session, str(strategy_id))
            run = get(session, c.discovery_id)
            links = [
                link
                for link in run.result.get("evaluation", {}).get("ledger_links", [])
                if link["fold"] == c.fold and link["kind"] == "test"
            ]
            prepared = run.result.get("prepared", run.result)
            if not links or prepared["folds"][c.fold]["selected"] != c.rule_hash:
                return {"items": [], "status": "no_selected_test_ledger"}
            ledger = links[0]["run_id"]
            fills = list(
                session.scalars(
                    select(BacktestArtifact)
                    .where(BacktestArtifact.run_id == ledger, BacktestArtifact.kind == "fills")
                    .order_by(BacktestArtifact.sequence)
                    .limit(limit)
                    .offset(offset)
                )
            )
            sequences = [int(r.payload["order_id"].rsplit("-", 1)[1]) - 1 for r in fills]
            orders = {
                r.payload["id"]: r.payload
                for r in session.scalars(
                    select(BacktestArtifact).where(
                        BacktestArtifact.run_id == ledger,
                        BacktestArtifact.kind == "orders",
                        BacktestArtifact.sequence.in_(sequences),
                    )
                )
            }
            traces = next(
                f["trace"] for f in run.result["evaluation"]["folds"] if f["fold"] == c.fold
            )
            items = []
            for r in fills:
                order = orders[r.payload["order_id"]]
                trace = next(
                    (
                        t
                        for t in traces
                        if t["at"] == order["submitted_at"] and t["ticker"] == order["ticker"]
                    ),
                    None,
                )
                items.append({"fill": r.payload, "order": order, "signal": trace})
            return {
                "items": items,
                "ledger_id": ledger,
                "portfolio_snapshots": f"/api/backtest/{ledger}/equity",
            }

    return router

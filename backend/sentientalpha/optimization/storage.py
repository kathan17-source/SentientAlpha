"""Persist/replay frozen estimates and research; link actual M4 ledgers."""

from importlib.metadata import version
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.contracts import Snapshot
from sentientalpha.backtesting.storage import build_id, digest, persist
from sentientalpha.database.base import new_id, now
from sentientalpha.database.optimization_models import OptimizationRun
from sentientalpha.optimization import VERSION
from sentientalpha.optimization.contracts import (
    FrontierRequest,
    OptimizationRequest,
    ResearchRequest,
    WalkResearch,
)
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.optimization.inputs import Inputs, freeze, load_inputs, thaw
from sentientalpha.optimization.research import compare, frontier, optimize, walk

Request = OptimizationRequest | FrontierRequest | ResearchRequest | WalkResearch


def base_request(request: Request) -> OptimizationRequest:
    if isinstance(request, OptimizationRequest):
        return request
    if isinstance(request, FrontierRequest):
        return request.optimization
    if isinstance(request, ResearchRequest):
        return request.optimization
    return request.research.optimization


def execute(request: Request, inputs: Inputs) -> tuple[str, dict[str, Any]]:
    if isinstance(request, OptimizationRequest):
        return "optimization", optimize(request, inputs)
    if isinstance(request, FrontierRequest):
        return "frontier", frontier(request, inputs)
    if isinstance(request, ResearchRequest):
        return "comparison", compare(request, inputs)
    return "walk_forward", walk(request, inputs)


def numerical(result: dict[str, Any]) -> dict[str, Any]:
    # Runtime measurements and random database link IDs are not numerical research outputs.
    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: clean(v)
                for k, v in value.items()
                if k not in {"solve_seconds", "backtest_run_id", "_backtests"}
            }
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    return clean(result)


def run(sessions: sessionmaker[Session], request: Request) -> OptimizationRun:
    base = base_request(request)
    extras = (
        request.sentiment_ablations
        if isinstance(request, ResearchRequest)
        else request.research.sentiment_ablations
        if isinstance(request, WalkResearch)
        else []
    )
    with sessions() as session:
        inputs = load_inputs(session, base, extras)
    import json

    frozen = freeze(inputs)
    if len(json.dumps(frozen)) > 64 * 1024 * 1024:
        raise OptimizationError("Frozen experiment exceeds 64 MiB budget")
    run_id = new_id()
    kind = (
        "optimization"
        if isinstance(request, OptimizationRequest)
        else "frontier"
        if isinstance(request, FrontierRequest)
        else "comparison"
        if isinstance(request, ResearchRequest)
        else "walk_forward"
    )
    manifest = {
        "run_id": run_id,
        "engine_version": VERSION,
        "build_id": build_id(),
        "created_at": now().isoformat(),
        "configuration": request.model_dump(mode="json"),
        "configuration_hash": digest(request.model_dump(mode="json")),
        "input_hash": digest(frozen),
        "dependencies": {
            n: version(n)
            for n in ("numpy", "scipy", "pandas", "SQLAlchemy", "pydantic", "exchange-calendars")
        },
        "backtest_links": [],
        "execution_certified": False,
        "random_seed": None,
    }
    saved = OptimizationRun(
        id=run_id,
        kind=kind,
        status="running",
        manifest=manifest,
        inputs=frozen,
        result={"status": "running"},
    )
    with sessions.begin() as session:
        session.add(saved)
    ledgers = []
    try:
        _, result = execute(request, inputs)
        for bt in result.pop("_backtests", []):
            config = BacktestRequest.model_validate(bt["request"])
            execution_snapshot = Snapshot(
                tuple(
                    b
                    for b in inputs.prices.bars
                    if b.ticker in config.tickers and config.start <= b.day <= config.end
                ),
                (),
                inputs.prices.definitions,
            )
            child = persist(
                sessions,
                config,
                execution_snapshot,
                bt["result"],
                {
                    "external_target_strategy": "optimization",
                    "optimization_run_id": run_id,
                    "method": bt["method"],
                    "fold_index": bt.get("fold"),
                },
            )
            ledgers.append(
                {"method": bt["method"], "fold": bt.get("fold"), "backtest_run_id": child.id}
            )
        result["backtest_links"] = ledgers
        if len(json.dumps(result)) > 64 * 1024 * 1024:
            raise OptimizationError("Experiment result exceeds 64 MiB budget")
        manifest = {**manifest, "backtest_links": ledgers, "result_hash": digest(numerical(result))}
        with sessions.begin() as session:
            current = get_run(session, run_id)
            current.status = result["status"]
            current.result = result
            current.manifest = manifest
        saved.status = result["status"]
        saved.result = result
        saved.manifest = manifest
        return saved
    except Exception as exc:
        with sessions.begin() as session:
            current = get_run(session, run_id)
            current.status = "failed"
            current.result = {
                "status": "failed",
                "error_code": getattr(exc, "code", "internal_error"),
                "backtest_links": ledgers,
            }
            current.manifest = {**manifest, "backtest_links": ledgers}
        raise


def get_run(session: Session, run_id: str) -> OptimizationRun:
    saved = session.get(OptimizationRun, run_id)
    if saved is None:
        raise OptimizationError("Optimization run not found", "not_found", 404)
    return saved


def replay(session: Session, run_id: str) -> dict[str, Any]:
    saved = get_run(session, run_id)
    if saved.status in {"running", "failed"}:
        raise OptimizationError(
            "Incomplete or failed experiment cannot be replayed as success", "incomplete_run", 409
        )
    m = saved.manifest
    if (
        digest(saved.inputs) != m["input_hash"]
        or digest(m["configuration"]) != m["configuration_hash"]
        or build_id() != m["build_id"]
        or any(version(n) != v for n, v in m["dependencies"].items())
    ):
        raise OptimizationError(
            "Frozen inputs, configuration, build or dependencies changed", "replay_mismatch", 409
        )
    types: dict[str, Any] = {
        "optimization": OptimizationRequest,
        "frontier": FrontierRequest,
        "comparison": ResearchRequest,
        "walk_forward": WalkResearch,
    }
    request = types[saved.kind].model_validate(m["configuration"])
    _, result = execute(request, thaw(saved.inputs))
    backtests = result.pop("_backtests", [])
    from sqlalchemy import select

    from sentientalpha.database.backtest_models import BacktestArtifact

    ledger_equal = True
    for bt, link in zip(backtests, m["backtest_links"], strict=True):
        for kind in ("orders", "fills", "equity", "actions"):
            stored = list(
                session.scalars(
                    select(BacktestArtifact)
                    .where(
                        BacktestArtifact.run_id == link["backtest_run_id"],
                        BacktestArtifact.kind == kind,
                    )
                    .order_by(BacktestArtifact.sequence)
                )
            )
            ledger_equal &= digest([r.payload for r in stored]) == digest(bt["result"][kind])
    result["backtest_links"] = m["backtest_links"]
    return {
        "run_id": saved.id,
        "equivalent_numerical_results": digest(numerical(result)) == m["result_hash"],
        "equivalent_execution_artifacts": ledger_equal,
    }

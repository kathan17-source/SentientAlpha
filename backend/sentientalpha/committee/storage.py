"""Idempotent durable audit, atomic M4 links and frozen-source historical replay."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from importlib.metadata import version
from math import isclose
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.storage import build_id, digest, encode, persist
from sentientalpha.backtesting.strategies import Context
from sentientalpha.committee.engine import CommitteeStrategy, backtest_config, run
from sentientalpha.committee.requests import Request
from sentientalpha.committee.sources import load_sources
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.base import new_id, now
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun
from sentientalpha.database.models import Asset, MarketPrice
from sentientalpha.database.session import serialize_writer
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.strategies.contracts import Request as DiscoveryRequest
from sentientalpha.strategies.evaluation import snapshot as execution_snapshot
from sentientalpha.strategies.inputs import Inputs, freeze, thaw

DEPENDENCIES = (
    "numpy",
    "scipy",
    "pandas",
    "SQLAlchemy",
    "pydantic",
    "exchange-calendars",
    "scikit-learn",
)


def frozen_sources(inputs: Inputs, metadata: dict[str, Any]) -> dict[str, Any]:
    frozen = freeze(inputs)
    prices = frozen.pop("prices")
    frozen["price_references"] = [b["source_id"] for b in prices["bars"]]
    frozen["price_hash"] = digest(prices)
    return {"features": frozen, "metadata": metadata}


def restore(session: Session, saved: dict[str, Any]) -> tuple[Inputs, dict[str, Any]]:
    frozen = dict(saved["features"])
    ids = frozen.pop("price_references")
    expected = frozen.pop("price_hash")
    bars = {}
    for start in range(0, len(ids), 500):
        for p, ticker in session.execute(
            select(MarketPrice, Asset.ticker)
            .join(Asset, Asset.id == MarketPrice.asset_id)
            .where(MarketPrice.id.in_(ids[start : start + 500]))
        ):
            bars[p.id] = Bar(
                ticker,
                p.session_date,
                p.open,
                p.close,
                p.volume,
                p.available_at,
                p.ingested_at,
                p.id,
                p.revision_no,
            )
    if set(bars) != set(ids):
        raise OptimizationError(
            "Required immutable market references are missing", "replay_mismatch", 409
        )
    prices = encode(Snapshot(tuple(bars[v] for v in ids)))
    if digest(prices) != expected:
        raise OptimizationError("Referenced source prices changed", "replay_mismatch", 409)
    frozen["prices"] = prices
    return thaw(frozen), saved["metadata"]


def get(session: Session, run_id: str) -> CommitteeRun:
    saved = session.get(CommitteeRun, run_id)
    if saved is None:
        raise OptimizationError("Committee run not found", "not_found", 404)
    return saved


def decisions(session: Session, run_id: str) -> list[dict[str, Any]]:
    return [
        d.payload
        for d in session.scalars(
            select(CommitteeDecision)
            .where(CommitteeDecision.run_id == run_id)
            .order_by(CommitteeDecision.sequence)
        )
    ]


def evaluate(
    request: Request, inputs: Inputs, metadata: dict[str, Any], execution: bool
) -> tuple[dict[str, Any], CommitteeStrategy]:
    if execution:
        return run(request, inputs, metadata)
    days = sessions_in_range(inputs.calendar, request.start, request.end)
    if not days:
        raise OptimizationError("Analysis requires an exchange session")
    day = days[-1]
    at = session_close(inputs.calendar, day) + timedelta(seconds=1)
    adapter = CommitteeStrategy(request, inputs, metadata)
    prices = {}
    for bar in inputs.prices.bars:
        clock = bar.available
        if request.information_policy == "online":
            clock = max(clock, bar.ingested)
        if request.information_policy == "retrospective":
            clock = session_close(inputs.calendar, bar.day) + timedelta(seconds=1)
        if bar.day <= day and clock <= at and bar.close is not None:
            prices[bar.ticker] = bar.close
    context = Context(at, day, tuple(sorted(prices.items())), (), (), Decimal(str(request.capital)))
    targets = adapter.targets(context)
    if adapter.risk_control is not None:
        adapter.risk_control.approve_targets(context, targets)
    return {"status": "analyzed", "metrics": {}, "orders": [], "fills": [], "equity": []}, adapter


def execute(
    sessions: sessionmaker[Session], request: Request, execution: bool = False
) -> CommitteeRun:
    request = Request.model_validate(request.model_dump())
    config = request.model_dump(mode="json")
    config_hash = digest({"configuration": config, "execution": execution})
    started = perf_counter()
    with sessions() as session:
        serialize_writer(session, "committee:" + request.idempotency_key)
        existing = session.scalar(
            select(CommitteeRun).where(CommitteeRun.idempotency_key == request.idempotency_key)
        )
        if existing:
            if existing.manifest["configuration_hash"] != config_hash:
                raise OptimizationError(
                    "Idempotency key has a different immutable configuration",
                    "idempotency_conflict",
                    409,
                )
            if existing.status == "running":
                raise OptimizationError("Committee job already running", "job_active", 409)
            return existing
        source_started = perf_counter()
        inputs, metadata = load_sources(session, request)
        source_seconds = perf_counter() - source_started
        frozen = frozen_sources(inputs, metadata)
        if len(json.dumps(frozen)) > 64 * 1024 * 1024:
            raise OptimizationError("Frozen committee input exceeds 64 MiB")
        saved = CommitteeRun(
            id=new_id(),
            idempotency_key=request.idempotency_key,
            status="running",
            backtest_id=None,
            manifest={
                "version": "8.0.0",
                "configuration": config,
                "configuration_hash": config_hash,
                "execution": execution,
                "build_id": build_id(),
                "input_hash": digest(frozen),
                "dependencies": {n: version(n) for n in DEPENDENCIES},
                "created_at": now().isoformat(),
                "simulation_only": True,
                "historical_scope": request.information_policy,
                "outcome_policy": "No holdout-based selection; sample previously inspected",
            },
            inputs=frozen,
            result={},
        )
        session.add(saved)
        commit_started = perf_counter()
        session.commit()
        initial_commit_seconds = perf_counter() - commit_started
    retrieval = perf_counter() - started
    try:
        calc_start = perf_counter()
        result, adapter = evaluate(request, inputs, metadata, execution)
        compute = perf_counter() - calc_start
        primary_persistence_started = perf_counter()
        with sessions.begin() as session:
            parent = get(session, saved.id)
            persistence_start = perf_counter()
            if execution:
                child = persist(
                    sessions,
                    backtest_config(request, inputs),
                    execution_snapshot(
                        DiscoveryRequest.model_validate(metadata["source_configuration"]),
                        inputs,
                        request.start,
                        request.end,
                    ),
                    result,
                    {"external_target_strategy": "investment_committee", "committee_id": saved.id},
                    transaction=session,
                )
                parent.backtest_id = child.id
            for i, record in enumerate(adapter.trace):
                session.add(
                    CommitteeDecision(
                        run_id=saved.id,
                        sequence=i,
                        decision_at=datetime.fromisoformat(record["decision_at"]),
                        payload=record,
                    )
                )
            if adapter.risk_control is not None:
                from sentientalpha.risk.storage import persist_events

                persist_events(session, adapter.risk_control, saved.id, parent.backtest_id)
            summary = {
                "metrics": result["metrics"],
                "decision_count": len(adapter.trace),
                "orders": len(result["orders"]),
                "fills": len(result["fills"]),
                "decision_hash": digest(adapter.trace),
                "artifact_hashes": {k: digest(result[k]) for k in ("orders", "fills", "equity")},
                "participation": {
                    a: sum(
                        r["status"] in {"positive", "negative", "neutral"}
                        for d in adapter.trace
                        for r in d["recommendations"]
                        if r["agent_id"] == a
                    )
                    for a in request.agents
                },
                "abstentions": sum(
                    r["signal"] is None for d in adapter.trace for r in d["recommendations"]
                ),
                "disagreement_decisions": sum(
                    any(v["disagreement"] for v in d["aggregation"].values()) for d in adapter.trace
                ),
                "risk_vetoes": sum(d["allocation"]["action"] == "reject" for d in adapter.trace),
            }
            if adapter.risk_control is not None:
                summary["m9_risk"] = {
                    "events": len(adapter.risk_control.events),
                    "timings_seconds": adapter.risk_control.timings,
                    "statuses": {
                        s: sum(e["result"]["status"] == s for e in adapter.risk_control.events)
                        for s in [
                            "APPROVED",
                            "APPROVED_WITH_REDUCTION",
                            "REJECTED",
                            "NO_NEW_RISK",
                            "INSUFFICIENT_RISK_DATA",
                        ]
                    },
                }
            parent.status = result["status"]
            parent.result = summary
            parent.manifest = {
                **parent.manifest,
                "result_hash": digest(summary),
                "timings_seconds": {
                    "retrieval": retrieval,
                    "source_retrieval": source_seconds,
                    "compute": compute,
                    **adapter.timings,
                },
                "persistence_work_seconds": perf_counter() - persistence_start,
            }
            session.flush()
        persistence_seconds = perf_counter() - primary_persistence_started + initial_commit_seconds
        with sessions.begin() as session:
            parent = get(session, saved.id)
            parent.manifest = {**parent.manifest, "persistence_seconds": persistence_seconds}
        with sessions() as session:
            return get(session, saved.id)
    except Exception:
        with sessions.begin() as session:
            parent = get(session, saved.id)
            if parent.status != "running":
                raise
            parent.status = "failed"
            parent.result = {
                "error": "committee_evaluation_failed",
                "detail": "No partial decisions or child ledger committed",
            }
        raise


def equivalent(a: Any, b: Any) -> bool:
    if isinstance(a, float) and isinstance(b, (float, int)):
        return isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def replay(session: Session, run_id: str) -> dict[str, Any]:
    saved = get(session, run_id)
    m = saved.manifest
    if saved.status in {"running", "failed"}:
        raise OptimizationError(
            "Cannot replay incomplete/failed committee run", "replay_mismatch", 409
        )
    if (
        m["build_id"] != build_id()
        or digest(saved.inputs) != m["input_hash"]
        or digest(saved.result) != m["result_hash"]
        or digest({"configuration": m["configuration"], "execution": m["execution"]})
        != m["configuration_hash"]
        or any(version(n) != v for n, v in m["dependencies"].items())
    ):
        raise OptimizationError(
            "Committee build/input/configuration/result/dependency mismatch", "replay_mismatch", 409
        )
    inputs, metadata = restore(session, saved.inputs)
    result, adapter = evaluate(
        Request.model_validate(m["configuration"]), inputs, metadata, m["execution"]
    )
    original = decisions(session, run_id)
    if digest(original) != saved.result["decision_hash"]:
        raise OptimizationError("Saved decision audit was altered", "replay_mismatch", 409)
    artifacts = True
    for kind in ("orders", "fills", "equity"):
        if saved.backtest_id:
            rows = [
                a.payload
                for a in session.scalars(
                    select(BacktestArtifact)
                    .where(
                        BacktestArtifact.run_id == saved.backtest_id, BacktestArtifact.kind == kind
                    )
                    .order_by(BacktestArtifact.sequence)
                )
            ]
            if digest(rows) != saved.result["artifact_hashes"][kind]:
                raise OptimizationError(
                    "Saved authoritative ledger artifacts differ", "replay_mismatch", 409
                )
            artifacts &= equivalent(rows, result[kind])
    if adapter.risk_control is not None:
        from sentientalpha.risk.storage import verify_events

        if not verify_events(session, run_id, adapter.risk_control):
            raise OptimizationError("Persisted M9 risk events differ", "replay_mismatch", 409)
    return {
        "run_id": run_id,
        "equivalent_decisions": equivalent(original, adapter.trace),
        "equivalent_ledger": artifacts,
        "equivalent_metrics": equivalent(saved.result["metrics"], result["metrics"]),
        "numeric_tolerance": {"relative": 1e-9, "absolute": 1e-9},
        "decimal_strings": "exact",
        "scope": "Frozen derived inputs/versions and immutable price references; no reacquisition",
    }

"""Frozen selection before test access, holdout reservations, canonical history and M4 links."""

import json
from datetime import date
from importlib.metadata import version
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.storage import build_id, digest, persist
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.base import new_id, now
from sentientalpha.database.ml_models import MLExperiment
from sentientalpha.database.session import serialize_writer
from sentientalpha.database.strategy_models import DiscoveryRun, HoldoutUse, StrategyCandidate
from sentientalpha.strategies import VERSION
from sentientalpha.strategies.contracts import DiscoveryError, Request
from sentientalpha.strategies.inputs import Inputs, freeze, load, thaw
from sentientalpha.strategies.research import final_evaluation, prepare


def dependencies() -> dict[str, str]:
    return {
        n: version(n) for n in ("numpy", "pandas", "SQLAlchemy", "pydantic", "exchange-calendars")
    }


def get(session: Session, run_id: str) -> DiscoveryRun:
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        raise DiscoveryError("Discovery not found", "not_found", 404)
    return run


def bounded(value: Any) -> None:
    if len(json.dumps(value, allow_nan=False)) > 64 * 1024 * 1024:
        raise DiscoveryError("Discovery JSON budget exceeds64MiB")


def reuse(session: Session, request: Request, provider: str) -> list[dict[str, Any]]:
    warnings = []
    for w in request.windows:
        prior = session.scalars(
            select(HoldoutUse).where(
                HoldoutUse.provider == provider,
                HoldoutUse.start <= w.test_end,
                HoldoutUse.end >= w.test_start,
            )
        )
        for h in prior:
            if set(h.tickers) & set(request.tickers):
                warnings.append(
                    {
                        "source": "discovery_reservation",
                        "run_id": h.discovery_id,
                        "status": h.status,
                    }
                )
    for ml in session.scalars(
        select(MLExperiment).where(MLExperiment.status.in_(["completed", "partial"]))
    ):
        cfg = ml.manifest.get("configuration", {})
        if not set(cfg.get("tickers", [])) & set(request.tickers):
            continue
        for other in cfg.get("windows", []):
            if any(
                w.test_start <= date.fromisoformat(other["test_end"])
                and w.test_end >= date.fromisoformat(other["test_start"])
                for w in request.windows
            ):
                warnings.append({"source": "prior_ml_holdout", "run_id": ml.id})
                break
    if warnings and request.holdout_history != "previously_inspected":
        raise DiscoveryError(
            "Overlapping reserved/previously inspected holdout; explicitly mark exploratory reuse",
            "holdout_reuse",
            409,
        )
    return warnings


def discover(
    sessions: sessionmaker[Session], request: Request, supplied: Inputs | None = None
) -> DiscoveryRun:
    configuration = request.model_dump(mode="json")
    with sessions() as session:
        existing = session.scalar(
            select(DiscoveryRun).where(DiscoveryRun.idempotency_key == request.idempotency_key)
        )
        if existing:
            if existing.manifest["configuration_hash"] != digest(configuration):
                raise DiscoveryError(
                    "Idempotency key cannot change the research manifest", "immutable_manifest", 409
                )
            session.expunge(existing)
            return existing
        inputs = supplied if supplied is not None else load(session, request)
    frozen = freeze(inputs)
    bounded(frozen)
    run_id = new_id()
    with sessions() as session:
        serialize_writer(session, "strategy_discovery_holdout_registry")
        # Global local-registry reservation is serialized, including cross-asset overlaps.
        existing = session.scalar(
            select(DiscoveryRun).where(DiscoveryRun.idempotency_key == request.idempotency_key)
        )
        if existing:
            if existing.manifest["configuration_hash"] != digest(configuration):
                raise DiscoveryError("Idempotency key conflict", "immutable_manifest", 409)
            session.expunge(existing)
            return existing
        reused = reuse(session, request, inputs.metadata["provider"])
        manifest = {
            "version": VERSION,
            "created_at": now().isoformat(),
            "configuration": configuration,
            "configuration_hash": digest(configuration),
            "input_hash": digest(frozen),
            "build_id": build_id(),
            "dependencies": dependencies(),
            "holdout_reuse": reused,
            "holdout_label": "previously_inspected_exploratory"
            if reused or request.holdout_history == "previously_inspected"
            else "new_local_reservation_not_global_attestation",
            "data_metadata": inputs.metadata,
        }
        session.add(
            DiscoveryRun(
                id=run_id,
                idempotency_key=request.idempotency_key,
                status="searching",
                manifest=manifest,
                inputs=frozen,
                result={},
            )
        )
        session.flush()
        for i, w in enumerate(request.windows):
            session.add(
                HoldoutUse(
                    discovery_id=run_id,
                    fold=i,
                    provider=inputs.metadata["provider"],
                    start=w.test_start,
                    end=w.test_end,
                    tickers=request.tickers,
                    status="reserved",
                )
            )
        session.commit()
    try:
        result = prepare(request, inputs)
        bounded(result)
        with sessions() as session:
            saved = get(session, run_id)
            saved.result, saved.status = result, result["status"]
            saved.manifest = {
                **saved.manifest,
                "prepared_hash": digest(result),
                "selection_hash": result["selection_hash"],
                "selection_frozen_at": now().isoformat(),
            }
            for fold in result["folds"]:
                for c in fold["candidates"]:
                    score = c.get("validation", {}).get("fitness", {}).get("score")
                    session.add(
                        StrategyCandidate(
                            id=new_id(),
                            discovery_id=run_id,
                            fold=fold["fold"],
                            rule_hash=c["rule_hash"],
                            status=c["status"],
                            validation_score=str(score) if score is not None else None,
                            payload=c,
                        )
                    )
            session.commit()
            session.expunge(saved)
            return saved
    except Exception as exc:
        with sessions() as session:
            saved = get(session, run_id)
            saved.status, saved.result = (
                "failed",
                {
                    "error_code": exc.code
                    if isinstance(exc, DiscoveryError)
                    else "discovery_failed",
                    "partial_search_history": getattr(exc, "partial_history", None),
                },
            )
            session.commit()
        if isinstance(exc, DiscoveryError):
            raise
        raise DiscoveryError(
            "Discovery failed; sanitized audit retained", "discovery_failed", 500
        ) from exc


def integrity(saved: DiscoveryRun) -> Request:
    m = saved.manifest
    if (
        m["build_id"] != build_id()
        or dependencies() != m["dependencies"]
        or digest(saved.inputs) != m["input_hash"]
        or digest(m["configuration"]) != m["configuration_hash"]
        or digest(saved.result.get("prepared", saved.result)) != m.get("prepared_hash")
    ):
        raise DiscoveryError(
            "Discovery build/dependencies/inputs/configuration/selection differ",
            "replay_mismatch",
            409,
        )
    return Request.model_validate(m["configuration"])


def evaluate_locked(sessions: sessionmaker[Session], run_id: str) -> DiscoveryRun:
    with sessions() as session:
        serialize_writer(session, "strategy_discovery_holdout_registry")
        saved = get(session, run_id)
        request = integrity(saved)
        if saved.status == "evaluated":
            if digest(saved.result) != saved.manifest.get("result_hash"):
                raise DiscoveryError("Saved evaluation changed", "replay_mismatch", 409)
            session.expunge(saved)
            return saved
        if saved.status != "ready_for_test":
            raise DiscoveryError(
                "Only a frozen, unevaluated selection can consume the holdout",
                "invalid_discovery_state",
                409,
            )
        inputs, prepared = thaw(saved.inputs), saved.result
        saved.status = "evaluating"
        saved.manifest = {**saved.manifest, "test_started_at": now().isoformat()}
        for h in session.scalars(select(HoldoutUse).where(HoldoutUse.discovery_id == run_id)):
            h.status = "consumed"
        session.commit()
    links = []

    def record(fold: int, kind: str, cfg: Any, snap: Any, result: Any) -> str:
        child = persist(
            sessions,
            cfg,
            snap,
            result,
            {
                "external_target_strategy": "strategy_discovery",
                "discovery_id": run_id,
                "fold": fold,
                "kind": kind,
            },
        )
        links.append(child.id)
        return child.id

    try:
        evaluated = final_evaluation(request, inputs, prepared, record)
        result = {"prepared": prepared, "evaluation": evaluated}
        bounded(result)
        with sessions() as session:
            saved = get(session, run_id)
            saved.status, saved.result = "evaluated", result
            saved.manifest = {
                **saved.manifest,
                "result_hash": digest(result),
                "test_finished_at": now().isoformat(),
            }
            session.commit()
            session.expunge(saved)
            return saved
    except Exception as exc:
        with sessions() as session:
            saved = get(session, run_id)
            saved.status = "failed_evaluation"
            saved.manifest = {
                **saved.manifest,
                "partial_child_links": links,
                "error_code": exc.code if isinstance(exc, DiscoveryError) else "evaluation_failed",
            }
            session.commit()
        if isinstance(exc, DiscoveryError):
            raise
        raise DiscoveryError(
            "Locked evaluation failed; consumed holdout/audit retained", "evaluation_failed", 500
        ) from exc


def replay(session: Session, run_id: str) -> dict[str, bool]:
    saved = get(session, run_id)
    if saved.status not in {"ready_for_test", "no_eligible_strategy", "evaluated"}:
        raise DiscoveryError(
            "Incomplete/failed discovery is not replay certified", "invalid_discovery_state", 409
        )
    request = integrity(saved)
    inputs = thaw(saved.inputs)
    fresh = prepare(request, inputs)
    original = saved.result.get("prepared", saved.result)
    equivalent = digest(fresh) == digest(original)
    ledgers = True
    if saved.status == "evaluated":
        if digest(saved.result) != saved.manifest["result_hash"]:
            raise DiscoveryError("Evaluation result hash differs", "replay_mismatch", 409)
        original_links = iter(saved.result["evaluation"]["ledger_links"])

        def check(fold: int, kind: str, cfg: Any, snap: Any, result: Any) -> str:
            nonlocal ledgers
            link = next(original_links)
            if link["fold"] != fold or link["kind"] != kind:
                raise DiscoveryError("Ledger link ordering differs", "replay_mismatch", 409)
            for k in ("orders", "fills", "equity", "actions"):
                artifacts = session.scalars(
                    select(BacktestArtifact)
                    .where(BacktestArtifact.run_id == link["run_id"], BacktestArtifact.kind == k)
                    .order_by(BacktestArtifact.sequence)
                )
                ledgers &= digest([r.payload for r in artifacts]) == digest(result[k])
            return link["run_id"]

        final = final_evaluation(request, inputs, fresh, check)
        equivalent &= digest(final) == digest(saved.result["evaluation"])
    return {"equivalent_search_and_selection": equivalent, "equivalent_ledger_artifacts": ledgers}

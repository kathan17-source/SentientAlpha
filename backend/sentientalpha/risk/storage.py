"""Atomic standalone/committee risk audit, immutable policy versions and exact source replay."""

import copy
import json
from datetime import datetime
from importlib.metadata import version
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.storage import build_id, digest
from sentientalpha.database.risk_models import RiskAlert, RiskAssessment, RiskPolicyVersion
from sentientalpha.database.session import serialize_writer
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.risk.contracts import EvaluationRequest, Policy
from sentientalpha.risk.governance import evaluate

DEPENDENCIES = ("numpy", "scipy", "pandas", "SQLAlchemy", "pydantic", "exchange-calendars")


def compact(result: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(result)
    for name in ["proposed", "approved"]:
        if value.get(name):
            for key in ["covariance", "correlation", "raw_correlation", "estimation"]:
                value[name].get("volatility", {}).pop(key, None)
            if "volatility" in value[name]:
                value[name]["volatility"]["matrix_reference"] = "current.volatility"
    if value.get("approved") == value.get("proposed"):
        value["approved"] = {"same_as": "proposed"}
    return value


def policy(session: Session, definition: Policy) -> RiskPolicyVersion:
    payload = definition.model_dump(mode="json")
    key = digest(payload)
    existing = session.scalar(
        select(RiskPolicyVersion).where(
            RiskPolicyVersion.policy_id == definition.id,
            RiskPolicyVersion.version == definition.version,
        )
    )
    if existing:
        if existing.key != key or digest(existing.definition) != key:
            raise OptimizationError(
                "Immutable risk policy version differs", "policy_version_conflict", 409
            )
        return existing
    saved = RiskPolicyVersion(
        key=key,
        policy_id=definition.id,
        version=definition.version,
        effective_at=definition.effective_at,
        definition=payload,
    )
    session.add(saved)
    session.flush()
    return saved


def write(
    session: Session,
    result: dict[str, Any],
    definition: Policy,
    inputs: dict[str, Any],
    phase: str,
    request_key: str | None = None,
    committee_id: str | None = None,
    backtest_id: str | None = None,
    sequence: int | None = None,
) -> RiskAssessment:
    row = policy(session, definition)
    payload = compact(result)
    id = result["decision_id"]
    existing = session.get(RiskAssessment, id)
    if existing:
        if digest(existing.payload) != digest(payload):
            raise OptimizationError("Risk decision identity conflict", "risk_conflict", 409)
        return existing
    saved = RiskAssessment(
        id=id,
        request_key=request_key,
        policy_key=row.key,
        portfolio_id=result["portfolio_id"],
        at=datetime.fromisoformat(result["at"]),
        status=result["status"],
        phase=phase,
        committee_id=committee_id,
        backtest_id=backtest_id,
        sequence=sequence,
        manifest={
            "build_id": build_id(),
            "version": "9.0.0",
            "input_hash": digest(inputs),
            "result_hash": digest(payload),
            "dependencies": {n: version(n) for n in DEPENDENCIES},
            "policy_hash": row.key,
        },
        inputs=inputs,
        payload=payload,
    )
    session.add(saved)
    session.flush()
    alerts = {v["metric"]: v for v in result.get("alerts", result["violations"])}
    for metric, value in alerts.items():
        session.add(
            RiskAlert(id=digest([id, metric]), assessment_id=id, metric=metric, payload=value)
        )
    return saved


def execute(sessions: sessionmaker[Session], request: EvaluationRequest) -> RiskAssessment:
    request = EvaluationRequest.model_validate(request.model_dump())
    frozen = request.model_dump(mode="json")
    if len(json.dumps(frozen)) > 64 * 1024 * 1024:
        raise OptimizationError("Risk input exceeds 64 MiB")
    with sessions() as session:
        serialize_writer(session, "risk:" + request.policy.id + ":" + request.policy.version)
        existing = session.scalar(
            select(RiskAssessment).where(RiskAssessment.request_key == request.idempotency_key)
        )
        if existing:
            if existing.manifest["input_hash"] != digest(frozen):
                raise OptimizationError("Risk request key differs", "idempotency_conflict", 409)
            return existing
        result = evaluate(request)
        saved = write(
            session, result, request.policy, frozen, "standalone", request.idempotency_key
        )
        session.commit()
        return saved


def persist_events(
    session: Session, controller: Any, committee_id: str, backtest_id: str | None
) -> list[str]:
    ids = []
    for event in controller.events:
        reference = {k: v for k, v in event.items() if k != "result"}
        reference["source"] = "committee frozen inputs and M4 actual ledger event"
        saved = write(
            session,
            event["result"],
            controller.policy,
            reference,
            event["phase"],
            committee_id=committee_id,
            backtest_id=backtest_id,
            sequence=event["sequence"],
        )
        ids.append(saved.id)
    return ids


def get(session: Session, id: str) -> RiskAssessment:
    saved = session.get(RiskAssessment, id)
    if saved is None:
        raise OptimizationError("Risk assessment not found", "not_found", 404)
    return saved


def replay(session: Session, id: str) -> dict[str, Any]:
    saved = get(session, id)
    m = saved.manifest
    version_row = session.get(RiskPolicyVersion, saved.policy_key)
    if (
        build_id() != m["build_id"]
        or digest(saved.inputs) != m["input_hash"]
        or digest(saved.payload) != m["result_hash"]
        or version_row is None
        or digest(version_row.definition) != m["policy_hash"]
        or any(version(n) != v for n, v in m["dependencies"].items())
    ):
        raise OptimizationError(
            "Risk source/policy/build/result/dependencies differ", "replay_mismatch", 409
        )
    from sentientalpha.committee.storage import equivalent

    if saved.committee_id:
        from sentientalpha.committee.requests import Request
        from sentientalpha.committee.storage import evaluate as committee_evaluate
        from sentientalpha.committee.storage import get as get_committee
        from sentientalpha.committee.storage import restore

        parent = get_committee(session, saved.committee_id)
        if digest(parent.inputs) != parent.manifest["input_hash"]:
            raise OptimizationError("Committee source differs", "replay_mismatch", 409)
        inputs, metadata = restore(session, parent.inputs)
        _, adapter = committee_evaluate(
            Request.model_validate(parent.manifest["configuration"]),
            inputs,
            metadata,
            parent.manifest["execution"],
        )
        event = (
            adapter.risk_control.events[saved.sequence]
            if adapter.risk_control is not None and saved.sequence is not None
            else None
        )
        if event is None:
            raise OptimizationError("Risk event unavailable", "replay_mismatch", 409)
        result = event["result"]
    else:
        result = evaluate(EvaluationRequest.model_validate(saved.inputs))
    return {
        "assessment_id": id,
        "equivalent_risk": equivalent(saved.payload, compact(result)),
        "numeric_tolerance": {"relative": 1e-9, "absolute": 1e-9},
        "scope": "Frozen inputs/policy or original M4 event; no reacquisition",
    }


def verify_events(session: Session, committee_id: str, controller: Any) -> bool:
    from sentientalpha.committee.storage import equivalent

    rows = list(
        session.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.committee_id == committee_id)
            .order_by(RiskAssessment.sequence)
        )
    )
    if len(rows) != len(controller.events):
        return False
    return all(
        digest(row.payload) == row.manifest["result_hash"]
        and equivalent(row.payload, compact(event["result"]))
        for row, event in zip(rows, controller.events, strict=True)
    )

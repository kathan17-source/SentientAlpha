"""Reuse audited M7 M2/M3/M6 adapters, retaining original source clocks and versions."""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.backtesting.evaluation import Split
from sentientalpha.backtesting.storage import digest
from sentientalpha.committee.requests import Request
from sentientalpha.database.ml_models import MLExperiment, MLModel, MLPrediction
from sentientalpha.database.models import Asset
from sentientalpha.database.strategy_models import DiscoveryRun, StrategyCandidate
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.strategies.contracts import Axis, Definition, Space
from sentientalpha.strategies.contracts import Request as DiscoveryRequest
from sentientalpha.strategies.grammar import identity, requirements
from sentientalpha.strategies.inputs import Inputs, load
from sentientalpha.strategies.research import prepare_lock


def load_sources(session: Session, request: Request) -> tuple[Inputs, dict[str, Any]]:
    names = {"return", request.technical_column}
    meta: dict[str, Any] = {"quant": None, "strategy": None}
    if request.sentiment_column:
        names.add(request.sentiment_column)
    if request.model_id:
        model = session.get(MLModel, request.model_id)
        if model is None:
            raise OptimizationError("Model not found", "not_found", 404)
        parent = session.get(MLExperiment, model.experiment_id)
        assert parent is not None
        if digest(parent.result) != parent.manifest.get("result_hash"):
            raise OptimizationError("ML research result integrity mismatch")
        meta["quant"] = {
            "id": model.id,
            "version": model.version,
            "created_at": model.created_at.isoformat(),
            "model": model.payload,
            "predictions": [
                {"id": p.id, "generated_at": p.generated_at.isoformat(), "payload": p.payload}
                for p in session.scalars(
                    select(MLPrediction).where(MLPrediction.model_id == model.id)
                )
            ],
            "research_evidence": "No later holdout metrics enter voting or weights",
            "usefulness": "Unproven; experimental participation has capped influence",
            "feature_set_hash": digest(parent.inputs["metadata"]),
            "outcomes": [
                {k: r[k] for k in ("ticker", "day", "target", "target_available")}
                for r in parent.inputs["rows"]
                if r["target"] is not None
            ],
            "baseline_probability": None,
        }
        if model.payload["target"]["task"] == "direction":
            window = parent.manifest["configuration"]["windows"][model.payload["fold"]]
            train = [
                r["target"]
                for r in parent.inputs["rows"]
                if window["train_start"] <= r["day"] <= window["train_end"]
                and r["target"] is not None
                and r["target_available"] is not None
                and r["target_available"] <= model.payload["training_cutoff"]
            ]
            meta["quant"]["baseline_probability"] = sum(train) / len(train) if train else None
    if request.strategy_id:
        candidate = session.get(StrategyCandidate, request.strategy_id)
        if candidate is None:
            raise OptimizationError("Strategy not found", "not_found", 404)
        run = session.get(DiscoveryRun, candidate.discovery_id)
        assert run is not None
        prepared = run.result.get("prepared", run.result)
        config = DiscoveryRequest.model_validate(run.manifest["configuration"])
        if (
            digest(run.inputs) != run.manifest["input_hash"]
            or digest(prepared) != run.manifest.get("prepared_hash")
            or digest(prepare_lock(config, prepared)) != prepared["selection_hash"]
        ):
            raise OptimizationError("Strategy selection/version integrity mismatch")
        definition = Definition.model_validate(candidate.payload["definition"])
        fold = prepared["folds"][candidate.fold]
        original = next(
            (v for v in fold["candidates"] if v["rule_hash"] == candidate.rule_hash), None
        )
        if original != candidate.payload or identity(definition) != candidate.rule_hash:
            raise OptimizationError("Candidate differs from immutable selected research")
        if config.dataset_id != request.dataset_id or config.tickers != request.tickers:
            raise OptimizationError("Strategy feature/universe mismatch")
        names |= requirements(definition) - {"close"}
        meta["strategy"] = {
            "id": candidate.id,
            "version": candidate.rule_hash,
            "definition": definition.model_dump(mode="json"),
            "payload": candidate.payload,
            "selected": fold["selected"] == candidate.rule_hash,
            "selection_frozen_at": run.manifest["selection_frozen_at"],
            "validation_end": config.windows[candidate.fold].validation_end.isoformat(),
            "selection_hash": prepared["selection_hash"],
            "fitness": config.fitness.model_dump(mode="json"),
            "robustness_scope": "Past validation/fragility only; holdout robustness cannot select",
        }
    # These windows only bound source retrieval. No discovery, fitting or selection is invoked.
    a = request.history_start
    if request.start - a < timedelta(days=6):
        raise OptimizationError(
            "Source retrieval requires at least six calendar days of prior history"
        )
    window = Split(
        train_start=a,
        train_end=a + timedelta(days=1),
        validation_start=a + timedelta(days=2),
        validation_end=request.start - timedelta(days=1),
        test_start=request.start,
        test_end=request.end,
    )
    axes = [Axis(feature=n, operator="gt", thresholds=[0]) for n in sorted(names)]
    cfg = DiscoveryRequest(
        dataset_id=request.dataset_id,
        sentiment_dataset_id=request.sentiment_dataset_id,
        ml_model_ids=[request.model_id] if request.model_id else [],
        ml_horizon=request.horizon,
        tickers=request.tickers,
        source_as_of=request.source_as_of,
        information_policy=request.information_policy,
        sentiment_provenance=request.sentiment_provenance,
        windows=[window],
        space=Space(axes=axes),
        candidates=1,
        idempotency_key="committee-source-only",
    )
    inputs = load(session, cfg)
    meta["source_configuration"] = cfg.model_dump(mode="json")
    meta["feature_version"] = digest(inputs.metadata["datasets"])
    meta["provenance"] = (
        "synthetic_fixture" if inputs.metadata["provider"] == "synthetic" else "genuine"
    )
    meta["risk_assets"] = {
        a.ticker: {"id": a.id, "currency": a.currency}
        for a in session.scalars(select(Asset).where(Asset.ticker.in_(request.tickers)))
    }
    return inputs, meta

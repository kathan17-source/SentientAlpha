"""Audited bounded experiments and safe immutable model/forecast persistence."""

import json
from datetime import datetime
from importlib.metadata import version
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.contracts import Costs, StrategySpec
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.storage import build_id, digest, persist
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.base import new_id, now
from sentientalpha.database.ml_models import MLExperiment, MLModel, MLPrediction
from sentientalpha.ml import VERSION
from sentientalpha.ml.contracts import MLException, PredictRequest, ResearchRequest
from sentientalpha.ml.dataset import Dataset, build, freeze, thaw
from sentientalpha.ml.evaluation import calibrate
from sentientalpha.ml.integration import economic
from sentientalpha.ml.models import infer
from sentientalpha.ml.research import eligible, evaluate, inference_guard, matrix


def dependencies() -> dict[str, str]:
    return {
        n: version(n)
        for n in ("numpy", "scipy", "scikit-learn", "SQLAlchemy", "pydantic", "exchange-calendars")
    }


def get(session: Session, run_id: str) -> MLExperiment:
    item = session.get(MLExperiment, run_id)
    if item is None:
        raise MLException("ML experiment not found", "not_found", 404)
    return item


def run(
    sessions: sessionmaker[Session], request: ResearchRequest, supplied: Dataset | None = None
) -> MLExperiment:
    with sessions() as session:
        ds = supplied if supplied is not None else build(session, request)
    frozen = freeze(ds)
    if len(json.dumps(frozen, allow_nan=False)) > 64 * 1024 * 1024:
        raise MLException("Frozen ML input budget exceeded")
    manifest = {
        "version": VERSION,
        "configuration": request.model_dump(mode="json"),
        "configuration_hash": digest(request.model_dump(mode="json")),
        "input_hash": digest(frozen),
        "dependencies": dependencies(),
        "build_id": build_id(),
        "random_seed": request.seed,
        "dataset_metadata": ds.metadata,
        "created_at": now().isoformat(),
        "prediction_origin": "retrospective_research"
        if request.information_policy == "retrospective"
        else "historical_walk_forward",
    }
    saved = MLExperiment(id=new_id(), status="running", manifest=manifest, inputs=frozen, result={})
    with sessions() as session:
        session.add(saved)
        session.commit()
    try:
        result = evaluate(request, ds)
        if len(json.dumps(result, allow_nan=False)) > 64 * 1024 * 1024:
            raise MLException("Result budget exceeded")
        model_ids = {}
        with sessions() as session:
            for model in result["models"]:
                item = MLModel(
                    id=new_id(),
                    experiment_id=saved.id,
                    version=digest(model),
                    payload=model,
                )
                session.add(item)
                model_ids[model["fold"]] = item.id
            session.flush()
            for p in result["predictions"]:
                session.add(
                    MLPrediction(
                        model_id=model_ids[p["fold"]],
                        ticker=p["ticker"],
                        decision_at=datetime.fromisoformat(p["decision_at"]),
                        payload=p,
                    )
                )
            session.commit()
        manifest.update(result_hash=digest(result), model_ids=model_ids, ledger_links=[])
        with sessions() as session:
            record = get(session, saved.id)
            record.status, record.manifest, record.result = result["status"], manifest, result
            session.commit()
            session.expunge(record)
        return record
    except Exception as exc:
        with sessions() as session:
            record = get(session, saved.id)
            record.status = "failed"
            record.result = {
                "error_code": exc.code if isinstance(exc, MLException) else "training_failed"
            }
            session.commit()
        if isinstance(exc, MLException):
            raise
        raise MLException("ML experiment failed; audit retained", "training_failed", 500) from exc


def replay(session: Session, run_id: str) -> dict[str, Any]:
    saved = get(session, run_id)
    m = saved.manifest
    if (
        saved.status in {"running", "failed"}
        or m["build_id"] != build_id()
        or m["dependencies"] != dependencies()
        or digest(saved.inputs) != m["input_hash"]
        or digest(m["configuration"]) != m["configuration_hash"]
        or digest(saved.result) != m["result_hash"]
    ):
        raise MLException(
            "ML build, configuration, inputs, results or dependencies differ",
            "replay_mismatch",
            409,
        )
    result = evaluate(ResearchRequest.model_validate(m["configuration"]), thaw(saved.inputs))
    equivalent = digest(result) == m["result_hash"]
    artifacts_ok = True
    if m.get("ledger_links"):
        experiments = economic(
            ResearchRequest.model_validate(m["configuration"]),
            thaw(saved.inputs),
            result["predictions"],
        )
        lookup = {e["fold"]: e for e in experiments if "net" in e}
        for link in m["ledger_links"]:
            current = (
                lookup[link["fold"]][link["kind"]]
                if link["kind"] in {"net", "gross"}
                else lookup[link["fold"]]["benchmarks"][link["kind"]]
            )
            for kind in ("orders", "fills", "equity", "actions"):
                stored = list(
                    session.scalars(
                        select(BacktestArtifact)
                        .where(BacktestArtifact.run_id == link["id"], BacktestArtifact.kind == kind)
                        .order_by(BacktestArtifact.sequence)
                    )
                )
                artifacts_ok &= digest([a.payload for a in stored]) == digest(current[kind])
    return {"equivalent_numerical_results": equivalent, "equivalent_ledger_artifacts": artifacts_ok}


def predict(session: Session, request: PredictRequest) -> list[dict[str, Any]]:
    model = session.get(MLModel, request.model_id)
    if model is None:
        raise MLException("Model not found", "not_found", 404)
    saved = get(session, model.experiment_id)
    cfg = ResearchRequest.model_validate(saved.manifest["configuration"])
    ds = thaw(saved.inputs)
    inference_guard(model.payload, request.decision_at, list(ds.columns))
    if (
        digest(saved.inputs) != saved.manifest["input_hash"]
        or model.version != digest(model.payload)
        or model.payload not in saved.result["models"]
        or saved.manifest["dependencies"] != dependencies()
        or saved.manifest["build_id"] != build_id()
    ):
        raise MLException(
            "Model snapshot, version, build or dependency mismatch", "artifact_mismatch", 409
        )
    # Frozen snapshots only; no arbitrary vectors, downloads or silent latest-row reuse.
    rows = eligible(
        [r for r in ds.rows if r.ticker in request.tickers and r.decision == request.decision_at],
        cfg,
    )
    output = []
    if rows:
        raw = infer(model.payload["artifact"], matrix(rows), list(ds.columns))
        values = (
            calibrate(model.payload["calibration"], raw) if cfg.target.task == "direction" else raw
        )
        for r, value in zip(rows, values, strict=True):
            existing = session.scalar(
                select(MLPrediction).where(
                    MLPrediction.model_id == model.id,
                    MLPrediction.ticker == r.ticker,
                    MLPrediction.decision_at == r.decision,
                )
            )
            if existing:
                output.append({"id": existing.id, **existing.payload})
                continue
            p = {
                "ticker": r.ticker,
                "asset_id": r.asset_id,
                "day": str(r.day),
                "decision_at": r.decision.isoformat(),
                "earliest_execution_at": r.execution.isoformat(),
                "model_hash": model.version,
                "training_cutoff": model.payload["training_cutoff"],
                "prediction_type": cfg.target.task,
                "value": float(value),
                "horizon": cfg.target.horizon,
                "target_convention": cfg.target.convention,
                "origin": "retrospective_research",
                "inference_status": "completed",
                "evaluation_eligible": False,
            }
            record = MLPrediction(
                id=new_id(), model_id=model.id, ticker=r.ticker, decision_at=r.decision, payload=p
            )
            session.add(record)
            output.append({"id": record.id, **p})
        session.commit()
    return output


def backtest(sessions: sessionmaker[Session], run_id: str) -> dict[str, Any]:
    with sessions() as session:
        saved = get(session, run_id)
        cfg = ResearchRequest.model_validate(saved.manifest["configuration"])
        ds, predictions = thaw(saved.inputs), saved.result["predictions"]
        if saved.manifest.get("ledger_links"):
            return {"ledger_links": saved.manifest["ledger_links"]}
    outputs = economic(cfg, ds, predictions)
    links = []
    for item in outputs:
        if "net" not in item:
            continue
        for kind, sim in [
            ("net", item["net"]),
            ("gross", item["gross"]),
            *item["benchmarks"].items(),
        ]:
            bcfg = BacktestRequest.model_validate(item["request"])
            if kind == "gross":
                bcfg = bcfg.model_copy(
                    update={"costs": Costs.model_validate({"fixed": 0, "slippage_bps": 0})}
                )
            elif kind in {"buy_hold", "equal_weight"}:
                bcfg = bcfg.model_copy(
                    update={
                        "strategy": StrategySpec.model_validate(
                            {"name": kind, "rebalance": "once" if kind == "buy_hold" else "monthly"}
                        )
                    }
                )
            child = persist(
                sessions,
                bcfg,
                item["snapshot"],
                sim,
                {
                    "external_target_strategy": "ml_forecast",
                    "ml_experiment_id": run_id,
                    "kind": kind,
                },
            )
            links.append(
                {
                    "fold": item["fold"],
                    "kind": kind,
                    "id": child.id,
                    "metrics": {
                        k: v
                        for k, v in child.metrics.items()
                        if k not in {"daily_returns", "monthly_returns", "rolling", "drawdown"}
                    },
                }
            )
    with sessions() as session:
        record = get(session, run_id)
        record.manifest = {**record.manifest, "ledger_links": links}
        session.commit()
    return {"ledger_links": links}

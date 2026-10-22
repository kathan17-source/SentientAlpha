"""Executed financial ML demonstration: copied retained data, never invented market history."""

import argparse
import json
import os
import resource
import shutil
from datetime import date
from pathlib import Path
from time import perf_counter

import numpy as np
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.database.base import now
from sentientalpha.database.ml_models import MLModel
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.ml.contracts import Candidate, ResearchRequest, Target, Window
from sentientalpha.ml.dataset import build
from sentientalpha.ml.integration import forecast_estimates
from sentientalpha.ml.models import infer
from sentientalpha.ml.research import matrix, partition
from sentientalpha.ml.storage import backtest, replay, run
from sentientalpha.optimization.contracts import Constraints, Objective
from sentientalpha.optimization.estimation import Estimates
from sentientalpha.optimization.solver import solve
from sqlalchemy import event, select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--assets", type=int, choices=[1, 5, 20, 50], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        raise ValueError("Refusing to replace an existing database")
    shutil.copyfile(args.source, args.database)
    url = f"sqlite:///{args.database.resolve()}"
    os.environ["DATABASE_URL"] = url
    root = Path(__file__).resolve().parents[1]
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    command.check(Config(str(root / "alembic.ini")))
    engine = make_engine(url)
    sessions = session_factory(engine)
    real = args.assets == 1
    tickers = ["IBM"] if real else [f"OPT{i:02d}" for i in range(args.assets)]
    provider = "alphavantage" if real else "synthetic"
    start, end = (
        (date(2026, 5, 21), date(2026, 10, 13)) if real else (date(2022, 1, 3), date(2024, 12, 31))
    )
    clock = perf_counter()
    features = [FeatureSpec(name="return"), FeatureSpec(name="sma", parameters={"window": 5})]
    if not real:
        features.append(FeatureSpec(name="realized_volatility", parameters={"window": 20}))
    dataset = generate(
        sessions,
        GenerationRequest(
            tickers=tickers, provider=provider, start=start, end=end, features=features
        ),
    ).dataset
    feature_seconds = perf_counter() - clock
    if real:
        days = sessions_in_range("XNYS", start, end)
        windows = [
            Window(
                train_start=days[0],
                train_end=days[44],
                validation_start=days[45],
                validation_end=days[59],
                calibration_start=days[60],
                calibration_end=days[74],
                test_start=days[75],
                test_end=days[98],
            )
        ]
    else:
        windows = [
            Window(
                train_start=start,
                train_end=date(2022, 12, 30),
                validation_start=date(2023, 1, 2),
                validation_end=date(2023, 3, 31),
                calibration_start=date(2023, 4, 3),
                calibration_end=date(2023, 6, 30),
                test_start=date(2023, 7, 3),
                test_end=date(2023, 12, 29),
            ),
            Window(
                train_start=start,
                train_end=date(2023, 6, 30),
                validation_start=date(2023, 7, 3),
                validation_end=date(2023, 9, 29),
                calibration_start=date(2023, 10, 2),
                calibration_end=date(2023, 12, 29),
                test_start=date(2024, 1, 2),
                test_end=date(2024, 6, 28),
            ),
        ]
    cfg = ResearchRequest(
        dataset_id=dataset.id,
        tickers=tickers,
        columns=dataset.columns,
        source_as_of=now(),
        information_policy="retrospective" if real else "research_replay",
        windows=windows,
        training_mode="expanding",
        minimum_train=20 if real else 60,
        minimum_evaluation=5 if real else 20,
        seconds=300,
    )
    clock = perf_counter()
    with sessions() as session:
        inputs = build(session, cfg)
    build_seconds = perf_counter() - clock
    results, times, model_sizes = {}, {}, {}
    persistence = []

    def before_commit(session):
        session.info["ml_commit_started"] = perf_counter()

    def after_commit(session):
        if "ml_commit_started" in session.info:
            persistence.append(perf_counter() - session.info.pop("ml_commit_started"))

    event.listen(sessions, "before_commit", before_commit)
    event.listen(sessions, "after_commit", after_commit)
    for family in ("prevalence", "logistic", "forest_classifier", "boost_classifier"):
        candidates = [
            Candidate.model_validate({"model": family, "strength": s, "depth": d, "trees": 20})
            for s, d in ([(1, 3)] if family == "prevalence" else [(0.1, 2), (1, 3)])
        ]
        request = cfg.model_copy(update={"candidates": candidates})
        clock = perf_counter()
        saved = run(sessions, request, inputs)
        times[family] = perf_counter() - clock
        with sessions() as session:
            reproduced = replay(session, saved.id)
        economic = backtest(sessions, saved.id)
        with sessions() as session:
            assert replay(session, saved.id) == {
                "equivalent_numerical_results": True,
                "equivalent_ledger_artifacts": True,
            }
        results[family] = {
            "id": saved.id,
            "status": saved.status,
            "folds": saved.result["folds"],
            "ledger_links": economic["ledger_links"],
            "replay": reproduced,
        }
        model_sizes[family] = [len(json.dumps(m)) for m in saved.result["models"]]
    # Expected-return handoff: independently fitted Ridge, no conversion from probability.
    returns = cfg.model_copy(
        update={
            "target": Target(task="return"),
            "calibration": "none",
            "candidates": [Candidate(model="ridge", strength=1)],
        }
    )
    with sessions() as session:
        return_inputs = build(session, returns)
    return_run = run(sessions, returns, return_inputs)
    first = return_run.result["predictions"][: args.assets]
    handoff = {"status": "insufficient_data"}
    if len(first) == args.assets:
        at = __import__("datetime").datetime.fromisoformat(first[0]["decision_at"])
        # Historical covariance from the exact training feature return column.
        parts, _ = partition(return_inputs, returns, windows[0])
        grouped = {}
        j = returns.columns.index("return")
        for r in parts["train"]:
            grouped.setdefault(r.day, {})[r.ticker] = r.values[j]
        x = np.array(
            [[v[t] for t in tickers] for _, v in sorted(grouped.items()) if len(v) == args.assets]
        )
        covariance = np.atleast_2d(np.cov(x, rowvar=False, ddof=1)) * 252
        base = Estimates(
            tuple(tickers),
            np.zeros(args.assets),
            covariance,
            {"source": "permitted training-only raw daily returns"},
        )
        estimates = forecast_estimates(base, first, at, 1)
        allocation = solve(estimates, Constraints(), Objective(method="mean_variance"), {})
        handoff = {
            "status": allocation["status"],
            "estimator": estimates.metadata,
            "allocation": allocation,
        }
    with sessions() as session:
        assert replay(session, return_run.id)["equivalent_numerical_results"]
        model = session.scalar(select(MLModel).where(MLModel.experiment_id == return_run.id))
        te = partition(return_inputs, returns, windows[0])[0]["test"][:100]
        clock = perf_counter()
        infer(model.payload["artifact"], matrix(te), returns.columns)
        inference_seconds = perf_counter() - clock
    smoke = {}
    with TestClient(create_app(Settings(database_url=url))) as client:
        for route in (
            "/ready",
            "/api/ml/models",
            "/api/ml/predictions/" + tickers[0],
            f"/api/ml/experiments/{return_run.id}/metrics",
            f"/api/ml/experiments/{return_run.id}/feature-importance",
        ):
            response = client.get(route)
            smoke[route] = response.status_code
            assert response.status_code == 200
        (root / "docs/openapi.json").write_text(
            json.dumps(client.get("/openapi.json").json(), indent=2) + "\n"
        )
    report = {
        "provenance": (
            "GENUINE retained IBM raw history; retrospective acquisition, "
            "no historical online availability"
        )
        if real
        else "SYNTHETIC seeded market prices; no real-market evidence",
        "assets": args.assets,
        "source": str(args.source),
        "feature_seconds": feature_seconds,
        "dataset_build_seconds": build_seconds,
        "training_selection_walk_seconds": times,
        "model_json_bytes": model_sizes,
        "inference_rows": len(te),
        "inference_seconds": inference_seconds,
        "persistence_flush_commit_seconds": sum(persistence),
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2,
        "results": results,
        "return_experiment": {"id": return_run.id, "folds": return_run.result["folds"]},
        "optimizer_handoff": handoff,
        "http_smoke": smoke,
        "sentiment_alpha": "UNVERIFIED",
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"results", "return_experiment", "optimizer_handoff"}
            },
            indent=2,
        )
    )
    engine.dispose()


if __name__ == "__main__":
    main()

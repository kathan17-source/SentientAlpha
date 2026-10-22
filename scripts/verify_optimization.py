"""Reproducible SYNTHETIC portfolio research benchmark; requires an empty database."""

import argparse
import json
import os
import platform
import resource
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.base import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.optimization.contracts import (
    Constraints,
    Estimator,
    FrontierRequest,
    Objective,
    OptimizationRequest,
    ResearchRequest,
    WalkResearch,
    default_methods,
)
from sentientalpha.optimization.estimation import estimate
from sentientalpha.optimization.inputs import load_inputs
from sentientalpha.optimization.solver import solve
from sentientalpha.optimization.storage import replay, run
from sentientalpha.services.ingestion import ingest
from sqlalchemy import event, inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=int, choices=[5, 20, 50], required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{args.database.resolve()}"
    engine = make_engine(url)
    if inspect(engine).get_table_names():
        raise ValueError("Refuses to replace an existing database")
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    sessions = session_factory(engine)
    tickers = [f"OPT{i:02d}" for i in range(args.assets)]
    first, last = date(2022, 1, 3), date(2024, 12, 31)
    started = perf_counter()
    for ticker in tickers:
        ingest(sessions, SyntheticProvider(51), ticker, first, last)
    seed_seconds = perf_counter() - started
    started = perf_counter()
    ds = generate(
        sessions,
        GenerationRequest(
            tickers=tickers,
            provider="synthetic",
            start=first,
            end=last,
            features=[FeatureSpec(name="return")],
        ),
    ).dataset
    feature_seconds = perf_counter() - started
    config = OptimizationRequest(
        price_dataset_id=ds.id,
        tickers=tickers,
        history_start=first,
        estimation_end=date(2023, 12, 29),
        decision_at=datetime(2023, 12, 30, tzinfo=UTC),
        source_as_of=now(),
        information_policy="research_replay",
        estimator=Estimator(lookback=126, minimum_observations=60),
        constraints=Constraints(concentration=0.25),
        objective=Objective(method="mean_variance", seconds=30),
    )
    started = perf_counter()
    with sessions() as session:
        inputs = load_inputs(session, config)
    source_load_seconds = perf_counter() - started
    started = perf_counter()
    e = estimate(
        inputs.panel,
        config.decision_at,
        config.history_start,
        config.estimation_end,
        config.estimator,
    )
    estimation_seconds = perf_counter() - started
    flush_times = []

    def begin_flush(session, context, instances):
        session.info["benchmark_flush"] = perf_counter()

    def after_commit(session):
        if "benchmark_flush" in session.info:
            flush_times.append(perf_counter() - session.info.pop("benchmark_flush"))

    event.listen(sessions.class_, "before_flush", begin_flush)
    event.listen(sessions.class_, "after_commit", after_commit)
    objective_results = []
    for method in default_methods():
        objective = config.objective.model_copy(update={"method": method})
        started = perf_counter()
        result = solve(e, config.constraints, objective, {})
        solve_seconds = perf_counter() - started
        phase = len(flush_times)
        started = perf_counter()
        saved = run(sessions, config.model_copy(update={"objective": objective}))
        end_to_end = perf_counter() - started
        with sessions() as session:
            reproduced = replay(session, saved.id)
            assert reproduced["equivalent_numerical_results"]
        objective_results.append(
            {
                "method": method,
                "status": result["status"],
                "solve_seconds": solve_seconds,
                "static_end_to_end_seconds": end_to_end,
                "persistence_flush_commit_seconds": sum(flush_times[phase:]),
                "run_id": saved.id,
                "risk": {
                    k: v for k, v in result.get("risk", {}).items() if k != "correlation_matrix"
                },
                "iterations": [
                    a["iterations"] for a in result.get("diagnostics", {}).get("attempts", [])
                ],
                "equivalent_replay": True,
            }
        )
    phase = len(flush_times)
    started = perf_counter()
    f = run(sessions, FrontierRequest(optimization=config, risk_aversions=[0.5, 1, 2, 5, 10, 25]))
    frontier_seconds = perf_counter() - started
    frontier_statuses = [p["status"] for p in f.result["points"]]
    b = BacktestRequest(
        tickers=tickers,
        provider="synthetic",
        start=date(2024, 1, 2),
        end=last,
        source_as_of=config.source_as_of,
        information_policy="research_replay",
        seconds=300,
    )
    research = ResearchRequest(optimization=config, backtest=b)
    phase = len(flush_times)
    started = perf_counter()
    compared = run(sessions, research)
    comparison_seconds = perf_counter() - started
    comparison_persistence = sum(flush_times[phase:])
    comparison_summary = [
        {
            "method": m["method"],
            "status": m["status"],
            "fills": m["fills"],
            "rebalance_decisions": len(m["decisions"]),
            "decision_status_counts": {
                s: m["decision_statuses"].count(s) for s in sorted(set(m["decision_statuses"]))
            },
            "metrics": {
                k: v
                for k, v in m["metrics"].items()
                if k not in {"daily_returns", "monthly_returns", "drawdown", "rolling"}
            },
            "mean_realized_concentration_hhi_including_cash": m[
                "mean_realized_concentration_hhi_including_cash"
            ],
        }
        for m in compared.result["methods"]
    ]
    with sessions() as session:
        reproduced = replay(session, compared.id)
        assert (
            reproduced["equivalent_numerical_results"]
            and reproduced["equivalent_execution_artifacts"]
        )
    wr = WalkResearch(
        research=research,
        train_sessions=126,
        validation_sessions=21,
        test_sessions=42,
        step_sessions=42,
        maximum_folds=4,
    )
    phase = len(flush_times)
    started = perf_counter()
    wf = run(sessions, wr)
    walk_seconds = perf_counter() - started
    walk_persistence = sum(flush_times[phase:])
    with sessions() as session:
        r = replay(session, wf.id)
        assert r["equivalent_numerical_results"] and r["equivalent_execution_artifacts"]
    api = []
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/ready").status_code == 200
        for endpoint in ("", "/weights", "/risk", "/explanation", "/result", "/training-lineage"):
            started = perf_counter()
            response = client.get(
                f"/api/portfolio/optimization/{objective_results[0]['run_id']}{endpoint}"
            )
            elapsed = perf_counter() - started
            assert response.status_code == 200, response.text
            api.append(
                {
                    "endpoint": endpoint or "manifest",
                    "status": response.status_code,
                    "seconds": elapsed,
                    "bytes": len(response.content),
                }
            )
    report = {
        "status": "VERIFIED_SYNTHETIC_SOFTWARE_RESEARCH",
        "assets": args.assets,
        "provenance": (
            "Synthetic raw prices and modeled weekdays; not genuine investment performance"
        ),
        "source_start": str(first),
        "source_end": str(last),
        "evaluation_start": str(b.start),
        "evaluation_end": str(b.end),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "seed_seconds": seed_seconds,
        "M2_return_generation_seconds": feature_seconds,
        "source_load_seconds": source_load_seconds,
        "estimation_seconds": estimation_seconds,
        "estimation_observations": e.metadata["observations"],
        "objectives": objective_results,
        "frontier_seconds": frontier_seconds,
        "frontier_statuses": frontier_statuses,
        "comparison_seconds": comparison_seconds,
        "comparison_persistence_flush_commit_seconds": comparison_persistence,
        "comparison": comparison_summary,
        "comparison_run_id": compared.id,
        "frontier_run_id": f.id,
        "walk_forward_seconds": walk_seconds,
        "walk_forward_persistence_flush_commit_seconds": walk_persistence,
        "walk_forward_folds": len(wf.result["folds"]),
        "walk_forward_run_id": wf.id,
        "walk_forward": {
            k: {
                "status": v.get("status"),
                "metrics": {
                    n: x
                    for n, x in v["metrics"].items()
                    if n not in {"daily_returns", "monthly_returns", "drawdown", "rolling"}
                },
            }
            for k, v in wf.result["aggregate"].items()
        },
        "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (2**20 if platform.system() == "Darwin" else 1024),
        "memory_scope": (
            "Whole separate process: ingestion, one M2 return output, "
            "estimation, five objectives, frontier, M4 comparative ledgers, "
            "walk-forward, persistence, replay and TestClient. Not comparable "
            "to M2's 44-output workload."
        ),
        "persistence_scope": (
            "Measured Session before_flush through after_commit, including SQL"
            " JSON encoding and commit; excludes frozen input "
            "construction/hash and source loading"
        ),
        "api": api,
        "database_bytes": args.database.stat().st_size,
        "sentiment_status": (
            "Genuine complete historical sentiment unavailable; no forced investment comparison"
        ),
        "spy_status": compared.result["spy"],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()

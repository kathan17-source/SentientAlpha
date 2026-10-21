"""Reproducible bounded discovery using copied retained observations, never invented real data."""

import argparse
import json
import os
import resource
import shutil
from datetime import date
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.evaluation import Split, WalkRequest
from sentientalpha.config import Settings
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.database.base import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.strategies.contracts import Axis, Fitness, Request, Space
from sentientalpha.strategies.inputs import load
from sentientalpha.strategies.search import generate as candidates
from sentientalpha.strategies.storage import discover, evaluate_locked, replay
from sqlalchemy import event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--assets", type=int, choices=[1, 5, 20, 50], required=True)
    parser.add_argument("--candidates", type=int, choices=[20, 100, 500, 1000], default=100)
    parser.add_argument("--folds", type=int, choices=[1, 2], default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        raise ValueError("Refusing an existing database")
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
    first, last = (
        (date(2026, 5, 21), date(2026, 10, 13)) if real else (date(2022, 1, 3), date(2024, 12, 31))
    )
    clock = perf_counter()
    ds = generate(
        sessions,
        GenerationRequest(
            tickers=tickers,
            provider=provider,
            start=first,
            end=last,
            features=[
                FeatureSpec(name="return"),
                FeatureSpec(name="sma", parameters={"window": 5}),
                FeatureSpec(name="price_to_sma", parameters={"window": 5}),
                FeatureSpec(name="rsi", parameters={"window": 14}),
                FeatureSpec(name="realized_volatility", parameters={"window": 20}),
            ],
        ),
    ).dataset
    feature_seconds = perf_counter() - clock
    days = sessions_in_range("XNYS" if real else "weekday", first, last)
    if real:
        windows = [
            Split(
                train_start=days[0],
                train_end=days[39],
                validation_start=days[40],
                validation_end=days[69],
                test_start=days[70],
                test_end=days[98],
            )
        ]
    else:
        b = BacktestRequest(
            tickers=tickers,
            start=days[0],
            end=days[377],
            source_as_of=now(),
            information_policy="research_replay",
        )
        windows = WalkRequest(
            backtest=b,
            mode="expanding",
            train_sessions=126,
            validation_sessions=63,
            test_sessions=63,
            step_sessions=126,
            maximum_folds=2,
        ).folds(days[: 252 + (args.folds - 1) * 126])
    axes = [
        Axis(feature="return", thresholds=[-0.01, -0.003, 0, 0.003, 0.01]),
        Axis(feature="price_to_sma__window_5", thresholds=[-0.02, -0.005, 0, 0.005, 0.02]),
        Axis(feature="rsi__window_14", operator="lt", thresholds=[20, 30, 40, 50, 60, 70]),
        Axis(
            feature="realized_volatility__annualization_252__window_20",
            operator="lt",
            thresholds=[0.05, 0.1, 0.2, 0.3, 0.5],
        ),
        Axis(feature="close", other_features=["sma__window_5"]),
    ]
    # Use actual canonical output key, not an assumed indicator alias.
    axes = [
        a.model_copy(
            update={"feature": next(c for c in ds.columns if c.startswith("realized_volatility__"))}
        )
        if a.feature.startswith("realized_volatility")
        else a
        for a in axes
    ]
    cfg = Request(
        dataset_id=ds.id,
        tickers=tickers,
        source_as_of=now(),
        information_policy="retrospective" if real else "research_replay",
        windows=windows,
        training_mode="expanding",
        space=Space(
            axes=axes, holdings=[1, 3, 5, 10], schedules=["daily", "weekly"], maximum_conditions=3
        ),
        candidates=args.candidates,
        maximum_simulations=5000,
        seconds=600,
        fitness=Fitness(minimum_sessions=20 if real else 40, minimum_closed_lots=2 if real else 5),
        holdout_history="previously_inspected" if real else "new_reservation",
        idempotency_key=f"demo_{args.assets}_{args.candidates}_{args.folds}",
    )
    clock = perf_counter()
    generated, history = candidates(cfg)
    generation_seconds = perf_counter() - clock
    clock = perf_counter()
    with sessions() as session:
        inputs = load(session, cfg)
    source_seconds = perf_counter() - clock
    commits = []

    def before(s):
        s.info["discovery_commit"] = perf_counter()

    def after(s):
        if "discovery_commit" in s.info:
            commits.append(perf_counter() - s.info.pop("discovery_commit"))

    event.listen(sessions, "before_commit", before)
    event.listen(sessions, "after_commit", after)
    clock = perf_counter()
    saved = discover(sessions, cfg, inputs)
    search_seconds = perf_counter() - clock
    prepared = saved.result
    clock = perf_counter()
    evaluated = evaluate_locked(sessions, saved.id) if saved.status == "ready_for_test" else saved
    final_seconds = perf_counter() - clock
    clock = perf_counter()
    with sessions() as session:
        reproduced = replay(session, saved.id)
        assert all(reproduced.values())
    replay_seconds = perf_counter() - clock
    with TestClient(create_app(Settings(database_url=url))) as client:
        smoke = {}
        for path in [
            "/ready",
            "/api/strategies",
            f"/api/strategies/discovery/{saved.id}",
            f"/api/strategies/leaderboard?run_id={saved.id}",
        ]:
            r = client.get(path)
            smoke[path] = r.status_code
            assert r.status_code == 200, r.text
        (root / "docs/openapi.json").write_text(
            json.dumps(client.get("/openapi.json").json(), indent=2) + "\n"
        )
    # A predeclared impossible trade-count requirement demonstrates a legitimate negative search.
    negative_cfg = cfg.model_copy(
        update={
            "candidates": min(20, args.candidates),
            "fitness": cfg.fitness.model_copy(update={"minimum_closed_lots": 1000}),
            "holdout_history": "previously_inspected",
            "idempotency_key": cfg.idempotency_key + "_negative",
        }
    )
    negative = discover(sessions, negative_cfg, inputs)
    assert negative.status == "no_eligible_strategy"
    report = {
        "provenance": (
            "GENUINE retained IBM; retrospective already-inspected sample, no new untouched holdout"
        )
        if real
        else "SYNTHETIC seeded market prices; no real-market alpha evidence",
        "assets": args.assets,
        "requested_candidates_per_fold": args.candidates,
        "folds": len(windows),
        "discovery_id": saved.id,
        "status": evaluated.status,
        "configuration": cfg.model_dump(mode="json"),
        "feature_seconds": feature_seconds,
        "source_seconds": source_seconds,
        "generation_seconds": generation_seconds,
        "generation": history,
        "search_seconds": search_seconds,
        "evaluation_stress_persistence_seconds": final_seconds,
        "replay_seconds": replay_seconds,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2,
        "persistence_flush_commit_seconds": sum(commits),
        "database_bytes": args.database.stat().st_size,
        "search_events_per_second": prepared["events_processed"] / search_seconds
        if search_seconds
        else None,
        "prepared": prepared,
        "evaluation": evaluated.result.get("evaluation"),
        "replay": reproduced,
        "negative_run": {"id": negative.id, "status": negative.status},
        "http_smoke": smoke,
        "alpha_established": False,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"prepared", "evaluation", "configuration"}
            },
            indent=2,
        )
    )
    engine.dispose()


if __name__ == "__main__":
    main()

"""Executed synthetic end-to-end demo / five-year benchmark. No investment evidence."""

import argparse
import gc
import json
import os
import platform
import resource
from datetime import date
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.contracts import Request, StrategySpec
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.evaluation import WalkRequest
from sentientalpha.backtesting.storage import execute_request, load, persist, replay, walk_forward
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.services.ingestion import ingest
from sqlalchemy import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=int, choices=[1, 20, 50], required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--real-database",
        type=Path,
        help="Read retained genuine IBM observations separately",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{args.database.resolve()}"
    engine = make_engine(url)
    if inspect(engine).get_table_names():
        raise ValueError("Requires empty DB; refuses to erase user data")
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    sessions = session_factory(engine)
    start, end = date(2020, 1, 1), date(2024, 12, 31)
    tickers = [f"SYN{i:02d}" for i in range(args.assets)]
    started = perf_counter()
    for ticker in tickers:
        ingest(sessions, SyntheticProvider(42), ticker, start, end)
    seed_seconds = perf_counter() - started
    started = perf_counter()
    feature = generate(
        sessions,
        GenerationRequest(
            tickers=tickers,
            provider="synthetic",
            start=start,
            end=end,
            features=[FeatureSpec(name="sma", parameters={"window": 20})],
        ),
    ).dataset
    feature_seconds = perf_counter() - started
    config = Request(
        tickers=tickers,
        start=start,
        end=end,
        source_as_of=now(),
        information_policy="research_replay",
        strategy=StrategySpec(
            name="moving_average",
            rebalance="signal",
            feature_dataset_id=feature.id,
            feature_column=feature.columns[0],
        ),
        benchmarks=["buy_hold", "equal_weight", "moving_average", "SPY"],
        seconds=300,
    )
    started = perf_counter()
    with sessions() as session:
        snapshot = load(session, config)
    load_seconds = perf_counter() - started
    started = perf_counter()
    pure = simulate(config, snapshot)
    simulation_seconds = perf_counter() - started
    started = perf_counter()
    result = execute_request(config, snapshot)
    comparisons_seconds = perf_counter() - started
    assert pure["orders"] == result["orders"] and pure["fills"] == result["fills"]
    started = perf_counter()
    run = persist(sessions, config, snapshot, result)
    persistence_seconds = perf_counter() - started
    started = perf_counter()
    with sessions() as session:
        reproduced = replay(session, run.id)
        assert reproduced["equivalent_metrics"] and reproduced["equivalent_artifacts"]
        assert reproduced["fills"] == result["fills"] and reproduced["equity"] == result["equity"]
    replay_seconds = perf_counter() - started
    gc.collect()
    wf_config = WalkRequest(
        backtest=config.model_copy(update={"benchmarks": []}),
        train_sessions=252,
        validation_sessions=63,
        test_sessions=126,
        step_sessions=126,
        maximum_folds=10,
    )
    started = perf_counter()
    wf = walk_forward(sessions, wf_config)
    walk_seconds = perf_counter() - started
    api = []
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/ready").status_code == 200
        for endpoint in ("", "/metrics", "/equity", "/trades", "/drawdown", "/report"):
            response = client.get(f"/api/backtest/{run.id}{endpoint}")
            assert response.status_code == 200, response.text
            api.append({"endpoint": endpoint or "manifest", "status": response.status_code})
        assert client.post(f"/api/backtest/{run.id}/replay").json()["equivalent_metrics"]
        for name in ("buy_hold", "equal_weight", "moving_average"):
            assert client.get(
                f"/api/backtest/{run.id}/equity", params={"benchmark": name, "limit": 2}
            ).json()["items"]
    real = None
    if args.real_database:
        real_engine = make_engine(f"sqlite:///{args.real_database.resolve()}")
        real_sessions = session_factory(real_engine)
        real_config = Request(
            tickers=["IBM"],
            provider="alphavantage",
            calendar="XNYS",
            start=date(2026, 5, 21),
            end=date(2026, 10, 13),
            source_as_of=now(),
            information_policy="online",
        )
        with real_sessions() as session:
            real_snapshot = load(session, real_config)
        real_result = simulate(real_config, real_snapshot)
        assert not real_result["fills"] and real_result["status"] == "insufficient_data"
        real = {
            "provider": "alphavantage",
            "ticker": "IBM",
            "observations": len(real_snapshot.bars),
            "status": real_result["status"],
            "fills": len(real_result["fills"]),
            "source": "Existing retained genuine public IBM sample, not a new acquisition",
            "reason": (
                "Daily observations acquired after the backtest period; "
                "no verified historical availability/actions"
            ),
            "earliest_acquired_at": min(b.ingested for b in real_snapshot.bars).isoformat(),
        }
        real_engine.dispose()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if platform.system() == "Darwin" else 1024
    )
    report = {
        "status": "VERIFIED_SYNTHETIC_ENGINE_DEMONSTRATION",
        "assets": args.assets,
        "years": 5,
        "start": str(start),
        "end": str(end),
        "provenance": "Deterministic synthetic weekdays, NOT real-market returns",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "seed_seconds": seed_seconds,
        "sma_generation_seconds": feature_seconds,
        "source_load_seconds": load_seconds,
        "simulation_seconds": simulation_seconds,
        "net_gross_and_three_baselines_seconds": comparisons_seconds,
        "persistence_seconds": persistence_seconds,
        "replay_seconds": replay_seconds,
        "walk_forward_including_fold_persistence_seconds": walk_seconds,
        "walk_forward_folds": len(
            wf_config.folds([date.fromisoformat(r["day"]) for r in result["equity"]])
        ),
        "process_peak_rss_mib": rss,
        "memory_scope": (
            "Whole process: ingestion, one M2 SMA output, sources, retained results, "
            "replay, API and walk-forward; not comparable to M2 44-output workload."
        ),
        "input_bars": len(snapshot.bars),
        "feature_rows": len(snapshot.features),
        "orders_processed": len(result["orders"]),
        "fills": len(result["fills"]),
        "events_processed": result["events_processed"],
        "equity_rows": len(result["equity"]),
        "run_id": run.id,
        "walk_forward_run_id": wf.id,
        "total_return": run.metrics["total_return"],
        "equivalent_replay": True,
        "api": api,
        "real_market": real,
        "database_bytes": args.database.stat().st_size,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()

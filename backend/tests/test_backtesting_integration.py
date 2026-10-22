"""Real migrated SQLite, existing M2 snapshots, HTTP and frozen replay."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.contracts import BacktestError, Request, StrategySpec
from sentientalpha.backtesting.evaluation import WalkRequest
from sentientalpha.backtesting.storage import get_run, load, replay, run_backtest, walk_forward
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun
from sentientalpha.database.models import FeatureInput, now
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.services.ingestion import ingest
from sqlalchemy import func, select
from test_integration import database as database

START, END = date(2023, 1, 2), date(2024, 3, 1)


def seed(sessions):
    for ticker in ("AAA", "BBB"):
        ingest(sessions, SyntheticProvider(), ticker, START, END)


def config(**kwargs):
    return Request(
        tickers=["AAA", "BBB"],
        start=START,
        end=END,
        source_as_of=now(),
        information_policy="research_replay",
        **kwargs,
    )


def feature_config(sessions):
    dataset = generate(
        sessions,
        GenerationRequest(
            tickers=["AAA", "BBB"],
            start=START,
            end=END,
            provider="synthetic",
            features=[FeatureSpec(name="sma", parameters={"window": 20})],
        ),
    ).dataset
    return config(
        strategy=StrategySpec(
            name="moving_average",
            rebalance="signal",
            feature_dataset_id=dataset.id,
            feature_column=dataset.columns[0],
        ),
        benchmarks=["buy_hold", "equal_weight", "moving_average", "SPY"],
    )


def test_persistence_features_benchmarks_replay_and_restart(database):
    url, sessions, _ = database
    seed(sessions)
    cfg = feature_config(sessions)
    run = run_backtest(sessions, cfg)
    assert run.status == "completed" and run.metrics["trade_count"] > 0
    assert run.manifest["execution_certified"] is False
    with sessions() as session:
        before = replay(session, run.id)
        assert before["equivalent_metrics"]
        assert session.scalar(select(func.count()).select_from(BacktestRun)) == 1
        assert session.scalar(select(func.count()).select_from(BacktestArtifact)) > 300
    # Subsequent provider revisions cannot mutate the copied original snapshot.
    ingest(sessions, SyntheticProvider(2), "AAA", START, END)
    with sessions() as session:
        assert replay(session, run.id) == before
    with TestClient(create_app(Settings(database_url=url))) as client:
        for endpoint in ("", "/metrics", "/equity", "/trades", "/drawdown", "/report"):
            response = client.get(f"/api/backtest/{run.id}{endpoint}")
            assert response.status_code == 200, response.text
        replayed = client.post(f"/api/backtest/{run.id}/replay").json()
        assert replayed["equivalent_metrics"] and replayed["equivalent_artifacts"]
        page = client.get(f"/api/backtest/{run.id}/equity", params={"limit": 2}).json()
        assert len(page["items"]) == 2 and page["next_offset"] == 2
        spec = client.get("/openapi.json").json()
        assert "WalkRequest" in spec["components"]["schemas"]


def test_api_backtest_validation_limits_and_online_refusal(database):
    url, sessions, _ = database
    seed(sessions)
    body = config().model_dump(mode="json")
    with TestClient(create_app(Settings(database_url=url))) as client:
        successful = client.post("/api/backtest", json=body)
        assert successful.status_code == 201, successful.text
        online = client.post("/api/backtest", json=body | {"information_policy": "online"})
        assert online.status_code == 201 and online.json()["status"] == "insufficient_data"
        for bad in (
            {"tickers": ["AAA"] * 51},
            {"capital": 0},
            {"end": "2040-01-01"},
            {"source_as_of": "2024-01-01"},
            {"price_convention": "adjusted_close"},
            {"strategy": {"name": "eval", "code": "evil"}},
            {"benchmarks": ["SPY"] * 5},
        ):
            assert client.post("/api/backtest", json=body | bad).status_code == 422
        assert client.get("/api/backtest/not-a-uuid").status_code == 422
        assert client.get("/api/backtest/00000000-0000-0000-0000-000000000000").status_code == 404
        rid = successful.json()["id"]
        assert client.get(f"/api/backtest/{rid}/equity?limit=2001").status_code == 422


def test_snapshot_cutoff_and_feature_price_lineage_mismatch(database):
    _, sessions, _ = database
    seed(sessions)
    cfg = feature_config(sessions)
    with sessions() as session:
        with pytest.raises(BacktestError, match="source observations"):
            load(
                session,
                cfg.model_copy(update={"source_as_of": cfg.source_as_of - timedelta(days=1)}),
            )
    # A retained input ID is mandatory for every execution-price revision.
    with sessions.begin() as session:
        item = session.scalar(
            select(FeatureInput).where(FeatureInput.dataset_id == cfg.strategy.feature_dataset_id)
        )
        session.delete(item)
    with sessions() as session, pytest.raises(BacktestError, match="versions differ"):
        load(session, cfg)


def test_walk_forward_api_fold_ledgers_and_aggregation(database):
    url, sessions, _ = database
    seed(sessions)
    cfg = config()
    wr = WalkRequest(
        backtest=cfg,
        train_sessions=100,
        validation_sessions=30,
        test_sessions=30,
        step_sessions=30,
        maximum_folds=10,
    )
    run = walk_forward(sessions, wr)
    with sessions() as session:
        folds = list(
            session.scalars(
                select(BacktestArtifact)
                .where(BacktestArtifact.run_id == run.id, BacktestArtifact.kind == "folds")
                .order_by(BacktestArtifact.sequence)
            )
        )
        values = []
        cumulative = Decimal(1)
        for f in folds:
            child = get_run(session, f.payload["run_id"])
            assert replay(session, child.id)["equivalent_metrics"]
            cumulative *= Decimal(1) + Decimal(str(child.metrics["total_return"]))
            assert child.manifest["selection_policy"] == "frozen_baseline_no_fitting"
            values.append(child.manifest["evaluation_split"])
        assert run.metrics["total_return"] == pytest.approx(float(cumulative - 1))
        assert all(
            a["test_end"] < b["test_start"] for a, b in zip(values, values[1:], strict=False)
        )
        assert run.metrics["turnover"] is None
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.post("/api/backtest/walk-forward", json=wr.model_dump(mode="json"))
        assert response.status_code == 201, response.text
        invalid = wr.model_dump(mode="json") | {"step_sessions": 29}
        assert client.post("/api/backtest/walk-forward", json=invalid).status_code == 422


def test_busy_job_refused_without_parallel_mutations(database):
    url, sessions, _ = database
    seed(sessions)
    entered, release = Event(), Event()

    def paused(sessions, request):
        entered.set()
        assert release.wait(10)
        return run_backtest(sessions, request)

    with (
        TestClient(create_app(Settings(database_url=url))) as client,
        patch("sentientalpha.api.backtesting.run_backtest", side_effect=paused),
        ThreadPoolExecutor(2) as workers,
    ):
        first = workers.submit(client.post, "/api/backtest", json=config().model_dump(mode="json"))
        try:
            assert entered.wait(10)
            response = client.post("/api/backtest", json=config().model_dump(mode="json"))
            assert (
                response.status_code == 429 and response.json()["detail"]["code"] == "backtest_busy"
            )
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 201


def test_atomic_artifact_persistence_failure(database):
    _, sessions, _ = database
    seed(sessions)
    from sentientalpha.backtesting.engine import simulate
    from sentientalpha.backtesting.storage import persist

    cfg = config()
    with sessions() as session:
        snap = load(session, cfg)
    result = simulate(cfg, snap)
    with (
        patch(
            "sentientalpha.backtesting.storage.insert",
            side_effect=RuntimeError("controlled write failure"),
        ),
        pytest.raises(RuntimeError),
    ):
        persist(sessions, cfg, snap, result)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(BacktestRun)) == 0
        assert session.scalar(select(func.count()).select_from(BacktestArtifact)) == 0


def test_snapshot_tampering_detected(database):
    _, sessions, _ = database
    seed(sessions)
    run = run_backtest(sessions, config())
    with sessions.begin() as session:
        saved = get_run(session, run.id)
        saved.snapshot = {**saved.snapshot, "definitions": ["tampered"]}
    with sessions() as session, pytest.raises(BacktestError, match="differs"):
        replay(session, run.id)


def test_validation_test_perturbation_preserves_prior_fold_selection(database):
    _, sessions, _ = database
    seed(sessions)
    cfg = config()
    wr = WalkRequest(
        backtest=cfg,
        train_sessions=100,
        validation_sessions=30,
        test_sessions=30,
        step_sessions=30,
        maximum_folds=10,
    )
    with sessions() as session:
        snap = load(session, cfg)
    splits = wr.folds(
        __import__("sentientalpha.data.calendar", fromlist=["sessions_in_range"]).sessions_in_range(
            cfg.calendar, cfg.start, cfg.end
        )
    )
    from dataclasses import replace

    from sentientalpha.backtesting.contracts import Snapshot
    from sentientalpha.backtesting.engine import simulate

    first = cfg.model_copy(update={"start": splits[0].test_start, "end": splits[0].test_end})
    changed = Snapshot(
        tuple(
            replace(b, close=b.close * 10) if b.day > splits[0].test_end else b for b in snap.bars
        )
    )
    before = simulate(first, snap)
    after = simulate(first, changed)
    assert before["orders"] == after["orders"] and before["fills"] == after["fills"]
    assert before["equity"] == after["equity"]
    assert cfg.strategy == wr.backtest.strategy  # no fitted/selected parameters exist


def test_failed_simulation_persists_sanitized_diagnostic(database):
    _, sessions, _ = database
    seed(sessions)
    with (
        patch(
            "sentientalpha.backtesting.storage.execute_request",
            side_effect=BacktestError("Budget exceeded", "time_budget", 429),
        ),
        pytest.raises(BacktestError),
    ):
        run_backtest(sessions, config())
    with sessions() as session:
        saved = session.scalar(select(BacktestRun))
        assert saved.status == "failed" and saved.metrics["error_code"] == "time_budget"
        assert session.scalar(select(func.count()).select_from(BacktestArtifact)) == 0

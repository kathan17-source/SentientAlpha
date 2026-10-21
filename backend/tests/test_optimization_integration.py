"""Actual SQLite migrations, M2/M3 adapters, solver, M4 ledger and API; no solver mock here."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.contracts import BacktestError
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.storage import replay as replay_ledger
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.base import now
from sentientalpha.database.optimization_models import OptimizationRun
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.optimization.contracts import (
    Constraints,
    Estimator,
    FrontierRequest,
    Objective,
    OptimizationRequest,
    ResearchRequest,
    Sentiment,
    WalkResearch,
)
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.optimization.inputs import freeze, load_inputs, thaw
from sentientalpha.optimization.research import compare, frontier, optimize
from sentientalpha.optimization.storage import get_run, replay, run
from sentientalpha.services.ingestion import ingest
from sqlalchemy import func, select
from test_integration import database as database

START, END = date(2023, 1, 2), date(2024, 6, 28)


def seed(sessions):
    for ticker in ("AAA", "BBB", "CCC"):
        ingest(sessions, SyntheticProvider(), ticker, START, END)
    ds = generate(
        sessions,
        GenerationRequest(
            tickers=["AAA", "BBB", "CCC"],
            provider="synthetic",
            start=START,
            end=END,
            features=[FeatureSpec(name="return")],
        ),
    ).dataset
    return OptimizationRequest(
        price_dataset_id=ds.id,
        tickers=["AAA", "BBB", "CCC"],
        history_start=START,
        estimation_end=date(2023, 12, 29),
        decision_at=datetime(2023, 12, 30, tzinfo=UTC),
        source_as_of=now(),
        information_policy="research_replay",
        estimator=Estimator(lookback=126, minimum_observations=30),
        objective=Objective(method="mean_variance", seconds=30),
    )


def research(config, methods=None):
    b = BacktestRequest(
        tickers=config.tickers,
        provider="synthetic",
        start=date(2024, 1, 2),
        end=END,
        source_as_of=config.source_as_of,
        information_policy="research_replay",
        seconds=120,
    )
    return ResearchRequest(
        optimization=config,
        backtest=b,
        methods=methods
        or ["equal_weight", "minimum_variance", "mean_variance", "maximum_sharpe", "risk_parity"],
    )


def test_all_methods_persist_and_replay_independent_inputs(database):
    url, sessions, _ = database
    cfg = seed(sessions)
    saved = run(sessions, cfg)
    assert saved.result["weights"] is not None
    assert sum(saved.result["weights"].values()) == pytest.approx(1, abs=2e-7)
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_numerical_results"]
        inputs = load_inputs(session, cfg)
        assert freeze(thaw(freeze(inputs))) == freeze(inputs)
    # New revisions invalidate current M2 snapshots but cannot rewrite a frozen allocation
    # experiment.
    ingest(sessions, SyntheticProvider(2), "AAA", START, END)
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_numerical_results"]
    with TestClient(create_app(Settings(database_url=url))) as client:
        for endpoint in ("", "/weights", "/risk", "/explanation", "/result"):
            response = client.get(f"/api/portfolio/optimization/{saved.id}{endpoint}")
            assert response.status_code == 200, response.text
        assert client.post(f"/api/portfolio/optimization/{saved.id}/replay").json()[
            "equivalent_numerical_results"
        ]


def test_frontier_uses_identical_estimates_and_solved_points(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    with sessions() as session:
        inputs = load_inputs(session, cfg)
    result = frontier(FrontierRequest(optimization=cfg, risk_aversions=[0.5, 2, 10, 100]), inputs)
    assert len(result["points"]) == 4
    for point in result["points"]:
        assert point["weights"] is not None
        assert min(point["diagnostics"]["constraint_slack"].values()) >= -2e-7
    assert (
        result["points"][-1]["risk"]["variance"] <= result["points"][0]["risk"]["variance"] + 1e-6
    )


def test_optimizer_targets_execute_through_existing_ledger_and_costs_once(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    req = research(cfg, methods=["equal_weight", "minimum_variance"])
    with sessions() as session:
        inputs = load_inputs(session, cfg)
    result = compare(req, inputs)
    for method, bt in zip(result["methods"], result["_backtests"], strict=True):
        sim = bt["result"]
        assert sim["fills"] and method["decisions"]
        assert all(
            f["at"] > o["submitted_at"] for f, o in zip(sim["fills"], sim["orders"], strict=False)
        )
        assert all(
            abs(Decimal(r["reconciliation_residual"])) < Decimal("1e-8") for r in sim["equity"]
        )
        assert float(sim["equity"][-1]["fees"]) == pytest.approx(
            sum(float(f["commission"]) for f in sim["fills"])
        )
        assert any(
            d["first_subsequent_closing_weights"] != d["decision"].get("weights")
            for d in method["decisions"]
        )
    # Ex-ante optimizer rates influence targets but are never charged as ledger entries.
    costly = cfg.model_copy(
        update={
            "objective": cfg.objective.model_copy(
                update={"asset_cost_rates": {t: 0.001 for t in cfg.tickers}}
            )
        }
    )
    cost_result = compare(research(costly, methods=["equal_weight"]), inputs)["_backtests"][0][
        "result"
    ]
    assert float(cost_result["equity"][-1]["fees"]) == pytest.approx(
        sum(float(f["commission"]) for f in cost_result["fills"])
    )


def test_comparison_links_and_exact_ledger_replay(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    saved = run(sessions, research(cfg, methods=["equal_weight", "minimum_variance"]))
    assert len(saved.result["backtest_links"]) == 2
    with sessions() as session:
        reproduced = replay(session, saved.id)
        assert (
            reproduced["equivalent_numerical_results"]
            and reproduced["equivalent_execution_artifacts"]
        )
        for link in saved.result["backtest_links"]:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(BacktestArtifact)
                    .where(BacktestArtifact.run_id == link["backtest_run_id"])
                )
                > 100
            )
            with pytest.raises(BacktestError, match="linked optimization"):
                replay_ledger(session, link["backtest_run_id"])


def test_future_panel_and_price_changes_preserve_past_allocations(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    with sessions() as session:
        inputs = load_inputs(session, cfg)
    before = optimize(cfg, inputs)
    p = replace(
        inputs.panel,
        rows=tuple(
            replace(r, values=(800.0, 900.0, 1000.0)) if r.day > cfg.estimation_end else r
            for r in inputs.panel.rows
        ),
    )
    changed = replace(inputs, panel=p)
    after = optimize(cfg, changed)
    assert before["weights"] == after["weights"] and before["covariance"] == after["covariance"]
    req = research(cfg, methods=["minimum_variance"])
    original = compare(req, inputs)
    alter = replace(
        inputs,
        panel=replace(
            inputs.panel,
            rows=tuple(
                replace(r, values=(50.0, 50.0, 50.0)) if r.day >= date(2024, 5, 1) else r
                for r in inputs.panel.rows
            ),
        ),
    )
    modified = compare(req, alter)
    old = [d for d in original["methods"][0]["decisions"] if d["day"] < "2024-05-01"]
    new = [d for d in modified["methods"][0]["decisions"] if d["day"] < "2024-05-01"]
    assert [d["decision"]["weights"] for d in old] == [d["decision"]["weights"] for d in new]


def test_online_backfilled_features_insufficient_not_historical_alpha(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    cfg = cfg.model_copy(update={"information_policy": "online"})
    saved = run(sessions, cfg)
    assert saved.status == "insufficient_data" and saved.result["weights"] is None


def test_walk_forward_boundaries_past_moments_and_replay(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    req = research(cfg, methods=["minimum_variance"])
    wf = WalkResearch(
        research=req,
        train_sessions=40,
        validation_sessions=10,
        test_sessions=20,
        step_sessions=20,
        maximum_folds=10,
    )
    saved = run(sessions, wf)
    assert saved.result["folds"]
    folds = saved.result["folds"]
    assert all(
        a["split"]["test_end"] < b["split"]["test_start"]
        for a, b in zip(folds, folds[1:], strict=False)
    )
    for f in folds:
        for d in f["methods"][0]["decisions"]:
            assert d["decision"]["estimation"]["end"] <= d["day"]
            assert datetime.fromisoformat(
                d["decision"]["estimation"]["earliest_availability"]
            ) <= datetime.fromisoformat(d["at"])
    with sessions() as session:
        result = replay(session, saved.id)
        assert result["equivalent_numerical_results"] and result["equivalent_execution_artifacts"]


def test_api_validation_solver_bounds_and_infeasibility(database):
    url, sessions, _ = database
    cfg = seed(sessions)
    body = cfg.model_dump(mode="json")
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.post("/api/portfolio/optimize", json=body)
        assert response.status_code == 201, response.text
        for bad in (
            {"tickers": ["AAA"] * 51},
            {"decision_at": "2023-01-01"},
            {"estimation_end": "2024-02-01"},
            {"objective": {"method": "eval"}},
            {"constraints": {"leverage": 2}},
            {"constraints": {"maximum": {"FUTURE_MEMBER": 0.1}}},
        ):
            assert client.post("/api/portfolio/optimize", json=body | bad).status_code == 422
        bad = client.post(
            "/api/portfolio/optimize", json=body | {"constraints": {"concentration": 0.1}}
        )
        assert bad.status_code == 201 and bad.json()["status"] == "infeasible"
        for route, payload in (
            (
                "efficient-frontier",
                FrontierRequest(optimization=cfg, risk_aversions=[1, 10]).model_dump(mode="json"),
            ),
            ("compare", research(cfg, methods=["equal_weight"]).model_dump(mode="json")),
        ):
            result = client.post("/api/portfolio/" + route, json=payload)
            assert result.status_code == 201, result.text
        assert client.get("/api/portfolio/optimization/not-uuid").status_code == 422
        assert (
            client.get(
                "/api/portfolio/optimization/00000000-0000-0000-0000-000000000000"
            ).status_code
            == 404
        )


def test_failed_experiment_is_audited_not_success(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    with (
        patch(
            "sentientalpha.optimization.storage.execute",
            side_effect=OptimizationError("controlled budget failure", "time_budget", 429),
        ),
        pytest.raises(OptimizationError),
    ):
        run(sessions, cfg)
    with sessions() as session:
        saved = session.scalar(select(OptimizationRun))
        assert saved.status == "failed" and saved.result["error_code"] == "time_budget"
        with pytest.raises(OptimizationError, match="Incomplete"):
            replay(session, saved.id)


def test_actual_m3_adapter_preserves_missing_coverage_and_provenance(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    from sentientalpha.sentiment.datasets import SentimentGenerationRequest, generate_sentiment
    from sentientalpha.sentiment.inference import infer
    from sentientalpha.sentiment.ingestion import ingest_news
    from sentiment_fixtures import ControlledNews, TestModel, article

    pub = datetime(2023, 2, 1, 15, tzinfo=UTC)
    ingest_news(
        sessions,
        ControlledNews([article(ticker="AAA", published=pub)], coverage="snapshot"),
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2023, 3, 1, tzinfo=UTC),
        ["AAA"],
    )
    model = TestModel()
    infer(sessions, model, "synthetic_news", max_items=100)
    ds = generate_sentiment(
        sessions,
        SentimentGenerationRequest(
            tickers=["AAA"],
            news_provider="synthetic_news",
            model_key=model.key,
            start=date(2023, 1, 2),
            end=date(2023, 12, 29),
            calendar="weekday",
            availability_policy="observed",
            features=[FeatureSpec(name="sent_mean", parameters={"window": 1, "min_articles": 1})],
        ),
    ).dataset
    spec = Sentiment(
        dataset_id=ds.id,
        column=ds.columns[0],
        train_start=START,
        train_end=date(2023, 6, 30),
        minimum_samples=10,
        provenance="synthetic_fixture",
    )
    cfg = cfg.model_copy(update={"source_as_of": now(), "sentiment": spec})
    with sessions() as session:
        inputs = load_inputs(session, cfg)
        assert inputs.sentiments
        assert any(
            s.coverage in {"missing_provider_coverage", "partial_observed"}
            for s in inputs.sentiments
        )
    unavailable = optimize(cfg, inputs)
    assert unavailable["status"] == "insufficient_sentiment"
    fallback = optimize(
        cfg.model_copy(update={"sentiment": spec.model_copy(update={"fallback": "price_only"})}),
        inputs,
    )
    assert fallback["status"] == "price_only_fallback" and fallback["weights"] is not None
    # A synthetic source cannot become genuine simply by relabeling the request.
    fake = cfg.model_copy(
        update={"sentiment": spec.model_copy(update={"provenance": "verified_history"})}
    )
    with sessions() as session:
        denied = load_inputs(session, fake)
        assert not denied.sentiments and denied.metadata["sentiment_unavailable"]


def test_research_rejects_full_evaluation_estimation_and_overlap(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    req = research(cfg, methods=["equal_weight"])
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(
            req.model_dump()
            | {"optimization": cfg.model_dump() | {"estimation_end": END, "decision_at": now()}}
        )
    with pytest.raises(ValidationError):
        WalkResearch(research=req, test_sessions=30, step_sessions=20)
    with pytest.raises(ValidationError):
        Sentiment.model_validate(
            {
                "dataset_id": "a" * 36,
                "column": "sent_mean__window_5",
                "train_start": "2023-01-01",
                "train_end": "2023-06-01",
                "lambda": 0.1,
            }
        )


def test_optimization_api_busy_and_paging_bounds(database):
    url, sessions, _ = database
    cfg = seed(sessions)
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()

    def paused(sessions, request):
        entered.set()
        assert release.wait(10)
        return run(sessions, request)

    with (
        TestClient(create_app(Settings(database_url=url))) as client,
        patch("sentientalpha.api.portfolio.run", side_effect=paused),
        ThreadPoolExecutor(2) as workers,
    ):
        first = workers.submit(
            client.post, "/api/portfolio/optimize", json=cfg.model_dump(mode="json")
        )
        try:
            assert entered.wait(10)
            assert (
                client.post("/api/portfolio/optimize", json=cfg.model_dump(mode="json")).status_code
                == 429
            )
        finally:
            release.set()
        rid = first.result(timeout=10).json()["id"]
        assert client.get(f"/api/portfolio/optimization/{rid}/result?limit=101").status_code == 422
        assert (
            client.get(f"/api/portfolio/optimization/{rid}/training-lineage?limit=501").status_code
            == 422
        )


def test_frozen_optimization_tampering_rejected(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    saved = run(sessions, cfg)
    with sessions.begin() as session:
        obj = get_run(session, saved.id)
        obj.inputs = {**obj.inputs, "metadata": {"tampered": True}}
    with sessions() as session, pytest.raises(OptimizationError, match="changed"):
        replay(session, saved.id)


def test_frontier_uses_convex_method_even_if_original_objective_has_unsupported_cash_range(
    database,
):
    _, sessions, _ = database
    cfg = seed(sessions)
    cfg = cfg.model_copy(
        update={
            "objective": Objective(method="risk_parity"),
            "constraints": Constraints(cash_maximum=1),
        }
    )
    with sessions() as session:
        inputs = load_inputs(session, cfg)
    result = frontier(FrontierRequest(optimization=cfg, risk_aversions=[1, 10]), inputs)
    assert len(result["points"]) == 2 and all(p["weights"] is not None for p in result["points"])


def test_actual_weights_are_taken_after_eligible_execution_not_after_old_observation_date(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    req = research(cfg, methods=["equal_weight"])
    req = req.model_copy(
        update={
            "backtest": req.backtest.model_copy(
                update={
                    "costs": req.backtest.costs.model_copy(
                        update={"unknown_volume": "unlimited_approximation"}
                    )
                }
            )
        }
    )
    with sessions() as session:
        data = load_inputs(session, cfg)
    delayed = replace(
        data,
        prices=replace(
            data.prices,
            bars=tuple(
                replace(b, available=b.available + timedelta(days=3)) for b in data.prices.bars
            ),
        ),
        panel=replace(
            data.panel,
            rows=tuple(
                replace(r, ready=tuple(t + timedelta(days=3) if t else None for t in r.ready))
                for r in data.panel.rows
            ),
        ),
    )
    result = compare(req, delayed)
    from sentientalpha.features.timing import next_open

    first = result["methods"][0]["decisions"][0]
    assert datetime.fromisoformat(first["first_subsequent_closing_at"]) >= next_open(
        "weekday", datetime.fromisoformat(first["at"])
    )
    assert first["first_subsequent_closing_weights"]

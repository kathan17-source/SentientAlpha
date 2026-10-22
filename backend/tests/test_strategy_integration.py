"""Actual M2/M6 data, SQLite migration, locked holdouts, persistent M4 ledgers and API."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.database.base import now
from sentientalpha.database.ml_models import MLModel
from sentientalpha.database.strategy_models import DiscoveryRun, HoldoutUse, StrategyCandidate
from sentientalpha.ml.storage import run as train_ml
from sentientalpha.strategies.contracts import Axis, DiscoveryError, Fitness, Request, Space
from sentientalpha.strategies.inputs import load
from sentientalpha.strategies.storage import discover, evaluate_locked, replay
from sqlalchemy import func, select
from test_integration import database as database
from test_ml_integration import seed as seed_ml
from test_strategy_research import fixture


def seed(sessions):
    ml = seed_ml(sessions)
    cfg, _ = fixture()
    return Request.model_validate(
        {
            **cfg.model_dump(),
            "tickers": ml.tickers,
            "dataset_id": ml.dataset_id,
            "source_as_of": now(),
        }
    )


def test_dataset_discovery_registry_evaluation_replay_api(database):
    url, sessions, cfg = database
    req = seed(sessions)
    saved = discover(sessions, req)
    assert saved.status == "ready_for_test"
    assert "test_started_at" not in saved.manifest
    assert saved.manifest["selection_frozen_at"]
    assert discover(sessions, req).id == saved.id
    evaluated = evaluate_locked(sessions, saved.id)
    assert evaluated.status == "evaluated"
    assert evaluated.manifest["selection_frozen_at"] <= evaluated.manifest["test_started_at"]
    with sessions() as session:
        assert replay(session, saved.id) == {
            "equivalent_search_and_selection": True,
            "equivalent_ledger_artifacts": True,
        }
        assert {h.status for h in session.scalars(select(HoldoutUse))} == {"consumed"}
        candidates = list(session.scalars(select(StrategyCandidate)))
        assert len(candidates) == len(saved.result["folds"][0]["candidates"])
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.get("/api/strategies/leaderboard", params={"run_id": saved.id})
        assert response.status_code == 200, response.text
        selected = next(c for c in response.json()["items"] if c["selected"])
        for suffix in ["", "/rules", "/performance", "/robustness", "/trades"]:
            r = client.get("/api/strategies/" + selected["id"] + suffix)
            assert r.status_code == 200, r.text
        r = client.get("/api/strategies/" + selected["id"] + "/trades")
        assert r.json()["items"] and r.json()["items"][0]["signal"]
        assert client.post("/api/strategies/" + selected["id"] + "/evaluate").status_code == 200
        assert client.post("/api/strategies/discovery/" + saved.id + "/replay").json()[
            "equivalent_ledger_artifacts"
        ]
        assert client.get("/api/strategies").status_code == 200
        assert client.get("/api/strategies/discovery/" + saved.id).status_code == 200
        assert (
            client.post(
                "/api/strategies/discover",
                json={**req.model_dump(mode="json"), "arbitrary_python": "import os"},
            ).status_code
            == 422
        )
        unselected = next((c for c in candidates if c.rule_hash != selected["version"]), None)
        if unselected:
            assert client.post("/api/strategies/" + unselected.id + "/evaluate").status_code == 409


def test_manifest_alteration_holdout_reuse_refused_and_disclosed(database):
    _, sessions, _ = database
    cfg, inputs = fixture(candidates=6)
    saved = discover(sessions, cfg, inputs)
    with pytest.raises(DiscoveryError, match="Idempotency"):
        discover(sessions, cfg.model_copy(update={"seed": 1}), inputs)
    with pytest.raises(DiscoveryError, match="holdout"):
        discover(
            sessions, cfg.model_copy(update={"idempotency_key": "another_fresh_search"}), inputs
        )
    repeated = discover(
        sessions,
        cfg.model_copy(
            update={
                "idempotency_key": "explicit_reused_search",
                "holdout_history": "previously_inspected",
            }
        ),
        inputs,
    )
    assert repeated.manifest["holdout_reuse"]
    assert repeated.manifest["holdout_label"] == "previously_inspected_exploratory"
    with sessions() as session:
        r = session.get(DiscoveryRun, saved.id)
        r.result = {**r.result, "selection_hash": "wrong"}
        session.commit()
    with pytest.raises(DiscoveryError):
        evaluate_locked(sessions, saved.id)


def test_failure_audit_and_consumed_holdout_never_reset(database):
    _, sessions, _ = database
    cfg, inputs = fixture(candidates=6)
    saved = discover(sessions, cfg, inputs)
    with patch(
        "sentientalpha.strategies.storage.final_evaluation", side_effect=RuntimeError("private")
    ):
        with pytest.raises(DiscoveryError):
            evaluate_locked(sessions, saved.id)
    with sessions() as session:
        r = session.get(DiscoveryRun, saved.id)
        assert r.status == "failed_evaluation"
        assert "private" not in str(r.manifest)
        assert session.scalar(select(HoldoutUse)).status == "consumed"
    with pytest.raises(DiscoveryError):
        evaluate_locked(sessions, saved.id)


def test_no_credible_strategy_is_a_successful_audited_search(database):
    _, sessions, _ = database
    cfg, inputs = fixture(candidates=8)
    cfg = cfg.model_copy(update={"fitness": Fitness(minimum_closed_lots=1000)})
    saved = discover(sessions, cfg, inputs)
    assert saved.status == "no_eligible_strategy"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(StrategyCandidate)) == 8
        assert replay(session, saved.id)["equivalent_search_and_selection"]


def test_ml_forecast_origin_version_horizon_and_future_training_gates(database):
    _, sessions, _ = database
    ml = seed_ml(sessions)
    trained = train_ml(sessions, ml)
    cfg = seed(sessions)
    with sessions() as session:
        model = session.scalar(select(MLModel).where(MLModel.experiment_id == trained.id))
    cfg = cfg.model_copy(
        update={
            "ml_model_ids": [model.id],
            "space": Space(axes=[Axis(feature="ml_probability", thresholds=[0.4, 0.5, 0.6])]),
            "source_as_of": now(),
            "holdout_history": "previously_inspected",
        }
    )
    with sessions() as session:
        inputs = load(session, cfg)
        assert "ml_probability" in inputs.available
        with pytest.raises(DiscoveryError, match="live"):
            load(session, cfg.model_copy(update={"information_policy": "online"}))
        with pytest.raises(DiscoveryError, match="horizon"):
            load(session, cfg.model_copy(update={"ml_horizon": 5}))
        model = session.get(MLModel, model.id)
        model.payload = {**model.payload, "effective_at": (now() + timedelta(days=1)).isoformat()}
        session.commit()
        with pytest.raises(DiscoveryError):
            load(session, cfg)


def test_online_materialization_and_unknown_feature_not_fake_signal(database):
    _, sessions, _ = database
    cfg = seed(sessions)
    online = cfg.model_copy(update={"information_policy": "online"})
    saved = discover(sessions, online)
    assert saved.status == "no_eligible_strategy"
    with sessions() as session:
        with pytest.raises(DiscoveryError):
            load(
                session,
                cfg.model_copy(
                    update={"space": Space(axes=[Axis(feature="future_return", thresholds=[0])])}
                ),
            )


def test_budget_failure_keeps_partial_evaluated_history(database):
    _, sessions, _ = database
    cfg, inputs = fixture(candidates=6)
    from sentientalpha.strategies.research import Budget

    original = Budget.check

    def limited(self):
        if self.count >= 3:
            raise DiscoveryError("controlled budget", "discovery_budget", 429)
        return original(self)

    with patch.object(Budget, "check", limited):
        with pytest.raises(DiscoveryError):
            discover(sessions, cfg, inputs)
    with sessions() as session:
        run = session.scalar(select(DiscoveryRun))
        assert run.status == "failed"
        assert run.result["partial_search_history"]["candidates"][0]["train"]
        assert run.result["partial_search_history"]["candidates"][0]["validation"]


def test_actual_m3_coverage_is_not_fabricated_for_discovery(database):
    from sentientalpha.backtesting.evaluation import Split
    from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
    from sentientalpha.features.storage import generate
    from sentientalpha.sentiment.datasets import generate_sentiment
    from test_sentiment_integration import request as sentiment_request
    from test_sentiment_integration import seed as news_seed

    _, sessions, _ = database
    _, model, _, _ = news_seed(sessions, days=20)
    sent = generate_sentiment(
        sessions, sentiment_request(model).model_copy(update={"availability_policy": "observed"})
    ).dataset
    price = generate(
        sessions,
        GenerationRequest(
            tickers=["AAPL"],
            provider="synthetic",
            start=date(2024, 1, 2),
            end=date(2024, 4, 30),
            features=[FeatureSpec(name="return")],
        ),
    ).dataset
    cfg, _ = fixture(candidates=5)
    cfg = Request.model_validate(
        {
            **cfg.model_dump(),
            "dataset_id": price.id,
            "sentiment_dataset_id": sent.id,
            "tickers": ["AAPL"],
            "source_as_of": now(),
            "sentiment_provenance": "synthetic_fixture",
            "space": Space(axes=[Axis(feature=sent.columns[0], thresholds=[0])]),
            "windows": [
                Split(
                    train_start=date(2024, 1, 2),
                    train_end=date(2024, 2, 16),
                    validation_start=date(2024, 2, 19),
                    validation_end=date(2024, 3, 15),
                    test_start=date(2024, 3, 18),
                    test_end=date(2024, 4, 30),
                )
            ],
        }
    )
    with sessions() as session:
        inputs = load(session, cfg)
        cells = [
            s
            for values in inputs.signals.values()
            for name, s in values.items()
            if name.startswith("sent_")
        ]
        from sentientalpha.data.calendar import session_close
        from sentientalpha.strategies.contracts import Definition, Rule
        from sentientalpha.strategies.evaluation import evaluate

        assert cells
        for (day, _), values in inputs.signals.items():
            for name, signal in values.items():
                if name.startswith("sent_"):
                    assert signal.value is None or (
                        signal.ready is not None
                        and signal.ready
                        > session_close(inputs.calendar, day) + timedelta(seconds=1)
                    )
        result, diagnostic = evaluate(
            cfg,
            inputs,
            Definition(entry=Rule(feature=sent.columns[0], operator="gt", threshold=0)),
            cfg.windows[0].train_start,
            cfg.windows[0].train_end,
        )
        assert result["fills"] == []
        assert diagnostic["signal_coverage"] == 0
        with pytest.raises(DiscoveryError):
            load(session, cfg.model_copy(update={"sentiment_provenance": "genuine"}))

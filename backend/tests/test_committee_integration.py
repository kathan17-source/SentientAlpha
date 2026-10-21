"""Actual SQL/M2/M5/M4/API integrations over labeled synthetic history."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.committee.contracts import Policy
from sentientalpha.committee.requests import Request
from sentientalpha.committee.sources import load_sources
from sentientalpha.committee.storage import decisions, execute, replay
from sentientalpha.config import Settings
from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun
from sentientalpha.database.base import now
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun
from sentientalpha.database.ml_models import MLModel
from sentientalpha.database.models import MarketPrice
from sentientalpha.database.strategy_models import StrategyCandidate
from sentientalpha.ml.storage import run as train_ml
from sentientalpha.optimization.contracts import Estimator
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.strategies.storage import discover
from sqlalchemy import func, select
from test_integration import database as database
from test_ml_integration import seed as seed_ml
from test_strategy_integration import seed as seed_strategy


def config(sessions, **updates):
    cfg = seed_ml(sessions)
    return Request.model_validate(
        {
            "dataset_id": cfg.dataset_id,
            "tickers": cfg.tickers,
            "history_start": "2022-01-03",
            "start": "2023-06-01",
            "end": "2023-06-30",
            "source_as_of": now(),
            "information_policy": "retrospective",
            "policy": Policy(
                effective_at=datetime(2022, 1, 1, tzinfo=UTC), minimum_independent_groups=1
            ),
            "estimator": Estimator(minimum_observations=20),
            "idempotency_key": "committee-integration",
            **updates,
        }
    )


def test_persistent_committee_m4_ledger_api_and_replay(database):
    url, sessions, _ = database
    req = config(sessions)
    saved = execute(sessions, req, True)
    assert saved.status == "completed" and saved.backtest_id
    assert saved.result["fills"] > 0
    assert execute(sessions, req, True).id == saved.id
    with sessions() as session:
        trace = decisions(session, saved.id)
        assert trace and len(trace[0]["recommendations"]) == 12
        assert all(d["execution_eligible_at"] > d["decision_at"] for d in trace)
        assert replay(session, saved.id)["equivalent_ledger"]
        fills = list(
            session.scalars(
                select(BacktestArtifact).where(
                    BacktestArtifact.run_id == saved.backtest_id, BacktestArtifact.kind == "fills"
                )
            )
        )
        orders = {
            a.payload["id"]: a.payload
            for a in session.scalars(
                select(BacktestArtifact).where(
                    BacktestArtifact.run_id == saved.backtest_id, BacktestArtifact.kind == "orders"
                )
            )
        }
        assert all(f.payload["at"] > orders[f.payload["order_id"]]["submitted_at"] for f in fills)
        assert all(
            abs(float(a.payload["reconciliation_residual"])) <= 1e-8
            for a in session.scalars(
                select(BacktestArtifact).where(
                    BacktestArtifact.run_id == saved.backtest_id, BacktestArtifact.kind == "equity"
                )
            )
        )
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/ready").status_code == 200
        for path in [
            "/api/agents",
            "/api/agents/quant",
            "/api/agents/quant/performance",
            "/api/investment-committee",
            f"/api/investment-committee/{saved.id}",
            *[
                f"/api/investment-committee/{saved.id}/{s}"
                for s in [
                    "decisions",
                    "agents",
                    "evidence",
                    "allocation",
                    "risk-review",
                    "execution",
                ]
            ],
        ]:
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
        assert client.post(f"/api/investment-committee/{saved.id}/replay").json()[
            "equivalent_decisions"
        ]
        assert client.get("/api/agents/nonexistent").status_code == 404
        assert (
            client.get("/api/investment-committee/00000000-0000-0000-0000-000000000000").status_code
            == 404
        )
        assert client.get("/api/investment-committee?limit=999").status_code == 422
        assert (
            client.post(
                "/api/agents/analyze",
                json={**req.model_dump(mode="json"), "idempotency_key": "committee-analysis"},
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/investment-committee/backtest",
                json={**req.model_dump(mode="json"), "arbitrary_code": "eval"},
            ).status_code
            == 422
        )
        assert (
            "/api/investment-committee/{run_id}/replay"
            in client.get("/openapi.json").json()["paths"]
        )
    with pytest.raises(OptimizationError, match="different immutable"):
        execute(sessions, req.model_copy(update={"technical_scale": 0.03}), True)


def test_veto_emits_no_targets_and_no_executions(database):
    _, sessions, _ = database
    req = config(sessions)
    veto = {
        "action": "reject",
        "proposal": {"weights": {"AAA": 1}},
        "risk_review": {"status": "vetoed", "override_permitted": False},
        "final_allocation": None,
    }
    with patch("sentientalpha.committee.engine.allocate", return_value=veto):
        saved = execute(sessions, req, True)
    assert saved.result["risk_vetoes"] > 0
    assert saved.result["fills"] == saved.result["orders"] == 0


def test_partial_failure_rolls_back_decisions_and_child_ledger(database):
    _, sessions, _ = database
    req = config(sessions)
    from sentientalpha.committee import storage

    original = storage.persist

    def fail_after_ledger(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure after ledger flush")

    with patch.object(storage, "persist", side_effect=fail_after_ledger):
        with pytest.raises(RuntimeError, match="injected"):
            execute(sessions, req, True)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(BacktestRun)) == 0
        assert session.scalar(select(func.count()).select_from(CommitteeDecision)) == 0
        saved = session.scalar(select(CommitteeRun))
        assert saved.status == "failed" and saved.backtest_id is None


def test_quant_uses_actual_versioned_original_forecasts(database):
    _, sessions, _ = database
    ml = seed_ml(sessions)
    trained = train_ml(sessions, ml)
    with sessions() as session:
        model = session.scalar(select(MLModel).where(MLModel.experiment_id == trained.id))
    req = Request(
        dataset_id=ml.dataset_id,
        tickers=ml.tickers,
        history_start=date(2022, 1, 3),
        start=ml.windows[0].test_start,
        end=ml.windows[0].test_end,
        source_as_of=now(),
        information_policy="retrospective",
        model_id=model.id,
        experimental_quant=True,
        policy=Policy(effective_at=datetime(2022, 1, 1, tzinfo=UTC), minimum_independent_groups=1),
        estimator=Estimator(minimum_observations=20),
        idempotency_key="quant-integration",
    )
    saved = execute(sessions, req, True)
    with sessions() as session:
        rows = [
            r
            for d in decisions(session, saved.id)
            for r in d["recommendations"]
            if r["agent_id"] == "quant" and r["prediction"] is not None
        ]
        assert rows and all(r["evidence"][0]["version"] == model.version for r in rows)
        assert all(r["expected_return"] is None and r["confidence"] is None for r in rows)
        assert replay(session, saved.id)["equivalent_decisions"]
        from sentientalpha.committee.adapters import quant

        inputs, meta = load_sources(session, req)
        at = datetime.fromisoformat(rows[0]["decision_at"])
        import copy

        for field, value in [
            ("units", "simple_return_horizon"),
            ("feature_set_hash", "altered"),
            ("value", float("nan")),
            ("horizon", 5),
        ]:
            altered = copy.deepcopy(meta["quant"])
            for prediction in altered["predictions"]:
                prediction["payload"][field] = value
            assert (
                quant(req, altered, rows[0]["ticker"], at, at.date().isoformat()).status
                == "invalid"
            )
        altered = copy.deepcopy(meta["quant"])
        altered["model"]["training_cutoff"] = (at + timedelta(days=1)).isoformat()
        assert quant(req, altered, rows[0]["ticker"], at, at.date().isoformat()).status == "invalid"
        meta["quant"]["model"]["effective_at"] = (at + timedelta(days=1)).isoformat()
        assert (
            quant(req, meta["quant"], rows[0]["ticker"], at, at.date().isoformat()).status
            == "invalid"
        )


def test_strategy_uses_real_locked_registry_without_search_on_analysis(database):
    _, sessions, _ = database
    discovery = seed_strategy(sessions)
    saved = discover(sessions, discovery)
    with sessions() as session:
        selected = saved.result["folds"][0]["selected"]
        candidate = session.scalar(
            select(StrategyCandidate).where(
                StrategyCandidate.discovery_id == saved.id, StrategyCandidate.rule_hash == selected
            )
        )
        assert candidate is not None
    req = Request(
        dataset_id=discovery.dataset_id,
        tickers=discovery.tickers,
        history_start=discovery.windows[0].train_start,
        start=discovery.windows[0].test_start,
        end=discovery.windows[0].test_end,
        source_as_of=now(),
        information_policy="retrospective",
        strategy_id=candidate.id,
        policy=Policy(effective_at=datetime(2022, 1, 1, tzinfo=UTC), minimum_independent_groups=1),
        estimator=Estimator(minimum_observations=20),
        idempotency_key="strategy-integration",
    )
    with patch("sentientalpha.strategies.search.generate", side_effect=AssertionError("No search")):
        result = execute(sessions, req, True)
    with sessions() as session:
        rows = [
            r
            for d in decisions(session, result.id)
            for r in d["recommendations"]
            if r["agent_id"] == "strategy"
        ]
        assert any(r["evidence"] for r in rows)
        assert replay(session, result.id)["equivalent_ledger"]


def test_future_sources_do_not_rewrite_frozen_decisions_and_changed_risk_is_rejected(database):
    _, sessions, _ = database
    req = config(sessions)
    saved = execute(sessions, req, True)
    with sessions.begin() as session:
        # New/future revisions and retraining are not queried by frozen committee replay.
        latest = session.scalar(
            select(MarketPrice).where(MarketPrice.session_date > req.end).limit(1)
        )
        latest.high *= 2
        latest.close *= 2
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_decisions"]
    with sessions.begin() as session:
        parent = session.get(CommitteeRun, saved.id)
        manifest = dict(parent.manifest)
        changed_config = dict(manifest["configuration"])
        changed_config["constraints"] = {**changed_config["constraints"], "concentration": 0.01}
        manifest["configuration"] = changed_config
        parent.manifest = manifest
    with sessions() as session:
        with pytest.raises(OptimizationError, match="mismatch"):
            replay(session, saved.id)


@pytest.mark.parametrize(
    "change", ["missing_evidence", "stale_recommendation", "future_news_revision"]
)
def test_saved_decision_tampering_is_detected_on_replay(database, change):
    _, sessions, _ = database
    req = config(sessions)
    saved = execute(sessions, req, True)
    import copy

    with sessions.begin() as session:
        record = session.scalar(
            select(CommitteeDecision).where(CommitteeDecision.run_id == saved.id)
        )
        value = copy.deepcopy(record.payload)
        if change == "missing_evidence":
            value["recommendations"][0]["evidence"] = []
        elif change == "stale_recommendation":
            value["recommendations"][0]["decision_at"] = "2020-01-01T00:00:00+00:00"
        else:
            value["recommendations"][0]["evidence"][0]["available_at"] = "2030-01-01T00:00:00+00:00"
        record.payload = value
    with sessions() as session:
        with pytest.raises(OptimizationError, match="audit was altered"):
            replay(session, saved.id)


def test_invalid_m5_proposal_is_vetoed_before_actual_m4_orders(database):
    _, sessions, _ = database
    req = config(sessions)
    with patch(
        "sentientalpha.committee.risk.solve",
        return_value={"status": "completed", "weights": {"AAA": 0.9, "BBB": 0.9}},
    ):
        saved = execute(sessions, req, True)
    assert saved.result["risk_vetoes"] > 0 and saved.result["orders"] == saved.result["fills"] == 0
    with sessions() as session:
        trace = decisions(session, saved.id)
        assert all(d["allocation"]["risk_review"]["status"] == "vetoed" for d in trace)


def test_real_api_backtest_and_child_must_replay_through_parent(database):
    url, sessions, _ = database
    req = config(sessions)
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.post(
            "/api/investment-committee/backtest", json=req.model_dump(mode="json")
        )
        assert response.status_code == 201, response.text
        child = response.json()["backtest_id"]
    from sentientalpha.backtesting.contracts import BacktestError
    from sentientalpha.backtesting.storage import replay as child_replay

    with sessions() as session:
        with pytest.raises(BacktestError, match="linked investment committee"):
            child_replay(session, child)


def test_future_retraining_and_selection_do_not_replace_saved_versions(database):
    _, sessions, _ = database
    ml = seed_ml(sessions)
    trained = train_ml(sessions, ml)
    with sessions() as session:
        model = session.scalar(select(MLModel).where(MLModel.experiment_id == trained.id))
    req = Request(
        dataset_id=ml.dataset_id,
        tickers=ml.tickers,
        history_start=date(2022, 1, 3),
        start=ml.windows[0].test_start,
        end=ml.windows[0].test_end,
        source_as_of=now(),
        information_policy="retrospective",
        model_id=model.id,
        experimental_quant=True,
        policy=Policy(effective_at=datetime(2022, 1, 1, tzinfo=UTC), minimum_independent_groups=1),
        estimator=Estimator(minimum_observations=20),
        idempotency_key="frozen-model-version",
    )
    saved = execute(sessions, req, True)
    future = train_ml(
        sessions, ml.model_copy(update={"target": ml.target.model_copy(update={"horizon": 5})})
    )
    assert future.id != trained.id
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_decisions"]
        assert replay(session, saved.id)["equivalent_ledger"]


def test_strategy_future_selection_is_invalid_even_in_retrospective_mode(database):
    _, sessions, _ = database
    discovery = seed_strategy(sessions)
    saved = discover(sessions, discovery)
    with sessions() as session:
        selected = saved.result["folds"][0]["selected"]
        candidate = session.scalar(
            select(StrategyCandidate).where(
                StrategyCandidate.discovery_id == saved.id, StrategyCandidate.rule_hash == selected
            )
        )
        req = Request(
            dataset_id=discovery.dataset_id,
            tickers=discovery.tickers,
            history_start=discovery.windows[0].train_start,
            start=discovery.windows[0].test_start,
            end=discovery.windows[0].test_end,
            source_as_of=now(),
            information_policy="retrospective",
            strategy_id=candidate.id,
            policy=Policy(
                effective_at=datetime(2022, 1, 1, tzinfo=UTC), minimum_independent_groups=1
            ),
            estimator=Estimator(minimum_observations=20),
            idempotency_key="future-strategy-check",
        )
        _, meta = load_sources(session, req)
    from sentientalpha.committee.adapters import strategy

    at = datetime.combine(req.start, datetime.min.time(), tzinfo=UTC)
    meta["strategy"]["validation_end"] = (req.end + timedelta(days=1)).isoformat()
    result = strategy(req, meta["strategy"], req.tickers[0], at, 0.5, at)
    assert result.status == "invalid" and result.signal is None


def test_stale_risk_inputs_have_a_nonoverridable_veto():
    from sentientalpha.committee.risk import review
    from sentientalpha.optimization.contracts import Constraints
    from test_committee_foundation import AT, estimates

    result = review(
        {"IBM": 0.5, "SPY": 0.5}, estimates(), Constraints(), {}, AT, AT - timedelta(days=8)
    )
    assert result["status"] == "vetoed" and result["final_allocation"] is None
    assert "staleness" in result["violations"]

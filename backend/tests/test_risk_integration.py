"""Actual SQL/API/M8/M4 risk authority, partial fills, atomic rollback and frozen replay."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.engine import simulate
from sentientalpha.committee.engine import backtest_config
from sentientalpha.committee.sources import load_sources
from sentientalpha.committee.storage import execute as run_committee
from sentientalpha.committee.storage import replay as replay_committee
from sentientalpha.config import Settings
from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun
from sentientalpha.database.risk_models import RiskAlert, RiskAssessment, RiskPolicyVersion
from sentientalpha.optimization.contracts import Constraints, Estimator
from sentientalpha.risk.contracts import Policy
from sentientalpha.risk.controller import RiskController
from sentientalpha.risk.storage import execute, replay
from sentientalpha.strategies.contracts import Request as DiscoveryRequest
from sentientalpha.strategies.evaluation import snapshot
from sqlalchemy import func, select
from test_committee_integration import config
from test_integration import database as database
from test_risk_math import AT, fixture


def policy(req, **updates):
    return Policy.model_validate(
        {
            "id": "integration-policy",
            "version": "1",
            "effective_at": req.policy.effective_at,
            "constraints": Constraints(cash_maximum=1, concentration=0.35),
            "estimator": Estimator(minimum_observations=20),
            "adjustment": "scale_to_cash",
            **updates,
        }
    )


def test_actual_committee_risk_events_orders_post_positions_and_replay(database):
    _, sessions, _ = database
    req = config(sessions)
    req = req.model_copy(update={"risk_policy": policy(req)})
    saved = run_committee(sessions, req, True)
    assert saved.result["fills"] > 0 and saved.result["m9_risk"]["events"] > 0
    with sessions() as session:
        rows = list(
            session.scalars(select(RiskAssessment).where(RiskAssessment.committee_id == saved.id))
        )
        assert {"pre_trade", "pre_fill", "post_open", "post_close"} <= {r.phase for r in rows}
        assert any(r.status == "APPROVED_WITH_REDUCTION" for r in rows)
        assert replay(session, rows[0].id)["equivalent_risk"]
        assert replay_committee(session, saved.id)["equivalent_ledger"]
        closes = {r.at.isoformat(): r.payload for r in rows if r.phase == "post_close"}
        equity = list(
            session.scalars(
                select(BacktestArtifact).where(
                    BacktestArtifact.run_id == saved.backtest_id, BacktestArtifact.kind == "equity"
                )
            )
        )
        for e in equity:
            weights = closes[e.payload["at"]]["current"]["exposure"]["weights"]
            for ticker, p in e.payload["positions"].items():
                assert weights[ticker] == pytest.approx(p["weight"])


def test_real_api_policies_idempotency_historical_cutoffs_and_replay(database):
    url, sessions, _ = database
    req = fixture(var_maximum=0.0001)
    saved = execute(sessions, req)
    assert saved.status == "REJECTED"
    assert execute(sessions, req).id == saved.id
    again = execute(
        sessions, req.model_copy(update={"idempotency_key": "another-rejected-identifier"})
    )
    assert again.id == saved.id
    with sessions() as session:
        count = session.scalar(select(func.count()).select_from(RiskAlert))
        assert count > 0
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.post("/api/risk/evaluate", json=req.model_dump(mode="json"))
        assert response.status_code == 201, response.text
        for suffix in [
            "",
            "/policies",
            "/policies/baseline_simulation",
            f"/decisions/{saved.id}",
            "/alerts",
            "/history",
            "/portfolio/fixture",
            *[
                f"/portfolio/fixture/{s}"
                for s in [
                    "exposure",
                    "var",
                    "cvar",
                    "drawdown",
                    "concentration",
                    "volatility",
                    "stress",
                ]
            ],
        ]:
            response = client.get("/api/risk" + suffix)
            assert response.status_code == 200, (suffix, response.text)
        assert client.post(f"/api/risk/decisions/{saved.id}/replay").json()["equivalent_risk"]
        assert (
            client.get(
                "/api/risk/portfolio/fixture",
                params={"as_of": (AT - timedelta(days=1)).isoformat()},
            ).status_code
            == 404
        )
        assert client.get("/api/risk/history?limit=9999").status_code == 422
        assert client.get("/api/risk/decisions/nonexistent").status_code == 404
        bad = {
            **req.model_dump(mode="json"),
            "idempotency_key": "new-policy-conflict",
            "policy": {**req.policy.model_dump(mode="json"), "var_maximum": 0.02},
        }
        assert client.post("/api/risk/evaluate", json=bad).status_code == 409
        assert (
            client.post(
                "/api/risk/evaluate", json={**req.model_dump(mode="json"), "python": "exec"}
            ).status_code
            == 422
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(RiskAlert)) == count
        assert replay(session, saved.id)["equivalent_risk"]


def test_risk_write_failure_rolls_back_committee_ledger_policy_and_alerts(database):
    _, sessions, _ = database
    req = config(sessions)
    req = req.model_copy(update={"risk_policy": policy(req)})
    from sentientalpha.risk import storage

    original = storage.write

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected risk audit failure")

    with patch.object(storage, "write", side_effect=fail):
        with pytest.raises(RuntimeError, match="injected"):
            run_committee(sessions, req, True)
    with sessions() as session:
        for model in [RiskAssessment, RiskAlert, RiskPolicyVersion, BacktestRun, CommitteeDecision]:
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(CommitteeRun)).status == "failed"


def test_partial_fills_post_monitor_uses_actual_not_theoretical_weights(database):
    _, sessions, _ = database
    req = config(sessions)
    req = req.model_copy(
        update={
            "risk_policy": policy(req),
            "costs": req.costs.model_copy(update={"participation": Decimal(".00001")}),
        }
    )
    saved = run_committee(sessions, req, True)
    with sessions() as session:
        orders = list(
            session.scalars(
                select(BacktestArtifact).where(
                    BacktestArtifact.run_id == saved.backtest_id, BacktestArtifact.kind == "orders"
                )
            )
        )
        assert any(o.payload["status"] == "partial_canceled" for o in orders)
        post = list(
            session.scalars(
                select(RiskAssessment).where(
                    RiskAssessment.committee_id == saved.id, RiskAssessment.phase == "post_open"
                )
            )
        )
        assert any(r.inputs.get("violation_origin") == "execution_mismatch" for r in post)
        assert any(0 < r.payload["current"]["exposure"]["gross"] < 0.1 for r in post)


def test_target_consensus_and_accidental_forwarding_cannot_bypass_fill_veto(database):
    _, sessions, _ = database
    req = config(sessions)
    req = req.model_copy(
        update={
            "risk_policy": policy(
                req,
                constraints=Constraints(cash_maximum=1, concentration=0.001),
                adjustment="reject",
            )
        }
    )
    with sessions() as session:
        inputs, meta = load_sources(session, req)
    controller = RiskController(req, inputs, meta, SimpleNamespace(trace=[]))

    class Bullish:
        def targets(self, context):
            return {t: Decimal(".5") for t in req.tickers}

    cfg = backtest_config(req, inputs)
    snap = snapshot(
        DiscoveryRequest.model_validate(meta["source_configuration"]), inputs, req.start, req.end
    )
    # Forwarding unapproved targets still cannot bypass the independent fill veto.
    with patch.object(
        controller, "approve_targets", side_effect=lambda context, targets, **kwargs: targets
    ):
        result = simulate(cfg, snap, strategy=Bullish(), risk_control=controller)
    assert result["orders"] and not result["fills"]
    assert all(o["status"] in {"rejected", "expired"} for o in result["orders"])
    assert any(o["reason"] == "independent_risk_veto" for o in result["orders"])


def test_frozen_risk_survives_later_policy_and_data_revision_and_detects_tampering(database):
    """New versions cannot replace a frozen historical policy or input snapshot."""
    _, sessions, _ = database
    req = fixture()
    saved = execute(sessions, req)
    newer = req.model_copy(
        update={
            "idempotency_key": "later-policy-version",
            "policy": req.policy.model_copy(update={"version": "2", "var_maximum": 0.00001}),
            "returns": [
                r.model_copy(update={"values": {t: 0.3 for t in r.values}}) for r in req.returns
            ],
        }
    )
    execute(sessions, newer)
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_risk"]
        row = session.get(RiskAssessment, saved.id)
        original = row.inputs
        row.inputs = {**original, "idempotency_key": "altered-source"}
        session.flush()
        from sentientalpha.optimization.estimation import OptimizationError

        with pytest.raises(OptimizationError, match="differ"):
            replay(session, saved.id)
        session.rollback()
    with sessions() as session:
        row = session.get(RiskAssessment, saved.id)
        version = session.get(RiskPolicyVersion, row.policy_key)
        version.definition = {**version.definition, "version": "2"}
        session.flush()
        with pytest.raises(OptimizationError, match="differ"):
            replay(session, saved.id)
        session.rollback()

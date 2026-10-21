"""SQLite migration, existing M2 snapshots, model/forecast storage and HTTP lifecycle."""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.base import now
from sentientalpha.database.ml_models import MLExperiment, MLModel, MLPrediction
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.ml.contracts import MLException, PredictRequest, ResearchRequest, Window
from sentientalpha.ml.dataset import build
from sentientalpha.ml.storage import backtest, predict, replay, run
from sentientalpha.services.ingestion import ingest
from sqlalchemy import func, select
from test_integration import database as database
from test_ml_research import fixture


def seed(sessions):
    start, end = date(2022, 1, 3), date(2024, 6, 28)
    for t in ("AAA", "BBB"):
        ingest(sessions, SyntheticProvider(61), t, start, end)
    ds = generate(
        sessions,
        GenerationRequest(
            tickers=["AAA", "BBB"],
            provider="synthetic",
            start=start,
            end=end,
            features=[
                FeatureSpec(name="return"),
                FeatureSpec(name="sma", parameters={"window": 5}),
            ],
        ),
    ).dataset
    cfg, _ = fixture()
    return ResearchRequest.model_validate(
        {
            **cfg.model_dump(),
            "dataset_id": ds.id,
            "columns": ["return", "sma__window_5"],
            "source_as_of": now(),
        }
    )


def test_real_feature_adapter_storage_predictions_replay_api_and_ledger(database):
    url, sessions, _ = database
    cfg = seed(sessions)
    with sessions() as session:
        ds = build(session, cfg)
    assert ds.rows and all(len(r.values) == 2 for r in ds.rows)
    saved = run(sessions, cfg)
    assert saved.status == "completed"
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_numerical_results"]
        model = session.scalar(select(MLModel).where(MLModel.experiment_id == saved.id))
        assert model
        p = saved.result["predictions"][0]
        req = PredictRequest(
            model_id=model.id,
            tickers=cfg.tickers,
            decision_at=datetime.fromisoformat(p["decision_at"]),
        )
        count = session.scalar(select(func.count()).select_from(MLPrediction))
        assert predict(session, req)
        assert session.scalar(select(func.count()).select_from(MLPrediction)) == count
    ledger = backtest(sessions, saved.id)
    assert len(ledger["ledger_links"]) == 4
    with sessions() as session:
        assert replay(session, saved.id) == {
            "equivalent_numerical_results": True,
            "equivalent_ledger_artifacts": True,
        }
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/ready").status_code == 200
        for path in [
            "/models",
            f"/models/{model.id}",
            "/predictions/AAA",
            f"/experiments/{saved.id}",
            f"/experiments/{saved.id}/metrics",
            f"/experiments/{saved.id}/feature-importance",
        ]:
            assert client.get("/api/ml" + path).status_code == 200
        assert client.post("/api/ml/predict", json=req.model_dump(mode="json")).status_code == 200
        assert client.post(f"/api/ml/experiments/{saved.id}/replay").json()[
            "equivalent_numerical_results"
        ]
        assert (
            client.post(
                "/api/ml/train", json={**cfg.model_dump(mode="json"), "columns": ["future_return"]}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/ml/train", json={**cfg.model_dump(mode="json"), "unknown": "code"}
            ).status_code
            == 422
        )
    ingest(sessions, SyntheticProvider(62), "AAA", date(2022, 1, 3), date(2024, 6, 28))
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_numerical_results"]


def test_online_late_materialization_cannot_be_backdated(database):
    _, sessions, _ = database
    cfg = seed(sessions).model_copy(update={"information_policy": "online"})
    with sessions() as session:
        ds = build(session, cfg)
    assert all(all(v is None for v in r.values) for r in ds.rows)
    saved = run(sessions, cfg)
    assert saved.status == "insufficient_data" and saved.result["predictions"] == []


def test_failed_training_audit_and_tampered_model_refusal(database):
    _, sessions, _ = database
    cfg, ds = fixture()
    with patch("sentientalpha.ml.storage.evaluate", side_effect=RuntimeError("private error")):
        with pytest.raises(MLException):
            run(sessions, cfg, ds)
    with sessions() as session:
        record = session.scalar(select(MLExperiment))
        assert record.status == "failed" and "private" not in str(record.result)
    saved = run(sessions, cfg, ds)
    with sessions() as session:
        item = session.get(MLExperiment, saved.id)
        item.inputs = {**item.inputs, "calendar": "wrong"}
        session.commit()
        with pytest.raises(MLException, match="differ"):
            replay(session, saved.id)


def test_fold_progression_train_cutoffs_and_no_label_input(database):
    _, sessions, _ = database
    cfg, ds = fixture()
    w = cfg.windows[0]
    w2 = Window(
        train_start=w.train_start,
        train_end=date(2023, 3, 31),
        validation_start=date(2023, 4, 3),
        validation_end=date(2023, 5, 31),
        calibration_start=date(2023, 6, 1),
        calibration_end=date(2023, 10, 6),
        test_start=date(2023, 10, 9),
        test_end=date(2024, 2, 29),
    )
    cfg = ResearchRequest.model_validate(
        {**cfg.model_dump(), "windows": [w, w2], "training_mode": "expanding"}
    )
    saved = run(sessions, cfg, ds)
    assert len(saved.result["models"]) == 2
    assert (
        saved.result["models"][0]["training_cutoff"] < saved.result["models"][1]["training_cutoff"]
    )
    assert all(p["training_cutoff"] < p["decision_at"] for p in saved.result["predictions"])


def test_default_model_configuration_round_trip_replays_exactly(database):
    _, sessions, _ = database
    cfg, ds = fixture()
    saved = run(sessions, cfg, ds)
    with sessions() as session:
        assert replay(session, saved.id)["equivalent_numerical_results"]

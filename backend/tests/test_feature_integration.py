"""Real migrations, SQLite persistence and HTTP schemas; no persistence mocks."""

from dataclasses import replace
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import FeatureDataset, FeatureInput, FeatureRow, now
from sentientalpha.features.contracts import FeatureError, FeatureSpec, GenerationRequest
from sentientalpha.features.matrices import MatrixRequest, assemble, cell
from sentientalpha.features.registry import CATALOG, Registry
from sentientalpha.features.storage import generate, get_dataset
from sentientalpha.services.ingestion import ingest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_integration import database as database

START, END = date(2023, 1, 2), date(2024, 3, 1)


def request(tickers=None, features=None, **kwargs):
    return GenerationRequest(
        tickers=tickers or ["AAA"],
        provider="synthetic",
        start=START,
        end=END,
        features=features or [FeatureSpec(name="sma", parameters={"window": 200})],
        **kwargs,
    )


def seed(sessions, symbols=("AAA",)):
    for symbol in symbols:
        ingest(sessions, SyntheticProvider(), symbol, START, END)


def test_persist_cache_lineage_and_restart(database):
    url, sessions, _ = database
    seed(sessions)
    first = generate(sessions, request())
    assert not first.reused and first.dataset.row_count > 300
    with patch(
        "sentientalpha.features.storage.calculate", side_effect=AssertionError("cache recalculated")
    ):
        second = generate(sessions, request())
    assert second.reused and second.dataset.id == first.dataset.id
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(FeatureDataset)) == 1
        assert (
            session.scalar(select(func.count()).select_from(FeatureInput))
            == first.dataset.row_count
        )
        rows = list(session.scalars(select(FeatureRow).order_by(FeatureRow.session_date)))
        assert all(row.values[first.dataset.columns[0]] is None for row in rows[:199])
        assert rows[199].values[first.dataset.columns[0]] > 0
        sample = cell(first.dataset, rows[-1], first.dataset.columns[0])
        assert sample["decision_ready_at"] >= sample["inputs_available_at"]
        assert sample["online_ready_at"] >= sample["inputs_ingested_at"]
        assert sample["online_ready_at"] >= sample["calculated_at"]
        assert sample["earliest_execution_at"] > sample["online_ready_at"]
    with TestClient(create_app(Settings(database_url=url))) as client:
        manifest = client.get(f"/api/feature-datasets/{first.dataset.id}")
        assert (
            manifest.status_code == 200
            and manifest.json()["source_hash"] == first.dataset.source_hash
        )
        lineage = client.get(
            f"/api/feature-datasets/{first.dataset.id}/lineage", params={"limit": 3}
        )
        assert lineage.status_code == 200 and len(lineage.json()["inputs"]) == 3
        assert all(item["is_synthetic"] for item in lineage.json()["inputs"])
        response = client.get(
            "/api/features/AAA",
            params={"dataset_id": first.dataset.id, "start": str(END), "end": str(END)},
        )
        assert (
            response.status_code == 200
            and response.json()["records"][0]["features"][0]["value"] > 0
        )


def test_revision_invalidation_and_historical_snapshot(database):
    _, sessions, _ = database
    seed(sessions)
    initial = generate(sessions, request())
    cutoff = now()
    unchanged = ingest(sessions, SyntheticProvider(), "AAA", START, END)
    assert unchanged.inserted == 0
    with sessions() as session:
        assert get_dataset(session, initial.dataset.id).status == "current"
    ingest(sessions, SyntheticProvider(2), "AAA", START, END)
    with sessions() as session:
        with pytest.raises(FeatureError, match="Regenerate"):
            get_dataset(session, initial.dataset.id)
        assert get_dataset(session, initial.dataset.id, True).status == "stale"
    fresh = generate(sessions, request())
    assert (
        fresh.dataset.id != initial.dataset.id
        and fresh.dataset.source_hash != initial.dataset.source_hash
    )
    old = generate(sessions, request(as_of=cutoff))
    assert old.reused and old.dataset.id == initial.dataset.id and old.dataset.status == "stale"


def test_missing_benchmark_creation_invalidates(database):
    _, sessions, _ = database
    seed(sessions)
    initial = generate(sessions, request(features=[FeatureSpec(name="rolling_beta")]))
    with sessions() as session:
        assert all(
            row.values[initial.dataset.columns[0]] is None
            for row in session.scalars(select(FeatureRow))
        )
    seed(sessions, ("SPY",))
    with sessions() as session:
        assert session.get(FeatureDataset, initial.dataset.id).status == "stale"
    fresh = generate(sessions, request(features=[FeatureSpec(name="rolling_beta")]))
    with sessions() as session:
        last = session.scalar(
            select(FeatureRow)
            .where(FeatureRow.dataset_id == fresh.dataset.id)
            .order_by(FeatureRow.session_date.desc())
        )
        assert last.values[fresh.dataset.columns[0]] is not None


def test_matrix_order_policies_and_point_in_time(database):
    _, sessions, _ = database
    seed(sessions, ("AAA", "BBB"))
    result = generate(
        sessions,
        request(
            ["BBB", "AAA"],
            [FeatureSpec(name="return"), FeatureSpec(name="sma", parameters={"window": 5})],
        ),
    )
    args = dict(dataset_id=result.dataset.id, start=START, end=END, limit=20)
    with sessions() as session:
        matrix = assemble(session, MatrixRequest(**args))
        assert matrix.columns == sorted(result.dataset.columns)
        assert [(row["session_date"], row["ticker"]) for row in matrix.rows] == sorted(
            (row["session_date"], row["ticker"]) for row in matrix.rows
        )
        assert matrix.to_numpy().shape == (20, 2)
        dropped = assemble(session, MatrixRequest(**args, missing_policy="drop_row"))
        assert len(dropped.rows) == 12 and dropped.next_offset == 20
        with pytest.raises(FeatureError, match="unavailable/undefined"):
            assemble(session, MatrixRequest(**args, missing_policy="raise"))
        with pytest.raises(FeatureError, match="Only persisted"):
            assemble(session, MatrixRequest(**args, columns=["future_return"]))
        before = result.dataset.calculated_at - timedelta(microseconds=1)
        online = assemble(session, MatrixRequest(**args, decision_at=before))
        assert all(value is None for row in online.rows for value in row["features"])
        historical = assemble(
            session, MatrixRequest(**args, decision_at=before, availability_mode="research")
        )
        assert any(value is not None for row in historical.rows for value in row["features"])


def test_definition_change_and_removal_require_recompute(database):
    _, sessions, _ = database
    seed(sessions)
    first = generate(sessions, request())
    changed = Registry(
        [replace(item, version="2.0.0") if item.name == "sma" else item for item in CATALOG]
    )
    with sessions() as session:
        with pytest.raises(FeatureError, match="Regenerate"):
            get_dataset(session, first.dataset.id, registry=changed)
        removed = Registry([item for item in CATALOG if item.name != "sma"])
        assert get_dataset(session, first.dataset.id, True, removed).id == first.dataset.id
        with pytest.raises(FeatureError, match="Regenerate"):
            get_dataset(session, first.dataset.id, registry=removed)
    regenerated = generate(sessions, request(), changed)
    assert regenerated.dataset.id != first.dataset.id


def test_failed_materialization_rolls_back_all_tables(database):
    _, sessions, _ = database
    seed(sessions)
    from sentientalpha.features.storage import _bulk

    def fail_rows(session, model, records, batch=1000):
        if model is FeatureRow:
            raise IntegrityError("controlled failure", {}, Exception("test"))
        return _bulk(session, model, records, batch)

    with (
        patch("sentientalpha.features.storage._bulk", side_effect=fail_rows),
        pytest.raises(IntegrityError),
    ):
        generate(sessions, request())
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(FeatureDataset)) == 0
        assert session.scalar(select(func.count()).select_from(FeatureInput)) == 0
        assert session.scalar(select(func.count()).select_from(FeatureRow)) == 0


def test_api_generation_validation_and_bounds(database):
    url, sessions, _ = database
    seed(sessions)
    body = request().model_dump(mode="json")
    with TestClient(create_app(Settings(database_url=url))) as client:
        definitions = client.get("/api/features/definitions")
        assert definitions.status_code == 200 and len(definitions.json()) == 38
        assert "DefinitionResponse" in client.get("/openapi.json").json()["components"]["schemas"]
        result = client.post("/api/features/generate", json=body)
        assert result.status_code == 201 and not result.json()["reused"]
        assert client.post("/api/features/generate", json=body).json()["reused"]
        for bad in [
            {"features": [{"name": "target"}]},
            {"features": [{"name": "sma", "parameters": {"window": 505}}]},
            {"tickers": ["AAA"] * 51},
            {"price_basis": "adjusted"},
            {"as_of": "2024-01-01T00:00:00"},
            {"end": "2022-01-01"},
        ]:
            response = client.post("/api/features/generate", json={**body, **bad})
            assert response.status_code == 422 and "code" in response.json()["detail"]
        dataset_id = result.json()["dataset"]["id"]
        matrix = dict(dataset_id=dataset_id, start=str(START), end=str(END), limit=2001)
        assert client.post("/api/features/matrix", json=matrix).status_code == 422
        assert (
            client.get(
                "/api/features/AAA",
                params={"dataset_id": "invalid", "start": str(START), "end": str(END)},
            ).status_code
            == 422
        )


def test_historical_output_range_does_not_reseed_recursive_features(database):
    _, sessions, _ = database
    seed(sessions)
    specs = [FeatureSpec(name="ema", parameters={"window": 200}), FeatureSpec(name="rsi")]
    full = generate(sessions, request(features=specs))
    short_request = request(features=specs).model_copy(update={"start": date(2024, 2, 1)})
    short = generate(sessions, short_request)
    with sessions() as session:
        left = {
            r.session_date: r.values
            for r in session.scalars(
                select(FeatureRow).where(
                    FeatureRow.dataset_id == full.dataset.id,
                    FeatureRow.session_date >= short_request.start,
                )
            )
        }
        right = {
            r.session_date: r.values
            for r in session.scalars(
                select(FeatureRow).where(FeatureRow.dataset_id == short.dataset.id)
            )
        }
        assert left == right


def test_output_and_response_budgets_are_enforced(database):
    _, sessions, _ = database
    seed(sessions)
    with (
        patch("sentientalpha.features.engine.MAX_OUTPUT_CELLS", 10),
        pytest.raises(FeatureError, match="cell budget"),
    ):
        generate(sessions, request())
    result = generate(
        sessions,
        request(features=[FeatureSpec(name="sma", parameters={"window": i}) for i in range(1, 65)]),
    )
    with sessions() as session, pytest.raises(FeatureError, match="Reduce row limit"):
        assemble(
            session, MatrixRequest(dataset_id=result.dataset.id, start=START, end=END, limit=2000)
        )


def test_api_rejects_overlapping_generation(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sentientalpha.features.storage import generate as actual_generate

    url, sessions, _ = database
    seed(sessions)
    entered, release = Event(), Event()

    def paused(sessions, request):
        entered.set()
        assert release.wait(10)
        return actual_generate(sessions, request)

    with (
        TestClient(create_app(Settings(database_url=url))) as client,
        patch("sentientalpha.api.features.generate", side_effect=paused),
        ThreadPoolExecutor(2) as workers,
    ):
        first = workers.submit(
            client.post, "/api/features/generate", json=request().model_dump(mode="json")
        )
        try:
            assert entered.wait(10)
            second = client.post("/api/features/generate", json=request().model_dump(mode="json"))
            assert (
                second.status_code == 429 and second.json()["detail"]["code"] == "generation_busy"
            )
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 201

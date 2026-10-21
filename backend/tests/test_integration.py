"""Run against temporary SQLite or an explicitly supplied EMPTY test PostgreSQL database."""

import os
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.contracts import ProviderError
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import IngestionRun, MarketPrice, now
from sentientalpha.database.repository import prices_as_of
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.services.ingestion import IngestionError, ingest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
START, END = date(2024, 1, 2), date(2024, 1, 5)


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SENTIENTALPHA_MODE", "simulation")
    cfg = Config(str(ROOT / "alembic.ini"))
    engine = make_engine(url)
    # Refuse to erase existing user data. CI provides a disposable empty DB.
    if inspect(engine).get_table_names():
        pytest.fail("Integration database must be empty; refusing to modify existing tables")
    command.upgrade(cfg, "head")
    sessions = session_factory(engine)
    try:
        yield url, sessions, cfg
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")
        # Only the known empty Alembic version table is removed; user tables are refused above.
        cleanup = make_engine(url)
        from sqlalchemy import text

        with cleanup.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
        cleanup.dispose()


def test_migration_matches_models(database):
    _, _, cfg = database
    command.check(cfg)


def test_idempotent_and_visible_asof(database):
    _, sessions, _ = database
    before = now() - timedelta(seconds=1)
    first = ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    second = ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    assert first.inserted == 4
    assert second.inserted == 0 and second.deduplicated == 4
    with sessions() as session:
        assert prices_as_of(session, "AAPL", "synthetic", START, END, before) == []
        assert len(prices_as_of(session, "AAPL", "synthetic", START, END, now())) == 4
        assert prices_as_of(session, "AAPL", "alphavantage", START, END, now()) == []
        assert session.scalar(select(func.count()).select_from(MarketPrice)) == 4


def test_revision_preserves_previous_snapshot(database):
    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(1), "AAPL", START, END)
    cutoff = now()
    ingest(sessions, SyntheticProvider(2), "AAPL", START, END)
    with sessions() as session:
        old = prices_as_of(session, "AAPL", "synthetic", START, END, cutoff)
        new = prices_as_of(session, "AAPL", "synthetic", START, END, now())
        assert len(old) == len(new) == 4
        assert old[0].checksum != new[0].checksum
        assert session.scalar(select(func.count()).select_from(MarketPrice)) == 8


def test_timestamp_contract_prevents_ingestion_before_availability(database):
    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    with pytest.raises(IntegrityError), sessions.begin() as session:
        row = session.scalar(select(MarketPrice).limit(1))
        row.ingested_at = datetime(2023, 1, 1, tzinfo=UTC)
    with sessions() as session:
        assert (
            prices_as_of(session, "AAPL", "synthetic", START, END, datetime(2024, 1, 3, tzinfo=UTC))
            == []
        )
        assert len(prices_as_of(session, "AAPL", "synthetic", START, END, now())) == 4


def test_failed_batch_is_atomic_and_audited(database):
    _, sessions, _ = database

    class BadBatch(SyntheticProvider):
        def fetch(self, ticker, start, end):
            rows = super().fetch(ticker, start, end)
            return rows + [replace(rows[0], ticker="MSFT")]

    with pytest.raises(IngestionError) as caught:
        ingest(sessions, BadBatch(), "AAPL", START, END)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketPrice)) == 0
        run = session.get(IngestionRun, caught.value.run_id)
        assert run.status == "failed" and run.inserted == 0
        assert run.error_code == "contract_mismatch"


def test_duplicate_session_rejected(database):
    _, sessions, _ = database

    class Duplicated(SyntheticProvider):
        def fetch(self, ticker, start, end):
            rows = super().fetch(ticker, start, end)
            return rows + [rows[0]]

    with pytest.raises(IngestionError, match="duplicate_session"):
        ingest(sessions, Duplicated(), "AAPL", START, END)


def test_provider_failure_audited_without_secret(database):
    _, sessions, _ = database

    class Failing(SyntheticProvider):
        def fetch(self, ticker, start, end):
            raise ProviderError("provider_limit", "SECRET")

    with pytest.raises(IngestionError) as caught:
        ingest(sessions, Failing(), "AAPL", START, END)
    assert "SECRET" not in str(caught.value)
    with sessions() as session:
        assert session.get(IngestionRun, caught.value.run_id).error_code == "provider_limit"


def test_future_dates_rejected(database):
    _, sessions, _ = database
    with pytest.raises(ValueError, match="completed"):
        ingest(sessions, SyntheticProvider(), "AAPL", START, now().date())


def test_api_end_to_end_and_pagination(database):
    url, _, _ = database
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/health").json()["real_trading_enabled"] is False
        assert client.get("/ready").status_code == 200
        run = client.post(
            "/api/market/ingest",
            json={
                "ticker": "aapl",
                "start": str(START),
                "end": str(END),
            },
        )
        assert run.status_code == 201
        assert run.json()["inserted"] == 4
        assert client.get(f"/api/ingestions/{run.json()['id']}").json()["status"] == "completed"
        params = {"start": str(START), "end": str(END), "limit": 2}
        first = client.get("/api/market/AAPL", params=params)
        assert first.status_code == 200
        body = first.json()
        assert len(body["prices"]) == 2 and body["next_offset"] == 2
        assert body["prices"][0]["is_synthetic"] is True
        second = client.get("/api/market/AAPL", params={**params, "offset": 2}).json()
        assert second["next_offset"] is None
        assert first.json()["prices"][-1]["session_date"] < second["prices"][0]["session_date"]
        assert len(client.get("/api/assets").json()) == 1
        assert client.get("/api/market/MISSING", params=params).status_code == 404
        assert client.get("/api/market/AAPL", params={**params, "limit": 0}).status_code == 422
        assert (
            client.get(
                "/api/market/AAPL", params={**params, "as_of": "2024-01-03T00:00:00"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/market/AAPL", params={**params, "as_of": "2024-01-03T00:00:00Z"}
            ).json()["prices"]
            == []
        )
        assert (
            client.post(
                "/api/market/ingest", json={"ticker": "AAPL", "start": str(END), "end": str(START)}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/market/ingest",
                json={"ticker": "AAPL", "start": str(START), "end": str(END), "live": True},
            ).status_code
            == 422
        )


def test_unmigrated_readiness_is_not_healthy(tmp_path):
    with TestClient(
        create_app(Settings(database_url=f"sqlite:///{tmp_path / 'empty.db'}"))
    ) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503


def test_reverted_correction_is_new_revision(database):
    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(1), "AAPL", START, END)
    ingest(sessions, SyntheticProvider(2), "AAPL", START, END)
    reverted = ingest(sessions, SyntheticProvider(1), "AAPL", START, END)
    assert reverted.inserted == 4
    assert reverted.parameters == {"seed": 1}
    with sessions() as session:
        rows = prices_as_of(session, "AAPL", "synthetic", START, END, now())
        assert rows[0].checksum == SyntheticProvider(1).fetch("AAPL", START, END)[0].checksum
        assert session.scalar(select(func.count()).select_from(MarketPrice)) == 12


def test_database_write_failure_rolls_back_whole_batch(database, monkeypatch):
    from sqlalchemy import event

    _, sessions, _ = database
    count = 0

    def fail_second_insert(mapper, connection, target):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("simulated write failure")

    event.listen(MarketPrice, "after_insert", fail_second_insert)
    try:
        with pytest.raises(IngestionError, match="validation_error") as caught:
            ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    finally:
        event.remove(MarketPrice, "after_insert", fail_second_insert)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketPrice)) == 0
        run = session.get(IngestionRun, caught.value.run_id)
        assert run.status == "failed" and run.inserted == 0


def test_empty_weekend_range_fails_visibly(database):
    _, sessions, _ = database
    with pytest.raises(IngestionError, match="empty_range"):
        ingest(sessions, SyntheticProvider(), "AAPL", date(2024, 1, 6), date(2024, 1, 7))

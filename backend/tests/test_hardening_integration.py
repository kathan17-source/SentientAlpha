"""Actual ORM/API/database regressions; provider payloads are deliberately controlled."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.alphavantage import AlphaVantageProvider
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import Asset, IngestionRun, MarketPrice, now
from sentientalpha.database.repository import prices_as_of
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.services.ingestion import IngestionError, ingest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_integration import END, START
from test_integration import database as database


def test_restart_preserves_prices_and_api_schema(database):
    url, sessions, _ = database
    ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    params = {"start": str(START), "end": str(END)}
    with TestClient(create_app(Settings(database_url=url))) as first:
        before = first.get("/api/market/AAPL", params=params).json()["prices"]
    with TestClient(create_app(Settings(database_url=url))) as second:
        after = second.get("/api/market/AAPL", params=params).json()["prices"]
        spec = second.get("/openapi.json").json()
        assert "PriceResponse" in spec["components"]["schemas"]
        assert "/api/backtest" in spec["paths"]  # M4 now implements this endpoint.
    assert before == after
    assert after[0]["observed_at"] <= after[0]["ingested_at"]
    assert after[0]["adjustment_status"] == "not_supplied"


def test_failed_provider_cannot_fall_back_to_synthetic(database):
    _, sessions, _ = database

    class Broken(AlphaVantageProvider):
        def fetch(self, ticker, start, end):
            raise RuntimeError("private internal detail")

    with pytest.raises(IngestionError) as caught:
        ingest(sessions, Broken("dummy"), "IBM", START, END)
    assert caught.value.code == "internal_error" and "private" not in str(caught.value)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketPrice)) == 0
        assert session.get(IngestionRun, caught.value.run_id).status == "failed"


def test_quality_warning_persisted_and_available_through_api(database):
    url, sessions, _ = database

    class Missing(SyntheticProvider):
        def fetch(self, ticker, start, end):
            rows = super().fetch(ticker, start, end)
            return [rows[0], rows[-1]]

    run = ingest(sessions, Missing(), "AAPL", START, END)
    with TestClient(create_app(Settings(database_url=url))) as client:
        report = client.get(f"/api/ingestions/{run.id}").json()["quality_report"]
        assert report["missing_sessions"] == ["2024-01-03", "2024-01-04"]
        assert report["transformations"] == []


def test_database_rejects_same_asset_source_date_revision(database):
    _, sessions, _ = database
    run = ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    with pytest.raises(IntegrityError), sessions.begin() as session:
        row = session.scalar(select(MarketPrice))
        copied = {
            column.name: getattr(row, column.name) for column in MarketPrice.__table__.columns
        }
        copied["id"] = str(uuid4())
        copied["ingestion_run_id"] = run.id
        session.add(MarketPrice(**copied))


def test_revision_ties_use_sequence_not_random_uuid(database):
    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(1), "AAPL", START, END)
    ingest(sessions, SyntheticProvider(2), "AAPL", START, END)
    tied = now() + timedelta(seconds=1)
    with sessions.begin() as session:
        for row in session.scalars(select(MarketPrice)):
            row.ingested_at = tied
    with sessions() as session:
        rows = prices_as_of(session, "AAPL", "synthetic", START, END, tied)
        assert all(row.revision_no == 2 for row in rows)


def test_source_conflicts_are_recorded_and_not_merged(database):
    _, sessions, _ = database

    class RealSample(SyntheticProvider):
        name = "source_a"

        def fetch(self, ticker, start, end):
            return [
                replace(row, provider=self.name, is_synthetic=False, availability_kind="observed")
                for row in SyntheticProvider(self.seed).fetch(ticker, start, end)
            ]

    class Other(RealSample):
        name = "source_b"

    first = ingest(sessions, RealSample(1), "AAPL", START, END)
    other = ingest(sessions, Other(2), "AAPL", START, END)
    assert first.quality_report["source_conflicts"] == []
    assert len(other.quality_report["source_conflicts"]) == 4
    with sessions() as session:
        rows_a = prices_as_of(session, "AAPL", "source_a", START, END, now())
        rows_b = prices_as_of(session, "AAPL", "source_b", START, END, now())
        assert rows_a[0].close != rows_b[0].close
        assert rows_b[0].quality_flags == ["source_conflict"]


def test_validation_does_not_echo_accidentally_submitted_secrets(database):
    url, _, _ = database
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.post(
            "/api/market/ingest",
            json={
                "ticker": "AAPL",
                "start": str(START),
                "end": str(END),
                "api_key": "DO_NOT_ECHO_THIS",
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_request"
        assert "DO_NOT_ECHO_THIS" not in response.text
        assert client.get("/api/ingestions/not-a-uuid").status_code == 422


def test_empty_known_asset_returns_typed_empty_data(database):
    url, sessions, _ = database
    with sessions.begin() as session:
        session.add(Asset(ticker="AAPL", name="Apple"))
    with TestClient(create_app(Settings(database_url=url))) as client:
        response = client.get("/api/market/AAPL", params={"start": str(START), "end": str(END)})
        assert response.status_code == 200
        assert response.json()["prices"] == [] and response.json()["next_offset"] is None


def test_migration_preserves_legacy_rows_without_inventing_metadata(database):
    _, sessions, cfg = database
    ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    with sessions() as session:
        before = [
            (row.id, row.checksum, row.close)
            for row in session.scalars(select(MarketPrice).order_by(MarketPrice.session_date))
        ]
    sessions.kw["bind"].dispose()
    command.downgrade(cfg, "0001_market_data")
    command.upgrade(cfg, "head")
    with sessions() as session:
        rows = list(session.scalars(select(MarketPrice).order_by(MarketPrice.session_date)))
        assert [(row.id, row.checksum, row.close) for row in rows] == before
        assert all(row.calendar == "unknown" and row.observed_at is None for row in rows)
    command.check(cfg)


def test_sqlite_parallel_first_ingestion_is_idempotent(tmp_path, monkeypatch):
    from alembic.config import Config
    from test_integration import ROOT

    url = f"sqlite:///{tmp_path / 'parallel.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    engine = make_engine(url)
    sessions = session_factory(engine)
    try:
        with ThreadPoolExecutor(max_workers=4) as workers:
            runs = list(
                workers.map(
                    lambda _: ingest(sessions, SyntheticProvider(), "AAPL", START, END), range(4)
                )
            )
        assert sum(run.inserted for run in runs) == 4
        assert sum(run.deduplicated for run in runs) == 12
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(Asset)) == 1
            assert session.scalar(select(func.count()).select_from(MarketPrice)) == 4
    finally:
        engine.dispose()


def test_unavailable_postgres_is_clear_without_private_url():
    import socket

    # Reserve a loopback port without listening, guaranteeing connection refusal for this test.
    with socket.socket() as guard:
        guard.bind(("127.0.0.1", 0))
        port = guard.getsockname()[1]
        settings = Settings(
            database_url=(f"postgresql+psycopg://user:DO_NOT_ECHO_THIS@127.0.0.1:{port}/missing")
        )
        with TestClient(create_app(settings)) as client:
            assert client.get("/health").status_code == 200
            ready = client.get("/ready")
            assert ready.status_code == 503
            assert ready.json()["detail"]["code"] == "database_unavailable"
            assert "DO_NOT_ECHO_THIS" not in ready.text
            assert client.get("/api/assets").status_code == 503


def test_database_error_after_successful_write_rolls_back(database):
    _, sessions, _ = database
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.add(Asset(ticker="AAPL", name="first"))
        session.flush()
        session.add(Asset(ticker="AAPL", name="duplicate"))
        session.flush()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_database_password_with_url_characters_is_preserved(monkeypatch):
    from sqlalchemy.engine import make_url

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user@localhost/research")
    monkeypatch.setenv("DATABASE_PASSWORD", "example@:/%#password")
    settings = Settings.from_env()
    assert make_url(settings.database_url).password == "example@:/%#password"
    assert "example" not in repr(settings)


def test_large_prices_round_trip_exactly(database):
    _, sessions, cfg = database
    value = Decimal("900000000001.12345678")

    class Large(SyntheticProvider):
        def fetch(self, ticker, start, end):
            return [
                replace(row, open=value, close=value, high=value + 1, low=value - 1)
                for row in super().fetch(ticker, start, end)
            ]

    ingest(sessions, Large(), "AAPL", START, END)
    with sessions() as session:
        assert session.scalar(select(MarketPrice)).close == value
    # Downgrading SQLite would reintroduce floating-point loss; refuse instead.
    if sessions.kw["bind"].dialect.name == "sqlite":
        with pytest.raises(ValueError, match="Lossy"):
            command.downgrade(cfg, "0002_data_contract")
    # This is a disposable test database; remove the extreme probe before fixture downgrade.
    from sqlalchemy import delete

    with sessions.begin() as session:
        session.execute(delete(MarketPrice))


def test_maximum_supported_price_is_not_float_rounded_out_of_range(database):
    _, sessions, _ = database
    value = Decimal("999999999999.99999999")

    class Maximum(SyntheticProvider):
        def fetch(self, ticker, start, end):
            return [
                replace(row, open=value, close=value, high=value, low=value)
                for row in super().fetch(ticker, start, end)
            ]

    ingest(sessions, Maximum(), "AAPL", START, END)
    with sessions() as session:
        assert session.scalar(select(MarketPrice)).high == value
    from sqlalchemy import delete

    with sessions.begin() as session:
        session.execute(delete(MarketPrice))

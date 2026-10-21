"""Connection lifecycle; schema is managed exclusively through Alembic."""

import hashlib
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    kwargs = (
        {"check_same_thread": False, "timeout": 10}
        if url.startswith("sqlite:")
        else {
            "connect_timeout": 5,
            "options": "-c timezone=UTC -c statement_timeout=15000 -c lock_timeout=5000",
        }
    )
    engine = create_engine(url, connect_args=kwargs, pool_pre_ping=True, hide_parameters=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection: Any, record: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def serialize_writer(session: Session, ticker: str) -> None:
    """Shared transaction lock used by ingestion and feature snapshot commits."""
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "postgresql":
        key = int.from_bytes(hashlib.sha256(ticker.encode()).digest()[:8], signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

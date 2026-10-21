"""Local boundary and genuine process-death regression tests."""

import os
import subprocess
import sys
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.paper import storage as paper
from sentientalpha.paper.contracts import Advance
from test_integration import database as database
from test_paper_operations import forward_fixture as forward_fixture
from test_paper_operations import initialize


@pytest.mark.parametrize("origin", ["https://evil.invalid", "null", "http://localhost:9999"])
def test_direct_api_origin(database, origin):
    url, _, _ = database
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert (
            client.post("/api/paper/sessions", headers={"origin": origin}, json={}).status_code
            == 403
        )


def test_host_and_chunked_body_boundary(database):
    url, _, _ = database
    with TestClient(create_app(Settings(database_url=url))) as c:
        assert c.get("/health", headers={"host": "evil.invalid"}).status_code == 400
        assert (
            c.post("/api/paper/sessions", headers={"sec-fetch-site": "cross-site"}).status_code
            == 403
        )
        assert c.post("/api/paper/sessions", content=iter([b"x" * 1048576] * 3)).status_code == 413
        assert c.get("/health").headers["x-content-type-options"] == "nosniff"


def test_session_age_is_not_market_staleness(forward_fixture):
    sessions, row, clock = forward_fixture
    for i, day in enumerate(sessions_in_range("XNYS", date(2024, 4, 1), date(2024, 4, 5))):
        clock[0] = session_close("XNYS", day) + timedelta(minutes=3)
        paper.advance(sessions, row.id, Advance(key=f"release-forward-{i}"))
    assert paper.advance(sessions, row.id, Advance(key="release-no-new"))["status"] == "RUNNING"
    clock[0] += timedelta(days=4)
    assert paper.advance(sessions, row.id, Advance(key="release-stale"))["status"] == "PAUSED"


@pytest.mark.parametrize("stage", ["after_fill", "after_commit"])
def test_process_death_around_durable_fill(database, stage):
    url, sessions, _ = database
    if not url.startswith("sqlite:"):
        pytest.skip("Local SQLite process-death test; separate PostgreSQL transaction suite")
    row = initialize(sessions)
    for i in range(5):
        paper.advance(sessions, row.id, Advance(key=f"release-prepare-{i}"))
        with sessions() as s:
            if any(
                a.payload["status"] == "QUEUED"
                for a in paper.artifacts(s, paper.get(s, row.id), "orders")
            ):
                break
    with sessions() as s:
        before = len(paper.artifacts(s, paper.get(s, row.id), "fills"))
    program = """
import os
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.paper.storage import advance
from sentientalpha.paper.contracts import Advance
def crash(stage):
    if stage == os.environ["CRASH_STAGE"]:
        os._exit(73)
advance(
    session_factory(make_engine(os.environ["CRASH_URL"])), os.environ["CRASH_ID"],
    Advance(key="release-crash-key"), fault=crash
)
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        env={
            **os.environ,
            "PYTHONPATH": "backend",
            "CRASH_STAGE": stage,
            "CRASH_URL": url,
            "CRASH_ID": row.id,
        },
        timeout=60,
    )
    assert result.returncode == 73
    with sessions() as s:
        assert len(paper.artifacts(s, paper.get(s, row.id), "fills")) == before + (
            stage == "after_commit"
        )
    response = paper.advance(sessions, row.id, Advance(key="release-crash-key"))
    with sessions() as s:
        state = paper.present(s, paper.get(s, row.id))["portfolio"]
        assert len(paper.artifacts(s, paper.get(s, row.id), "fills")) == before + 1
        assert paper.replay(s, paper.get(s, row.id))["equivalent"]
    assert paper.advance(sessions, row.id, Advance(key="release-crash-key")) == response
    with sessions() as s:
        assert paper.present(s, paper.get(s, row.id))["portfolio"] == state

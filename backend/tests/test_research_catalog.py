"""Actual read-only discovery routes, bounded pages and preserved run sources."""

from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from test_integration import database as database


def test_empty_catalog_and_invalid_parameters(database):
    url, _, _ = database
    with TestClient(create_app(Settings(database_url=url))) as client:
        for kind in [
            "backtest",
            "optimization",
            "ml",
            "strategy",
            "committee",
            "features",
            "sentiment",
        ]:
            response = client.get("/api/research/catalog", params={"kind": kind})
            assert response.status_code == 200
            assert response.json() == {"items": [], "next_offset": None}
        assert client.get("/api/research/catalog?kind=arbitrary_sql").status_code == 422
        assert client.get("/api/research/catalog?kind=ml&limit=1000").status_code == 422
        assert client.get("/api/research/coverage?limit=1000").status_code == 422


def test_catalog_finds_actual_committee_and_linked_ledger_without_raw_sources(database):
    from sentientalpha.committee.storage import execute
    from test_committee_integration import config

    url, sessions, _ = database
    saved = execute(sessions, config(sessions), True)
    with TestClient(create_app(Settings(database_url=url))) as client:
        rows = client.get("/api/research/catalog?kind=committee&limit=1").json()
        assert rows["items"][0]["id"] == saved.id
        assert rows["items"][0]["links"]["backtest"] == "/api/backtest/" + saved.backtest_id
        assert "inputs" not in rows["items"][0] and "artifact" not in rows["items"][0]
        assert client.get(rows["items"][0]["links"]["detail"]).status_code == 200
        assert client.get("/api/research/catalog?kind=features").json()["items"]
        coverage = client.get("/api/research/coverage?limit=1").json()["items"]
        assert len(coverage) == 1 and coverage[0]["provenance"] == "synthetic"
        assert "not full coverage or live quotes" in coverage[0]["limitation"]

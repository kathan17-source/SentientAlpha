"""Self-contained synthetic paper session, measured stages, restart recovery and API evidence.

Never creates forward-looking or genuine market claims. Existing database paths are refused.
"""

import argparse
import json
import os
import resource
import subprocess
import sys
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.paper import storage
from sentientalpha.paper.contracts import Advance, Command, Create
from sentientalpha.services.ingestion import ingest
from sqlalchemy import event


def demo(database: Path, assets: int = 1, observations: int = 5) -> dict[str, Any]:
    if database.exists():
        raise ValueError("Refusing existing database")
    if not 1 <= assets <= 50 or not 1 <= observations <= 20:
        raise ValueError("Bounded demo sizes required")
    database.parent.mkdir(parents=True, exist_ok=True)
    url = "sqlite:///" + str(database.resolve())
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    sessions = session_factory(engine)
    statements = [0]

    @event.listens_for(engine, "before_cursor_execute")
    def counted(*args: Any) -> None:
        statements[0] += 1

    tickers = ["AAPL"] if assets == 1 else [f"DEMO{i:02}" for i in range(assets)]
    begin = perf_counter()
    t = perf_counter()
    for ticker in tickers:
        ingest(sessions, SyntheticProvider(), ticker, date(2024, 1, 2), date(2024, 4, 26))
    ingestion_seconds = perf_counter() - t
    q = Create.model_validate(
        dict(
            key="offline-paper-demo",
            mode="synthetic_demo",
            tickers=tickers,
            provider="synthetic",
            capital="100000",
            history_start="2024-01-02",
            simulation_start="2024-04-01",
            committee_policy={
                "effective_at": "2023-12-31T00:00:00Z",
                "minimum_independent_groups": 1,
            },
            risk_policy={
                "id": "paper-demo-policy",
                "version": "1",
                "effective_at": "2023-12-31T00:00:00Z",
                "constraints": {"cash_maximum": 1, "concentration": 0.4},
                "estimator": {"minimum_observations": 20},
            },
        )
    )
    t = perf_counter()
    row = storage.create(sessions, q)
    creation = perf_counter() - t
    storage.transition(sessions, row.id, "ready", Command(key="demo-ready"))
    storage.transition(sessions, row.id, "start", Command(key="demo-start"))
    t = perf_counter()
    response = storage.advance(
        sessions, row.id, Advance(key="demo-batch", maximum_events=observations)
    )
    advance_seconds = perf_counter() - t
    assert (
        storage.advance(sessions, row.id, Advance(key="demo-batch", maximum_events=observations))
        == response
    )
    storage.transition(sessions, row.id, "pause", Command(key="demo-pause"))
    with sessions() as s:
        before = storage.present(s, storage.get(s, row.id))
    engine.dispose()
    # New connections and no in-memory queue/ledger survive this recovery boundary.
    t = perf_counter()
    engine = make_engine(url)
    sessions = session_factory(engine)
    with sessions() as s:
        recovered = storage.present(s, storage.get(s, row.id))
        replay = storage.replay(s, storage.get(s, row.id))
        assert recovered["portfolio"] == before["portfolio"]
    recovery_seconds = perf_counter() - t
    t = perf_counter()
    child_code = (
        "import json,sys; from sentientalpha.database.session import make_engine,session_factory; "
        "from sentientalpha.paper.storage import get,present,replay; "
        "e=make_engine(sys.argv[1]); s=session_factory(e)(); r=get(s,sys.argv[2]); "
        "print(json.dumps({'portfolio':present(s,r)['portfolio'],'replay':replay(s,r)})); "
        "s.close(); e.dispose()"
    )
    child = subprocess.run(
        [sys.executable, "-c", child_code, url, row.id],
        capture_output=True,
        text=True,
        timeout=90,
        check=True,
    )
    child_state = json.loads(child.stdout)
    assert child_state["portfolio"] == before["portfolio"]
    process_recovery_seconds = perf_counter() - t
    storage.transition(sessions, row.id, "resume", Command(key="demo-resume"))
    with sessions() as s:
        row = storage.get(s, row.id)
        records = [e.payload for e in storage.events(s, row.id) if e.kind == "market"]
        final = storage.present(s, row)
        perf = storage.performance(s, row)
        order_rows = [a.payload for a in storage.artifacts(s, row, "orders")]
        fills = [a.payload for a in storage.artifacts(s, row, "fills")]
    with sessions() as measurement:
        current = storage.get(measurement, row.id)
        storage.append(
            measurement,
            current,
            "demo-measure-commit",
            "commit_measurement",
            {"no_economic_effect": True},
        )
        t = perf_counter()
        measurement.commit()
        commit_seconds = perf_counter() - t
    with TestClient(create_app(Settings(database_url=url))) as c:
        t = perf_counter()
        http = c.get("/api/paper/sessions/" + row.id)
        api_seconds = perf_counter() - t
        assert http.status_code == 200
        assert c.post(
            "/api/paper/sessions/" + row.id + "/reconcile", json={"key": "demo-api-reconcile"}
        ).json()["data"]["equivalent"]
        assert c.get("/api/research/catalog?kind=backtest").json()["items"] == []
        assert c.get("/api/research/catalog?kind=committee").json()["items"] == []
    engine.dispose()
    elapsed = perf_counter() - begin
    return {
        "provenance": "SYNTHETIC_DEMONSTRATION_NOT_FORWARD_TRADING",
        "session_id": row.id,
        "assets": assets,
        "observations": len(records),
        "database": str(database.resolve()),
        "seconds": {
            "market_update": ingestion_seconds,
            "session_creation": creation,
            "batch_advance_including_features_and_commits": advance_seconds,
            "recovery_and_full_replay": recovery_seconds,
            "new_process_recovery_and_replay": process_recovery_seconds,
            "measured_audit_transaction_commit": commit_seconds,
            "api_retrieval": api_seconds,
            "end_to_end": elapsed,
        },
        "stage_seconds": {k: sum(e["timings"][k] for e in records) for k in records[0]["timings"]}
        if records
        else {},
        "sql_statements_before_restart": statements[0],
        "event_throughput_per_second": len(records) / advance_seconds,
        "peak_process_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024 * 1024 if sys.platform == "darwin" else 1024),
        "orders": len(order_rows),
        "fills": len(fills),
        "order_states": {
            status: sum(o["status"] == status for o in order_rows)
            for status in sorted({o["status"] for o in order_rows})
        },
        "duplicate_request_economic_effects": 0,
        "restart_portfolio_equal": True,
        "separate_process_portfolio_equal": True,
        "replay": replay,
        "portfolio": final["portfolio"],
        "metrics": perf["metrics"],
        "simulation_only": True,
        "no_alpha_claim": True,
        "continuous_availability_tested": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--assets", type=int, default=1)
    parser.add_argument("--observations", type=int, default=5)
    args = parser.parse_args()
    result = demo(args.database, args.assets, args.observations)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "session_id",
                    "assets",
                    "observations",
                    "orders",
                    "fills",
                    "seconds",
                    "peak_process_rss_mib",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

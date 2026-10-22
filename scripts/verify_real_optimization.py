"""Read retained genuine IBM data, migrate a COPY, and refuse unavailable historical signals."""

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.database.base import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.optimization.contracts import (
    Estimator,
    Objective,
    OptimizationRequest,
    ResearchRequest,
)
from sentientalpha.optimization.storage import replay, run


def inventory(path):
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            if r[0] != "alembic_version"
        ]
        return {
            t: {
                "rows": db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0],
                "sha256": hashlib.sha256(
                    json.dumps(
                        sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=str), default=str
                    ).encode()
                ).hexdigest(),
            }
            for t in tables
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        raise ValueError("Refuses existing copy path")
    with (
        sqlite3.connect(f"file:{args.source.resolve()}?mode=ro", uri=True) as source,
        sqlite3.connect(args.database) as target,
    ):
        source.backup(target)
    before = inventory(args.database)
    url = f"sqlite:///{args.database.resolve()}"
    os.environ["DATABASE_URL"] = url
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    command.check(cfg)
    after = inventory(args.database)
    assert all(after[t] == v for t, v in before.items())
    engine = make_engine(url)
    sessions = session_factory(engine)
    ds = generate(
        sessions,
        GenerationRequest(
            tickers=["IBM"],
            provider="alphavantage",
            start=date(2026, 5, 21),
            end=date(2026, 10, 13),
            features=[FeatureSpec(name="return")],
        ),
    ).dataset
    decision = now()
    request = OptimizationRequest(
        price_dataset_id=ds.id,
        tickers=["IBM"],
        history_start=date(2026, 5, 21),
        estimation_end=date(2026, 10, 13),
        decision_at=decision,
        source_as_of=now(),
        information_policy="online",
        estimator=Estimator(minimum_observations=30),
        objective=Objective(method="minimum_variance"),
    )
    current = run(sessions, request)
    assert current.status == "completed" and current.result["weights"] == {"IBM": 1.0}
    with sessions() as session:
        assert replay(session, current.id)["equivalent_numerical_results"]
    old = request.model_copy(
        update={
            "estimation_end": date(2026, 6, 30),
            "decision_at": datetime(2026, 7, 1, tzinfo=UTC),
        }
    )
    historical = run(sessions, old)
    assert historical.status == "insufficient_data"
    b = BacktestRequest(
        tickers=["IBM"],
        provider="alphavantage",
        calendar="XNYS",
        start=date(2026, 7, 2),
        end=date(2026, 10, 13),
        source_as_of=request.source_as_of,
        information_policy="online",
    )
    evaluated = run(
        sessions, ResearchRequest(optimization=old, backtest=b, methods=["minimum_variance"])
    )
    assert (
        evaluated.result["methods"][0]["fills"] == 0
        and evaluated.result["methods"][0]["status"] == "unavailable"
    )
    report = {
        "status": "VERIFIED_CURRENT_SINGLE_ASSET_ESTIMATION_AND_HISTORICAL_REFUSAL",
        "provider": "alphavantage",
        "synthetic": False,
        "source": "Retained genuine public IBM sample; no fresh acquisition",
        "price_observations": 100,
        "daily_return_observations": current.result["estimation"]["observations"],
        "current_estimate_run_id": current.id,
        "current_decision_at": decision.isoformat(),
        "data_through": "2026-10-13",
        "weights": current.result["weights"],
        "expected_risk": current.result["risk"],
        "historical_estimation_status": historical.status,
        "historical_comparison_status": evaluated.status,
        "historical_fills": 0,
        "sentiment_coefficient": "unavailable: no complete compatible IBM historical news",
        "warnings": [
            "Single-asset 100% IBM is a mathematical identity, not evidence of"
            " diversification, profitability or optimal real investment.",
            "Raw action-incomplete sample, observed after historical period; "
            "no historical performance claim.",
        ],
        "original_database_read_only": str(args.source.resolve()),
        "migration_old_table_hashes_preserved": True,
        "migration_before": before,
        "migration_after": after,
        "source_database_unchanged": inventory(args.source) == before,
    }
    assert report["source_database_unchanged"]
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()

"""Reproducible committee demo/ablations and measured workloads. No data downloads."""

import argparse
import json
import os
import resource
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.storage import persist
from sentientalpha.committee.contracts import Policy
from sentientalpha.committee.engine import backtest_config
from sentientalpha.committee.requests import Request
from sentientalpha.committee.storage import decisions, execute, replay, restore
from sentientalpha.config import Settings
from sentientalpha.database.base import now
from sentientalpha.database.committee_models import CommitteeRun
from sentientalpha.database.feature_models import FeatureDataset
from sentientalpha.database.ml_models import MLModel
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.database.strategy_models import DiscoveryRun, StrategyCandidate
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.optimization.contracts import Estimator
from sentientalpha.strategies.contracts import Request as DiscoveryRequest
from sentientalpha.strategies.evaluation import snapshot
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--assets", type=int, choices=[1, 5, 20, 50], default=1)
    parser.add_argument("--genuine", action="store_true")
    args = parser.parse_args()
    if args.database.exists():
        raise SystemExit("Refusing to overwrite an existing audit database")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    prep = perf_counter()
    shutil.copy2(args.source, args.database)
    url = "sqlite:///" + str(args.database.resolve())
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    sessions = session_factory(engine)
    with sessions() as session:
        if args.genuine:
            discovery = session.scalar(
                select(DiscoveryRun).where(DiscoveryRun.idempotency_key.like("%"))
            )
            while (
                discovery
                and not discovery.result.get("prepared", discovery.result)["folds"][0]["selected"]
            ):
                raise RuntimeError("First original discovery has no locked selection")
            prepared = discovery.result.get("prepared", discovery.result)
            selected = prepared["folds"][0]["selected"]
            candidate = session.scalar(
                select(StrategyCandidate).where(
                    StrategyCandidate.discovery_id == discovery.id,
                    StrategyCandidate.rule_hash == selected,
                )
            )
            dataset = session.get(FeatureDataset, discovery.manifest["configuration"]["dataset_id"])
            model = next(
                m
                for m in session.scalars(select(MLModel))
                if m.payload["selected"]["model"] == "logistic"
            )
            tickers = ["IBM"]
            start, end = date(2026, 9, 9), date(2026, 10, 12)
        else:
            dataset = max(
                session.scalars(
                    select(FeatureDataset).where(FeatureDataset.provider == "synthetic")
                ),
                key=lambda d: len(d.columns),
            )
            tickers = dataset.configuration["tickers"][: args.assets]
            if len(tickers) != args.assets:
                raise RuntimeError("Source has too few assets")
            start = end = date(2024, 10, 31)
            model = candidate = None
        cfg = Request(
            dataset_id=dataset.id,
            tickers=tickers,
            history_start=dataset.start_date,
            start=start,
            end=end,
            source_as_of=now(),
            information_policy="retrospective",
            model_id=model.id if model else None,
            strategy_id=candidate.id if candidate else None,
            experimental_quant=True,
            policy=Policy(
                effective_at=datetime(2022, 1, 1, tzinfo=UTC), minimum_independent_groups=1
            ),
            estimator=Estimator(minimum_observations=20 if args.genuine else 60),
            idempotency_key="committee-full",
        )
    feature_config = {k: v for k, v in dataset.configuration.items() if k != "resolved_features"}
    feature_config["features"] = [
        FeatureSpec(name=d["name"], parameters=d["parameters"])
        for d in dataset.configuration["resolved_features"]
    ]
    generated = generate(
        sessions,
        GenerationRequest.model_validate({**feature_config, "as_of": dataset.source_as_of}),
    )
    assert generated.dataset.source_hash == dataset.source_hash
    feature_generation = {
        "dataset_id": generated.dataset.id,
        "reused_immutable_cache": generated.reused,
        "source_hash": generated.dataset.source_hash,
        "row_count": generated.dataset.row_count,
    }
    preparation = perf_counter() - prep
    configurations = {"full": cfg.agents}
    if args.genuine:
        configurations = {
            "technical": ["technical"],
            "quant": ["quant"],
            "strategy": ["strategy"],
            "technical_quant": ["technical", "quant"],
            "technical_strategy": ["technical", "strategy"],
            "full": cfg.agents,
            "m5_equal_weight_baseline": cfg.agents,
        }
    report = {
        "provenance": "genuine_retrospective_IBM"
        if args.genuine
        else "synthetic_infrastructure_workload",
        "source": str(args.source),
        "assets": args.assets,
        "start": str(start),
        "end": str(end),
        "preparation_seconds": preparation,
        "feature_generation": feature_generation,
        "configuration_locked_before_execution": True,
        "model_choice": "Predeclared logistic; simplest nonbaseline, not chosen by M8 results"
        if args.genuine
        else None,
        "limitations": [
            "No fresh holdout: previously inspected research period",
            "No empirical alpha claim",
            "No genuine PIT fundamental/macro/sentiment coverage",
            "Quant-only exposure capped at 10% by fixed experimental policy",
        ],
        "runs": {},
        "baselines": {},
        "model_loading_inference": "Retrieval only; excludes fitting/inference/transformer loads",
    }
    for name, agents in configurations.items():
        request = Request.model_validate(
            {
                **cfg.model_dump(),
                "agents": agents,
                "idempotency_key": "committee-" + name,
                "allocation_policy": "m5_equal_weight_baseline"
                if name == "m5_equal_weight_baseline"
                else "committee",
            }
        )
        t = perf_counter()
        saved = execute(sessions, request, execution=args.genuine)
        elapsed = perf_counter() - t
        with sessions() as session:
            t = perf_counter()
            rep = replay(session, saved.id)
            replay_seconds = perf_counter() - t
            trace = decisions(session, saved.id)
            risk_counts = {}
            for d in trace:
                key = d["allocation"]["action"]
                risk_counts[key] = risk_counts.get(key, 0) + 1
        report["runs"][name] = {
            "run_id": saved.id,
            "backtest_id": saved.backtest_id,
            "result": saved.result,
            "latency_seconds": elapsed,
            "timings_seconds": saved.manifest["timings_seconds"],
            "persistence_work_seconds": saved.manifest["persistence_work_seconds"],
            "persistence_seconds": saved.manifest["persistence_seconds"],
            "replay_seconds": replay_seconds,
            "replay": rep,
            "risk_actions": risk_counts,
            "first_decision": trace[0] if trace else None,
        }
    if args.genuine:
        with sessions() as session:
            parent = session.get(CommitteeRun, report["runs"]["full"]["run_id"])
            inputs, meta = restore(session, parent.inputs)
        config = backtest_config(cfg, inputs)
        snap = snapshot(
            DiscoveryRequest.model_validate(meta["source_configuration"]), inputs, start, end
        )
        for name in ["buy_hold", "equal_weight"]:
            baseline = config.model_copy(
                update={
                    "strategy": config.strategy.model_copy(
                        update={
                            "name": name,
                            "rebalance": "daily" if name == "equal_weight" else "monthly",
                        }
                    )
                }
            )
            result = simulate(baseline, snap)
            saved = persist(
                sessions,
                baseline,
                snap,
                result,
                {"committee_comparison": "fixed matched dates/costs/universe"},
            )
            report["baselines"][name] = {"run_id": saved.id, "metrics": result["metrics"]}
    with TestClient(create_app(Settings(database_url=url))) as client:
        run_id = report["runs"]["full"]["run_id"]
        smoke = {}
        for suffix in [
            "",
            "/decisions",
            "/agents",
            "/evidence",
            "/allocation",
            "/risk-review",
            "/execution",
        ]:
            response = client.get("/api/investment-committee/" + run_id + suffix)
            smoke[suffix or "run"] = response.status_code
            assert response.status_code == 200, response.text
        response = client.post("/api/investment-committee/" + run_id + "/replay")
        assert response.status_code == 200 and response.json()["equivalent_ledger"]
        smoke["replay"] = response.json()
        report["api_smoke"] = smoke
    # macOS ru_maxrss is bytes. This includes data loading, SciPy, API and replay in this process.
    report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    engine.dispose()
    print(
        json.dumps(
            {
                "assets": args.assets,
                "genuine": args.genuine,
                "peak_rss_mib": report["peak_rss_mib"],
                "report": str(args.report),
            }
        )
    )


if __name__ == "__main__":
    main()

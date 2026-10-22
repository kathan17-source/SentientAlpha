"""Fixed M9 comparisons on retained inputs; never downloads data or tunes on results."""

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
from sentientalpha.committee.contracts import Policy as CommitteePolicy
from sentientalpha.committee.requests import Request
from sentientalpha.committee.storage import execute, replay
from sentientalpha.config import Settings
from sentientalpha.database.base import now
from sentientalpha.database.feature_models import FeatureDataset
from sentientalpha.database.risk_models import RiskAssessment
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.optimization.contracts import Constraints, Estimator
from sentientalpha.risk.contracts import Policy, Scenario
from sentientalpha.risk.storage import replay as risk_replay
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--genuine", action="store_true")
    parser.add_argument("--assets", type=int, choices=[1, 5, 20, 50], default=1)
    args = parser.parse_args()
    if args.database.exists():
        raise SystemExit("Refusing to overwrite audit database")
    started = perf_counter()
    shutil.copy2(args.source, args.database)
    url = "sqlite:///" + str(args.database.resolve())
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    sessions = session_factory(engine)
    effective = datetime(2022, 1, 1, tzinfo=UTC)
    with sessions() as s:
        if args.genuine:
            dataset = s.get(FeatureDataset, "dc18ca61-1136-401a-aa81-538e527d6e54")
            tickers = ["IBM"]
            start, end = date(2026, 9, 9), date(2026, 10, 12)
            from sentientalpha.database.strategy_models import StrategyCandidate

            candidate = s.scalar(
                select(StrategyCandidate).where(
                    StrategyCandidate.discovery_id == "9b3203e4-55f9-4ca5-99cd-decb760acc14",
                    StrategyCandidate.rule_hash
                    == "cfad21990a4fc98f850f1796a5f9ddff74832481121694a08b8164fae9ae0d8b",
                )
            )
            extra = {
                "model_id": "0c585707-d36b-4453-9096-e0c664242e83",
                "strategy_id": candidate.id,
            }
        else:
            dataset = max(
                s.scalars(select(FeatureDataset).where(FeatureDataset.provider == "synthetic")),
                key=lambda d: len(d.columns),
            )
            tickers = dataset.configuration["tickers"][: args.assets]
            start = end = date(2024, 10, 31)
            extra = {}
        cfg = Request(
            dataset_id=dataset.id,
            tickers=tickers,
            history_start=dataset.start_date,
            start=start,
            end=end,
            source_as_of=now(),
            information_policy="retrospective",
            experimental_quant=True,
            policy=CommitteePolicy(effective_at=effective, minimum_independent_groups=1),
            estimator=Estimator(minimum_observations=20 if args.genuine else 60),
            idempotency_key="m9-baseline",
            **extra,
        )

    def p(name, **updates):
        return Policy(
            id="m9-risk-" + name,
            effective_at=effective,
            adjustment="scale_to_cash",
            estimator=Estimator(minimum_observations=20 if args.genuine else 60),
            **updates,
        )

    profiles = {"m8_baseline": None, "guard_only": p("guard")}
    if args.genuine:
        profiles.update(
            {
                "concentration": p(
                    "concentration", constraints=Constraints(cash_maximum=1, concentration=0.5)
                ),
                "volatility": p(
                    "volatility", constraints=Constraints(cash_maximum=1, volatility_maximum=0.25)
                ),
                "drawdown": p("drawdown", drawdown_maximum=0.03, drawdown_mode="cash"),
                "var": p("var", var_maximum=0.025),
                "cvar": p("cvar", cvar_maximum=0.035),
                "combined": p(
                    "combined",
                    constraints=Constraints(
                        cash_maximum=1,
                        concentration=0.5,
                        volatility_maximum=0.30,
                        turnover_maximum=0.4,
                    ),
                    drawdown_maximum=0.04,
                    drawdown_mode="cash",
                    participation_maximum=0.01,
                    stress_loss_maximum=0.05,
                    scenarios=[
                        Scenario(
                            id="broad-down10", version="1", effective_at=effective, broad_shock=-0.1
                        )
                    ],
                ),
            }
        )
    report = {
        "provenance": "genuine_retrospective_IBM" if args.genuine else "synthetic_infrastructure",
        "assets": len(tickers),
        "start": str(start),
        "end": str(end),
        "preparation_seconds": perf_counter() - started,
        "fixed_profiles": True,
        "no_holdout_tuning": True,
        "runs": {},
    }
    for name, risk_policy in profiles.items():
        q = Request.model_validate(
            {**cfg.model_dump(), "risk_policy": risk_policy, "idempotency_key": "m9-risk-" + name}
        )
        t = perf_counter()
        saved = execute(sessions, q, execution=args.genuine)
        elapsed = perf_counter() - t
        with sessions() as s:
            t = perf_counter()
            rep = replay(s, saved.id)
            replay_time = perf_counter() - t
            rows = list(
                s.scalars(
                    select(RiskAssessment)
                    .where(RiskAssessment.committee_id == saved.id)
                    .order_by(RiskAssessment.sequence)
                )
            )
            statuses = {}
            for row in rows:
                statuses[row.status] = statuses.get(row.status, 0) + 1
            risk_rep, risk_time = None, None
            if rows:
                t = perf_counter()
                risk_rep = risk_replay(s, rows[0].id)
                risk_time = perf_counter() - t
        report["runs"][name] = {
            "run_id": saved.id,
            "backtest_id": saved.backtest_id,
            "result": saved.result,
            "seconds": elapsed,
            "replay_seconds": replay_time,
            "replay": rep,
            "manifest": saved.manifest,
            "risk_status_counts": statuses,
            "risk_replay": risk_rep,
            "risk_replay_seconds": risk_time,
            "first_risk_id": rows[0].id if rows else None,
        }
        print(
            json.dumps({"profile": name, "seconds": elapsed, "status_counts": statuses}), flush=True
        )
    if args.genuine:
        from sentientalpha.backtesting.engine import simulate
        from sentientalpha.backtesting.storage import persist
        from sentientalpha.committee.engine import backtest_config
        from sentientalpha.committee.storage import restore
        from sentientalpha.database.committee_models import CommitteeRun
        from sentientalpha.strategies.contracts import Request as DiscoveryRequest
        from sentientalpha.strategies.evaluation import snapshot

        with sessions() as session:
            parent = session.get(CommitteeRun, report["runs"]["m8_baseline"]["run_id"])
            inputs, meta = restore(session, parent.inputs)
        config = backtest_config(cfg, inputs)
        snap = snapshot(
            DiscoveryRequest.model_validate(meta["source_configuration"]), inputs, start, end
        )
        report["baselines"] = {}
        for name in ["buy_hold", "equal_weight"]:
            baseline = config.model_copy(
                update={
                    "strategy": config.strategy.model_copy(
                        update={
                            "name": name,
                            "rebalance": "monthly" if name == "buy_hold" else "daily",
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
                {"m9_comparison": "fixed matched costs/dates/universe"},
            )
            report["baselines"][name] = {"run_id": saved.id, "metrics": result["metrics"]}
    with TestClient(create_app(Settings(database_url=url))) as client:
        smoke = {}
        rid = report["runs"]["guard_only"]["first_risk_id"]
        for path in [
            "/api/risk",
            "/api/risk/policies",
            "/api/risk/history",
            "/api/risk/alerts",
            "/api/risk/decisions/" + rid,
        ]:
            response = client.get(path)
            assert response.status_code == 200, response.text
            smoke[path] = response.status_code
        report["api"] = smoke
    report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    engine.dispose()


if __name__ == "__main__":
    main()

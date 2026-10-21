"""Create a new deterministic SYNTHETIC local dashboard database through existing engines."""

import argparse
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.evaluation import Split
from sentientalpha.backtesting.storage import run_backtest
from sentientalpha.committee.contracts import Policy as CommitteePolicy
from sentientalpha.committee.requests import Request as CommitteeRequest
from sentientalpha.committee.storage import execute
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.base import now
from sentientalpha.database.ml_models import MLModel
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.ml.contracts import Candidate, ResearchRequest, Window
from sentientalpha.ml.storage import run as train
from sentientalpha.optimization.contracts import (
    Constraints,
    Estimator,
    FrontierRequest,
    OptimizationRequest,
)
from sentientalpha.optimization.storage import run as optimize
from sentientalpha.risk.contracts import Policy, Scenario
from sentientalpha.services.ingestion import ingest
from sentientalpha.strategies.contracts import Axis, Space
from sentientalpha.strategies.contracts import Request as DiscoveryRequest
from sentientalpha.strategies.storage import discover
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        raise SystemExit("Refusing to overwrite an existing database")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    url = "sqlite:///" + str(args.database.resolve())
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    sessions = session_factory(make_engine(url))
    tickers = ["DEMOA", "DEMOB"]
    first, last = date(2023, 1, 2), date(2024, 6, 28)
    for t in tickers:
        ingest(sessions, SyntheticProvider(seed=42), t, first, last)
    dataset = generate(
        sessions,
        GenerationRequest(
            tickers=tickers,
            provider="synthetic",
            start=first,
            end=last,
            features=[
                FeatureSpec(name="return"),
                FeatureSpec(name="sma", parameters={"window": 5}),
            ],
        ),
    ).dataset
    cut = now()
    ml = train(
        sessions,
        ResearchRequest(
            dataset_id=dataset.id,
            tickers=tickers,
            columns=dataset.columns,
            source_as_of=cut,
            information_policy="research_replay",
            candidates=[Candidate(model="logistic")],
            windows=[
                Window(
                    train_start=first,
                    train_end=date(2023, 6, 30),
                    validation_start=date(2023, 7, 3),
                    validation_end=date(2023, 9, 29),
                    calibration_start=date(2023, 10, 2),
                    calibration_end=date(2023, 12, 29),
                    test_start=date(2024, 1, 1),
                    test_end=date(2024, 3, 29),
                )
            ],
        ),
    )
    search = discover(
        sessions,
        DiscoveryRequest(
            dataset_id=dataset.id,
            tickers=tickers,
            source_as_of=cut,
            information_policy="research_replay",
            windows=[
                Split(
                    train_start=first,
                    train_end=date(2023, 12, 29),
                    validation_start=date(2024, 1, 1),
                    validation_end=date(2024, 3, 29),
                    test_start=date(2024, 4, 1),
                    test_end=last,
                )
            ],
            space=Space(
                axes=[Axis(feature="return", thresholds=[-0.01, 0, 0.01])], maximum_conditions=1
            ),
            candidates=6,
            robustness=False,
            holdout_history="previously_inspected",
            idempotency_key="synthetic-dashboard-search",
        ),
    )
    static = OptimizationRequest(
        price_dataset_id=dataset.id,
        tickers=tickers,
        history_start=first,
        estimation_end=last,
        decision_at=datetime(2024, 6, 28, 23, 59, 59, tzinfo=UTC),
        source_as_of=cut,
        information_policy="research_replay",
        constraints=Constraints(cash_maximum=1, concentration=0.6),
    )
    opt = optimize(sessions, static)
    frontier = optimize(
        sessions, FrontierRequest(optimization=static, risk_aversions=[1, 3, 10, 30])
    )
    backtest = run_backtest(
        sessions,
        BacktestRequest(
            tickers=tickers,
            start=date(2024, 4, 1),
            end=last,
            source_as_of=cut,
            information_policy="research_replay",
            provider="synthetic",
            benchmarks=["buy_hold", "equal_weight"],
        ),
    )
    with sessions() as session:
        model = session.scalar(select(MLModel).where(MLModel.experiment_id == ml.id))
    effective = datetime(2023, 1, 1, tzinfo=UTC)
    committee = execute(
        sessions,
        CommitteeRequest(
            dataset_id=dataset.id,
            tickers=tickers,
            history_start=first,
            start=date(2024, 4, 1),
            end=last,
            source_as_of=now(),
            information_policy="research_replay",
            model_id=model.id if model else None,
            experimental_quant=True,
            policy=CommitteePolicy(effective_at=effective, minimum_independent_groups=1),
            risk_policy=Policy(
                id="synthetic-dashboard-risk",
                effective_at=effective,
                constraints=Constraints(cash_maximum=1, concentration=0.35),
                estimator=Estimator(minimum_observations=20),
                adjustment="scale_to_cash",
                scenarios=[
                    Scenario(
                        id="hypothetical-down10",
                        version="1",
                        effective_at=effective,
                        broad_shock=-0.1,
                    )
                ],
            ),
            idempotency_key="synthetic-dashboard-committee",
        ),
        True,
    )
    report = {
        "provenance": "ENTIRELY_SYNTHETIC_DEMONSTRATION",
        "no_alpha_claim": True,
        "dataset_id": dataset.id,
        "ml_id": ml.id,
        "discovery_id": search.id,
        "optimization_id": opt.id,
        "frontier_id": frontier.id,
        "backtest_id": backtest.id,
        "committee_id": committee.id,
        "sentiment": "No news or FinBERT inference generated; no fabricated sentiment",
        "database": str(args.database.resolve()),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

"""Synthetic sentiment-variable engineering and ACTUAL sklearn forecast strategy integration."""

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
from alembic import command
from alembic.config import Config
from sentientalpha.backtesting.evaluation import Split
from sentientalpha.database.base import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.ml.storage import run as train_ml
from sentientalpha.strategies.contracts import Axis, Request, Space
from sentientalpha.strategies.inputs import Signal
from sentientalpha.strategies.storage import discover, evaluate_locked, replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        raise ValueError("Refuses to replace a database")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "backend/tests"))
    from test_ml_integration import seed as ml_seed
    from test_strategy_research import fixture

    url = f"sqlite:///{args.database.resolve()}"
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    engine = make_engine(url)
    sessions = session_factory(engine)
    cfg, inputs = fixture(candidates=20)
    rng = np.random.default_rng(73)
    signals = {}
    for key, cells in inputs.signals.items():
        ready = cells["return"].ready
        signals[key] = {
            **cells,
            "sent_mean": Signal(
                float(rng.normal()), ready, "EXPLICIT synthetic statistical variable, not NLP/news"
            ),
        }
    synthetic = replace(
        inputs,
        signals=signals,
        available=inputs.available | frozenset(["sent_mean"]),
        metadata={
            **inputs.metadata,
            "sentiment": (
                "Synthetic generated variable, never genuine news coverage or NLP evidence"
            ),
        },
    )
    cfg = cfg.model_copy(
        update={
            "space": Space(
                axes=[
                    Axis(feature="sent_mean", thresholds=[-0.3, 0, 0.3]),
                    Axis(feature="return", thresholds=[-0.003, 0, 0.003]),
                ],
                holdings=[1, 3, 5],
            ),
            "idempotency_key": "synthetic_sentiment_discovery",
            "sentiment_provenance": "synthetic_fixture",
        }
    )
    sent = discover(sessions, cfg, synthetic)
    if sent.status == "ready_for_test":
        sent = evaluate_locked(sessions, sent.id)
    with sessions() as session:
        sent_replay = replay(session, sent.id)
    ml_cfg = ml_seed(sessions)
    trained = train_ml(sessions, ml_cfg)
    model_ids = list(trained.manifest["model_ids"].values())
    cfg = Request.model_validate(
        {
            **cfg.model_dump(),
            "dataset_id": ml_cfg.dataset_id,
            "tickers": ml_cfg.tickers,
            "ml_model_ids": model_ids,
            "space": Space(
                axes=[
                    Axis(feature="ml_probability", thresholds=[0.4, 0.5, 0.6]),
                    Axis(feature="return", thresholds=[0]),
                ],
                holdings=[1, 3, 5],
            ),
            "source_as_of": now(),
            "holdout_history": "previously_inspected",
            "idempotency_key": "actual_sklearn_signal_discovery",
            "windows": [
                Split(
                    train_start=date(2023, 5, 22),
                    train_end=date(2023, 7, 7),
                    validation_start=date(2023, 7, 10),
                    validation_end=date(2023, 8, 18),
                    test_start=date(2023, 8, 21),
                    test_end=date(2023, 10, 6),
                )
            ],
        }
    )
    ml = discover(sessions, cfg)
    if ml.status == "ready_for_test":
        ml = evaluate_locked(sessions, ml.id)
    with sessions() as session:
        ml_replay = replay(session, ml.id)
    report = {
        "sentiment": {
            "id": sent.id,
            "status": sent.status,
            "replay": sent_replay,
            "provenance": "SYNTHETIC statistical-variable fixture, not actual headlines or FinBERT",
            "evaluation": sent.result.get("evaluation"),
        },
        "ml": {
            "id": ml.id,
            "status": ml.status,
            "training_experiment": trained.id,
            "model_ids": model_ids,
            "replay": ml_replay,
            "provenance": (
                "Actual sklearn fit on SYNTHETIC prices; historical research "
                "forecasts, not live issued"
            ),
            "evaluation": ml.result.get("evaluation"),
        },
        "genuine_sentiment_alpha": "UNVERIFIED",
        "alpha_established": False,
    }
    assert all(sent_replay.values()) and all(ml_replay.values())
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"sentiment_status": sent.status, "actual_ml_status": ml.status, "all_replays": True}
        )
    )
    engine.dispose()


if __name__ == "__main__":
    main()

"""Isolated train+preprocess and validation-selection timings on frozen research inputs."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from sentientalpha.database.ml_models import MLExperiment
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.ml.contracts import ResearchRequest
from sentientalpha.ml.dataset import thaw
from sentientalpha.ml.models import infer, train
from sentientalpha.ml.research import matrix, partition, score
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = make_engine(f"sqlite:///{args.database.resolve()}")
    with session_factory(engine)() as session:
        records = list(session.scalars(select(MLExperiment)))
    results = []
    for record in records:
        cfg = ResearchRequest.model_validate(record.manifest["configuration"])
        if cfg.candidates[0].model not in {"logistic", "forest_classifier", "boost_classifier"}:
            continue
        ds = thaw(record.inputs)
        groups = partition(ds, cfg, cfg.windows[0])[0]
        x, xv = matrix(groups["train"]), matrix(groups["validation"])
        y = np.array([r.target for r in groups["train"]])
        yv = np.array([r.target for r in groups["validation"]])
        clock = perf_counter()
        candidates = []
        for c in cfg.candidates:
            begin = perf_counter()
            model = train(c, x, y, cfg)
            fit_seconds = perf_counter() - begin
            begin = perf_counter()
            loss = score(yv, infer(model, xv, cfg.columns), cfg.target.task)
            validation_seconds = perf_counter() - begin
            candidates.append(
                {
                    "configuration": c.model_dump(),
                    "preprocess_and_training_seconds": fit_seconds,
                    "validation_inference_scoring_seconds": validation_seconds,
                    "validation_loss": loss,
                }
            )
        results.append(
            {
                "family": cfg.candidates[0].model,
                "selection_workload_seconds": perf_counter() - clock,
                "train_rows": len(x),
                "validation_rows": len(xv),
                "candidates": candidates,
            }
        )
    args.output.write_text(
        json.dumps(
            {
                "database": str(args.database),
                "scope": (
                    "First fold, warm sequential local timings; not unbiased algorithm comparison"
                ),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    engine.dispose()


if __name__ == "__main__":
    main()

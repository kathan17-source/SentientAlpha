"""Explicit SYNTHETIC statistical fixtures, not historical headlines or FinBERT evidence."""

import argparse
import json
import sys
from pathlib import Path

from sentientalpha.backtesting.storage import build_id, digest
from sentientalpha.database.base import now
from sentientalpha.ml.dataset import freeze
from sentientalpha.ml.research import ablations, evaluate
from sentientalpha.ml.storage import dependencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/tests"))
    from test_ml_research import fixture

    cfg, ds = fixture()
    results = ablations(cfg, ds)
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    result, frozen = evaluate(cfg, ds), freeze(ds)
    manifest = {
        "configuration": cfg.model_dump(mode="json"),
        "configuration_hash": digest(cfg.model_dump(mode="json")),
        "build_id": build_id(),
        "dependencies": dependencies(),
        "input_hash": digest(frozen),
        "result_hash": digest(result),
        "created_at": now().isoformat(),
        "prediction_origin": "historical_walk_forward",
        "ledger_links": [],
        "provenance": "SYNTHETIC statistical variables; never genuine news sentiment",
    }
    args.export.write_text(
        json.dumps({"manifest": manifest, "inputs": frozen, "result": result}, allow_nan=False)
        + "\n"
    )
    print(
        json.dumps(
            {
                "status": results["status"],
                "common_rows": results["common_rows"],
                "sentiment_alpha": "UNVERIFIED",
            }
        )
    )


if __name__ == "__main__":
    main()

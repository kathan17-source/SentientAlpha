"""Replay a local numeric ML experiment export; never deserialize Python objects."""

import argparse
import json
from pathlib import Path

from sentientalpha.backtesting.storage import build_id, digest
from sentientalpha.ml.contracts import ResearchRequest
from sentientalpha.ml.dataset import thaw
from sentientalpha.ml.research import evaluate
from sentientalpha.ml.storage import dependencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    if args.export.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Export exceeds local replay budget")
    payload = json.loads(args.export.read_text())
    m = payload["manifest"]
    if (
        m["build_id"] != build_id()
        or m["dependencies"] != dependencies()
        or digest(payload["inputs"]) != m["input_hash"]
        or digest(m["configuration"]) != m["configuration_hash"]
        or digest(payload["result"]) != m["result_hash"]
    ):
        raise ValueError("Export build, dependencies, configuration, inputs or result differ")
    if m.get("ledger_links"):
        raise ValueError("Replay linked ledgers through their original ML experiment database")
    result = evaluate(ResearchRequest.model_validate(m["configuration"]), thaw(payload["inputs"]))
    if digest(result) != m["result_hash"]:
        raise ValueError("Numerical replay differs")
    print(json.dumps({"equivalent_numerical_results": True, "origin": m["prediction_origin"]}))


if __name__ == "__main__":
    main()

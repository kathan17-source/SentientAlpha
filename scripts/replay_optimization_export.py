"""Replay a standalone allocation/frontier export without a database or provider access."""

import argparse
import json
from importlib.metadata import version
from pathlib import Path

from sentientalpha.backtesting.storage import build_id, digest
from sentientalpha.optimization.contracts import FrontierRequest, OptimizationRequest
from sentientalpha.optimization.inputs import thaw
from sentientalpha.optimization.storage import execute, numerical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    saved = json.loads(args.export.read_text())
    manifest = saved["manifest"]
    if manifest["backtest_links"]:
        raise ValueError(
            "Linked execution ledgers require database replay; this helper is standalone only"
        )
    if (
        build_id() != manifest["build_id"]
        or digest(saved["inputs"]) != manifest["input_hash"]
        or digest(manifest["configuration"]) != manifest["configuration_hash"]
        or any(version(n) != v for n, v in manifest["dependencies"].items())
    ):
        raise ValueError("Export inputs/configuration/build/dependencies differ")
    if saved["kind"] == "optimization":
        request = OptimizationRequest.model_validate(manifest["configuration"])
    elif saved["kind"] == "frontier":
        request = FrontierRequest.model_validate(manifest["configuration"])
    else:
        raise ValueError("Unsupported standalone export kind")
    _, result = execute(request, thaw(saved["inputs"]))
    result["backtest_links"] = []
    equivalent = digest(numerical(result)) == manifest["result_hash"]
    if not equivalent:
        raise ValueError("Reproduced numerical result differs")
    print(
        json.dumps(
            {
                "run_id": manifest["run_id"],
                "kind": saved["kind"],
                "status": result["status"],
                "equivalent_numerical_results": True,
                "weights": result.get("weights"),
                "provenance": saved["provenance"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

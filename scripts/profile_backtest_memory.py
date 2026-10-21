"""Read a saved run and profile Python allocations in frozen-input simulation; no writes."""

import argparse
import json
import tracemalloc
from pathlib import Path

from sentientalpha.backtesting.contracts import Request
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.storage import decode, get_run
from sentientalpha.database.session import make_engine, session_factory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = make_engine(f"sqlite:///{args.database.resolve()}")
    sessions = session_factory(engine)
    tracemalloc.start()
    with sessions() as session:
        run = get_run(session, args.run_id)
        request = Request.model_validate(run.manifest["configuration"])
        snapshot = decode(run.snapshot)
    source_current, source_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    result = simulate(request, snapshot)
    current, peak = tracemalloc.get_traced_memory()
    top = [
        {"location": str(stat.traceback), "bytes": stat.size, "allocations": stat.count}
        for stat in tracemalloc.take_snapshot().statistics("lineno")[:12]
    ]
    report = {
        "scope": (
            "Tracked Python allocations; excludes interpreter/import/native memory; not process RSS"
        ),
        "source_current_mib": source_current / 2**20,
        "source_peak_mib": source_peak / 2**20,
        "simulation_current_mib": current / 2**20,
        "simulation_peak_mib": peak / 2**20,
        "incremental_simulation_peak_mib": (peak - source_current) / 2**20,
        "input_bars": len(snapshot.bars),
        "orders": len(result["orders"]),
        "equity_rows": len(result["equity"]),
        "top_allocations": top,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    tracemalloc.stop()
    engine.dispose()


if __name__ == "__main__":
    main()

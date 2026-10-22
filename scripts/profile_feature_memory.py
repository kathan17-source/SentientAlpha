"""Read-only M2 allocation profiling; input is an existing synthetic benchmark database."""

import argparse
import json
import tracemalloc
from datetime import date
from pathlib import Path

from sentientalpha.database.models import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import GenerationRequest
from sentientalpha.features.engine import calculate
from sentientalpha.features.registry import Registry
from sentientalpha.features.storage import load_sources

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--database", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
engine = make_engine("sqlite:///" + str(args.database.resolve()))
sessions = session_factory(engine)
request = GenerationRequest(
    tickers=[f"SYN{i:02d}" for i in range(20)],
    provider="synthetic",
    start=date(2020, 1, 1),
    end=date(2024, 12, 31),
)
resolved = Registry().resolve([])
with sessions() as session:
    sources = load_sources(session, request, now(), resolved)
tracemalloc.start()
result = calculate(sources, request, resolved)
current, peak = tracemalloc.get_traced_memory()
top = [
    {"source": str(item.traceback), "bytes": item.size, "allocations": item.count}
    for item in tracemalloc.take_snapshot().statistics("lineno")[:10]
]
report = {
    "assets": 20,
    "rows": len(result.rows),
    "columns": len(result.columns),
    "tracked_current_mib": current / 1024**2,
    "tracked_peak_mib": peak / 1024**2,
    "scope": (
        "Python-tracked allocations during pure M2 calculation; excludes previously loaded "
        "source ORM and most native allocations; not comparable to whole-process RSS"
    ),
    "top_allocations": top,
}
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
engine.dispose()

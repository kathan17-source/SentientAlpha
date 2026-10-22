"""Read-only full M2 calculation with resident real FinBERT; isolates combined memory cause."""

import argparse
import json
import platform
import resource
from datetime import date
from pathlib import Path
from time import perf_counter

from sentientalpha.database.models import now
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import GenerationRequest
from sentientalpha.features.engine import calculate
from sentientalpha.features.registry import Registry
from sentientalpha.features.storage import load_sources
from sentientalpha.sentiment.model import FinBERT

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--database", type=Path, required=True)
parser.add_argument("--model-cache", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
model = FinBERT(str(args.model_cache), local_only=True)
model.predict(["The company reported a profit."])
engine = make_engine("sqlite:///" + str(args.database.resolve()))
sessions = session_factory(engine)
request = GenerationRequest(
    tickers=[f"SYN{i:02d}" for i in range(50)],
    provider="synthetic",
    start=date(2020, 1, 1),
    end=date(2024, 12, 31),
)
resolved = Registry().resolve([])
with sessions() as session:
    sources = load_sources(session, request, now(), resolved)
clock = perf_counter()
calculated = calculate(sources, request, resolved)
report = {
    "scope": (
        "single process with real resident CPU model plus full five-year "
        "50-asset SYNTHETIC price calculation; excludes feature persistence"
    ),
    "assets": 50,
    "rows": len(calculated.rows),
    "columns": len(calculated.columns),
    "pure_calculation_seconds": perf_counter() - clock,
    "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    / (1024**2 if platform.system() == "Darwin" else 1024),
    "model_key": model.key,
    "model": model.metadata,
}
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
engine.dispose()

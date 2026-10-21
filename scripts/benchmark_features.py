"""Reproducible SYNTHETIC five-year feature/storage benchmark; requires an empty DB."""

import argparse
import gc
import json
import os
import platform
import resource
from collections import Counter
from datetime import date
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.features.contracts import GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.services.ingestion import ingest
from sqlalchemy import event, inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=int, choices=[20, 50], required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{args.database.resolve()}"
    engine = make_engine(url)
    if inspect(engine).get_table_names():
        raise ValueError("Benchmark database must be empty; existing data will not be erased")
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    sessions = session_factory(engine)
    start, end = date(2020, 1, 1), date(2024, 12, 31)
    symbols = [f"SYN{i:02d}" for i in range(args.assets)]
    seed_start = perf_counter()
    for ticker in [*symbols, "SPY"]:
        ingest(sessions, SyntheticProvider(), ticker, start, end)
    seed_seconds = perf_counter() - seed_start
    queries = Counter()

    def count(connection, cursor, statement, parameters, context, executemany):
        queries[statement.split()[0].upper()] += 1

    event.listen(engine, "before_cursor_execute", count)
    request = GenerationRequest(tickers=symbols, provider="synthetic", start=start, end=end)
    first = generate(sessions, request)
    fresh_queries = dict(queries)
    queries.clear()
    gc.collect()
    repeat = generate(sessions, request)
    assert repeat.reused and repeat.dataset.id == first.dataset.id
    maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "provenance": "synthetic weekdays, including exchange holidays; no investment result",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "assets": args.assets,
        "benchmark_assets": 1,
        "start": str(start),
        "end": str(end),
        "input_rows": first.dataset.diagnostics["input_rows"],
        "output_rows": first.dataset.row_count,
        "columns": len(first.dataset.columns),
        "output_cells": first.dataset.diagnostics["output_cells"],
        "seed_seconds": seed_seconds,
        "generation_seconds": first.elapsed_seconds,
        "pre_persistence_seconds": first.dataset.diagnostics["compute_seconds"],
        "repeat_seconds": repeat.elapsed_seconds,
        "repeat_reused": repeat.reused,
        "fresh_sql_executions": fresh_queries,
        "repeat_sql_executions": dict(queries),
        "process_peak_rss_mib": maximum / (1024**2 if platform.system() == "Darwin" else 1024),
        "memory_scope": (
            "whole isolated process including ingestion, sources, "
            "Python/native arrays and persistence"
        ),
        "database_bytes": args.database.stat().st_size,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()

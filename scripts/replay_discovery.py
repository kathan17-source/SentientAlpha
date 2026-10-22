"""Replay a retained discovery database offline, including selected M4 ledger artifacts."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.strategies.storage import replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--run-id", type=UUID, required=True)
    args = parser.parse_args()
    if not args.database.is_file():
        raise ValueError("A retained experiment database is required")
    engine = make_engine(f"sqlite:///{args.database.resolve()}")
    with session_factory(engine)() as session:
        result = replay(session, str(args.run_id))
    engine.dispose()
    print(json.dumps(result))
    if not all(result.values()):
        raise SystemExit("Replay differs")


if __name__ == "__main__":
    main()

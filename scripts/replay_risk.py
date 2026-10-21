"""Replay an existing immutable risk audit without data acquisition or fitting."""

import argparse
import json

from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.risk.storage import replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--assessment-id", required=True)
    args = parser.parse_args()
    engine = make_engine(args.database_url)
    try:
        with session_factory(engine)() as session:
            print(json.dumps(replay(session, args.assessment_id), indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

"""One offline database: real research engines plus explicitly synthetic paper sessions."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.paper import storage as paper
from sentientalpha.paper.contracts import Advance, Command, Create


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists() or args.report.exists():
        raise SystemExit("Refusing to replace existing demo files")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "scripts/seed_dashboard_demo.py",
            "--database",
            str(args.database),
            "--report",
            str(args.report),
        ],
        check=True,
        env={**os.environ, "PYTHONPATH": "backend"},
    )
    report = json.loads(args.report.read_text())
    engine = make_engine("sqlite:///" + str(args.database.resolve()))
    sessions = session_factory(engine)
    try:
        for name, veto in [("paper", False), ("risk_veto", True)]:
            risk = {
                "id": "release-" + name,
                "version": "1",
                "effective_at": "2023-01-01T00:00:00Z",
                "constraints": {"cash_maximum": 1, "concentration": 0.4},
                "estimator": {"minimum_observations": 20},
            }
            if veto:
                risk["var_maximum"] = 0.01
            row = paper.create(
                sessions,
                Create.model_validate(
                    {
                        "key": "release-create-" + name,
                        "mode": "synthetic_demo",
                        "tickers": ["DEMOA", "DEMOB"],
                        "provider": "synthetic",
                        "history_start": "2024-01-02",
                        "simulation_start": "2024-04-01",
                        "capital": "10000",
                        "committee_policy": {
                            "effective_at": "2023-01-01T00:00:00Z",
                            "minimum_independent_groups": 1,
                        },
                        "risk_policy": risk,
                    }
                ),
            )
            for action in ["ready", "start"]:
                paper.transition(sessions, row.id, action, Command(key="release-" + action + name))
            q = Advance(key="release-advance-" + name, maximum_events=5)
            paper.advance(sessions, row.id, q)
            with sessions() as s:
                r = paper.get(s, row.id)
                fills = paper.artifacts(s, r, "fills")
                assert paper.replay(s, r)["equivalent"]
                if veto:
                    assert not fills and r.status == "PAUSED", "Expected insufficient-tail veto"
                else:
                    assert fills, "Demo must contain actual persisted simulated fills"
                report[name] = {
                    "session_id": r.id,
                    "status": r.status,
                    "fills": len(fills),
                    "replay_equivalent": True,
                }
        report["scope"] = "Offline synthetic integration, not genuine alpha or forward performance"
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

"""Compare actual paper events with existing M4/M8 research without forcing agreement."""

import argparse
import json
from pathlib import Path
from typing import Any

from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.paper import storage
from sqlalchemy import select
from sqlalchemy.orm import Session


def compare(
    s: Session, session_id: str, backtest_id: str, committee_id: str | None = None
) -> dict[str, Any]:
    row = storage.get(s, session_id)
    backtest = s.get(BacktestRun, backtest_id)
    if backtest is None:
        raise ValueError("Historical backtest not found")
    paper_fills = [a.payload for a in storage.artifacts(s, row, "fills")]
    research_fills = [
        a.payload
        for a in s.scalars(
            select(BacktestArtifact)
            .where(BacktestArtifact.run_id == backtest_id, BacktestArtifact.kind == "fills")
            .order_by(BacktestArtifact.sequence)
        )
    ]
    differences = []
    fields = ["ticker", "side", "quantity", "price", "commission", "slippage", "at"]
    for i in range(max(len(paper_fills), len(research_fills))):
        left = paper_fills[i] if i < len(paper_fills) else {}
        right = research_fills[i] if i < len(research_fills) else {}
        changed = {
            f: {"paper": left.get(f), "research": right.get(f)}
            for f in fields
            if left.get(f) != right.get(f)
        }
        if changed:
            differences.append({"sequence": i, "fields": changed})
    paper_decisions = [
        e.payload["decision"]["record"]
        for e in storage.events(s, row.id)
        if e.kind == "market" and e.payload.get("decision")
    ]
    historical_decisions = []
    if committee_id:
        if s.get(CommitteeRun, committee_id) is None:
            raise ValueError("Historical committee not found")
        historical_decisions = [
            d.payload
            for d in s.scalars(
                select(CommitteeDecision)
                .where(CommitteeDecision.run_id == committee_id)
                .order_by(CommitteeDecision.sequence)
            )
        ]
    return {
        "session_id": row.id,
        "mode": row.mode,
        "backtest_id": backtest_id,
        "committee_id": committee_id,
        "immutable_paper_replay": storage.replay(s, row),
        "paper_fill_count": len(paper_fills),
        "research_fill_count": len(research_fills),
        "fill_differences": differences,
        "paper_decisions": paper_decisions,
        "research_committee_decisions": historical_decisions,
        "research_configuration": backtest.manifest.get("configuration", {}),
        "paper_configuration": row.configuration,
        "equivalence_not_forced": True,
        "possible_explanations_requiring_source_inspection": [
            "actual receipt/processing clocks versus retrospective modeling",
            "different data revisions and feature/model versions",
            "missed processing windows",
            "risk state",
            "next-observed-close versus historical next-open execution",
            "different cost assumptions",
        ],
        "scope": (
            "Ordered fill differences and complete decision evidence. "
            "Reasons are hypotheses unless supported by inspected provenance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--backtest", required=True)
    parser.add_argument("--committee")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    engine = make_engine("sqlite:///" + str(args.database.resolve()))
    try:
        with session_factory(engine)() as s:
            result = compare(s, args.session, args.backtest, args.committee)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

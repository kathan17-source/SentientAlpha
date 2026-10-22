"""Nonzero 1/5/20/50-asset risk workloads on retained synthetic market observations."""

import argparse
import json
import resource
from datetime import timedelta
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from sentientalpha.committee.requests import Request
from sentientalpha.committee.storage import restore
from sentientalpha.data.calendar import session_close
from sentientalpha.database.committee_models import CommitteeRun
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.risk.contracts import EvaluationRequest, Scenario
from sentientalpha.risk.controller import RiskController
from sentientalpha.risk.governance import evaluate
from sentientalpha.risk.storage import execute, replay, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    paired = json.loads(args.comparison.read_text())
    sessions = session_factory(make_engine("sqlite:///" + str(args.database.resolve())))
    with sessions() as s:
        parent = s.get(CommitteeRun, paired["runs"]["guard_only"]["run_id"])
        q = Request.model_validate(parent.manifest["configuration"])
        inputs, meta = restore(s, parent.inputs)
    controller = RiskController(q, inputs, meta, SimpleNamespace(trace=[]))
    at = session_close(inputs.calendar, q.end) + timedelta(seconds=1)
    prices = {
        t: next(b.close for b in inputs.prices.bars if b.ticker == t and b.day == q.end)
        for t in q.tickers
    }
    quantities = {
        t: (Decimal(50000) / len(prices) / p).to_integral_value(rounding=ROUND_FLOOR)
        for t, p in prices.items()
    }
    cash = Decimal(100000) - sum(quantities[t] * p for t, p in prices.items())
    state = controller.state(at, quantities, cash, prices, "decision")
    scenario = Scenario(
        id="broad-down10", version="1", effective_at=q.risk_policy.effective_at, broad_shock=-0.1
    )
    policy = controller.policy.model_copy(
        update={"id": "m9-nonzero-benchmark-v2", "scenarios": [scenario]}
    )
    request = EvaluationRequest(
        state=state,
        policy=policy,
        returns=[r for r in controller.returns if r.available_at <= at][-1260:],
        volumes=[
            v for v in controller.volumes if v.available_at <= at and (at.date() - v.day).days < 40
        ],
        targets={t: 0.6 / len(prices) for t in prices},
        idempotency_key="m9-benchmark-nonzero-v2",
    )
    timings = {}
    t = perf_counter()
    result = evaluate(request, timings)
    compute = perf_counter() - t
    t = perf_counter()
    saved = execute(sessions, request)
    persistence_plus_compute = perf_counter() - t
    with sessions() as s:
        t = perf_counter()
        rep = replay(s, saved.id)
        replay_time = perf_counter() - t
    direct = request.model_copy(
        update={
            "policy": policy.model_copy(update={"id": "m9-direct-persistence-v2"}),
            "idempotency_key": "m9-direct-persistence-v2",
        }
    )
    direct_result = evaluate(direct)
    with sessions() as s:
        t = perf_counter()
        write(
            s,
            direct_result,
            direct.policy,
            direct.model_dump(mode="json"),
            "standalone",
            direct.idempotency_key,
        )
        s.commit()
        direct_persistence = perf_counter() - t
    report = {
        "direct_persistence_seconds": direct_persistence,
        "assets": len(prices),
        "provenance": "Retained synthetic M5 data; constructed ledger identity; no alpha evidence",
        "timings_seconds": timings,
        "compute_seconds": compute,
        "persistence_including_recompute_seconds": persistence_plus_compute,
        "persistence_overhead_estimate_seconds": persistence_plus_compute - compute,
        "replay_seconds": replay_time,
        "replay": rep,
        "tail_timing_scope": "VaR/CVaR share one sorted loss array; combined runtime",
        "assessment_id": saved.id,
        "tail": result["current"]["tail"],
        "stress": result["current"]["stress"],
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2,
        "paired_committee_seconds": {k: v["seconds"] for k, v in paired["runs"].items()},
        "paired_committee_increment_seconds": paired["runs"]["guard_only"]["seconds"]
        - paired["runs"]["m8_baseline"]["seconds"],
        "committee_peak_rss_mib": paired["peak_rss_mib"],
        "comparison_scope": "Paired warm samples; no speedup claim against prior M8.",
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "assets": len(prices),
                "compute_seconds": compute,
                "peak_rss_mib": report["peak_rss_mib"],
            }
        )
    )


if __name__ == "__main__":
    main()

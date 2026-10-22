"""Retained IBM shadow forecasts, sensitivity and fixed independent-capital M4 folds."""

import argparse
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sentientalpha.backtesting.evaluation import WalkRequest
from sentientalpha.committee.engine import backtest_config
from sentientalpha.committee.requests import Request
from sentientalpha.committee.storage import execute, restore
from sentientalpha.database.backtest_models import BacktestArtifact
from sentientalpha.database.committee_models import CommitteeRun
from sentientalpha.database.risk_models import RiskAssessment
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.risk.analytics import analyse
from sentientalpha.risk.contracts import Equity, EvaluationRequest, Scenario
from sentientalpha.risk.controller import RiskController
from sentientalpha.risk.governance import evaluate
from sentientalpha.risk.storage import execute as save_risk
from sentientalpha.risk.validation import ForecastOutcome, exception_diagnostics
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text())
    sessions = session_factory(make_engine("sqlite:///" + str(args.database.resolve())))
    with sessions() as s:
        parent = s.get(CommitteeRun, comparison["runs"]["guard_only"]["run_id"])
        q = Request.model_validate(parent.manifest["configuration"])
        inputs, meta = restore(s, parent.inputs)
        rows = list(
            s.scalars(
                select(RiskAssessment)
                .where(
                    RiskAssessment.committee_id == parent.id, RiskAssessment.phase == "post_close"
                )
                .order_by(RiskAssessment.at)
            )
        )
        bars = {b.day: b for b in inputs.prices.bars}
        days = sorted(bars)
        forecasts = []
        for row in rows:
            weights = row.payload["current"]["exposure"]["weights"]
            tail = row.payload["current"]["tail"]
            day = row.at.date()
            if not sum(weights.values()) or day not in days or days.index(day) + 1 >= len(days):
                continue
            next_day = days[days.index(day) + 1]
            loss = -sum(
                w * (float(bars[next_day].close / bars[day].close) - 1) for w in weights.values()
            )
            forecasts.append(
                ForecastOutcome(
                    portfolio_id=q.idempotency_key,
                    policy_version=q.risk_policy.version,
                    forecast_at=row.at,
                    outcome_at=datetime.combine(next_day, row.at.timetz()),
                    available_at=datetime.combine(next_day, row.at.timetz()) + timedelta(seconds=1),
                    confidence=q.risk_policy.confidence,
                    var_loss_fraction=tail["var_loss_fraction"],
                    realized_loss_fraction=loss,
                    reliable_sample=tail["status"] == "CALCULATED",
                )
            )
        report = {
            "scope": (
                "Previously inspected retrospective IBM; static close weights, "
                "no execution costs in shadow losses; no alpha or VaR validation claim"
            ),
            "forecast_records": [f.model_dump(mode="json") for f in forecasts],
            "exceptions": exception_diagnostics(forecasts, q.source_as_of),
            "sensitivity": [],
        }
        equity = list(
            s.scalars(
                select(BacktestArtifact).where(
                    BacktestArtifact.run_id == parent.backtest_id, BacktestArtifact.kind == "equity"
                )
            )
        )
        held = next(e.payload for e in reversed(equity) if e.payload["positions"])
        controller = RiskController(q, inputs, meta, SimpleNamespace(trace=[]))
        at = datetime.fromisoformat(held["at"]) + timedelta(seconds=1)
        controller.history = [
            Equity(
                at=datetime.fromisoformat(e.payload["at"]),
                value=Decimal(e.payload["equity"]),
                kind="closing",
            )
            for e in sorted(equity, key=lambda e: e.payload["at"])
            if datetime.fromisoformat(e.payload["at"]) < at
        ]
        state = controller.state(
            at,
            {t: Decimal(p["quantity"]) for t, p in held["positions"].items()},
            Decimal(held["cash"]),
            {t: bars[at.date()].close for t in q.tickers},
            "decision",
        )
        scenario = Scenario(
            id="prior-August",
            version="1",
            effective_at=q.risk_policy.effective_at,
            kind="historical",
            start=__import__("datetime").date(2026, 8, 3),
            end=__import__("datetime").date(2026, 8, 31),
        )
        hypot = Scenario(
            id="broad-down10",
            version="1",
            effective_at=q.risk_policy.effective_at,
            broad_shock=-0.1,
        )
        base = EvaluationRequest(
            state=state,
            policy=q.risk_policy.model_copy(update={"scenarios": [scenario, hypot]}),
            returns=[r for r in controller.returns if r.available_at <= at],
            volumes=[v for v in controller.volumes if v.available_at <= at],
            idempotency_key="m9-genuine-state",
        )
        report["actual_state_assessment"] = evaluate(base)
        bad = base.model_copy(
            update={
                "policy": base.policy.model_copy(
                    update={
                        "id": "m9-intentional-cap",
                        "constraints": base.policy.constraints.model_copy(
                            update={"concentration": 0.1}
                        ),
                    }
                ),
                "targets": {"IBM": 0.9},
                "idempotency_key": "m9-intentional-ledger-history",
            }
        )
        bad_saved = save_risk(sessions, bad)
        report["intentional_violation"] = {"id": bad_saved.id, "result": bad_saved.payload}
        for lookback in [20, 60, 90]:
            for covariance in ["sample", "exponential", "diagonal_shrinkage"]:
                for confidence in [0.95, 0.99]:
                    policy = base.policy.model_copy(
                        update={
                            "confidence": confidence,
                            "estimator": base.policy.estimator.model_copy(
                                update={
                                    "lookback": lookback,
                                    "minimum_observations": min(20, lookback),
                                    "covariance": covariance,
                                }
                            ),
                        }
                    )
                    result = analyse(base.model_copy(update={"policy": policy}))
                    report["sensitivity"].append(
                        {
                            "lookback": lookback,
                            "covariance": covariance,
                            "confidence": confidence,
                            "tail": result["tail"],
                            "volatility": result["volatility"],
                        }
                    )
    cfg = backtest_config(q, inputs).model_copy(update={"benchmarks": []})
    folds = WalkRequest(
        backtest=cfg, train_sessions=40, validation_sessions=10, test_sessions=20, step_sessions=20
    ).folds(days)
    report["walk_forward"] = {
        "method": (
            "Existing M4 WalkRequest; independent capital each test window; "
            "fixed concentration .5, no fitting/tuning; early M6/M7 adapters may abstain"
        ),
        "folds": [],
    }
    for n, fold in enumerate(folds):
        policy = q.risk_policy.model_copy(
            update={
                "id": "m9-fold-fixed",
                "constraints": q.risk_policy.constraints.model_copy(update={"concentration": 0.5}),
            }
        )
        fq = Request.model_validate(
            {
                **q.model_dump(),
                "start": fold.test_start,
                "end": fold.test_end,
                "risk_policy": policy,
                "idempotency_key": f"m9-walk-fold-{n}",
            }
        )
        saved = execute(sessions, fq, True)
        report["walk_forward"]["folds"].append(
            {"split": fold.model_dump(mode="json"), "run_id": saved.id, "result": saved.result}
        )
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"exceptions": report["exceptions"], "folds": len(folds)}))


if __name__ == "__main__":
    main()

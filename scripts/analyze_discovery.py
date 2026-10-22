"""Descriptive lagged market-context and fold-stability analysis; no model selection."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sentientalpha.data.calendar import session_close
from sentientalpha.database.backtest_models import BacktestRun
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.database.strategy_models import DiscoveryRun
from sentientalpha.strategies.inputs import thaw
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = make_engine(f"sqlite:///{args.database.resolve()}")
    reports = []
    with session_factory(engine)() as session:
        for run in session.scalars(select(DiscoveryRun).where(DiscoveryRun.status == "evaluated")):
            inputs = thaw(run.inputs)
            cfg = run.manifest["configuration"]
            selected = []
            analysis = []
            for fold in run.result["evaluation"]["folds"]:
                if "rule_hash" not in fold:
                    continue
                selected.append(fold["rule_hash"])
                window = cfg["windows"][fold["fold"]]
                volatility = next(
                    (c for c in inputs.available if c.startswith("realized_volatility__")), None
                )
                historical = []
                for (day, _), values in inputs.signals.items():
                    s = values.get(volatility) if volatility else None
                    if (
                        window["train_start"] <= str(day) <= window["train_end"]
                        and s
                        and s.value is not None
                        and s.ready
                        and s.ready <= session_close(inputs.calendar, day) + timedelta(seconds=1)
                    ):
                        historical.append(s.value)
                boundary = float(np.median(historical)) if historical else None
                link = next(
                    x
                    for x in run.result["evaluation"]["ledger_links"]
                    if x["fold"] == fold["fold"] and x["kind"] == "test"
                )
                ledger = session.get(BacktestRun, link["run_id"])
                days = sorted({b.day for b in inputs.prices.bars})
                groups = {
                    k: []
                    for k in [
                        "positive_prior_return",
                        "negative_prior_return",
                        "high_prior_volatility",
                        "low_prior_volatility",
                        "unknown",
                    ]
                }
                for row in ledger.metrics["daily_returns"]:
                    day = date.fromisoformat(row["day"])
                    i = days.index(day)
                    if not i:
                        groups["unknown"].append(row["return"])
                        continue
                    prior = days[i - 1]
                    ready = session_close(inputs.calendar, prior) + timedelta(seconds=1)
                    values = [inputs.signals.get((prior, t), {}) for t in cfg["tickers"]]
                    returns = [v.get("return") for v in values]
                    if all(
                        s and s.value is not None and s.ready and s.ready <= ready for s in returns
                    ):
                        mean = float(np.mean([s.value for s in returns]))
                        groups[
                            "positive_prior_return" if mean >= 0 else "negative_prior_return"
                        ].append(row["return"])
                    else:
                        groups["unknown"].append(row["return"])
                    vols = [v.get(volatility) for v in values] if volatility else []
                    if (
                        boundary is not None
                        and vols
                        and all(
                            s and s.value is not None and s.ready and s.ready <= ready for s in vols
                        )
                    ):
                        mean = float(np.mean([s.value for s in vols]))
                        groups[
                            "high_prior_volatility" if mean > boundary else "low_prior_volatility"
                        ].append(row["return"])
                analysis.append(
                    {
                        "fold": fold["fold"],
                        "training_volatility_median": boundary,
                        "regimes": {
                            k: {
                                "n": len(v),
                                "mean_daily_return": float(np.mean(v)) if v else None,
                                "descriptive_sd": float(np.std(v, ddof=1)) if len(v) > 1 else None,
                            }
                            for k, v in groups.items()
                        },
                    }
                )
            reports.append(
                {
                    "discovery_id": run.id,
                    "selected_hashes": selected,
                    "selection_switches": sum(
                        a != b for a, b in zip(selected, selected[1:], strict=False)
                    ),
                    "folds": analysis,
                    "warning": (
                        "Conditional descriptive subsets, lagged fixed-universe proxies; "
                        "no causal regime or significance claim"
                    ),
                }
            )
    args.output.write_text(json.dumps({"reports": reports}, indent=2) + "\n")
    engine.dispose()


if __name__ == "__main__":
    main()

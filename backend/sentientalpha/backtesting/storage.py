"""Frozen original inputs, deterministic replay, atomic bounded artifact persistence."""

import hashlib
import json
from contextlib import nullcontext
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting import ENGINE_VERSION
from sentientalpha.backtesting.analytics import analytics
from sentientalpha.backtesting.contracts import (
    BacktestError,
    Bar,
    Feature,
    Request,
    Snapshot,
    StrategySpec,
)
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.evaluation import WalkRequest
from sentientalpha.data.calendar import calendar_version, sessions_in_range
from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun
from sentientalpha.database.base import new_id, now
from sentientalpha.database.models import (
    Asset,
    FeatureInput,
    FeatureRow,
    MarketPrice,
)
from sentientalpha.database.repository import prices_as_of
from sentientalpha.features.matrices import cell
from sentientalpha.features.storage import get_dataset


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


def build_id() -> str:
    root = Path(__file__).resolve().parents[1]
    return digest(
        {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*.py"))
        }
    )


def encode(snapshot: Snapshot) -> dict[str, Any]:
    # Explicit JSON representation retains Decimal strings and UTC timestamps exactly.
    return json.loads(
        json.dumps(
            {
                "bars": [asdict(b) for b in snapshot.bars],
                "features": [asdict(f) for f in snapshot.features],
                "definitions": snapshot.definitions,
            },
            default=str,
        )
    )


def decode(value: dict[str, Any]) -> Snapshot:
    bars = tuple(
        Bar(
            ticker=b["ticker"],
            day=date.fromisoformat(b["day"]),
            opening=Decimal(b["opening"]) if b["opening"] is not None else None,
            close=Decimal(b["close"]) if b["close"] is not None else None,
            volume=b["volume"],
            available=datetime.fromisoformat(b["available"]),
            ingested=datetime.fromisoformat(b["ingested"]),
            source_id=b["source_id"],
            revision=b["revision"],
        )
        for b in value["bars"]
    )
    features = tuple(
        Feature(
            ticker=f["ticker"],
            day=date.fromisoformat(f["day"]),
            value=Decimal(f["value"]) if f["value"] is not None else None,
            ready=datetime.fromisoformat(f["ready"]),
            online=datetime.fromisoformat(f["online"]),
            source_id=f["source_id"],
        )
        for f in value["features"]
    )
    return Snapshot(bars, features, tuple(value["definitions"]))


def load(session: Session, request: Request) -> Snapshot:
    rows: list[tuple[str, MarketPrice]] = []
    symbols = request.tickers + (
        ["SPY"]
        if "SPY" in request.benchmarks
        and request.provider == "alphavantage"
        and "SPY" not in request.tickers
        else []
    )
    for ticker in symbols:
        prices = prices_as_of(
            session,
            ticker,
            request.provider,
            request.start,
            request.end,
            request.source_as_of,
            12000,
        )
        if not prices and ticker not in request.tickers:
            continue
        if not prices:
            raise BacktestError(
                "No immutable source observations for selected security", "insufficient_data"
            )
        if any(
            p.calendar != request.calendar or p.currency != "USD" or p.quality_flags for p in prices
        ):
            raise BacktestError("Price calendar, currency, or quality contract failed")
        rows.extend((ticker, p) for p in prices)
    features = []
    definitions: tuple[str, ...] = ()
    spec = request.strategy
    if spec.feature_dataset_id:
        dataset = get_dataset(session, spec.feature_dataset_id)
        column = spec.feature_column
        if (
            column not in dataset.columns
            or dataset.provider != request.provider
            or dataset.diagnostics["calendar"] != request.calendar
            or dataset.calculated_at > request.source_as_of
        ):
            raise BacktestError("Incompatible or unavailable feature snapshot")
        if not any(d["name"] == "sma" for d in dataset.definitions):
            raise BacktestError("Feature snapshot does not contain registered SMA")
        inputs = set(
            session.scalars(
                select(FeatureInput.price_id).where(FeatureInput.dataset_id == dataset.id)
            )
        )
        if any(p.id not in inputs for ticker, p in rows if ticker in request.tickers):
            raise BacktestError(
                "Feature/price source versions differ; regenerate a matching snapshot",
                "snapshot_mismatch",
            )
        definitions = tuple(json.dumps(d, sort_keys=True) for d in dataset.definitions)
        query = (
            select(FeatureRow, Asset.ticker)
            .join(Asset, Asset.id == FeatureRow.asset_id)
            .where(
                FeatureRow.dataset_id == dataset.id,
                Asset.ticker.in_(request.tickers),
                FeatureRow.session_date.between(request.start, request.end),
            )
        )
        assert column is not None
        for row, ticker in session.execute(query):
            metadata = cell(dataset, row, column)
            if metadata["value"] is not None:
                features.append(
                    Feature(
                        ticker,
                        row.session_date,
                        Decimal(str(metadata["value"])),
                        metadata["decision_ready_at"],
                        metadata["online_ready_at"],
                        dataset.id,
                    )
                )
    return Snapshot(
        tuple(
            Bar(
                t,
                p.session_date,
                p.open,
                p.close,
                p.volume,
                p.available_at,
                p.ingested_at,
                p.id,
                p.revision_no,
            )
            for t, p in rows
        ),
        tuple(features),
        definitions,
    )


def execute_request(request: Request, snapshot: Snapshot) -> dict[str, Any]:
    start = monotonic()
    result = simulate(request, snapshot)
    gross_costs = request.costs.model_copy(
        update={
            "fixed": Decimal(0),
            "per_share": Decimal(0),
            "percentage": Decimal(0),
            "slippage_bps": Decimal(0),
        }
    )
    gross = simulate(request.model_copy(update={"costs": gross_costs, "benchmarks": []}), snapshot)
    result["metrics"]["gross_counterfactual_total_return"] = gross["metrics"].get("total_return")
    comparisons: list[dict[str, Any]] = []
    for name in request.benchmarks:
        if monotonic() - start > request.seconds:
            raise BacktestError("Comparison workload exceeded time budget", "time_budget", 429)
        if name == "SPY":
            spy = tuple(b for b in snapshot.bars if b.ticker == "SPY")
            if request.provider != "alphavantage" or not spy:
                comparisons.append(
                    {
                        "name": "SPY",
                        "status": "insufficient_data",
                        "reason": (
                            "No genuine frozen SPY observations; "
                            "synthetic SPY is not a market benchmark"
                        ),
                    }
                )
            else:
                spy_request = request.model_copy(
                    update={
                        "tickers": ["SPY"],
                        "strategy": StrategySpec(),
                        "benchmarks": [],
                        "actions": [a for a in request.actions if a.ticker == "SPY"],
                    }
                )
                bench = simulate(spy_request, Snapshot(spy))
                comparisons.append(
                    {
                        "name": "SPY",
                        "status": bench["status"],
                        "metrics": bench["metrics"],
                        "equity": bench["equity"],
                    }
                )
            continue
        if name == "moving_average" and request.strategy.feature_dataset_id is None:
            comparisons.append(
                {
                    "name": name,
                    "status": "insufficient_data",
                    "reason": "Existing matching SMA snapshot required",
                }
            )
            continue
        spec = StrategySpec(
            name=name,
            rebalance="signal"
            if name == "moving_average"
            else "monthly"
            if name == "equal_weight"
            else "once",
            feature_dataset_id=request.strategy.feature_dataset_id
            if name == "moving_average"
            else None,
            feature_column=request.strategy.feature_column if name == "moving_average" else None,
        )
        bench = simulate(request.model_copy(update={"strategy": spec, "benchmarks": []}), snapshot)
        comparisons.append(
            {
                "name": name,
                "status": bench["status"],
                "metrics": bench["metrics"],
                "equity": bench["equity"],
            }
        )
    result["benchmarks"] = comparisons
    compatible = next((c for c in comparisons if c["status"] == "completed"), None)
    if compatible:
        relative = analytics(
            result["equity"],
            float(request.capital),
            result["fills"],
            result["closed_pnl"],
            compatible["equity"],
        )
        for key in (
            "alpha",
            "beta",
            "tracking_error",
            "information_ratio",
            "excess_return",
            "rolling",
        ):
            result["metrics"][key] = relative[key]
        result["metrics"]["relative_benchmark"] = compatible["name"]
    return result


def persist(
    sessions: sessionmaker[Session],
    request: Request,
    snapshot: Snapshot,
    result: dict[str, Any],
    extra: dict[str, Any] | None = None,
    transaction: Session | None = None,
) -> BacktestRun:
    payload = encode(snapshot)
    if len(json.dumps(payload)) > 64 * 1024 * 1024:
        raise BacktestError("Frozen input snapshot exceeds 64 MiB budget")
    config = request.model_dump(mode="json")
    run_id = new_id()
    manifest = {
        "run_id": run_id,
        "engine_version": ENGINE_VERSION,
        "dependencies": {
            name: version(name)
            for name in ("numpy", "pandas", "SQLAlchemy", "pydantic", "exchange-calendars")
        },
        "build_id": build_id(),
        "calendar_version": calendar_version(request.calendar),
        "configuration": config,
        "snapshot_hash": digest(payload),
        "configuration_hash": digest(config),
        "feature_definitions": list(snapshot.definitions),
        "created_at": now().isoformat(),
        "random_seed": None,
        "execution_certified": False,
        "warnings": result["warnings"],
        "price_ids": [b.source_id for b in snapshot.bars],
        "feature_snapshot": request.strategy.feature_dataset_id,
        **(extra or {}),
    }
    run = BacktestRun(
        id=run_id,
        status=result["status"],
        manifest=manifest,
        snapshot=payload,
        metrics=result["metrics"],
        diagnostics={
            "events_processed": result["events_processed"],
            "decisions": result["decisions"],
            "closed_pnl": result["closed_pnl"],
        },
    )
    artifacts = []
    for kind in ("orders", "fills", "equity", "actions", "benchmarks", "folds"):
        for sequence, item in enumerate(result.get(kind, [])):
            if kind == "benchmarks":
                for number, row in enumerate(item.get("equity", [])):
                    artifacts.append(
                        {
                            "run_id": run_id,
                            "kind": "bench_" + item["name"],
                            "sequence": number,
                            "payload": row,
                        }
                    )
                item = {k: v for k, v in item.items() if k != "equity"}
            if kind in {"benchmarks", "folds"} and "metrics" in item:
                item = {
                    **item,
                    "metrics": {
                        k: v
                        for k, v in item["metrics"].items()
                        if k not in {"daily_returns", "monthly_returns", "rolling", "drawdown"}
                    },
                }
            artifacts.append(
                {"run_id": run_id, "kind": kind, "sequence": sequence, "payload": item}
            )
    if len(artifacts) > 300000:
        raise BacktestError("Artifact budget exceeded")
    with sessions.begin() if transaction is None else nullcontext(transaction) as session:
        session.add(run)
        session.flush()
        for offset in range(0, len(artifacts), 1000):
            session.execute(insert(BacktestArtifact), artifacts[offset : offset + 1000])
    return run


def run_backtest(sessions: sessionmaker[Session], request: Request) -> BacktestRun:
    with sessions() as session:
        snapshot = load(session, request)
    try:
        result = execute_request(request, snapshot)
    except BacktestError as exc:
        persist(
            sessions,
            request,
            snapshot,
            {
                "status": "failed",
                "warnings": [exc.code],
                "metrics": {"status": "failed", "error_code": exc.code},
                "events_processed": 0,
                "decisions": 0,
                "closed_pnl": [],
            },
        )
        raise
    return persist(sessions, request, snapshot, result)


def get_run(session: Session, run_id: str) -> BacktestRun:
    run = session.get(BacktestRun, run_id)
    if run is None:
        raise BacktestError("Backtest run not found", "not_found", 404)
    return run


def replay(session: Session, run_id: str) -> dict[str, Any]:
    run = get_run(session, run_id)
    if (
        digest(run.snapshot) != run.manifest["snapshot_hash"]
        or build_id() != run.manifest["build_id"]
    ):
        raise BacktestError("Saved snapshot or executable build differs", "replay_mismatch", 409)
    if digest(run.manifest["configuration"]) != run.manifest["configuration_hash"] or any(
        version(name) != v for name, v in run.manifest["dependencies"].items()
    ):
        raise BacktestError("Configuration or dependency versions differ", "replay_mismatch", 409)
    if run.manifest.get("external_target_strategy") == "investment_committee":
        raise BacktestError(
            "Replay this ledger through its linked investment committee",
            "committee_replay_required",
            409,
        )
    if run.manifest.get("external_target_strategy") == "strategy_discovery":
        raise BacktestError(
            "Replay this ledger through its discovery experiment", "strategy_replay_required", 409
        )
    if run.manifest.get("external_target_strategy") == "ml_forecast":
        raise BacktestError(
            "Replay this ledger through its linked ML experiment", "ml_replay_required", 409
        )
    if run.manifest.get("external_target_strategy"):
        raise BacktestError(
            "Replay this ledger through its linked optimization experiment",
            "optimization_replay_required",
            409,
        )
    request = Request.model_validate(run.manifest["configuration"])
    if "walk_forward" in run.manifest:
        raise BacktestError(
            "Replay individual fold run IDs; aggregate is a fold manifest", "fold_replay_required"
        )
    result = execute_request(request, decode(run.snapshot))
    equivalent_artifacts = True
    for kind in ("orders", "fills", "equity", "actions"):
        saved = list(
            session.scalars(
                select(BacktestArtifact)
                .where(BacktestArtifact.run_id == run.id, BacktestArtifact.kind == kind)
                .order_by(BacktestArtifact.sequence)
            )
        )
        equivalent_artifacts &= digest([a.payload for a in saved]) == digest(result[kind])
    return {
        "run_id": run.id,
        "equivalent_artifacts": equivalent_artifacts,
        "equivalent_metrics": digest(result["metrics"]) == digest(run.metrics),
        "metrics": result["metrics"],
        "orders": result["orders"],
        "fills": result["fills"],
        "equity": result["equity"],
    }


def walk_forward(sessions: sessionmaker[Session], request: WalkRequest) -> BacktestRun:
    started = monotonic()
    base = request.backtest
    splits = request.folds(sessions_in_range(base.calendar, base.start, base.end))
    with sessions() as session:
        snapshot = load(session, base)
    folds = []
    aggregate = []
    capital = base.capital
    for index, split in enumerate(splits):
        if monotonic() - started > base.seconds:
            raise BacktestError(
                "Walk-forward exceeded cooperative fold time budget", "time_budget", 429
            )
        config = base.model_copy(
            update={
                "start": split.test_start,
                "end": split.test_end,
                "benchmarks": [],
                "actions": [a for a in base.actions if split.test_start <= a.day <= split.test_end],
            }
        )
        fold_snapshot = Snapshot(
            tuple(b for b in snapshot.bars if split.test_start <= b.day <= split.test_end),
            tuple(f for f in snapshot.features if split.test_start <= f.day <= split.test_end),
            snapshot.definitions,
        )
        result = execute_request(config, fold_snapshot)
        child = persist(
            sessions,
            config,
            fold_snapshot,
            result,
            {
                "evaluation_split": split.model_dump(mode="json"),
                "selection_policy": "frozen_baseline_no_fitting",
                "fold_index": index,
            },
        )
        folds.append(
            {
                "index": index,
                "run_id": child.id,
                "split": split.model_dump(mode="json"),
                "status": result["status"],
                "metrics": result["metrics"],
            }
        )
        previous = base.capital
        for row in result["equity"]:
            current = Decimal(row["equity"])
            capital *= current / previous
            previous = current
            aggregate.append({**row, "equity": str(capital), "fold": index})
    # Linked OOS return index, not a fictitious carried cash/position ledger.
    metrics = analytics(aggregate, float(base.capital), [], [])
    metrics["trade_count"] = sum(f["metrics"].get("trade_count", 0) for f in folds)
    for key in (
        "average_exposure",
        "turnover",
        "commissions",
        "slippage",
        "closed_lot_count",
        "win_rate",
        "profit_factor",
        "average_trade_pnl",
    ):
        metrics[key] = None
    summary = {
        "status": "completed"
        if all(f["status"] == "completed" for f in folds)
        else "insufficient_data",
        "equity": [],
        "folds": folds,
        "metrics": metrics,
        "warnings": [
            (
                "Independent initial-capital fold ledgers; OOS returns linked "
                "without carrying positions or capital. Aggregate trading ratios undefined."
            ),
            "Frozen baseline parameters; no training, normalization or selection performed.",
        ],
        "events_processed": sum(len(f["metrics"].get("daily_returns", [])) * 2 for f in folds),
        "decisions": 0,
        "closed_pnl": [],
    }
    summary["equity"] = [
        {
            "day": r["day"],
            "equity": r["equity"],
            "fold": r["fold"],
            "kind": "linked_oos_return_index",
        }
        for r in aggregate
    ]
    return persist(
        sessions,
        base,
        snapshot,
        summary,
        {
            "walk_forward": request.model_dump(mode="json"),
            "selection_policy": "frozen_baseline_no_fitting",
        },
    )

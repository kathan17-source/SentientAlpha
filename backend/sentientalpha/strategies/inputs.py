"""Source-linked M2/M3 and immutable M6 forecast adapters; no new indicators."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.storage import decode, digest, encode
from sentientalpha.data.calendar import session_close
from sentientalpha.data.contracts import utc
from sentientalpha.database.ml_models import MLExperiment, MLModel, MLPrediction
from sentientalpha.database.models import (
    Asset,
    FeatureInput,
    FeatureRow,
    FeatureSourceAsset,
    MarketPrice,
)
from sentientalpha.features.matrices import cell
from sentientalpha.features.storage import get_dataset
from sentientalpha.strategies.contracts import DiscoveryError, Request


@dataclass(frozen=True)
class Signal:
    value: float | None
    ready: datetime | None
    source: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.value is not None:
            if not isfinite(self.value):
                raise DiscoveryError("Nonfinite feature signal")
            object.__setattr__(self, "value", float(self.value))
        if self.ready is not None:
            object.__setattr__(self, "ready", utc(self.ready))
        if not self.source:
            raise DiscoveryError("Signal source identity required")


@dataclass(frozen=True)
class Inputs:
    prices: Snapshot
    signals: dict[tuple[date, str], dict[str, Signal]]
    calendar: str
    metadata: dict[str, Any]
    available: frozenset[str]


def freeze(inputs: Inputs) -> dict[str, Any]:
    return {
        "prices": encode(inputs.prices),
        "calendar": inputs.calendar,
        "metadata": inputs.metadata,
        "available": sorted(inputs.available),
        "signals": [
            {
                "day": str(day),
                "ticker": ticker,
                "values": {
                    c: [s.value, s.ready.isoformat() if s.ready else None, s.source, s.reason]
                    for c, s in sorted(values.items())
                },
            }
            for (day, ticker), values in sorted(inputs.signals.items())
        ],
    }


def thaw(v: dict[str, Any]) -> Inputs:
    return Inputs(
        decode(v["prices"]),
        {
            (date.fromisoformat(r["day"]), r["ticker"]): {
                c: Signal(s[0], datetime.fromisoformat(s[1]) if s[1] else None, s[2], s[3])
                for c, s in r["values"].items()
            }
            for r in v["signals"]
        },
        v["calendar"],
        v["metadata"],
        frozenset(v["available"]),
    )


def load(session: Session, request: Request) -> Inputs:
    dataset = get_dataset(session, request.dataset_id)
    if dataset.configuration.get("kind") == "sentiment":
        raise DiscoveryError("A price-feature dataset is required")
    datasets = [dataset]
    if request.sentiment_dataset_id:
        datasets.append(get_dataset(session, request.sentiment_dataset_id))
    calendar = dataset.diagnostics["calendar"]
    if set(request.tickers) - set(dataset.configuration["tickers"]):
        raise DiscoveryError("Asset not in feature snapshot")
    required = {a.feature for a in request.space.axes} | {
        v for a in request.space.axes for v in a.other_features
    }
    required.add("close")
    available = {"close"}
    signals: dict[tuple[date, str], dict[str, Signal]] = {}
    meta: dict[str, Any] = {
        "datasets": [],
        "provider": dataset.provider,
        "ml_sources": [],
        "synthetic": dataset.provider == "synthetic",
        "information_policy": request.information_policy,
        "limitations": [
            (
                "Fixed current universe; raw daily research execution; "
                "incomplete historical actions/news rights."
            )
        ],
    }
    cell_count = 0
    for ds in datasets:
        if ds.calculated_at > request.source_as_of or ds.diagnostics["calendar"] != calendar:
            raise DiscoveryError("Feature source cutoff/calendar mismatch")
        sentiment = ds.configuration.get("kind") == "sentiment"
        if sentiment and (
            ds.configuration.get("scope") != "security"
            or ds.configuration.get("availability_policy") != "observed"
            or (
                (ds.configuration.get("news_provider") == "synthetic_news")
                != (request.sentiment_provenance == "synthetic_fixture")
            )
        ):
            raise DiscoveryError("Incompatible sentiment provenance or availability policy")
        cols = set(ds.columns) & required
        available.update(cols)
        meta["datasets"].append(
            {
                "id": ds.id,
                "source_hash": ds.source_hash,
                "definition_hash": ds.definition_hash,
                "definitions": ds.definitions,
            }
        )
        q = (
            select(FeatureRow, FeatureSourceAsset.ticker)
            .join(
                FeatureSourceAsset,
                (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
                & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
            )
            .where(
                FeatureRow.dataset_id == ds.id,
                FeatureSourceAsset.ticker.in_(request.tickers),
                FeatureRow.session_date.between(
                    request.windows[0].train_start, request.windows[-1].test_end
                ),
            )
        )
        for row, ticker in session.execute(q):
            group = signals.setdefault((row.session_date, ticker), {})
            for c in cols:
                item = cell(ds, row, c)
                value, reason = item["value"], item["missing_reason"]
                clock = (
                    item["online_ready_at"]
                    if request.information_policy == "online"
                    else item["decision_ready_at"]
                )
                if sentiment and item["coverage_state"] != "complete":
                    value, reason = None, "incomplete_sentiment_coverage"
                if (
                    not sentiment
                    and request.information_policy == "retrospective"
                    and value is not None
                ):
                    clock = session_close(calendar, row.session_date) + timedelta(seconds=1)
                group[c] = Signal(value, clock, ds.id + ":" + c, reason)
            cell_count += len(cols)
            if cell_count > 1_000_000:
                raise DiscoveryError("Discovery feature cell budget exceeded")
    price_query = (
        select(MarketPrice, Asset.ticker)
        .join(FeatureInput, FeatureInput.price_id == MarketPrice.id)
        .join(Asset, Asset.id == MarketPrice.asset_id)
        .where(
            FeatureInput.dataset_id == dataset.id,
            Asset.ticker.in_(request.tickers),
            MarketPrice.session_date.between(
                request.windows[0].train_start, request.windows[-1].test_end
            ),
        )
        .order_by(MarketPrice.session_date, Asset.ticker)
    )
    bars = []
    for p, t in session.execute(price_query):
        if (
            p.revision_no != 1
            or p.quality_flags
            or p.calendar != calendar
            or max(p.available_at, p.ingested_at) > request.source_as_of
        ):
            raise DiscoveryError("Price revision/quality/calendar/cutoff incompatible")
        bars.append(
            Bar(t, p.session_date, p.open, p.close, p.volume, p.available_at, p.ingested_at, p.id)
        )
        ready = max(p.available_at, session_close(calendar, p.session_date) + timedelta(seconds=1))
        if request.information_policy == "online":
            ready = max(ready, p.ingested_at)
        elif request.information_policy == "retrospective":
            ready = session_close(calendar, p.session_date) + timedelta(seconds=1)
        signals.setdefault((p.session_date, t), {})["close"] = Signal(float(p.close), ready, p.id)
        if len(bars) > 140000:
            raise DiscoveryError("Discovery price budget exceeded")
    for model_id in request.ml_model_ids:
        model = session.get(MLModel, model_id)
        parent = session.get(MLExperiment, model.experiment_id) if model else None
        if (
            model is None
            or parent is None
            or model.created_at > request.source_as_of
            or digest(model.payload) != model.version
            or model.payload not in parent.result.get("models", [])
            or digest(parent.inputs) != parent.manifest["input_hash"]
            or digest(model.payload["artifact"]) != model.payload["artifact_hash"]
        ):
            raise DiscoveryError("ML model/version/snapshot integrity failed")
        name = {
            "direction": "ml_probability",
            "return": "ml_return",
            "volatility": "ml_volatility",
        }[model.payload["target"]["task"]]
        if model.payload["target"]["horizon"] != request.ml_horizon:
            raise DiscoveryError("Forecast horizon mismatch")
        available.add(name)
        for pred in session.scalars(
            select(MLPrediction).where(
                MLPrediction.model_id == model_id, MLPrediction.ticker.in_(request.tickers)
            )
        ):
            p = pred.payload
            if p not in parent.result.get("predictions", []):
                raise DiscoveryError("Only immutable original out-of-sample forecasts are accepted")
            decision = pred.decision_at
            if (
                p.get("model_version") != model.version
                or p.get("model_hash") != model.payload["artifact_hash"]
                or datetime.fromisoformat(model.payload["effective_at"]) > decision
                or datetime.fromisoformat(p["training_cutoff"]) >= decision
            ):
                raise DiscoveryError("Future-trained or mismatched ML forecast")
            if (
                p.get("origin") == "retrospective_research"
                and request.information_policy != "retrospective"
            ):
                raise DiscoveryError("Retrospective forecasts cannot be relabeled PIT")
            if request.information_policy == "online" and (
                pred.generated_at > decision or model.created_at > decision
            ):
                raise DiscoveryError("Research forecasts were not actually issued live")
            if (
                pred.generated_at > request.source_as_of
                or p["horizon"] != request.ml_horizon
                or p["inference_status"] != "completed"
            ):
                continue
            group = signals.setdefault((date.fromisoformat(p["day"]), pred.ticker), {})
            if name in group:
                raise DiscoveryError("Overlapping ML versions require separate discovery runs")
            group[name] = Signal(float(p["value"]), decision, pred.id)
        meta["ml_sources"].append(
            {
                "model_id": model.id,
                "version": model.version,
                "parent": parent.id,
                "source_build": parent.manifest["build_id"],
            }
        )
    if required - available:
        raise DiscoveryError("Search requires unavailable/unregistered features")
    return Inputs(Snapshot(tuple(bars)), signals, calendar, meta, frozenset(available))

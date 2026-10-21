"""Adapt existing immutable M2/M3 datasets, retaining source and availability clocks."""

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.storage import decode, encode
from sentientalpha.database.models import (
    Asset,
    FeatureInput,
    FeatureRow,
    FeatureSourceAsset,
    MarketPrice,
)
from sentientalpha.features.matrices import cell
from sentientalpha.features.storage import get_dataset
from sentientalpha.optimization.contracts import OptimizationRequest, Sentiment
from sentientalpha.optimization.estimation import OptimizationError, Panel, ReturnRow
from sentientalpha.optimization.sentiment import SentimentCell


@dataclass(frozen=True)
class Inputs:
    panel: Panel
    prices: Snapshot
    sentiments: tuple[SentimentCell, ...]
    metadata: dict[str, Any]


def freeze(inputs: Inputs) -> dict[str, Any]:
    return {
        "panel": {
            "tickers": list(inputs.panel.tickers),
            "calendar": inputs.panel.calendar,
            "rows": [
                {
                    "day": str(r.day),
                    "values": list(r.values),
                    "ready": [t.isoformat() if t else None for t in r.ready],
                }
                for r in inputs.panel.rows
            ],
        },
        "prices": encode(inputs.prices),
        "sentiments": [
            {**asdict(s), "day": str(s.day), "ready": s.ready.isoformat() if s.ready else None}
            for s in inputs.sentiments
        ],
        "metadata": inputs.metadata,
    }


def thaw(value: dict[str, Any]) -> Inputs:
    p = value["panel"]
    panel = Panel(
        tuple(p["tickers"]),
        tuple(
            ReturnRow(
                date.fromisoformat(r["day"]),
                tuple(r["values"]),
                tuple(datetime.fromisoformat(t) if t else None for t in r["ready"]),
            )
            for r in p["rows"]
        ),
        p["calendar"],
    )
    cells = tuple(
        SentimentCell(
            **{
                **s,
                "day": date.fromisoformat(s["day"]),
                "ready": datetime.fromisoformat(s["ready"]) if s["ready"] else None,
            }
        )
        for s in value["sentiments"]
    )
    return Inputs(panel, decode(value["prices"]), cells, value["metadata"])


def load_inputs(
    session: Session, request: OptimizationRequest, extra_sentiment: list[Sentiment] | None = None
) -> Inputs:
    dataset = get_dataset(session, request.price_dataset_id)
    definitions = [d for d in dataset.definitions if d["name"] == "return"]
    if (
        dataset.configuration.get("kind") == "sentiment"
        or not definitions
        or dataset.calculated_at > request.source_as_of
    ):
        raise OptimizationError(
            "A compatible persisted M2 simple daily-return snapshot is required"
        )
    column = next((k for k in dataset.columns if k == "return"), None)
    if column is None:
        raise OptimizationError("Only one-session simple return inputs are accepted")
    if set(request.tickers) - set(dataset.configuration["tickers"]):
        raise OptimizationError("Unavailable asset in return snapshot")
    # Entire snapshot is frozen so a later experiment can use it chronologically, never all at once.
    days: dict[date, dict[str, tuple[float | None, datetime | None]]] = {}
    query = (
        select(FeatureRow, FeatureSourceAsset.ticker)
        .join(
            FeatureSourceAsset,
            (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
            & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
        )
        .where(FeatureRow.dataset_id == dataset.id, FeatureSourceAsset.ticker.in_(request.tickers))
        .execution_options(yield_per=1000)
    )
    count = 0
    for row, ticker in session.execute(query):
        count += 1
        if count > 140000:
            raise OptimizationError("Return panel input budget exceeded")
        item = cell(dataset, row, column)
        ready = (
            item["online_ready_at"]
            if request.information_policy == "online"
            else item["decision_ready_at"]
        )
        days.setdefault(row.session_date, {})[ticker] = (item["value"], ready)
    panel = Panel(
        tuple(request.tickers),
        tuple(
            ReturnRow(
                d,
                tuple(group.get(t, (None, None))[0] for t in request.tickers),
                tuple(group.get(t, (None, None))[1] for t in request.tickers),
            )
            for d, group in sorted(days.items())
        ),
        dataset.diagnostics["calendar"],
    )
    price_query = (
        select(MarketPrice, Asset.ticker)
        .join(FeatureInput, FeatureInput.price_id == MarketPrice.id)
        .join(Asset, Asset.id == MarketPrice.asset_id)
        .where(
            FeatureInput.dataset_id == dataset.id,
            Asset.ticker.in_(request.tickers),
            MarketPrice.session_date >= request.history_start,
        )
        .order_by(MarketPrice.session_date, Asset.ticker)
        .execution_options(yield_per=1000)
    )
    bars = []
    for p, t in session.execute(price_query):
        if (
            p.available_at > request.source_as_of
            or p.ingested_at > request.source_as_of
            or p.calendar != panel.calendar
            or p.quality_flags
            or p.revision_no != 1
        ):
            raise OptimizationError("Unverified, revised, flagged or unavailable source prices")
        bars.append(
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
        )
        if len(bars) > 140000:
            raise OptimizationError("Price input budget exceeded")
    if not bars:
        raise OptimizationError("No retained source prices", "insufficient_data")
    if dataset.provider == "alphavantage" and "SPY" not in request.tickers:
        from sentientalpha.database.repository import prices_as_of

        spy = prices_as_of(
            session,
            "SPY",
            "alphavantage",
            dataset.start_date,
            dataset.end_date,
            request.source_as_of,
            12000,
        )
        if spy and all(
            p.revision_no == 1 and not p.quality_flags and p.calendar == panel.calendar for p in spy
        ):
            bars.extend(
                Bar(
                    "SPY",
                    p.session_date,
                    p.open,
                    p.close,
                    p.volume,
                    p.available_at,
                    p.ingested_at,
                    p.id,
                    p.revision_no,
                )
                for p in spy
            )
    cells = []
    sent_meta = {}
    unavailable = {}
    configs = ([request.sentiment] if request.sentiment else []) + (extra_sentiment or [])
    for spec in configs:
        key = spec.dataset_id + ":" + spec.column
        if key in sent_meta or key in unavailable:
            continue
        s = get_dataset(session, spec.dataset_id)
        valid = (
            s.configuration.get("kind") == "sentiment"
            and s.configuration.get("scope") == "security"
            and s.diagnostics["calendar"] == panel.calendar
            and spec.column in s.columns
            and s.calculated_at <= request.source_as_of
        )
        provider = s.configuration.get("news_provider")
        valid = (
            valid
            and s.configuration.get("availability_policy") == "observed"
            and (
                (spec.provenance == "synthetic_fixture" and provider == "synthetic_news")
                or (spec.provenance == "verified_history" and provider != "synthetic_news")
            )
        )
        if not valid:
            unavailable[key] = (
                "Sentiment provenance, publication policy, calendar or feature incompatible"
            )
            continue
        sent_meta[key] = {
            "dataset_id": s.id,
            "source_hash": s.source_hash,
            "definitions": s.definitions,
            "provenance": spec.provenance,
        }
        query = (
            select(FeatureRow, FeatureSourceAsset.ticker)
            .join(
                FeatureSourceAsset,
                (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
                & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
            )
            .where(FeatureRow.dataset_id == s.id, FeatureSourceAsset.ticker.in_(request.tickers))
            .execution_options(yield_per=1000)
        )
        for row, ticker in session.execute(query):
            item = cell(s, row, spec.column)
            ready = (
                item["online_ready_at"]
                if request.information_policy == "online"
                else item["decision_ready_at"]
            )
            cells.append(
                SentimentCell(
                    ticker,
                    row.session_date,
                    item["value"],
                    ready,
                    item["coverage_state"],
                    item["missing_reason"],
                    s.id,
                    spec.column,
                )
            )
            if len(cells) > 140000:
                raise OptimizationError("Sentiment input budget exceeded")
    return Inputs(
        panel,
        Snapshot(tuple(bars), (), tuple(str(d) for d in dataset.definitions)),
        tuple(cells),
        {
            "price_dataset_id": dataset.id,
            "source_hash": dataset.source_hash,
            "definition_hash": dataset.definition_hash,
            "definitions": dataset.definitions,
            "provider": dataset.provider,
            "sentiment_snapshots": sent_meta,
            "sentiment_unavailable": unavailable,
            "warnings": [
                "Fixed requested universe/current declared sectors are not "
                "survivorship-free membership.",
                "Raw close returns omit unprovided distributions and can jump at "
                "unprovided splits; execution remains M4 research approximation.",
            ],
        },
    )

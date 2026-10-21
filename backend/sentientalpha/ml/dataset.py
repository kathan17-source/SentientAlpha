"""Frozen feature/price lineage, explicit research clocks, future-only labels."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.storage import decode, encode
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.database.models import (
    Asset,
    FeatureInput,
    FeatureRow,
    FeatureSourceAsset,
    MarketPrice,
)
from sentientalpha.features.matrices import cell
from sentientalpha.features.storage import get_dataset
from sentientalpha.features.timing import next_open
from sentientalpha.ml.contracts import MLException, ResearchRequest


@dataclass(frozen=True)
class Observation:
    ticker: str
    asset_id: str
    day: date
    decision: datetime
    execution: datetime
    values: tuple[float | None, ...]
    target: float | None
    target_start: datetime | None
    target_end: datetime | None
    target_available: datetime | None
    lineage: dict[str, Any]


@dataclass(frozen=True)
class Dataset:
    columns: tuple[str, ...]
    rows: tuple[Observation, ...]
    prices: Snapshot
    calendar: str
    metadata: dict[str, Any]


def freeze(ds: Dataset) -> dict[str, Any]:
    return {
        "columns": list(ds.columns),
        "calendar": ds.calendar,
        "metadata": ds.metadata,
        "prices": encode(ds.prices),
        "rows": [
            {
                **asdict(r),
                "day": str(r.day),
                **{
                    k: getattr(r, k).isoformat() if getattr(r, k) else None
                    for k in (
                        "decision",
                        "execution",
                        "target_start",
                        "target_end",
                        "target_available",
                    )
                },
            }
            for r in ds.rows
        ],
    }


def thaw(v: dict[str, Any]) -> Dataset:
    return Dataset(
        tuple(v["columns"]),
        tuple(
            Observation(
                **{
                    **r,
                    "day": date.fromisoformat(r["day"]),
                    "values": tuple(r["values"]),
                    **{
                        k: datetime.fromisoformat(r[k]) if r[k] else None
                        for k in (
                            "decision",
                            "execution",
                            "target_start",
                            "target_end",
                            "target_available",
                        )
                    },
                }
            )
            for r in v["rows"]
        ),
        decode(v["prices"]),
        v["calendar"],
        v["metadata"],
    )


def label(
    ticker: str,
    decision: datetime,
    request: ResearchRequest,
    prices: Snapshot,
    calendar: str,
    lookup: dict[tuple[str, date], Bar] | None = None,
) -> tuple[float | None, datetime | None, datetime | None, datetime | None, list[str]]:
    target = request.target
    start = next_open(calendar, decision)
    days = sessions_in_range(calendar, start.date(), start.date() + timedelta(days=30))[
        : target.horizon
    ]
    if lookup is None:
        lookup = {(b.ticker, b.day): b for b in prices.bars}
    bars = [lookup.get((ticker, d)) for d in days]
    if len(days) != target.horizon or any(b is None for b in bars):
        return None, start, None, None, []
    actual = [b for b in bars if b is not None]
    if any(b.opening is None or b.close is None for b in actual):
        return None, start, None, None, []
    finish = session_close(calendar, days[-1])
    entry = float(actual[0].opening)  # type: ignore[arg-type]
    if target.convention == "close_to_close_research":
        previous = [
            b
            for b in prices.bars
            if b.ticker == ticker and session_close(calendar, b.day) <= decision
        ]
        if not previous or previous[-1].close is None:
            return None, start, finish, None, []
        entry = float(previous[-1].close)
        start = session_close(calendar, previous[-1].day)
    simple = float(actual[-1].close) / entry - 1  # type: ignore[arg-type]
    if target.task == "volatility":
        # Future-session intraday log-return RMS; no pre-decision observations, annualized.
        logs = np.array([np.log(float(b.close) / float(b.opening)) for b in actual])  # type: ignore[arg-type]
        y = float(np.sqrt(np.mean(logs**2) * 252))
    else:
        y = float(simple > 0) if target.task == "direction" else simple
    if request.information_policy == "retrospective":
        available = finish + timedelta(seconds=1)
    else:
        available = max([finish] + [b.available for b in actual])
        if request.information_policy == "online":
            available = max(available, *(b.ingested for b in actual))
    return y, start, finish, available, [b.source_id for b in actual]


def build(session: Session, request: ResearchRequest) -> Dataset:
    price = get_dataset(session, request.dataset_id)
    datasets = [price]
    if request.sentiment_dataset_id:
        datasets.append(get_dataset(session, request.sentiment_dataset_id))
    calendar = price.diagnostics["calendar"]
    available_columns = set().union(*(set(d.columns) for d in datasets))
    if set(request.columns) - available_columns or price.configuration.get("kind") == "sentiment":
        raise MLException(
            "Only existing registered feature columns are accepted; labels are forbidden"
        )
    if any(d.calculated_at > request.source_as_of for d in datasets):
        raise MLException("Feature snapshot is newer than source cutoff")
    if any(t not in price.configuration["tickers"] for t in request.tickers):
        raise MLException("Unknown dataset asset")
    if len(datasets) == 2:
        s = datasets[1]
        if (
            s.configuration.get("scope") != "security"
            or s.diagnostics["calendar"] != calendar
            or s.configuration.get("availability_policy") != "observed"
            or (s.configuration.get("news_provider") == "synthetic_news")
            != (request.sentiment_provenance == "synthetic_fixture")
        ):
            raise MLException("Incompatible sentiment scope, calendar, policy or provenance")
    bars = []
    query = (
        select(MarketPrice, Asset.ticker)
        .join(FeatureInput, FeatureInput.price_id == MarketPrice.id)
        .join(Asset, Asset.id == MarketPrice.asset_id)
        .where(FeatureInput.dataset_id == price.id, Asset.ticker.in_(request.tickers))
        .order_by(MarketPrice.session_date, Asset.ticker)
    )
    for p, t in session.execute(query):
        if (
            p.available_at > request.source_as_of
            or p.ingested_at > request.source_as_of
            or p.quality_flags
            or p.revision_no != 1
            or p.calendar != calendar
        ):
            raise MLException("Source prices revised, flagged or incompatible with cutoff")
        bars.append(
            Bar(t, p.session_date, p.open, p.close, p.volume, p.available_at, p.ingested_at, p.id)
        )
        if len(bars) > 140000:
            raise MLException("Price budget exceeded")
    prices = Snapshot(tuple(bars))
    grouped: dict[tuple[date, str], dict[str, Any]] = {}
    for d in datasets:
        columns = [c for c in request.columns if c in d.columns]
        q = (
            select(FeatureRow, FeatureSourceAsset.ticker)
            .join(
                FeatureSourceAsset,
                (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
                & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
            )
            .where(FeatureRow.dataset_id == d.id, FeatureSourceAsset.ticker.in_(request.tickers))
        )
        for r, t in session.execute(q):
            g = grouped.setdefault((r.session_date, t), {"asset_id": r.asset_id, "cells": {}})
            for c in columns:
                item = cell(d, r, c)
                if (
                    d.configuration.get("kind") == "sentiment"
                    and item["coverage_state"] != "complete"
                ):
                    item = {
                        **item,
                        "value": None,
                        "missing_reason": "incomplete_sentiment_coverage",
                    }
                g["cells"][c] = item
            if len(grouped) * len(request.columns) > 2_000_000:
                raise MLException("Feature cell budget exceeded")
    rows = []
    price_lookup = {(b.ticker, b.day): b for b in prices.bars}
    lo, hi = request.windows[0].train_start, request.windows[-1].test_end
    for (day, t), g in sorted(grouped.items()):
        if not lo <= day <= hi:
            continue
        nominal = session_close(calendar, day) + timedelta(seconds=1)
        items = [g["cells"].get(c, {}) for c in request.columns]
        clocks = [
            i.get(
                "online_ready_at" if request.information_policy == "online" else "decision_ready_at"
            )
            for i in items
        ]
        # Retrospective price reconstruction is explicit; never backdate observed news.
        if request.information_policy == "retrospective":
            clocks = [
                nominal if not c.startswith("sent_") else clock
                for c, clock in zip(request.columns, clocks, strict=True)
            ]
        decision = nominal
        values = tuple(
            i.get("value") if clock is not None and clock <= decision else None
            for i, clock in zip(items, clocks, strict=True)
        )
        if any(v is not None and not np.isfinite(v) for v in values):
            raise MLException("Infinite input feature")
        y, start, end, ready, ids = label(t, decision, request, prices, calendar, price_lookup)
        rows.append(
            Observation(
                t,
                g["asset_id"],
                day,
                decision,
                next_open(calendar, decision),
                values,
                y,
                start,
                end,
                ready,
                {
                    "source_price_ids": ids,
                    "features": [
                        {
                            "column": c,
                            "available_at": clock.isoformat() if clock else None,
                            "missing_reason": i.get("missing_reason"),
                            "source_available_at": i.get("inputs_available_at").isoformat()
                            if i.get("inputs_available_at")
                            else None,
                        }
                        for c, i, clock in zip(request.columns, items, clocks, strict=True)
                    ],
                },
            )
        )
    return Dataset(
        tuple(request.columns),
        tuple(rows),
        prices,
        calendar,
        {
            "datasets": [
                {
                    "id": d.id,
                    "source_hash": d.source_hash,
                    "definition_hash": d.definition_hash,
                    "definitions": d.definitions,
                    "provider": d.provider,
                }
                for d in datasets
            ],
            "information_policy": request.information_policy,
            "warning": (
                "Retrospective raw-price research; historical universe, corporate-action "
                "completeness and live forecasts are unverified."
            ),
        },
    )

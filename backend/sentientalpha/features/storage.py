"""Source snapshot loading and immutable/idempotent feature materialization."""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from time import perf_counter
from typing import Any, Literal, cast

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.data.contracts import AvailabilityKind, PriceBar
from sentientalpha.database.models import (
    Asset,
    FeatureDataset,
    FeatureInput,
    FeatureRow,
    FeatureSourceAsset,
    MarketPrice,
    now,
)
from sentientalpha.database.session import serialize_writer
from sentientalpha.features import ENGINE_VERSION
from sentientalpha.features.contracts import (
    MAX_INPUT_ROWS,
    FeatureError,
    GenerationRequest,
    Observation,
    digest,
)
from sentientalpha.features.engine import calculate
from sentientalpha.features.registry import Registry, Resolved, definition_hash

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationResult:
    dataset: FeatureDataset
    reused: bool
    elapsed_seconds: float


def load_sources(
    session: Session, request: GenerationRequest, cutoff: datetime, resolved: list[Resolved]
) -> dict[str, list[Observation]]:
    needs_benchmark = any("benchmark_close" in item.definition.inputs for item in resolved)
    symbols = sorted(set(request.tickers + ([request.benchmark] if needs_benchmark else [])))
    assets = {
        asset.ticker: asset
        for asset in session.scalars(select(Asset).where(Asset.ticker.in_(symbols)))
    }
    if set(request.tickers) - assets.keys():
        raise FeatureError(
            "unknown_asset", "Ingest requested assets before calculating features", 404
        )
    ranked = (
        select(
            MarketPrice.id,
            func.row_number()
            .over(
                partition_by=(MarketPrice.asset_id, MarketPrice.session_date),
                order_by=MarketPrice.revision_no.desc(),
            )
            .label("rank"),
        )
        .where(
            MarketPrice.asset_id.in_([asset.id for asset in assets.values()]),
            MarketPrice.provider == request.provider,
            MarketPrice.session_date.between(date(2000, 1, 1), request.end),
            MarketPrice.available_at <= cutoff,
            MarketPrice.ingested_at <= cutoff,
        )
        .subquery()
    )
    # One bounded query resolves revisions across all selected assets/benchmark together.
    prices = list(
        session.scalars(
            select(MarketPrice)
            .join(ranked, ranked.c.id == MarketPrice.id)
            .where(ranked.c.rank == 1)
            .order_by(MarketPrice.asset_id, MarketPrice.session_date)
            .limit(MAX_INPUT_ROWS + 1)
        )
    )
    if len(prices) > MAX_INPUT_ROWS:
        raise FeatureError("resource_limit", "Source snapshot exceeds the input-row budget")
    tickers_by_id = {asset.id: asset.ticker for asset in assets.values()}
    result: dict[str, list[Observation]] = {ticker: [] for ticker in symbols}
    for row in prices:
        try:
            bar = PriceBar(
                ticker=tickers_by_id[row.asset_id],
                session_date=row.session_date,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                adjusted_close=row.adjusted_close,
                available_at=row.available_at,
                provider=row.provider,
                is_synthetic=row.is_synthetic,
                availability_kind=cast(AvailabilityKind, row.availability_kind),
                session_close_at=row.session_close_at,
                calendar=row.calendar,
                adjustment_status=cast(
                    Literal["not_supplied", "supplied", "unknown"], row.adjustment_status
                ),
                currency=row.currency,
            )
            observation = Observation(
                row.id,
                row.asset_id,
                bar,
                row.ingested_at,
                row.revision_no,
                tuple(row.quality_flags),
            )
        except ValueError:
            raise FeatureError(
                "invalid_source", "Stored source observations failed validation"
            ) from None
        result[bar.ticker].append(observation)
    return result


def source_digest(sources: dict[str, list[Observation]]) -> str:
    return digest(
        {
            ticker: [item.fingerprint() for item in sorted(items, key=lambda x: x.bar.session_date)]
            for ticker, items in sorted(sources.items())
        }
    )


def _bulk(session: Session, model: Any, records: list[dict[str, Any]], batch: int = 1000) -> None:
    for i in range(0, len(records), batch):
        session.execute(insert(model), records[i : i + batch])


def generate(
    sessions: sessionmaker[Session], request: GenerationRequest, registry: Registry | None = None
) -> GenerationResult:
    start_clock = perf_counter()
    registry = registry or Registry()
    resolved = registry.resolve(request.features, list(request.groups))
    cutoff = request.as_of or now()
    metadata = [item.metadata() for item in resolved]
    config = request.model_dump(mode="json", exclude={"as_of", "features", "groups"})
    config["resolved_features"] = metadata
    config_key, definitions_key = digest(config), definition_hash(resolved)
    with sessions() as session:
        sources = load_sources(session, request, cutoff, resolved)
        source_key = source_digest(sources)
        cache_key = digest([config_key, definitions_key, source_key])
        existing = session.scalar(
            select(FeatureDataset).where(FeatureDataset.cache_key == cache_key)
        )
        if existing is not None:
            return GenerationResult(existing, True, perf_counter() - start_clock)
    # Calculations occur outside a write lock. Every input belongs to the frozen cutoff.
    engine = calculate(sources, request, resolved)
    calculation_time = now()
    with sessions.begin() as session:
        lock_order = sorted(sources)
        serialize_writer(session, lock_order[0])
        if session.get_bind().dialect.name == "postgresql":
            for ticker in lock_order[1:]:
                serialize_writer(session, ticker)
        existing = session.scalar(
            select(FeatureDataset).where(FeatureDataset.cache_key == cache_key)
        )
        if existing is not None:
            return GenerationResult(existing, True, perf_counter() - start_clock)
        # Recheck latest inputs under the same locks as ingestion: concurrent source changes
        # cannot produce a misleading "current" dataset. Historical snapshots are retained.
        latest = load_sources(session, request, now(), resolved)
        stale = source_digest(latest) != source_key
        dataset = FeatureDataset(
            cache_key=cache_key,
            configuration_key=config_key,
            source_hash=source_key,
            definition_hash=definitions_key,
            engine_version=ENGINE_VERSION,
            provider=request.provider,
            start_date=request.start,
            end_date=request.end,
            source_as_of=cutoff,
            calculated_at=calculation_time,
            status="stale" if stale else "current",
            invalidated_at=now() if stale else None,
            invalidation_reason="source_snapshot_is_historical" if stale else None,
            configuration=config,
            definitions=metadata,
            columns=engine.columns,
            diagnostics={
                **engine.diagnostics,
                "input_rows": sum(map(len, sources.values())),
                "output_cells": len(engine.rows) * len(engine.columns),
                "compute_seconds": perf_counter() - start_clock,
                "universe_policy": "fixed requested symbols; historical membership unverified",
            },
            row_count=len(engine.rows),
        )
        session.add(dataset)
        session.flush()
        _bulk(
            session,
            FeatureSourceAsset,
            [
                {
                    "dataset_id": dataset.id,
                    "asset_id": frame.asset_id,
                    "ticker": ticker,
                    "role": "selected" if ticker in request.tickers else "benchmark",
                }
                for ticker, frame in engine.frames.items()
            ],
        )
        _bulk(
            session,
            FeatureInput,
            [
                {"dataset_id": dataset.id, "price_id": observation.price_id, "position": position}
                for frame in engine.frames.values()
                for position, observation in frame.observations.items()
            ],
        )
        _bulk(
            session,
            FeatureRow,
            [
                {
                    key: value
                    for key, value in {**row, "dataset_id": dataset.id}.items()
                    if key != "ticker"
                }
                for row in engine.rows
            ],
        )
    log.info("features_generated", extra={"rows": dataset.row_count})
    return GenerationResult(dataset, False, perf_counter() - start_clock)


def get_dataset(
    session: Session, dataset_id: str, allow_stale: bool = False, registry: Registry | None = None
) -> FeatureDataset:
    dataset = session.get(FeatureDataset, dataset_id)
    if dataset is None:
        raise FeatureError("unknown_dataset", "Feature dataset not found", 404)
    if registry is None and any(item["name"].startswith("sent_") for item in dataset.definitions):
        from sentientalpha.sentiment.registry import UnifiedRegistry

        registry = UnifiedRegistry()
    registry = registry or Registry()
    specs = [dict(name=item["name"], parameters=item["parameters"]) for item in dataset.definitions]
    from sentientalpha.features.contracts import FeatureSpec

    try:
        current_hash = definition_hash(registry.resolve([FeatureSpec(**spec) for spec in specs]))
        obsolete = current_hash != dataset.definition_hash
    except FeatureError:
        # Removed definitions remain inspectable, but cannot enter current matrices.
        obsolete = True
    if (dataset.status == "stale" or obsolete) and not allow_stale:
        raise FeatureError(
            "stale_dataset", "Regenerate features; source or calculation definition changed", 409
        )
    return dataset

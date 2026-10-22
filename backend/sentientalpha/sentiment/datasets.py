"""Sentiment generation reuses M2 dataset rows, asset IDs, versions, matrices and timing."""

from datetime import date, datetime, timedelta
from time import perf_counter
from typing import Any, Literal
from uuid import NAMESPACE_DNS, uuid5

from pydantic import Field, model_validator
from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.database.models import Asset, FeatureDataset, FeatureRow, FeatureSourceAsset, now
from sentientalpha.database.sentiment_models import (
    ArticleAssociation,
    NewsArticle,
    NewsCoverage,
    NewsVersion,
    SentimentInference,
    SentimentInput,
)
from sentientalpha.database.session import serialize_writer
from sentientalpha.features.contracts import FeatureError, GenerationRequest, digest
from sentientalpha.features.frames import micros
from sentientalpha.features.registry import definition_hash
from sentientalpha.features.storage import GenerationResult, _bulk
from sentientalpha.sentiment import VERSION
from sentientalpha.sentiment.aggregation import Evidence, feature
from sentientalpha.sentiment.registry import SentimentRegistry


class SentimentGenerationRequest(GenerationRequest):
    news_provider: Literal["federal_reserve", "alphavantage_news", "synthetic_news"]
    model_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    calendar: Literal["XNYS", "weekday"] = "XNYS"
    availability_policy: Literal["observed", "research_assumed"] = "observed"
    feed_delay_seconds: int = Field(default=300, ge=0, le=86400, strict=True)
    lookback_mode: Literal["sessions", "calendar"] = "sessions"
    scope: Literal["security", "sector", "universe", "broad_market"] = "security"
    sector: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def sentiment_bounds(self) -> "SentimentGenerationRequest":
        if self.groups:
            raise ValueError(
                "Select explicit sentiment features; market groups are not sentiment groups"
            )
        if (self.end - self.start).days > 366 or self.end.year > 2034:
            raise ValueError("Sentiment range is at most one year, through 2034")
        if self.availability_policy == "research_assumed" and self.feed_delay_seconds < 60:
            raise ValueError(
                "Assumed delivery needs an explicit nonzero delay of at least 60 seconds"
            )
        if self.scope == "sector" and not self.sector:
            raise ValueError("Sector must be specified")
        return self


def source(
    session: Session, request: SentimentGenerationRequest, cutoff: datetime, first: date
) -> tuple[list[Evidence], list[tuple[datetime, datetime, datetime]], str, dict[str, Any]]:
    assets = {
        a.id: a for a in session.scalars(select(Asset).where(Asset.ticker.in_(request.tickers)))
    }
    if len(assets) != len(request.tickers) and request.scope != "broad_market":
        raise FeatureError(
            "unknown_asset", "Ingest canonical assets before sentiment generation", 404
        )
    if request.scope == "sector":
        assets = {k: a for k, a in assets.items() if a.sector == request.sector}
        if not assets:
            raise FeatureError(
                "unknown_sector", "No selected assets have this explicit sector classification"
            )
    versions = list(
        session.scalars(
            select(NewsVersion)
            .join(NewsArticle)
            .where(
                NewsArticle.provider == request.news_provider,
                NewsVersion.ingested_at <= cutoff,
                NewsVersion.observed_at <= cutoff,
                or_(
                    NewsVersion.published_at
                    >= datetime.combine(first, datetime.min.time(), cutoff.tzinfo),
                    NewsVersion.updated_at
                    >= datetime.combine(first, datetime.min.time(), cutoff.tzinfo),
                    NewsVersion.first_seen_at
                    >= datetime.combine(first, datetime.min.time(), cutoff.tzinfo),
                    NewsVersion.observed_at
                    >= datetime.combine(first, datetime.min.time(), cutoff.tzinfo)
                    if request.availability_policy == "observed"
                    else false(),
                ),
            )
            .order_by(NewsVersion.id)
            .limit(5001)
        )
    )
    if len(versions) > 5000:
        raise FeatureError(
            "news_source_limit", "Narrow source range/provider; maximum 5000 news versions"
        )
    if request.quality_policy == "reject_flagged" and any(v.quality_flags for v in versions):
        raise FeatureError(
            "flagged_news", "Review news quality flags or explicitly allow flagged inputs"
        )
    ids = [v.id for v in versions]
    associations = (
        list(
            session.scalars(
                select(ArticleAssociation).where(ArticleAssociation.version_id.in_(ids))
            )
        )
        if ids
        else []
    )
    predictions = (
        list(
            session.scalars(
                select(SentimentInference)
                .where(
                    SentimentInference.version_id.in_(ids),
                    SentimentInference.model_key == request.model_key,
                    SentimentInference.inferred_at <= cutoff,
                )
                .order_by(SentimentInference.attempt)
            )
        )
        if ids
        else []
    )
    prediction_map = {(p.version_id, p.context_key): p for p in predictions}
    links = (
        {
            a.id: a
            for a in session.scalars(
                select(NewsArticle).where(NewsArticle.id.in_([v.article_id for v in versions]))
            )
        }
        if versions
        else {}
    )
    by_version: dict[str, list[ArticleAssociation]] = {}
    for association in associations:
        if association.asset_id in assets:
            by_version.setdefault(association.version_id, []).append(association)
    evidence = []
    for v in versions:
        base = max(
            v.published_at, v.updated_at or v.published_at, v.first_seen_at or v.published_at
        )
        if v.revision_no > 1 and (v.updated_at is None or v.updated_at <= v.published_at):
            # Publication of the original story cannot timestamp newly discovered corrected text.
            base = max(base, v.observed_at, v.ingested_at)
        available = (
            max(base, v.observed_at) if request.availability_policy == "observed" else base
        ) + timedelta(seconds=request.feed_delay_seconds)
        contexts = (
            [("BROAD", "article", 1.0)]
            if request.scope == "broad_market" and v.scope == "broad_market"
            else [(assets[a.asset_id].ticker, a.id, a.weight) for a in by_version.get(v.id, [])]
            if request.scope != "broad_market"
            else []
        )
        for ticker, context, relevance in contexts:
            p = prediction_map.get((v.id, context))
            unresolved = relevance == 0
            probabilities = None
            if p is not None and p.status == "success":
                probabilities = (
                    float(p.positive or 0),
                    float(p.negative or 0),
                    float(p.neutral or 0),
                )
            evidence.append(
                Evidence(
                    v.id,
                    v.article_id,
                    links[v.article_id].story_id,
                    None if p is None else p.id,
                    v.revision_no,
                    ticker,
                    v.publisher,
                    available,
                    v.ingested_at,
                    v.ingested_at if p is None else p.inferred_at,
                    "unresolved_relevance"
                    if unresolved
                    else "not_scored"
                    if p is None
                    else p.status,
                    probabilities,
                    relevance,
                )
            )
    coverage_rows = list(
        session.scalars(
            select(NewsCoverage).where(
                NewsCoverage.provider == request.news_provider,
                NewsCoverage.known_at <= cutoff,
                NewsCoverage.end_at >= datetime.combine(first, datetime.min.time(), cutoff.tzinfo),
            )
        )
    )
    complete = [
        (c.start_at, c.end_at, c.known_at)
        for c in coverage_rows
        if c.status == "complete" and (not c.tickers or set(request.tickers) <= set(c.tickers))
    ]
    fingerprint = digest(
        {
            "versions": [
                (v.id, v.version_hash, v.ingested_at.isoformat(), v.observed_at.isoformat())
                for v in versions
            ],
            "associations": [
                (a.id, a.asset_id, a.status, a.weight, a.context) for a in associations
            ],
            "inferences": [
                (
                    p.id,
                    p.input_hash,
                    p.status,
                    p.score,
                    p.positive,
                    p.negative,
                    p.neutral,
                    p.inferred_at.isoformat(),
                )
                for p in predictions
            ],
            "coverage": [(c.id, c.status, c.known_at.isoformat()) for c in coverage_rows],
            "entities": [
                (a.id, a.name, a.sector) for a in sorted(assets.values(), key=lambda a: a.id)
            ],
        }
    )
    return (
        evidence,
        complete,
        fingerprint,
        {
            "model_metadata": predictions[0].model_metadata if predictions else None,
            "coverage_runs": len(coverage_rows),
            "observed_entity_tickers": sorted({v.ticker for v in evidence}),
            "unresolved_entity_contexts": sum(v.status == "unresolved_relevance" for v in evidence),
            "complete_coverage_intervals": len(complete),
            "entity_mapping": {
                a.ticker: {"asset_id": a.id, "sector": a.sector, "name": a.name}
                for a in assets.values()
            },
            "is_synthetic": request.news_provider == "synthetic_news",
            "availability_policy": request.availability_policy,
            "historical_universe": (
                "fixed requested cohort and current sector metadata; no historical membership claim"
            ),
        },
    )


def generate_sentiment(
    sessions: sessionmaker[Session], request: SentimentGenerationRequest
) -> GenerationResult:
    clock = perf_counter()
    registry = SentimentRegistry()
    resolved = registry.resolve(request.features)
    if any(
        int(v) > 60
        for item in resolved
        for k, v in item.parameters.items()
        if k in {"window", "baseline", "long_window"}
    ):
        raise FeatureError(
            "sentiment_window_limit", "Initial sentiment windows/baselines are limited to 60"
        )
    history = max(i.warmups["value"] for i in resolved)
    first = max(date(2000, 1, 1), request.start - timedelta(days=history * 3 + 7))
    days = sessions_in_range(request.calendar, first, request.end)
    closes = [session_close(request.calendar, d) for d in days]
    cutoff = request.as_of or now()
    definitions = [i.metadata() for i in resolved]
    config = request.model_dump(mode="json", exclude={"as_of", "features", "groups"})
    config["resolved_features"] = definitions
    config["kind"] = "sentiment"
    config["provider"] = request.news_provider
    config_key = digest(config)
    def_key = definition_hash(resolved)
    columns = sorted(i.key for i in resolved)
    if sum(d >= request.start for d in days) * len(request.tickers) * len(columns) > 1_000_000:
        raise FeatureError("sentiment_cell_limit", "Sentiment request exceeds 1m output cells")
    with sessions() as session:
        evidence, coverage, source_key, diagnostics = source(session, request, cutoff, first)
        key = digest([config_key, def_key, source_key])
        existing = session.scalar(select(FeatureDataset).where(FeatureDataset.cache_key == key))
        if existing is not None:
            return GenerationResult(existing, True, perf_counter() - clock)
        assets = {
            a.ticker: a.id
            for a in session.scalars(select(Asset).where(Asset.ticker.in_(request.tickers)))
        }
    targets = (
        list(request.tickers)
        if request.scope == "security"
        else [
            "SENT.MKT"
            if request.scope == "broad_market"
            else "SENT.SECT"
            if request.scope == "sector"
            else "SENT.UNIV"
        ]
    )
    if request.scope == "sector":
        targets = ["SENT." + digest(request.sector)[:6].upper()]
    rows = []
    input_links = set()
    states = {}
    lineage: dict[str, Any] = {}
    contribution_sets: dict[str, list[str]] = {}
    for ticker in targets:
        selected = (
            [v for v in evidence if v.ticker == ticker] if request.scope == "security" else evidence
        )
        memo: dict[tuple[int, int, int], dict[str, Any]] = {}
        asset_id = assets.get(
            ticker, str(uuid5(NAMESPACE_DNS, "sentientalpha:sentiment:" + ticker))
        )
        assets[ticker] = asset_id
        for i, day in enumerate(days):
            if day < request.start:
                continue
            values = {}
            reasons = {}
            timing = {}
            row_states = {}
            for definition in resolved:
                aggregate = feature(
                    definition, i, closes, selected, coverage, request.lookback_mode, memo
                )
                name = definition.key
                values[name] = aggregate.value
                row_states[name] = aggregate.coverage
                if aggregate.value is None:
                    reasons[name] = aggregate.reason or "undefined_sentiment"
                else:
                    assert aggregate.available_at is not None and aggregate.pipeline_at is not None
                    timing[name] = [
                        micros(aggregate.available_at),
                        micros(aggregate.pipeline_at),
                        max(0, i - definition.warmups["value"] + 1),
                    ]
                for v in aggregate.evidence:
                    for inference_id in v.contributor_ids or (
                        (v.inference_id,) if v.inference_id else ()
                    ):
                        input_links.add((v.version_id, inference_id))
                # Exact cell -> evidence IDs retained separately from M2 dependency positions.
                contribution_ids = sorted(
                    {
                        inference_id
                        for v in aggregate.evidence
                        for inference_id in (
                            v.contributor_ids or ((v.inference_id,) if v.inference_id else ())
                        )
                    }
                )
                contribution_key = digest(contribution_ids)
                contribution_sets.setdefault(contribution_key, contribution_ids)
                lineage[ticker + ":" + str(day) + ":" + name] = contribution_key
            states[ticker + ":" + str(day)] = row_states
            rows.append(
                {
                    "asset_id": asset_id,
                    "session_date": day,
                    "position": i,
                    "market_at": closes[i],
                    "values": values,
                    "reasons": reasons,
                    "timing": timing,
                }
            )
    calculated = now()
    with sessions.begin() as session:
        serialize_writer(session, "sentiment")
        existing = session.scalar(select(FeatureDataset).where(FeatureDataset.cache_key == key))
        if existing is not None:
            return GenerationResult(existing, True, perf_counter() - clock)
        latest = source(session, request, now(), first)[2]
        stale = latest != source_key
        for ticker in targets:
            if session.get(Asset, assets[ticker]) is None:
                session.add(
                    Asset(
                        id=assets[ticker],
                        ticker=ticker,
                        name="Sentiment aggregate (not a tradable asset)",
                        sector=request.sector or "aggregate",
                        currency="USD",
                    )
                )
        config["tickers"] = targets
        dataset = FeatureDataset(
            cache_key=key,
            configuration_key=config_key,
            source_hash=source_key,
            definition_hash=def_key,
            engine_version=VERSION,
            provider=request.news_provider,
            start_date=request.start,
            end_date=request.end,
            source_as_of=cutoff,
            calculated_at=calculated,
            status="stale" if stale else "current",
            invalidated_at=calculated if stale else None,
            invalidation_reason="news_snapshot_historical" if stale else None,
            configuration=config,
            definitions=definitions,
            columns=columns,
            diagnostics={
                **diagnostics,
                "calendar": request.calendar,
                "unclosed_sessions_at_cutoff": [
                    str(day)
                    for day, close in zip(days, closes, strict=True)
                    if day >= request.start and close > cutoff
                ],
                "coverage_states": states,
                "cell_lineage": lineage,
                "contribution_sets": contribution_sets,
                "news_input_versions": len({v.version_id for v in evidence}),
                "aggregation": (
                    "unique story; earliest successful observable representative; "
                    "fixed requested composition"
                ),
                "input_clock": "inputs_ingested_at additionally includes inference completion",
                "processing_seconds": perf_counter() - clock,
            },
            row_count=len(rows),
        )
        session.add(dataset)
        session.flush()
        _bulk(
            session,
            FeatureSourceAsset,
            [
                {
                    "dataset_id": dataset.id,
                    "asset_id": assets[t],
                    "ticker": t,
                    "role": request.scope,
                }
                for t in targets
            ],
        )
        _bulk(session, FeatureRow, [{**r, "dataset_id": dataset.id} for r in rows])
        _bulk(
            session,
            SentimentInput,
            [
                {"dataset_id": dataset.id, "version_id": v, "inference_id": p}
                for v, p in sorted(input_links)
            ],
        )
    return GenerationResult(dataset, False, perf_counter() - clock)

"""Atomic news ingestion, retained corrections, deterministic syndication linking and audits."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.data.contracts import ProviderError
from sentientalpha.database.models import Asset, FeatureDataset, now
from sentientalpha.database.sentiment_models import (
    ArticleAssociation,
    NewsArticle,
    NewsCoverage,
    NewsStory,
    NewsVersion,
    SentimentRun,
)
from sentientalpha.database.session import serialize_writer
from sentientalpha.features.contracts import FeatureError, digest
from sentientalpha.sentiment.contracts import NewsProvider, normalized
from sentientalpha.sentiment.entities import Entity, resolve


def invalidate(session: Session, provider: str) -> None:
    # Conservative: a changed article/model/coverage may affect warmup or a previously empty day.
    for dataset in session.scalars(
        select(FeatureDataset).where(FeatureDataset.status == "current")
    ):
        if dataset.configuration.get("news_provider") == provider:
            dataset.status = "stale"
            dataset.invalidated_at = now()
            dataset.invalidation_reason = "news_or_model_inputs_changed"


def begin_run(
    sessions: sessionmaker[Session], kind: str, provider: str, config: dict[str, Any]
) -> str:
    with sessions.begin() as session:
        run = SentimentRun(kind=kind, provider=provider, configuration=config)
        session.add(run)
        session.flush()
        return run.id


def failed(sessions: sessionmaker[Session], run_id: str, code: str) -> None:
    with sessions.begin() as session:
        run = session.get(SentimentRun, run_id)
        if run is not None:
            run.status = "failed"
            run.completed_at = now()
            run.error_code = code


def ingest_news(
    sessions: sessionmaker[Session],
    provider: NewsProvider,
    start: datetime,
    end: datetime,
    tickers: list[str],
    limit: int = 100,
) -> SentimentRun:
    if (
        start > end
        or end - start > timedelta(days=366)
        or not 1 <= limit <= 1000
        or len(tickers) > 50
    ):
        raise FeatureError("news_bounds", "News request exceeds resource bounds")
    run_id = begin_run(
        sessions,
        "ingestion",
        provider.name,
        {"start": start.isoformat(), "end": end.isoformat(), "tickers": tickers, "limit": limit},
    )
    try:
        batch = provider.fetch(start, end, tickers, limit)
        if len(batch.articles) > limit or any(
            a.provider != provider.name or not start <= a.published_at <= end
            for a in batch.articles
        ):
            raise FeatureError("news_contract", "Provider returned mismatched or oversized news")
        with sessions.begin() as session:
            serialize_writer(session, "sentiment")
            assets = list(session.scalars(select(Asset).limit(1001)))
            if len(assets) > 1000:
                raise FeatureError("entity_limit", "Configure a smaller canonical entity universe")
            by_ticker = {a.ticker: a for a in assets}
            import re

            entities = [
                Entity(
                    a.ticker,
                    a.name,
                    a.sector,
                    (
                        re.sub(
                            r"\b(Inc\.?|Corp\.?|Corporation|Ltd\.?|Co\.?|PLC)\b", "", a.name
                        ).strip(" ,."),
                    ),
                )
                for a in assets
            ]
            inserted = reused = 0
            for item in batch.articles:
                article = session.scalar(
                    select(NewsArticle).where(
                        NewsArticle.provider == provider.name,
                        NewsArticle.external_id == item.external_id,
                    )
                )
                if article is None:
                    same_url = session.scalar(
                        select(NewsArticle)
                        .where(NewsArticle.canonical_url == item.url)
                        .order_by(NewsArticle.id)
                        .limit(1)
                    )
                    duplicate = session.scalar(
                        select(NewsArticle)
                        .join(NewsVersion)
                        .where(
                            NewsVersion.content_hash == item.content_hash,
                            NewsVersion.published_at.between(
                                item.published_at - timedelta(hours=48),
                                item.published_at + timedelta(hours=48),
                            ),
                        )
                        .order_by(NewsArticle.id)
                        .limit(1)
                    )
                    linked = same_url or duplicate
                    if linked is None:
                        story = NewsStory()
                        session.add(story)
                        session.flush()
                        story_id = story.id
                    else:
                        story_id = linked.story_id
                    article = NewsArticle(
                        provider=provider.name,
                        external_id=item.external_id,
                        canonical_url=item.url,
                        original_url=item.original_url,
                        story_id=story_id,
                        dedup_reason="canonical_url"
                        if same_url
                        else "exact_content_48h"
                        if duplicate
                        else "new_story",
                    )
                    session.add(article)
                    session.flush()
                versions = list(
                    session.scalars(
                        select(NewsVersion)
                        .where(NewsVersion.article_id == article.id)
                        .order_by(NewsVersion.revision_no.desc())
                    )
                )
                if versions and versions[0].version_hash == item.version_hash:
                    reused += 1
                    continue
                # Reversions get new revisions; earlier evidence is never overwritten.
                version_hash = digest([item.version_hash, len(versions) + 1])
                version = NewsVersion(
                    article_id=article.id,
                    revision_no=len(versions) + 1,
                    publisher=item.publisher,
                    headline=item.headline,
                    description=item.description,
                    content_hash=item.content_hash,
                    version_hash=version_hash,
                    headline_hash=digest(normalized(item.headline).casefold()),
                    published_at=item.published_at,
                    updated_at=item.updated_at,
                    first_seen_at=item.first_seen_at,
                    event_at=item.event_at,
                    observed_at=item.observed_at,
                    ingested_at=now(),
                    language=item.language,
                    scope=item.scope,
                    is_synthetic=item.is_synthetic,
                    text_rights=item.text_rights,
                    source_metadata={**item.metadata, "provider_version_hash": item.version_hash},
                    quality_flags=list(item.quality_flags),
                )
                # Compare provider hash, not the revision-disambiguated persistence hash.
                if (
                    versions
                    and versions[0].source_metadata.get("provider_version_hash")
                    == item.version_hash
                ):
                    reused += 1
                    continue
                session.add(version)
                session.flush()
                inserted += 1
                for relevant in resolve(item.text, item.tickers, entities):
                    if relevant.ticker not in by_ticker:
                        continue
                    session.add(
                        ArticleAssociation(
                            version_id=version.id,
                            asset_id=by_ticker[relevant.ticker].id,
                            status=relevant.status,
                            weight=relevant.weight,
                            reason=relevant.reason,
                            context=relevant.context,
                        )
                    )
            run = session.get(SentimentRun, run_id)
            assert run is not None
            run.status = "completed"
            run.completed_at = now()
            run.inserted = inserted
            run.reused = reused
            run.diagnostics = batch.diagnostics
            session.add(
                NewsCoverage(
                    run_id=run_id,
                    provider=provider.name,
                    start_at=start,
                    end_at=end,
                    known_at=run.completed_at,
                    status=batch.coverage,
                    tickers=tickers,
                )
            )
            if inserted or batch.coverage == "complete":
                invalidate(session, provider.name)
        return run
    except Exception as exc:
        code = (
            exc.code if isinstance(exc, (FeatureError, ProviderError)) else "news_ingestion_failed"
        )
        failed(sessions, run_id, code)
        raise FeatureError(
            code, "News ingestion failed; inspect its sanitized pipeline audit", 502
        ) from None

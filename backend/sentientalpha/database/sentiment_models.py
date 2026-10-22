"""News versions, relevance, model evidence and feature lineage; no model blobs."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from sentientalpha.database.base import Base, UTCDateTime, new_id, now


class NewsStory(Base):
    __tablename__ = "news_stories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_news_identity"),
        Index("ix_news_url", "canonical_url"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    story_id: Mapped[str] = mapped_column(ForeignKey("news_stories.id"))
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(256))
    original_url: Mapped[str] = mapped_column(String(2000))
    canonical_url: Mapped[str] = mapped_column(String(2000))
    dedup_reason: Mapped[str] = mapped_column(String(64))


class NewsVersion(Base):
    __tablename__ = "news_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "revision_no", name="uq_news_revision"),
        UniqueConstraint("article_id", "version_hash", name="uq_news_version_hash"),
        Index("ix_news_content", "content_hash", "published_at"),
        CheckConstraint(
            "published_at <= observed_at AND observed_at <= ingested_at", name="news_clock_order"
        ),
        CheckConstraint("revision_no > 0", name="news_revision_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(ForeignKey("news_articles.id"))
    revision_no: Mapped[int] = mapped_column(Integer)
    publisher: Mapped[str] = mapped_column(String(200))
    headline: Mapped[str] = mapped_column(String(2000))
    description: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    version_hash: Mapped[str] = mapped_column(String(64))
    headline_hash: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    first_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    event_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    language: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(20))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    text_rights: Mapped[str] = mapped_column(String(40))
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON)
    quality_flags: Mapped[list[str]] = mapped_column(JSON)


class ArticleAssociation(Base):
    __tablename__ = "article_associations"
    __table_args__ = (
        UniqueConstraint("version_id", "asset_id", name="uq_article_asset"),
        CheckConstraint("weight >= 0 AND weight <= 1", name="relevance_weight"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version_id: Mapped[str] = mapped_column(ForeignKey("news_versions.id"))
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    status: Mapped[str] = mapped_column(String(20))
    weight: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(80))
    context: Mapped[str | None] = mapped_column(Text)


class SentimentInference(Base):
    __tablename__ = "sentiment_inferences"
    __table_args__ = (
        UniqueConstraint(
            "version_id", "context_key", "model_key", "attempt", name="uq_sentiment_inference"
        ),
        Index("ix_sentiment_model", "model_key", "input_hash"),
        CheckConstraint(
            (
                "status != 'success' OR (positive IS NOT NULL AND negative IS NOT NULL "
                "AND neutral IS NOT NULL AND score IS NOT NULL "
                "AND positive >= 0 AND positive <= 1 AND negative >= 0 AND negative <= 1 "
                "AND neutral >= 0 AND neutral <= 1 AND abs(positive+negative+neutral-1) < 0.00001 "
                "AND score >= -1 AND score <= 1 AND abs(score-positive+negative)<0.00001)"
            ),
            name="probability_distribution",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version_id: Mapped[str] = mapped_column(ForeignKey("news_versions.id"))
    context_key: Mapped[str] = mapped_column(String(36))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    model_key: Mapped[str] = mapped_column(String(64))
    model_metadata: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    inferred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(32))
    positive: Mapped[float | None] = mapped_column(Float)
    negative: Mapped[float | None] = mapped_column(Float)
    neutral: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)


class SentimentRun(Base):
    __tablename__ = "sentiment_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    reused: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))


class NewsCoverage(Base):
    __tablename__ = "news_coverage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("sentiment_runs.id"))
    provider: Mapped[str] = mapped_column(String(40))
    start_at: Mapped[datetime] = mapped_column(UTCDateTime())
    end_at: Mapped[datetime] = mapped_column(UTCDateTime())
    known_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    status: Mapped[str] = mapped_column(String(20))
    tickers: Mapped[list[str]] = mapped_column(JSON)
    __table_args__ = (
        CheckConstraint("start_at <= end_at", name="news_coverage_range"),
        Index("ix_news_coverage", "provider", "start_at", "end_at"),
    )


class SentimentInput(Base):
    __tablename__ = "sentiment_inputs"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("feature_datasets.id"), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("news_versions.id"), primary_key=True)
    inference_id: Mapped[str] = mapped_column(
        ForeignKey("sentiment_inferences.id"), primary_key=True
    )

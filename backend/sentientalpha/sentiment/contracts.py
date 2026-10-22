"""Immutable, validated financial-news contracts with conservative delivery clocks."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sentientalpha.data.contracts import ticker_symbol, utc
from sentientalpha.features.contracts import FeatureError, digest


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def canonical_url(value: str) -> str:
    url = urlsplit(value)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
        raise ValueError("An ordinary public HTTP(S) URL is required")
    query = [
        (k, v)
        for k, v in parse_qsl(url.query)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (url.scheme.lower(), url.netloc.lower(), url.path or "/", urlencode(sorted(query)), "")
    )


@dataclass(frozen=True)
class Article:
    provider: str
    external_id: str
    publisher: str
    url: str
    headline: str
    published_at: datetime
    observed_at: datetime
    original_url: str = ""
    description: str = ""
    tickers: tuple[str, ...] = ()
    updated_at: datetime | None = None
    first_seen_at: datetime | None = None
    event_at: datetime | None = None
    language: str = "en"
    scope: Literal["company", "broad_market"] = "company"
    is_synthetic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_flags: tuple[str, ...] = ()
    text_rights: str = "headline_only"

    def __post_init__(self) -> None:
        for name in ("published_at", "observed_at", "updated_at", "first_seen_at", "event_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, utc(value))
        object.__setattr__(self, "original_url", self.original_url or self.url)
        object.__setattr__(self, "url", canonical_url(self.url))
        object.__setattr__(self, "tickers", tuple(sorted({ticker_symbol(t) for t in self.tickers})))
        if (
            not self.provider
            or len(self.provider) > 40
            or not self.external_id
            or len(self.external_id) > 256
        ):
            raise ValueError("Provider identity is required and bounded")
        if (
            len(self.headline) > 2000
            or len(self.description) > 16000
            or len(self.publisher) > 200
            or len(self.url) > 2000
        ):
            raise ValueError("News text/metadata exceeds resource bounds")
        if self.published_at > self.observed_at or (
            self.updated_at is not None
            and (self.updated_at < self.published_at or self.updated_at > self.observed_at)
        ):
            raise ValueError("Publication/update clocks are inconsistent with observation")
        if self.first_seen_at is not None and self.first_seen_at > self.observed_at:
            raise ValueError("Provider first-seen is in the future")
        if self.description and self.text_rights not in {
            "public_domain_feed",
            "licensed_excerpt",
            "synthetic",
        }:
            raise ValueError("Description retention requires explicit permitted rights")
        if self.is_synthetic != (self.provider == "synthetic_news"):
            raise ValueError("Synthetic provenance must be explicit")

    @property
    def text(self) -> str:
        return normalized(self.headline + (". " + self.description if self.description else ""))

    @property
    def content_hash(self) -> str:
        return digest({"text": self.text, "language": self.language})

    @property
    def version_hash(self) -> str:
        return digest(
            {
                "content": self.content_hash,
                "publication": self.published_at.isoformat(),
                "update": None if self.updated_at is None else self.updated_at.isoformat(),
                "tags": self.tickers,
                "scope": self.scope,
                "rights": self.text_rights,
                "first_seen": None
                if self.first_seen_at is None
                else self.first_seen_at.isoformat(),
                "event": None if self.event_at is None else self.event_at.isoformat(),
                "quality_flags": self.quality_flags,
                "publisher": self.publisher,
                "url": self.url,
            }
        )

    def availability(self, policy: str, delay: int) -> datetime:
        if (
            policy not in {"observed", "research_assumed"}
            or type(delay) is not int
            or not 0 <= delay <= 86400
        ):
            raise ValueError(
                "Availability requires an explicit known policy and nonnegative bounded delay"
            )
        base = max(
            self.published_at,
            self.updated_at or self.published_at,
            self.first_seen_at or self.published_at,
        )
        return (
            max(base, self.observed_at) + timedelta(seconds=delay)
            if policy == "observed"
            else base + timedelta(seconds=delay)
        )


@dataclass(frozen=True)
class NewsBatch:
    articles: list[Article]
    coverage: Literal["complete", "snapshot", "partial"] = "snapshot"
    diagnostics: dict[str, Any] = field(default_factory=dict)


class NewsProvider(Protocol):
    name: str

    def fetch(
        self, start: datetime, end: datetime, tickers: list[str], limit: int
    ) -> NewsBatch: ...


class NewsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["federal_reserve", "alphavantage_news"]
    start: datetime
    end: datetime
    tickers: list[str] = Field(default_factory=list, max_length=50)
    max_articles: int = Field(default=100, ge=1, le=1000, strict=True)

    @field_validator("start", "end")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, value: list[str]) -> list[str]:
        return sorted({ticker_symbol(t) for t in value})

    @model_validator(mode="after")
    def range(self) -> "NewsRequest":
        if self.start > self.end or self.end - self.start > timedelta(days=366):
            raise ValueError("News range must be chronological and at most a year")
        return self


@dataclass(frozen=True)
class Prediction:
    positive: float
    negative: float
    neutral: float
    tokens: int
    truncated: bool

    def __post_init__(self) -> None:
        import math

        p = (self.positive, self.negative, self.neutral)
        if any(not math.isfinite(x) or not 0 <= x <= 1 for x in p) or abs(sum(p) - 1) > 1e-5:
            raise FeatureError(
                "invalid_probabilities", "Model did not return a probability distribution"
            )

    @property
    def score(self) -> float:
        return self.positive - self.negative

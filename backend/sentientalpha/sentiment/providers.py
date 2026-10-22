"""Bounded public-feed and authenticated news adapters. No full-page scraping."""

import json
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sentientalpha.data.contracts import ProviderError
from sentientalpha.features.contracts import digest
from sentientalpha.sentiment.contracts import Article, NewsBatch, canonical_url


def download(
    url: str, opener: Callable[..., Any] = urlopen, sleeper: Callable[[float], None] = time.sleep
) -> bytes:
    for attempt in range(3):
        try:
            with opener(
                Request(url, headers={"User-Agent": "SentientAlpha/0.3 local financial research"}),
                timeout=15,
            ) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ProviderError("oversized_response", "News response exceeded byte budget")
            return data
        except HTTPError as exc:
            status = exc.code
            retry = exc.headers.get("Retry-After", "") if exc.headers else ""
            exc.close()
            if status not in {429, 500, 502, 503, 504} or attempt == 2:
                raise ProviderError(
                    "news_http_error", "News provider unavailable or rate limited"
                ) from None
            try:
                wait = float(retry)
            except ValueError:
                if retry:
                    try:
                        wait = (parsedate_to_datetime(retry) - datetime.now(UTC)).total_seconds()
                    except (ValueError, TypeError):
                        raise ProviderError(
                            "news_rate_limit", "Unrecognized retry deadline; retry later"
                        ) from None
                else:
                    wait = 2**attempt
            if wait > 30:
                raise ProviderError(
                    "news_rate_limit", "Provider requested a long retry; retry later"
                ) from None
            sleeper(max(0, wait))
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise ProviderError("news_network_error", "News provider unavailable") from None
            sleeper(float(2**attempt))
    raise ProviderError("news_network_error", "News provider unavailable")


class FederalReserveProvider:
    name = "federal_reserve"
    URL = "https://www.federalreserve.gov/feeds/press_all.xml"

    def __init__(
        self,
        *,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.opener, self.sleeper, self.clock = opener, sleeper, clock

    def fetch(self, start: datetime, end: datetime, tickers: list[str], limit: int) -> NewsBatch:
        if tickers:
            raise ProviderError(
                "news_scope", "Federal Reserve feed is broad-market only; use no ticker filter"
            )
        raw = download(self.URL, self.opener, self.sleeper)
        return self.parse(raw, start, end, self.clock(), limit)

    @staticmethod
    def parse(
        raw: bytes, start: datetime, end: datetime, observed: datetime, limit: int
    ) -> NewsBatch:
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ProviderError("unsafe_xml", "XML entities are unsupported")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            raise ProviderError("invalid_news_xml", "News feed is malformed") from None
        articles = []
        rejected = 0
        for item in root.findall(".//item")[:1000]:
            try:
                pub = parsedate_to_datetime(item.findtext("pubDate") or "")
                if not start <= pub <= end:
                    continue
                url = item.findtext("link") or ""
                articles.append(
                    Article(
                        provider="federal_reserve",
                        external_id=item.findtext("guid") or url,
                        publisher="Federal Reserve Board",
                        url=url,
                        headline=item.findtext("title") or "",
                        published_at=pub,
                        observed_at=observed,
                        scope="broad_market",
                        text_rights="public_domain_feed",
                        metadata={
                            "feed": FederalReserveProvider.URL,
                            "analysis_scope": "headline_only",
                        },
                    )
                )
            except (ValueError, TypeError):
                rejected += 1
        articles = sorted(articles, key=lambda a: (a.published_at, a.external_id))
        return NewsBatch(
            articles[:limit],
            "snapshot",
            {
                "rejected_items": rejected,
                "truncated": len(articles) > limit,
                "historical_coverage": "current RSS snapshot; not complete historical coverage",
            },
        )


class AlphaVantageNewsProvider:
    name = "alphavantage_news"

    def __init__(
        self,
        key: str,
        *,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not key:
            raise ProviderError("missing_key", "ALPHA_VANTAGE_API_KEY is required")
        self.key, self.opener, self.sleeper, self.clock = key, opener, sleeper, clock

    def fetch(self, start: datetime, end: datetime, tickers: list[str], limit: int) -> NewsBatch:
        if self.key == "demo":
            if tickers not in ([], ["AAPL"]):
                raise ProviderError(
                    "public_demo_scope", "Public demo verification is limited to AAPL"
                )
            demo_params = {"function": "NEWS_SENTIMENT", "tickers": "AAPL", "apikey": "demo"}
            raw = download(
                "https://www.alphavantage.co/query?" + urlencode(demo_params),
                self.opener,
                self.sleeper,
            )
            try:
                payload = json.loads(raw)
            except ValueError:
                raise ProviderError("invalid_news_json", "News response is malformed") from None
            items = self.parse(payload, self.clock())
            items = [a for a in items if start <= a.published_at <= end]
            return NewsBatch(
                sorted(items, key=lambda a: (a.published_at, a.external_id))[:limit],
                "snapshot",
                {
                    "public_demo": True,
                    "pages": 1,
                    "historical_coverage": (
                        "current public demo snapshot; date range is a local filter, "
                        "not historical entitlement"
                    ),
                    "provider_sentiment_ignored": True,
                },
            )
        # API has no cursor: page backwards in bounded date partitions, with an overlap dedup.
        articles: dict[str, Article] = {}
        cursor = end
        pages = 0
        saturated = False
        while cursor >= start and len(articles) < limit and pages < 5:
            params = {
                "function": "NEWS_SENTIMENT",
                "apikey": self.key,
                "time_from": start.strftime("%Y%m%dT%H%M"),
                "time_to": cursor.strftime("%Y%m%dT%H%M"),
                "sort": "LATEST",
                "limit": min(100, limit),
            }
            if tickers:
                params["tickers"] = ",".join(tickers)
            raw = download(
                "https://www.alphavantage.co/query?" + urlencode(params), self.opener, self.sleeper
            )
            try:
                payload = json.loads(raw)
            except ValueError:
                raise ProviderError("invalid_news_json", "News response is malformed") from None
            batch = self.parse(payload, self.clock())
            pages += 1
            for article in batch:
                if start <= article.published_at <= end:
                    articles.setdefault(article.external_id, article)
            if len(batch) < int(str(params["limit"])) or not batch:
                break
            next_cursor = min(a.published_at for a in batch) - timedelta(minutes=1)
            # Minute-granular API can omit saturated boundary minutes; never declare completeness.
            if next_cursor >= cursor:
                break
            cursor = next_cursor
            saturated = True
        return NewsBatch(
            sorted(articles.values(), key=lambda a: (a.published_at, a.external_id))[:limit],
            "partial" if saturated else "snapshot",
            {"pages": pages, "minute_boundary_risk": saturated, "provider_sentiment_ignored": True},
        )

    @staticmethod
    def parse(payload: Any, observed: datetime) -> list[Article]:
        if not isinstance(payload, dict) or any(
            k in payload for k in ("Note", "Information", "Error Message")
        ):
            raise ProviderError("news_entitlement", "News access/quota unavailable")
        if not isinstance(payload.get("feed"), list):
            raise ProviderError("invalid_news_schema", "News feed is missing")
        result = []
        try:
            for row in payload["feed"][:1000]:
                pub = datetime.strptime(row["time_published"], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
                url = row["url"]
                # Retain headlines only; excerpts/full articles require separate rights.
                result.append(
                    Article(
                        provider="alphavantage_news",
                        external_id=digest(canonical_url(url)),
                        publisher=row["source"],
                        url=url,
                        headline=row["title"],
                        published_at=pub,
                        observed_at=observed,
                        tickers=tuple(
                            t["ticker"]
                            for t in row.get("ticker_sentiment", [])
                            if ":" not in t["ticker"]
                        ),
                        language="en",
                        text_rights="headline_only",
                        metadata={"analysis_scope": "headline_only", "summary_not_retained": True},
                    )
                )
        except (KeyError, ValueError, TypeError):
            raise ProviderError("invalid_news_schema", "News item failed validation") from None
        return result

"""Independent aggregation arithmetic and temporal fixtures; no real model is mocked as verified."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from statistics import mean, variance
from urllib.error import HTTPError, URLError

import numpy as np
import pytest
from sentientalpha.data.contracts import ProviderError
from sentientalpha.features.contracts import FeatureError, FeatureSpec
from sentientalpha.sentiment.aggregation import Evidence, feature, level
from sentientalpha.sentiment.contracts import Article, Prediction, canonical_url
from sentientalpha.sentiment.entities import Entity, resolve
from sentientalpha.sentiment.model import preprocess
from sentientalpha.sentiment.providers import (
    AlphaVantageNewsProvider,
    FederalReserveProvider,
    download,
)
from sentientalpha.sentiment.registry import SENTIMENT_CATALOG, SentimentRegistry
from sentiment_fixtures import article

T = datetime(2024, 1, 2, 20, tzinfo=UTC)


def evidence(index, probabilities=(0.7, 0.1, 0.2), when=None, **kwargs):
    return Evidence(
        str(index),
        str(index),
        str(index),
        str(index),
        1,
        "AAPL",
        "Synthetic",
        when or T - timedelta(hours=1),
        T,
        T,
        "success",
        probabilities,
        1.0,
        **kwargs,
    )


@pytest.mark.parametrize(
    "p", [(0.5, 0.5, 0.5), (-0.1, 0.2, 0.9), (float("nan"), 0.1, 0.9), (float("inf"), 0, 0)]
)
def test_probability_validation(p):
    with pytest.raises(FeatureError):
        Prediction(*p, 5, False)


def test_score_and_preprocessing():
    assert Prediction(0.2, 0.7, 0.1, 5, False).score == pytest.approx(-0.5)
    assert preprocess("  Ｐrofit\n grew\t 10%  ") == "Profit grew 10%"
    assert preprocess("   ") == ""


def test_news_contract_missing_publication_empty_and_rights():
    with pytest.raises(TypeError):
        Article(
            provider="x",
            external_id="x",
            publisher="x",
            url="https://example.com",
            headline="x",
            observed_at=T,
        )
    assert article(headline="").text == ""
    with pytest.raises(ValueError):
        replace(article(), description="Restricted article", text_rights="headline_only")
    with pytest.raises(ValueError):
        replace(article(), published_at=T + timedelta(days=1))
    with pytest.raises(ValueError):
        replace(article(), updated_at=T + timedelta(days=2))
    with pytest.raises(ValueError):
        replace(article(), is_synthetic=False)


def test_news_clocks_after_hours_weekend_and_delay():
    friday = datetime(2024, 1, 5, 20, tzinfo=UTC)
    late = article(published=friday + timedelta(hours=2), observed=friday + timedelta(hours=3))
    weekend = article(
        published=friday + timedelta(days=1), observed=friday + timedelta(days=1, hours=2)
    )
    assert late.availability("observed", 300) > friday
    assert weekend.availability("observed", 300) > friday
    backfill = replace(late, observed_at=T + timedelta(days=365))
    assert backfill.availability("observed", 300) > backfill.published_at + timedelta(days=300)
    assert backfill.availability("research_assumed", 300) == late.published_at + timedelta(
        minutes=5
    )


def test_url_normalization_and_boundaries():
    assert (
        canonical_url("https://EXAMPLE.com/a?utm_source=x&b=2#fragment")
        == "https://example.com/a?b=2"
    )
    for bad in ["file:///tmp/a", "https://secret:password@example.com", "javascript:alert(1)"]:
        with pytest.raises(ValueError):
            canonical_url(bad)


def test_entity_alias_word_ticker_and_comparison():
    entities = [
        Entity("AAPL", "Apple Inc.", "Technology", ("Apple",)),
        Entity("MSFT", "Microsoft", "Technology"),
        Entity("IT", "Gartner", "Technology"),
    ]
    assert resolve("It was a good day", (), entities) == []
    matched = resolve("Apple reports a profit", (), entities)
    assert matched[0].ticker == "AAPL" and matched[0].weight == 1
    compared = resolve("Apple outperforms Microsoft", ("AAPL", "MSFT"), entities)
    assert all(item.status == "unresolved" and item.context is None for item in compared)
    separate = resolve(
        "Apple reports a profit. Microsoft reports a loss.", ("AAPL", "MSFT"), entities
    )
    assert all(item.status == "resolved" for item in separate)
    assert separate[0].context != separate[1].context
    assert resolve("$IT reports earnings", (), entities)[0].ticker == "IT"


def test_mean_variance_probabilities_fractions_independent():
    items = [
        evidence(1, (0.7, 0.1, 0.2)),
        evidence(2, (0.1, 0.7, 0.2)),
        evidence(3, (0.1, 0.1, 0.8)),
    ]
    result = level(items, T - timedelta(days=1), T, 3, False, None)
    scores = [0.6, -0.6, 0]
    assert result["mean"].value == pytest.approx(mean(scores))
    assert result["dispersion"].value == pytest.approx(variance(scores))
    assert result["std"].value == pytest.approx(np.sqrt(variance(scores)))
    assert result["positive_fraction"].value == pytest.approx(1 / 3)
    assert result["disagreement"].value == pytest.approx(4 / 9)
    assert result["strong_fraction"].value == pytest.approx(2 / 3)
    assert result["positive_probability"].value == pytest.approx(0.3)
    assert result["neutral_probability"].value == pytest.approx(0.4)


def test_weighted_mean_and_syndication_counts():
    a = evidence(1)
    b = replace(evidence(2, (0.1, 0.7, 0.2)), relevance=0.5)
    result = level([a, b], T - timedelta(days=1), T, 2, False, None)
    assert result["weighted_mean"].value == pytest.approx((0.6 - 0.6 * 0.5) / 1.5)
    duplicate = replace(
        a,
        article_id="syndicated",
        inference_id="dup",
        publisher="Other",
        eligible_at=a.eligible_at + timedelta(minutes=1),
    )
    result = level([a, duplicate], T - timedelta(days=1), T, 1, False, None)
    assert result["unique_story_count"].value == 1
    assert result["article_count"].value == 2 and result["unique_publisher_count"].value == 2
    assert result["mean"].value == pytest.approx(0.6)


def test_revision_does_not_replace_past_and_future_articles_not_used():
    old = evidence(1)
    new = replace(
        old,
        version_id="revision",
        revision=2,
        eligible_at=T + timedelta(days=1),
        probabilities=(0.1, 0.7, 0.2),
    )
    before = level([old, new], T - timedelta(days=1), T, 1, False, None)
    assert before["mean"].value == pytest.approx(0.6)
    after = level([old, new], T - timedelta(days=1), T + timedelta(days=1), 1, False, None)
    assert after["mean"].value == pytest.approx(-0.6)
    future = evidence(2, when=T + timedelta(days=5))
    assert (
        level([old, future], T - timedelta(days=1), T, 1, False, None)["unique_story_count"].value
        == 1
    )


def test_no_news_neutral_missing_coverage_and_failed_inference_differ():
    unknown = level([], T - timedelta(days=1), T, 1, False, None)
    known = level([], T - timedelta(days=1), T, 1, True, T)
    neutral = level([evidence(1, (0.1, 0.1, 0.8))], T - timedelta(days=1), T, 1, False, None)
    failure = level(
        [replace(evidence(1), status="inference_failed", probabilities=None)],
        T - timedelta(days=1),
        T,
        1,
        False,
        None,
    )
    assert (
        unknown["news_volume"].value is None
        and unknown["mean"].reason == "missing_provider_coverage"
    )
    assert (
        known["news_volume"].value == 0
        and known["mean"].value is None
        and known["mean"].reason == "no_news_observed"
    )
    assert neutral["mean"].value == 0 and neutral["neutral_fraction"].value == 1
    assert failure["mean"].reason == "inference_failure_or_unsupported_text"
    assert (
        level([evidence(1)], T - timedelta(days=1), T, 3, False, None)["mean"].reason
        == "insufficient_articles"
    )


@pytest.mark.parametrize("definition", SENTIMENT_CATALOG, ids=lambda d: d.name)
def test_every_sentiment_feature_prefix_invariant(definition):
    dates = [T + timedelta(days=i) for i in range(100)]
    items = [
        evidence(
            i,
            (0.6 if i % 2 else 0.1, 0.1 if i % 2 else 0.6, 0.3),
            when=dates[i] - timedelta(hours=1),
        )
        for i in range(100)
    ]
    resolved = SentimentRegistry().resolve(
        [FeatureSpec(name=definition.name, parameters={"min_articles": 1})]
    )[0]
    coverage = [(T - timedelta(days=20), dates[-1], T)]
    before = [
        feature(resolved, i, dates[:70], items[:70], coverage, "sessions", {}) for i in range(70)
    ]
    after = [feature(resolved, i, dates, items, coverage, "sessions", {}) for i in range(70)]
    assert before == after


def test_momentum_surprise_acceleration_and_zero_baseline():
    dates = [T + timedelta(days=i) for i in range(50)]
    items = [
        evidence(i, (0.3 + i * 0.01, 0.2, 0.5 - i * 0.01), when=dates[i] - timedelta(hours=1))
        for i in range(50)
    ]
    coverage = [(T - timedelta(days=30), dates[-1], T)]
    for name, expected in [
        ("sent_momentum", 0.01),
        ("sent_change", 0.01),
        ("sent_acceleration", 0),
        ("sent_surprise", 0.02),
    ]:
        params = {"window": 1, "min_articles": 1}
        if name == "sent_surprise":
            params.update(baseline=3, min_history=3)
        item = SentimentRegistry().resolve([FeatureSpec(name=name, parameters=params)])[0]
        assert feature(item, 30, dates, items, coverage, "sessions", {}).value == pytest.approx(
            expected
        )
    item = SentimentRegistry().resolve(
        [
            FeatureSpec(
                name="sent_volume_zscore", parameters={"window": 1, "baseline": 3, "min_history": 3}
            )
        ]
    )[0]
    assert feature(item, 30, dates, items, coverage, "sessions", {}).value is None


def test_provider_rss_schema_and_missing_fields():
    raw = (
        b"<rss><channel><item><title>Financial fixture</title>"
        b"<link>https://example.com/a</link>"
        b"<pubDate>Tue, 02 Jan 2024 15:00:00 GMT</pubDate></item>"
        b"<item><title>Missing time</title></item></channel></rss>"
    )
    batch = FederalReserveProvider.parse(raw, T - timedelta(days=1), T, T, 10)
    assert (
        len(batch.articles) == 1
        and batch.coverage == "snapshot"
        and batch.diagnostics["rejected_items"] == 1
    )
    assert batch.articles[0].scope == "broad_market" and not batch.articles[0].is_synthetic
    for invalid in [b"<!DOCTYPE rss><rss/>", b"broken"]:
        with pytest.raises(ProviderError):
            FederalReserveProvider.parse(invalid, T, T, T, 10)


def test_provider_retries_and_rate_limit():
    calls = []
    waits = []

    def opener(*args, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) < 3:
            raise HTTPError("https://example.com", 429, "limit", {"Retry-After": "2"}, None)
        return BytesIO(b"ok")

    assert download("https://example.com", opener, waits.append) == b"ok"
    assert calls == [15, 15, 15] and waits == [2, 2]

    def broken(*args, **kwargs):
        raise URLError("secret detail")

    with pytest.raises(ProviderError) as caught:
        download("https://example.com", broken, lambda _: None)
    assert "secret" not in str(caught.value)


def test_alphavantage_schema_and_pagination():
    payload = {
        "feed": [
            {
                "title": "Company earnings",
                "url": "https://example.com/a",
                "source": "Synthetic transport publisher",
                "time_published": "20240102T150000",
                "summary": "Restricted summary",
                "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_score": "0.99"}],
            }
        ]
    }
    result = AlphaVantageNewsProvider.parse(payload, T)
    assert len(result) == 1 and result[0].description == "" and result[0].tickers == ("AAPL",)
    for bad in [{"Information": "quota"}, {"feed": [{}]}, {}]:
        with pytest.raises(ProviderError):
            AlphaVantageNewsProvider.parse(bad, T)
    import json

    calls = []

    def opener(request, **kwargs):
        calls.append(request.full_url)
        return BytesIO(json.dumps(payload if len(calls) == 1 else {"feed": []}).encode())

    provider = AlphaVantageNewsProvider("NOT A REAL KEY", opener=opener, clock=lambda: T)
    batch = provider.fetch(T - timedelta(days=5), T, [], 2)
    assert len(batch.articles) == 1 and len(calls) == 1


def test_multi_entity_aggregate_keeps_both_contexts_and_uncertainty():
    a = evidence(1, (0.7, 0.1, 0.2))
    b = replace(a, ticker="MSFT", inference_id="msft-context", probabilities=(0.1, 0.7, 0.2))
    result = level([a, b], T - timedelta(days=1), T, 1, False, None)
    assert result["mean"].value == pytest.approx(0)
    assert set(result["mean"].evidence[0].contributor_ids) == {"1", "msft-context"}
    uncertain = replace(a, status="unresolved_relevance", probabilities=None, relevance=0)
    assert (
        level([uncertain], T - timedelta(days=1), T, 1, False, None)["mean"].reason
        == "unresolved_entity_relevance"
    )


def test_ambiguous_name_requires_company_or_financial_context():
    entities = [Entity("AAPL", "Apple Inc.", "Technology", ("Apple",))]
    assert resolve("Apple fruit is served at lunch", (), entities) == []
    assert resolve("Apple raises earnings guidance", (), entities)[0].ticker == "AAPL"


def test_after_hours_weekend_session_alignment_and_calendar_lookback():
    from sentientalpha.data.calendar import session_close, sessions_in_range

    dates = [
        session_close("XNYS", d)
        for d in sessions_in_range("XNYS", T.date(), (T + timedelta(days=10)).date())
    ]
    friday_index = next(i for i, d in enumerate(dates) if d.weekday() == 4)
    friday = dates[friday_index]
    weekend = evidence(1, when=friday + timedelta(days=1))
    spec = SentimentRegistry().resolve(
        [FeatureSpec(name="sent_mean", parameters={"window": 1, "min_articles": 1})]
    )[0]
    assert feature(spec, friday_index, dates, [weekend], [], "sessions", {}).value is None
    assert feature(
        spec, friday_index + 1, dates, [weekend], [], "sessions", {}
    ).value == pytest.approx(0.6)
    assert feature(spec, friday_index + 1, dates, [weekend], [], "calendar", {}).value is None
    after_hours = evidence(2, when=friday + timedelta(minutes=30))
    assert feature(spec, friday_index, dates, [after_hours], [], "sessions", {}).value is None
    assert feature(
        spec, friday_index + 1, dates, [after_hours], [], "sessions", {}
    ).value == pytest.approx(0.6)


def test_actual_adapter_pagination_is_bounded_and_moves_backwards():
    import json
    from urllib.parse import parse_qs, urlsplit

    calls = []

    def opener(request, **kwargs):
        calls.append(parse_qs(urlsplit(request.full_url).query))
        if len(calls) == 1:
            feed = [
                {
                    "title": f"Fixture {i}",
                    "url": f"https://example.com/{i}",
                    "source": "Fixture",
                    "time_published": "20240102T150000",
                }
                for i in range(100)
            ]
        else:
            feed = [
                {
                    "title": "Older fixture",
                    "url": "https://example.com/older",
                    "source": "Fixture",
                    "time_published": "20240102T140000",
                }
            ]
        import io

        return io.BytesIO(json.dumps({"feed": feed}).encode())

    provider = AlphaVantageNewsProvider("TEST ONLY", opener=opener, clock=lambda: T)
    batch = provider.fetch(T - timedelta(days=5), T, [], 200)
    assert (
        len(batch.articles) == 101
        and batch.diagnostics["pages"] == 2
        and batch.coverage == "partial"
    )
    assert calls[1]["time_to"][0] < calls[0]["time_to"][0]


def test_public_demo_uses_documented_canonical_url_and_local_date_filter():
    import json
    from io import BytesIO

    seen = []
    payload = {
        "feed": [
            {
                "title": "Company earnings",
                "url": "https://example.com/earnings",
                "source": "Fixture",
                "time_published": "20240102T150000",
            }
        ]
    }

    def opener(request, **kwargs):
        seen.append(request.full_url)
        return BytesIO(json.dumps(payload).encode())

    provider = AlphaVantageNewsProvider("demo", opener=opener, clock=lambda: T)
    batch = provider.fetch(T - timedelta(days=2), T, ["AAPL"], 10)
    assert seen == [
        "https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=AAPL&apikey=demo"
    ]
    assert len(batch.articles) == 1 and batch.coverage == "snapshot"
    assert batch.diagnostics["public_demo"]
    with pytest.raises(ProviderError):
        provider.fetch(T - timedelta(days=2), T, ["IBM"], 10)


def test_exact_constant_score_variance_is_zero_and_zscore_is_null():
    dates = [T + timedelta(days=i) for i in range(50)]
    items = [evidence(i, when=dates[i] - timedelta(hours=1)) for i in range(50)]
    level_values = level(items, T - timedelta(days=1), dates[-1], 3, False, None)
    assert level_values["dispersion"].value == 0 and level_values["std"].value == 0
    spec = SentimentRegistry().resolve(
        [
            FeatureSpec(
                name="sent_zscore",
                parameters={"window": 1, "min_articles": 1, "baseline": 20, "min_history": 5},
            )
        ]
    )[0]
    result = feature(spec, 40, dates, items, [], "sessions", {})
    assert result.value is None and result.reason == "zero_baseline_variance_or_volume"

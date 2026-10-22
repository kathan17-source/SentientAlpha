"""Explicitly synthetic news and TEST DOUBLE probabilities, never production NLP evidence."""

from datetime import UTC, datetime, timedelta

from sentientalpha.features.contracts import digest
from sentientalpha.sentiment.contracts import Article, NewsBatch, Prediction


class ControlledNews:
    name = "synthetic_news"

    def __init__(self, articles, coverage="complete"):
        self.articles = articles
        self.coverage = coverage

    def fetch(self, start, end, tickers, limit):
        return NewsBatch(
            [a for a in self.articles if start <= a.published_at <= end][:limit],
            self.coverage,
            {"synthetic_fixture": True},
        )


class TestModel:
    __test__ = False
    metadata = {
        "model_id": "TEST DOUBLE ONLY",
        "revision": "test-v1",
        "preprocessing": "test",
        "is_test_double": True,
        "probabilities_calibrated": False,
    }

    def __init__(self):
        self.calls = 0

    @property
    def key(self):
        return digest(self.metadata)

    def predict(self, texts):
        self.calls += 1
        return [
            Prediction(0.7, 0.1, 0.2, 10, False)
            if "profit" in t
            else Prediction(0.1, 0.7, 0.2, 10, False)
            if "loss" in t
            else Prediction(0.1, 0.1, 0.8, 10, False)
            for t in texts
        ]


def article(
    index=0, ticker="AAPL", headline="Company profit rises", published=None, observed=None, **kwargs
):
    published = published or datetime(2024, 1, 2, 15, tzinfo=UTC) + timedelta(days=index)
    return Article(
        provider="synthetic_news",
        external_id=f"{ticker}-{index}",
        publisher="Synthetic Financial Fixture",
        url=f"https://example.invalid/news/{ticker}/{index}",
        headline=headline,
        published_at=published,
        observed_at=observed or published + timedelta(minutes=10),
        tickers=(ticker,),
        is_synthetic=True,
        text_rights="synthetic",
        **kwargs,
    )

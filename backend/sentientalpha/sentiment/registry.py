"""Sentiment definitions use the same metadata/parameter/schema contract as M2."""

from sentientalpha.features.contracts import FeatureError, FeatureSpec
from sentientalpha.features.registry import CATALOG, Definition, Registry, Resolved

NAMES = {
    "mean": "Arithmetic mean of eligible unique-story scores",
    "weighted_mean": "Relevance-weighted mean of eligible unique-story scores",
    "positive_probability": "Mean positive model probability",
    "negative_probability": "Mean negative model probability",
    "neutral_probability": "Mean neutral model probability",
    "positive_fraction": "Fraction whose maximum-probability label is positive",
    "negative_fraction": "Fraction whose maximum-probability label is negative",
    "neutral_fraction": "Fraction whose maximum-probability label is neutral",
    "momentum": "Window mean minus mean w sessions earlier",
    "change": "Window mean minus preceding-session window mean",
    "acceleration": "Second difference of window sentiment mean",
    "short_long_difference": "Current window mean minus long-window mean",
    "reversal": "Sign-reversal event of consecutive nonzero window means",
    "dispersion": "Sample score variance, ddof=1",
    "std": "Sample score standard deviation, ddof=1",
    "disagreement": "4 times positive-label fraction times negative-label fraction",
    "strong_fraction": "Fraction with absolute continuous score at least 0.5",
    "article_count": "Observed article identities before syndication deduplication",
    "unique_story_count": "Observed unique stories after deduplication",
    "unique_publisher_count": "Distinct observed publishers",
    "news_volume": "Unique-story volume over the lookback",
    "abnormal_volume": "Window unique-story count minus prior baseline mean count",
    "volume_zscore": "Window unique-story count standardized against prior baseline counts",
    "surprise": "Window mean minus prior baseline mean of window means",
    "zscore": "Window mean standardized against prior baseline window means",
    "abnormal_positive": "Positive part of sentiment surprise",
    "abnormal_negative": "Negative part of sentiment surprise",
    "intensity_adjusted": "Mean times bounded log-volume intensity relative to past baseline",
}


class SentimentDefinition(Definition):
    def warmups(self, parameters: dict[str, int | float]) -> dict[str, int]:
        w = int(parameters["window"])
        name = self.name.removeprefix("sent_")
        extra = (
            w
            if name == "momentum"
            else 1
            if name in {"change", "reversal"}
            else 2
            if name == "acceleration"
            else int(parameters.get("baseline", 0))
        )
        return {"value": max(w + extra, int(parameters.get("long_window", 0)))}


SENTIMENT_CATALOG = [
    SentimentDefinition(
        "sent_" + name,
        "sentiment",
        description,
        {
            "window": 5,
            "min_articles": 3,
            **(
                {"baseline": 20, "min_history": 5}
                if name
                in {
                    "abnormal_volume",
                    "volume_zscore",
                    "surprise",
                    "zscore",
                    "abnormal_positive",
                    "abnormal_negative",
                    "intensity_adjusted",
                }
                else {}
            ),
            **({"long_window": 20} if name == "short_long_difference" else {}),
        },
        inputs=("sentiment_articles", "coverage", "model_probabilities"),
    )
    for name, description in NAMES.items()
]


class SentimentRegistry(Registry):
    def __init__(self) -> None:
        super().__init__([item for item in SENTIMENT_CATALOG])

    def resolve(self, specs: list[FeatureSpec], groups: list[str] | None = None) -> list[Resolved]:
        resolved = super().resolve(specs, groups)
        for item in resolved:
            p = item.parameters
            if "long_window" in p and p["long_window"] <= p["window"]:
                raise FeatureError("sentiment_parameters", "Long window must exceed short window")
            if "min_history" in p and p["min_history"] > p["baseline"]:
                raise FeatureError("sentiment_parameters", "Minimum history cannot exceed baseline")
        return resolved


class UnifiedRegistry(Registry):
    def __init__(self) -> None:
        super().__init__([*CATALOG, *SENTIMENT_CATALOG])

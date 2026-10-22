"""Causal unique-story aggregation, explicit coverage states and trailing statistics."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import cast

import numpy as np

from sentientalpha.features.registry import Resolved


@dataclass(frozen=True)
class Evidence:
    version_id: str
    article_id: str
    story_id: str
    inference_id: str | None
    revision: int
    ticker: str
    publisher: str
    eligible_at: datetime
    ingested_at: datetime
    inferred_at: datetime
    status: str
    probabilities: tuple[float, float, float] | None
    relevance: float
    contributor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Aggregate:
    value: float | None
    reason: str | None
    available_at: datetime | None
    pipeline_at: datetime | None
    evidence: tuple[Evidence, ...]
    coverage: str


def eligible(
    items: list[Evidence], first: datetime, last: datetime
) -> tuple[list[Evidence], int, int]:
    # Resolve latest visible revision per article, never a future corrected version.
    versions: dict[str, Evidence] = {}
    for item in items:
        if item.eligible_at <= last:
            key = item.article_id + ":" + item.ticker
            previous = versions.get(key)
            if previous is None or (item.eligible_at, item.revision, item.version_id) > (
                previous.eligible_at,
                previous.revision,
                previous.version_id,
            ):
                versions[key] = item
    active = [v for v in versions.values() if first < v.eligible_at <= last]
    raw_count = len({v.article_id for v in active})
    publisher_count = len({v.publisher for v in active})
    # One representative per story/entity, preferring earliest observable nonfailed evidence.
    stories: dict[str, list[Evidence]] = {}
    for item in active:
        stories.setdefault(item.story_id, []).append(item)
    selected = []
    for group in stories.values():
        successful = [v for v in group if v.status == "success"]
        candidates = successful or group
        representative = sorted(candidates, key=lambda v: (v.eligible_at, v.article_id, v.ticker))[
            0
        ]
        contexts = [v for v in successful if v.article_id == representative.article_id]
        if len(contexts) > 1:
            probabilities = tuple(
                float(x)
                for x in np.average(
                    [v.probabilities for v in contexts],
                    axis=0,
                    weights=[v.relevance for v in contexts],
                )
            )
            representative = replace(
                representative,
                probabilities=cast(tuple[float, float, float], probabilities),
                ingested_at=max(v.ingested_at for v in contexts),
                inferred_at=max(v.inferred_at for v in contexts),
                contributor_ids=tuple(sorted(v.inference_id for v in contexts if v.inference_id)),
            )
        selected.append(representative)
    return selected, raw_count, publisher_count


def level(
    items: list[Evidence],
    first: datetime,
    last: datetime,
    minimum: int,
    complete: bool,
    coverage_clock: datetime | None,
) -> dict[str, Aggregate]:
    selected, raw, publishers = eligible(items, first, last)
    good = [v for v in selected if v.status == "success" and v.probabilities is not None]
    available = max((v.eligible_at for v in selected), default=coverage_clock)
    pipeline = max((max(v.ingested_at, v.inferred_at) for v in selected), default=coverage_clock)
    if complete and coverage_clock is not None:
        available = max(available or coverage_clock, coverage_clock)
        pipeline = max(pipeline or coverage_clock, coverage_clock)
    coverage = (
        "complete" if complete else "partial_observed" if selected else "missing_provider_coverage"
    )

    def output(value: float | None, reason: str | None = None) -> Aggregate:
        return Aggregate(value, reason, available, pipeline, tuple(selected), coverage)

    if not selected:
        reason = "no_news_observed" if complete else "missing_provider_coverage"
    elif not good:
        reason = (
            "unresolved_entity_relevance"
            if all(v.status == "unresolved_relevance" for v in selected)
            else "inference_failure_or_unsupported_text"
        )
    elif len(good) < minimum:
        reason = "insufficient_articles"
    else:
        reason = None
    counts = {
        "article_count": raw,
        "unique_story_count": len(selected),
        "unique_publisher_count": publishers,
        "news_volume": len(selected),
    }
    result = {
        k: output(float(v)) if selected or complete else output(None, "missing_provider_coverage")
        for k, v in counts.items()
    }
    scores = np.array([p[0] - p[1] for v in good if (p := v.probabilities) is not None])
    probabilities = np.array([v.probabilities for v in good])
    for name in (
        "mean",
        "weighted_mean",
        "positive_probability",
        "negative_probability",
        "neutral_probability",
        "positive_fraction",
        "negative_fraction",
        "neutral_fraction",
        "dispersion",
        "std",
        "disagreement",
        "strong_fraction",
    ):
        if reason:
            result[name] = output(None, reason)
            continue
        labels = np.argmax(probabilities, axis=1)
        fraction = [float(np.mean(labels == i)) for i in range(3)]
        values: dict[str, float | None] = {
            "mean": float(np.mean(scores)),
            "weighted_mean": float(np.average(scores, weights=[v.relevance for v in good])),
            "positive_probability": float(np.mean(probabilities[:, 0])),
            "negative_probability": float(np.mean(probabilities[:, 1])),
            "neutral_probability": float(np.mean(probabilities[:, 2])),
            "positive_fraction": fraction[0],
            "negative_fraction": fraction[1],
            "neutral_fraction": fraction[2],
            "dispersion": float(np.var(scores, ddof=1)) if len(scores) > 1 else None,
            "std": float(np.std(scores, ddof=1)) if len(scores) > 1 else None,
            "disagreement": 4 * fraction[0] * fraction[1],
            "strong_fraction": float(np.mean(np.abs(scores) >= 0.5)),
        }
        if name in {"dispersion", "std"} and len(scores) > 1 and np.ptp(scores) == 0:
            values[name] = 0.0
        value = values[name]
        result[name] = output(value, None if value is not None else "insufficient_articles")
    return result


def feature(
    item: Resolved,
    index: int,
    dates: list[datetime],
    items: list[Evidence],
    coverage: list[tuple[datetime, datetime, datetime]],
    mode: str,
    memo: dict[tuple[int, int, int], dict[str, Aggregate]],
) -> Aggregate:
    p = item.parameters
    window = int(p["window"])
    minimum = int(p["min_articles"])

    def at(i: int, w: int = window) -> dict[str, Aggregate]:
        key = (i, w, minimum)
        if key in memo:
            return memo[key]
        if i < 0 or i - w + 1 < 0:
            empty = Aggregate(
                None, "insufficient_history", None, None, (), "insufficient_historical_coverage"
            )
            return {n: empty for n in ("mean", "news_volume")}
        last = dates[i]
        first = (
            dates[i - w]
            if mode == "sessions" and i >= w
            else (last - timedelta(days=w) if mode == "calendar" else dates[0] - timedelta(days=1))
        )
        covering = [known for start, end, known in coverage if start <= first and end >= last]
        result = level(
            items, first, last, minimum, bool(covering), max(covering) if covering else None
        )
        memo[key] = result
        return result

    name = item.definition.name.removeprefix("sent_")
    if index < item.warmups["value"] - 1:
        return Aggregate(
            None, "insufficient_history", None, None, (), "insufficient_historical_coverage"
        )
    current = at(index)
    base = current["news_volume" if name in {"abnormal_volume", "volume_zscore"} else "mean"]
    if name in current:
        return current[name]
    dependencies = [base]
    value = None
    reason = base.reason
    if name in {"momentum", "change", "acceleration", "reversal", "short_long_difference"}:
        other = (
            at(index - window if name == "momentum" else index, int(p["long_window"]))["mean"]
            if name == "short_long_difference"
            else at(index - (window if name == "momentum" else 1))["mean"]
        )
        dependencies.append(other)
        if base.value is not None and other.value is not None:
            if name == "reversal":
                value = float(np.sign(base.value)) if base.value * other.value < 0 else 0.0
            else:
                value = base.value - other.value
            if name == "acceleration":
                third = at(index - 2)["mean"]
                dependencies.append(third)
                value = None if third.value is None else base.value - 2 * other.value + third.value
        reason = None if value is not None else "insufficient_sentiment_history"
    else:
        baseline = int(p["baseline"])
        history = [
            at(j)[
                "news_volume"
                if name in {"abnormal_volume", "volume_zscore", "intensity_adjusted"}
                else "mean"
            ]
            for j in range(index - baseline, index)
        ]
        valid = [v for v in history if v.value is not None]
        dependencies += valid
        if base.value is not None and len(valid) >= int(p["min_history"]):
            previous = np.array([v.value for v in valid], dtype=float)
            center = float(np.mean(previous))
            spread = 0.0 if np.ptp(previous) == 0 else float(np.std(previous, ddof=1))
            difference = base.value - center
            if name in {"volume_zscore", "zscore"}:
                value = difference / spread if spread > 0 else None
            elif name == "abnormal_positive":
                value = max(0.0, difference)
            elif name == "abnormal_negative":
                value = min(0.0, difference)
            elif name == "intensity_adjusted":
                volume = current["news_volume"]
                dependencies.append(volume)
                value = (
                    base.value * min(3.0, float(np.log1p(volume.value) / np.log1p(center)))
                    if volume.value is not None and center > 0
                    else None
                )
            else:
                value = difference
            reason = None if value is not None else "zero_baseline_variance_or_volume"
        else:
            reason = "insufficient_baseline_coverage"
    available = max(
        (v.available_at for v in dependencies if v.available_at is not None), default=None
    )
    pipeline = max((v.pipeline_at for v in dependencies if v.pipeline_at is not None), default=None)
    evidence = {v.inference_id or v.version_id: v for d in dependencies for v in d.evidence}
    return Aggregate(value, reason, available, pipeline, tuple(evidence.values()), base.coverage)

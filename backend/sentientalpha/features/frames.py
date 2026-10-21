"""Chronological calendar alignment; missing sessions are explicit, never imputed."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.features.contracts import FeatureError, Observation

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def micros(value: datetime) -> int:
    delta = value - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


@dataclass
class Frame:
    ticker: str
    asset_id: str
    dates: list[date]
    observations: dict[int, Observation]
    prices: dict[str, NDArray[np.float64]]
    availability: NDArray[np.int64]
    ingestion: NDArray[np.int64]
    segment_start: NDArray[np.int64]
    calendar: str
    missing_sessions: list[date]

    @classmethod
    def build(cls, ticker: str, observations: list[Observation], dates: list[date]) -> "Frame":
        if not observations:
            raise FeatureError("no_data", f"No visible prices for {ticker}")
        ordered = sorted(observations, key=lambda item: item.bar.session_date)
        seen = [item.bar.session_date for item in ordered]
        if len(set(seen)) != len(seen):
            raise FeatureError(
                "duplicate_session", "Resolve price revisions before feature calculation"
            )
        calendars = {item.bar.calendar for item in ordered}
        assets = {item.asset_id for item in ordered}
        if (
            len(calendars) != 1
            or len(assets) != 1
            or any(item.bar.ticker != ticker for item in ordered)
        ):
            raise FeatureError("mixed_inputs", "Per-asset inputs must share identity and calendar")
        calendar = calendars.pop()
        valid_sessions = set(sessions_in_range(calendar, dates[0], dates[-1]))
        if set(seen) - valid_sessions:
            raise FeatureError("unexpected_session", "Price contains a nontrading session")
        positions = {day: i for i, day in enumerate(dates)}
        arrays = {
            name: np.full(len(dates), np.nan) for name in ("open", "high", "low", "close", "volume")
        }
        available, ingested = (
            np.zeros(len(dates), dtype=np.int64),
            np.zeros(len(dates), dtype=np.int64),
        )
        mapped = {}
        for item in ordered:
            i = positions[item.bar.session_date]
            for name in arrays:
                value = float(getattr(item.bar, name))
                if (
                    not np.isfinite(value)
                    or (name != "volume" and value <= 0)
                    or (name == "volume" and value < 0)
                ):
                    raise FeatureError(
                        "invalid_data", "Feature inputs must be finite coherent OHLCV"
                    )
                arrays[name][i] = value
            if (
                not arrays["low"][i]
                <= min(arrays["open"][i], arrays["close"][i])
                <= max(arrays["open"][i], arrays["close"][i])
                <= arrays["high"][i]
            ):
                raise FeatureError("invalid_data", "Invalid OHLC ordering")
            available[i], ingested[i] = micros(item.bar.available_at), micros(item.ingested_at)
            mapped[i] = item
        starts = np.zeros(len(dates), dtype=np.int64)
        beginning = 0
        for i in range(len(dates)):
            if i not in mapped:
                beginning = i + 1
            starts[i] = beginning
        # IPO/pre-source dates remain absent, not "missing market history" that can be filled.
        seen_set = set(seen)
        missing = [day for day in dates if seen[0] <= day <= seen[-1] and day not in seen_set]
        return cls(
            ticker,
            ordered[0].asset_id,
            dates,
            mapped,
            arrays,
            available,
            ingested,
            starts,
            calendar,
            missing,
        )

    def span_times(self, first: int, last: int) -> tuple[int, int]:
        return int(self.availability[first : last + 1].max()), int(
            self.ingestion[first : last + 1].max()
        )

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {"position": position, **item.fingerprint()}
            for position, item in self.observations.items()
        ]

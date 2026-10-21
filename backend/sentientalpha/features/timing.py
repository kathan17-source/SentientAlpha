"""Decision availability and next-open execution eligibility; feature values are not shifted."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sentientalpha.data.calendar import session_open, sessions_in_range
from sentientalpha.features.contracts import FeatureError
from sentientalpha.features.frames import EPOCH


def instant(value: int) -> datetime:
    return EPOCH + timedelta(microseconds=value)


@lru_cache(maxsize=8192)
def next_open(calendar: str, after: datetime) -> datetime:
    """First session open strictly after the readiness instant (never same closing fill)."""
    after = after.astimezone(UTC)
    end = after.date() + timedelta(days=14)
    if calendar == "XNYS" and end.year > 2035:
        raise FeatureError("execution_calendar_unavailable", "Execution calendar ends in 2035")
    for day in sessions_in_range(calendar, after.date(), end):
        opening = session_open(calendar, day)
        if opening > after:
            return opening
    raise FeatureError(
        "execution_calendar_unavailable", "Cannot determine a supported next session open"
    )


def readiness(market_at: datetime, available_us: int, delay: int) -> datetime:
    return max(instant(available_us), market_at + timedelta(seconds=delay))


def execution(
    calendar: str, decision_ready_at: datetime, ingested_us: int, calculated_at: datetime
) -> datetime:
    return next_open(calendar, max(decision_ready_at, instant(ingested_us), calculated_at))

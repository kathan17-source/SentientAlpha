"""Session validation only; no indicators or feature calculations."""

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from importlib.metadata import version
from typing import Any


def calendar_version(name: str) -> str:
    return (
        "weekday-v1" if name == "weekday" else f"exchange-calendars-{version('exchange-calendars')}"
    )


@lru_cache(maxsize=1)
def _xnys() -> Any:
    import exchange_calendars

    return exchange_calendars.get_calendar("XNYS", start="2000-01-01", end="2035-12-31")


def sessions_in_range(name: str, start: date, end: date) -> list[date]:
    if name == "weekday":
        days = (start + timedelta(days=n) for n in range((end - start).days + 1))
        return [day for day in days if day.weekday() < 5]
    if name == "XNYS":
        return [value.date() for value in _xnys().sessions_in_range(str(start), str(end))]
    raise ValueError("A declared session calendar is required")


def session_close(name: str, day: date) -> datetime:
    if name == "weekday":
        if day.weekday() >= 5:
            raise ValueError("Not a modeled weekday session")
        return datetime.combine(day, time(23, 59, 59), UTC)
    if name == "XNYS":
        return _xnys().session_close(str(day)).to_pydatetime().astimezone(UTC)
    raise ValueError("Unknown session calendar")


def session_open(name: str, day: date) -> datetime:
    """Scheduled opening time; weekday demo uses an explicitly modeled UTC schedule."""
    if name == "weekday":
        if day.weekday() >= 5:
            raise ValueError("Not a modeled weekday session")
        return datetime.combine(day, time(14, 30), UTC)
    if name == "XNYS":
        return _xnys().session_open(str(day)).to_pydatetime().astimezone(UTC)
    raise ValueError("Unknown session calendar")

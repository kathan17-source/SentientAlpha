"""Auditable quality observations. Suspicious prices are flagged, never repaired."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sentientalpha.data.calendar import calendar_version, sessions_in_range
from sentientalpha.data.contracts import PriceBar, ProviderError


@dataclass(frozen=True)
class QualityPolicy:
    discontinuity_threshold: Decimal = Decimal("0.30")


def assess_batch(
    bars: list[PriceBar],
    start: date,
    end: date,
    previous: tuple[date, Decimal] | None = None,
    policy: QualityPolicy | None = None,
) -> tuple[dict[str, Any], dict[date, list[str]]]:
    policy = policy or QualityPolicy()
    names = {bar.calendar for bar in bars}
    if len(names) != 1 or "unknown" in names:
        raise ProviderError("unknown_calendar", "Provider must declare one known session calendar")
    calendar = names.pop()
    expected = set(sessions_in_range(calendar, start, end))
    observed = {bar.session_date for bar in bars}
    if observed - expected:
        raise ProviderError("unexpected_session", "Provider returned a nontrading session")
    flags: dict[date, list[str]] = {}
    discontinuities = []
    for bar in sorted(bars, key=lambda item: item.session_date):
        if previous is not None:
            prior_date, prior_close = previous
            change = bar.close / prior_close - 1
            if abs(change) > policy.discontinuity_threshold:
                flags.setdefault(bar.session_date, []).append("price_discontinuity")
                discontinuities.append(
                    {
                        "session_date": str(bar.session_date),
                        "previous_session": str(prior_date),
                        "raw_close_change": str(change),
                        "possible_corporate_action": True,
                    }
                )
        previous = (bar.session_date, bar.close)
    missing = sorted(expected - observed)
    report: dict[str, Any] = {
        "calendar": calendar,
        "calendar_version": calendar_version(calendar),
        "expected_sessions": len(expected),
        "received_sessions": len(bars),
        "missing_sessions": [str(day) for day in missing],
        "discontinuities": discontinuities,
        "discontinuity_threshold": str(policy.discontinuity_threshold),
        "corporate_actions": "not_ingested",
        "transformations": [],
        "source_conflicts": [],
        "state": "warnings" if missing or discontinuities else "passed",
    }
    return report, flags

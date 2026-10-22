"""Explicitly synthetic 300+ session research fixtures; no network or financial claims."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_DNS, uuid5

import numpy as np
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.data.contracts import PriceBar
from sentientalpha.features.contracts import Observation


def observations(
    ticker: str = "AAA",
    count: int = 320,
    close: list[float] | None = None,
    sizes: list[int] | None = None,
    start: date = date(2020, 1, 2),
) -> list[Observation]:
    if close is not None:
        count = len(close)
    dates = sessions_in_range("weekday", start, start + timedelta(days=count * 2 + 20))[:count]
    close = close or [100 * np.exp(0.0003 * i + 0.03 * np.sin(i / 11)) for i in range(count)]
    sizes = sizes or [1000 + (i * 17) % 503 for i in range(count)]
    asset_id = str(uuid5(NAMESPACE_DNS, ticker))
    result = []
    for i, day in enumerate(dates):
        value = Decimal(str(close[i])).quantize(Decimal("0.00000001"))
        bar = PriceBar(
            ticker=ticker,
            session_date=day,
            open=value,
            high=value + 1,
            low=max(value - 1, value / 2),
            close=value,
            volume=sizes[i],
            available_at=session_close("weekday", day) + timedelta(seconds=1),
            provider="synthetic",
            is_synthetic=True,
            availability_kind="modeled",
            session_close_at=session_close("weekday", day),
            calendar="weekday",
            adjustment_status="not_supplied",
        )
        result.append(
            Observation(
                str(uuid5(NAMESPACE_DNS, f"{ticker}:{day}:{value}")),
                asset_id,
                bar,
                datetime(2026, 1, 1, tzinfo=UTC),
                1,
            )
        )
    return result

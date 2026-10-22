"""Deterministic demo data. Weekdays only, NOT an exchange calendar or market history."""

import hashlib
import math
import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sentientalpha.data.contracts import PriceBar, ticker_symbol, validate_range


class SyntheticProvider:
    name = "synthetic"

    def __init__(self, seed: int = 42) -> None:
        if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
            raise ValueError("Seed must be an integer between 0 and 2**31−1")
        self.seed = seed
        self.parameters = {"seed": seed}

    def fetch(self, ticker: str, start: date, end: date) -> list[PriceBar]:
        validate_range(start, end)
        ticker = ticker_symbol(ticker)
        rows: list[PriceBar] = []
        day = start
        while day <= end:
            if day.weekday() < 5:
                key = f"{self.seed}:{ticker}:{day.isoformat()}"
                rng = random.Random(int(hashlib.sha256(key.encode()).hexdigest(), 16))
                t = (day - date(2000, 1, 1)).days
                base = 100 * math.exp(0.00004 * t + 0.05 * math.sin(t / 31))
                opening = Decimal(str(base * (1 + rng.uniform(-0.01, 0.01))))
                close = opening * Decimal(str(1 + rng.uniform(-0.025, 0.025)))
                rows.append(
                    PriceBar(
                        ticker=ticker,
                        session_date=day,
                        open=opening,
                        high=max(opening, close) * Decimal("1.008"),
                        low=min(opening, close) * Decimal("0.992"),
                        close=close,
                        volume=rng.randint(100_000, 10_000_000),
                        available_at=datetime.combine(day + timedelta(days=1), time(), UTC),
                        provider=self.name,
                        is_synthetic=True,
                        availability_kind="modeled",
                        session_close_at=datetime.combine(day, time(23, 59, 59), UTC),
                        calendar="weekday",
                        adjustment_status="not_supplied",
                    )
                )
            day += timedelta(days=1)
        return rows

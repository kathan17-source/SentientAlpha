"""Strategies receive only frozen current information; no feed/database/future table."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from sentientalpha.backtesting.contracts import StrategySpec


@dataclass(frozen=True, slots=True)
class Context:
    at: datetime
    day: date
    prices: tuple[tuple[str, Decimal], ...]
    features: tuple[tuple[str, Decimal | None], ...]
    quantities: tuple[tuple[str, Decimal], ...]
    cash: Decimal


class Strategy(Protocol):
    def targets(self, context: Context) -> dict[str, Decimal]: ...


class Baseline:
    def __init__(self, spec: StrategySpec, tickers: list[str]):
        self.spec, self.tickers = spec, tuple(tickers)
        self.previous: date | None = None
        self.previous_targets: dict[str, Decimal] | None = None

    def targets(self, context: Context) -> dict[str, Decimal]:
        weights = (
            self.spec.allocation
            if self.spec.allocation is not None
            else {t: Decimal(1) / len(self.tickers) for t in self.tickers}
        )
        prices, features = dict(context.prices), dict(context.features)
        result = {t: w for t, w in weights.items() if t in prices}
        if self.spec.name == "moving_average":
            result = {
                t: (w if prices[t] > (features[t] or Decimal(0)) else Decimal(0))
                for t, w in result.items()
                if features.get(t) is not None
            }
        schedule = self.spec.rebalance
        previous = self.previous
        due = (
            previous is None
            or schedule in {"daily", "signal"}
            or (
                schedule == "weekly" and context.day.isocalendar()[:2] != previous.isocalendar()[:2]
            )
            or (
                schedule == "monthly"
                and (context.day.year, context.day.month) != (previous.year, previous.month)
            )
        )
        if schedule == "signal" and result == self.previous_targets:
            due = False
        if not result or not due:
            return {}
        self.previous, self.previous_targets = context.day, result.copy()
        return result

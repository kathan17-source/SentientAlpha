"""Volatility, Wilder ATR and population-width Bollinger Bands."""

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from sentientalpha.features.momentum import shift
from sentientalpha.features.trend import seeded_smoothing, sma

Array = NDArray[np.float64]


def rolling_std(values: Array, window: int, ddof: int = 1) -> Array:
    return pd.Series(values).rolling(window, min_periods=window).std(ddof=ddof).to_numpy()


def realized_volatility(returns: Array, window: int, annualization: int = 252) -> Array:
    return rolling_std(returns, window) * np.sqrt(annualization)


def true_range(high: Array, low: Array, close: Array) -> Array:
    previous = shift(close, 1)
    result = np.fmax(high - low, np.fmax(np.abs(high - previous), np.abs(low - previous)))
    result[~np.isfinite(high) | ~np.isfinite(low) | ~np.isfinite(close)] = np.nan
    return result


def atr(high: Array, low: Array, close: Array, window: int) -> Array:
    return seeded_smoothing(true_range(high, low, close), window, 1 / window)


def divide(numerator: Array, denominator: Array) -> Array:
    result = np.full(len(numerator), np.nan)
    valid = np.isfinite(numerator) & np.isfinite(denominator) & (denominator != 0)
    np.divide(numerator, denominator, out=result, where=valid)
    return result


def bollinger(close: Array, window: int, width: float = 2.0) -> dict[str, Array]:
    middle = sma(close, window)
    spread = width * rolling_std(close, window, ddof=0)
    upper, lower = middle + spread, middle - spread
    return {
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "bandwidth": divide(upper - lower, middle),
        "percent_b": divide(close - lower, upper - lower),
    }


def downside_volatility(returns: Array, window: int, annualization: int = 252) -> Array:
    downside = np.minimum(returns, 0) ** 2
    return np.sqrt(sma(downside, window) * annualization)

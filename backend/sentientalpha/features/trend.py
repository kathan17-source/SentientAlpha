"""Trend kernels with explicit SMA seeds and gap-reset recursive state."""

import numpy as np
import pandas as pd
from numpy.typing import NDArray

Array = NDArray[np.float64]


def sma(values: Array, window: int) -> Array:
    return pd.Series(values).rolling(window, min_periods=window).mean().to_numpy()


def seeded_smoothing(values: Array, window: int, alpha: float) -> Array:
    """Seed with first complete window mean; reset at every missing observation."""
    result = np.full(len(values), np.nan)
    count = 0
    total = 0.0
    previous = np.nan
    for i, value in enumerate(values):
        if not np.isfinite(value):
            count, total, previous = 0, 0.0, np.nan
            continue
        if count < window:
            count += 1
            total += value
            if count == window:
                previous = total / window
                result[i] = previous
        else:
            previous = alpha * value + (1 - alpha) * previous
            result[i] = previous
    return result


def ema(values: Array, window: int) -> Array:
    return seeded_smoothing(values, window, 2 / (window + 1))


def macd(values: Array, fast: int, slow: int, signal: int) -> dict[str, Array]:
    line = ema(values, fast) - ema(values, slow)
    signal_line = ema(line, signal)
    return {"line": line, "signal": signal_line, "histogram": line - signal_line}


def crossover(fast: Array, slow: Array) -> Array:
    spread = fast - slow
    previous = np.r_[np.nan, spread[:-1]]
    result = np.where(
        (spread > 0) & (previous <= 0), 1.0, np.where((spread < 0) & (previous >= 0), -1.0, 0.0)
    )
    result[~np.isfinite(spread) | ~np.isfinite(previous)] = np.nan
    return result

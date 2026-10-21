"""Trailing returns and Wilder RSI; no future-return targets exist here."""

import numpy as np
from numpy.typing import NDArray

from sentientalpha.features.trend import seeded_smoothing

Array = NDArray[np.float64]


def shift(values: Array, lag: int) -> Array:
    result = np.full(len(values), np.nan)
    if lag == 0:
        return values.copy()
    if lag < len(values):
        result[lag:] = values[:-lag]
    return result


def trailing_return(close: Array, horizon: int) -> Array:
    with np.errstate(divide="ignore", invalid="ignore"):
        return close / shift(close, horizon) - 1


def log_return(close: Array, horizon: int = 1) -> Array:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(close / shift(close, horizon))


def rsi(close: Array, window: int) -> Array:
    change = close - shift(close, 1)
    gain = seeded_smoothing(np.maximum(change, 0), window, 1 / window)
    loss = seeded_smoothing(np.maximum(-change, 0), window, 1 / window)
    result = np.full(len(close), np.nan)
    valid = np.isfinite(gain) & np.isfinite(loss)
    result[valid & (gain == 0) & (loss == 0)] = 50.0
    result[valid & (loss == 0) & (gain > 0)] = 100.0
    result[valid & (gain == 0) & (loss > 0)] = 0.0
    normal = valid & (gain > 0) & (loss > 0)
    result[normal] = 100 - 100 / (1 + gain[normal] / loss[normal])
    return result

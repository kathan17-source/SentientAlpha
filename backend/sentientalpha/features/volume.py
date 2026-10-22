"""Volume statistics and segment-reset On-Balance Volume."""

import numpy as np
from numpy.typing import NDArray

from sentientalpha.features.trend import sma
from sentientalpha.features.volatility import divide, rolling_std

Array = NDArray[np.float64]


def relative_volume(volume: Array, window: int) -> Array:
    return divide(volume, sma(volume, window))


def volume_zscore(volume: Array, window: int) -> Array:
    return divide(volume - sma(volume, window), rolling_std(volume, window))


def obv(close: Array, volume: Array) -> Array:
    result = np.full(len(close), np.nan)
    previous = np.nan
    balance = 0.0
    for i, (price, size) in enumerate(zip(close, volume, strict=True)):
        if not np.isfinite(price) or not np.isfinite(size):
            previous, balance = np.nan, 0.0
            continue
        if np.isfinite(previous):
            balance += np.sign(price - previous) * size
        result[i] = balance
        previous = price
    return result

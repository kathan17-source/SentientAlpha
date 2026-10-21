"""Windowed sample statistics, benchmark alignment and chronological drawdown."""

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from sentientalpha.features.trend import sma
from sentientalpha.features.volatility import divide, rolling_std

Array = NDArray[np.float64]


def skewness(returns: Array, window: int) -> Array:
    result = pd.Series(returns).rolling(window, min_periods=window).skew().to_numpy(copy=True)
    result[rolling_std(returns, window) == 0] = np.nan
    return result


def kurtosis(returns: Array, window: int) -> Array:
    result = pd.Series(returns).rolling(window, min_periods=window).kurt().to_numpy(copy=True)
    result[rolling_std(returns, window) == 0] = np.nan
    return result


def zscore(values: Array, window: int) -> Array:
    return divide(values - sma(values, window), rolling_std(values, window))


def covariance(left: Array, right: Array, window: int) -> Array:
    return (
        pd.Series(left).rolling(window, min_periods=window).cov(pd.Series(right), ddof=1).to_numpy()
    )


def correlation(left: Array, right: Array, window: int) -> Array:
    return divide(
        covariance(left, right, window), rolling_std(left, window) * rolling_std(right, window)
    )


def beta(asset_returns: Array, benchmark_returns: Array, window: int) -> Array:
    return divide(
        covariance(asset_returns, benchmark_returns, window),
        rolling_std(benchmark_returns, window) ** 2,
    )


def maximum_drawdown(close: Array, window: int) -> Array:
    """Worst ordered peak-to-trough decline inside each trailing price window; negative ratio."""
    result = np.full(len(close), np.nan)
    if len(close) >= window:
        blocks = np.lib.stride_tricks.sliding_window_view(close, window)
        peaks = np.maximum.accumulate(blocks, axis=1)
        result[window - 1 :] = np.min(blocks / peaks - 1, axis=1)
    return result


def distance_from_extreme(close: Array, window: int, high: bool) -> Array:
    rolling = pd.Series(close).rolling(window, min_periods=window)
    extreme = (rolling.max() if high else rolling.min()).to_numpy()
    return divide(close, extreme) - 1


def synchronized_rank(values: Array) -> Array:
    """Complete fixed-cohort ranks [0,1], average ties. Any missing member nulls the cohort."""
    if len(values) < 2 or not np.isfinite(values).all():
        return np.full(len(values), np.nan)
    return (pd.Series(values).rank(method="average").to_numpy() - 1) / (len(values) - 1)

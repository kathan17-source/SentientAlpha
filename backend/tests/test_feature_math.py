"""Independent numerical references, not tests that repeat the implementation."""

import math
from statistics import mean, stdev

import numpy as np
import pytest
from sentientalpha.features.momentum import log_return, rsi, trailing_return
from sentientalpha.features.statistics import (
    beta,
    correlation,
    covariance,
    distance_from_extreme,
    kurtosis,
    maximum_drawdown,
    skewness,
    synchronized_rank,
    zscore,
)
from sentientalpha.features.trend import crossover, ema, macd, sma
from sentientalpha.features.volatility import (
    atr,
    bollinger,
    downside_volatility,
    realized_volatility,
)
from sentientalpha.features.volume import obv, relative_volume, volume_zscore


def arr(values):
    return np.asarray(values, dtype=float)


@pytest.mark.parametrize("window", [5, 10, 20, 50, 100, 200])
def test_sma_against_arithmetic_reference(window):
    prices = [i + 1 for i in range(260)]
    result = sma(arr(prices), window)
    assert np.isnan(result[: window - 1]).all()
    assert result[window - 1] == mean(prices[:window])
    assert result[-1] == mean(prices[-window:])


def test_sma_seeded_ema_reference_and_warmup():
    result = ema(arr([3, 6, 9, 12, 3, 15]), 3)
    np.testing.assert_allclose(result, [np.nan, np.nan, 6, 9, 6, 10.5], equal_nan=True)


def test_ema_state_resets_on_gap():
    np.testing.assert_allclose(
        ema(arr([1, 2, 3, np.nan, 10, 20, 30, 40]), 3),
        [np.nan, np.nan, 2, np.nan, np.nan, np.nan, 20, 30],
        equal_nan=True,
    )


@pytest.mark.parametrize(
    "prices,expected",
    [([10, 11, 12, 13, 14], 100), ([14, 13, 12, 11, 10], 0), ([10, 10, 10, 10, 10], 50)],
)
def test_rsi_edges(prices, expected):
    result = rsi(arr(prices), 3)
    assert np.isnan(result[:3]).all()
    assert result[3] == result[4] == expected


def test_wilder_rsi_independent_seed_and_update():
    # Changes +2,-1,+3,-2: seed gain=5/3, loss=1/3; next gain=10/9, loss=8/9.
    result = rsi(arr([10, 12, 11, 14, 12]), 3)
    assert result[3] == pytest.approx(100 - 100 / 6)
    assert result[4] == pytest.approx(100 - 100 / 2.25)


def test_macd_linear_series_reference():
    result = macd(arr(range(1, 11)), 2, 3, 2)
    assert np.isnan(result["line"][:2]).all()
    np.testing.assert_allclose(result["line"][2:], 0.5)
    assert np.isnan(result["signal"][:3]).all()
    np.testing.assert_allclose(result["signal"][3:], 0.5)
    np.testing.assert_allclose(result["histogram"][3:], 0)


def test_atr_known_true_ranges_and_wilder_smoothing():
    result = atr(arr([10, 12, 15, 16]), arr([8, 9, 10, 12]), arr([9, 11, 14, 13]), 3)
    # True ranges are 2,3,5,4; initial ATR=10/3, next=(2*(10/3)+4)/3.
    assert result[2] == pytest.approx(10 / 3)
    assert result[3] == pytest.approx(32 / 9)


def test_bollinger_population_convention():
    result = bollinger(arr([1, 2, 3, 4, 5]), 5)
    assert result["middle"][-1] == 3
    assert result["upper"][-1] == pytest.approx(3 + 2 * math.sqrt(2))
    assert result["lower"][-1] == pytest.approx(3 - 2 * math.sqrt(2))
    assert result["bandwidth"][-1] == pytest.approx(4 * math.sqrt(2) / 3)
    assert result["percent_b"][-1] == pytest.approx(
        (5 - (3 - 2 * math.sqrt(2))) / (4 * math.sqrt(2))
    )


def test_returns_and_annualized_sample_volatility():
    prices = arr([100, 110, 99, 108.9])
    np.testing.assert_allclose(trailing_return(prices, 1)[1:], [0.1, -0.1, 0.1])
    np.testing.assert_allclose(
        log_return(prices)[1:], [math.log(1.1), math.log(0.9), math.log(1.1)]
    )
    result = realized_volatility(trailing_return(prices, 1), 3)
    assert result[-1] == pytest.approx(stdev([0.1, -0.1, 0.1]) * math.sqrt(252))
    assert downside_volatility(trailing_return(prices, 1), 3)[-1] == pytest.approx(
        math.sqrt(0.01 / 3 * 252)
    )


def test_covariance_correlation_beta_reference():
    benchmark = arr([0.01, -0.02, 0.03, 0.04])
    asset = 2 * benchmark + 0.005
    left_mean, right_mean = mean(asset), mean(benchmark)
    expected_cov = (
        sum((x - left_mean) * (y - right_mean) for x, y in zip(asset, benchmark, strict=True)) / 3
    )
    assert covariance(asset, benchmark, 4)[-1] == pytest.approx(expected_cov)
    assert correlation(asset, benchmark, 4)[-1] == pytest.approx(1)
    assert beta(asset, benchmark, 4)[-1] == pytest.approx(2)
    assert np.isnan(beta(asset, np.zeros(4), 4)[-1])


def test_adjusted_sample_skew_and_excess_kurtosis_reference():
    values = [0.01, -0.03, 0.02, 0.09, -0.01, 0.04]
    n, center, scale = len(values), mean(values), stdev(values)
    third = sum(((v - center) / scale) ** 3 for v in values)
    fourth = sum(((v - center) / scale) ** 4 for v in values)
    expected_skew = n * third / ((n - 1) * (n - 2))
    expected_kurt = n * (n + 1) * fourth / ((n - 1) * (n - 2) * (n - 3)) - 3 * (n - 1) ** 2 / (
        (n - 2) * (n - 3)
    )
    assert skewness(arr(values), n)[-1] == pytest.approx(expected_skew)
    assert kurtosis(arr(values), n)[-1] == pytest.approx(expected_kurt)
    assert np.isnan(skewness(np.zeros(10), 5)[-1])


def test_drawdown_respects_peak_before_trough():
    assert maximum_drawdown(arr([100, 120, 90, 110]), 4)[-1] == pytest.approx(-0.25)
    # The 90 occurs before the 120; it is not a drawdown from that future peak.
    assert maximum_drawdown(arr([90, 120, 110]), 3)[-1] == pytest.approx(110 / 120 - 1)


def test_cross_section_rank_ties_and_incomplete_cohort():
    np.testing.assert_allclose(
        synchronized_rank(arr([0.2, 0.1, 0.2, -0.1])), [5 / 6, 1 / 3, 5 / 6, 0]
    )
    np.testing.assert_allclose(synchronized_rank(arr([1, 1, 1])), 0.5)
    assert np.isnan(synchronized_rank(arr([1, np.nan]))).all()
    assert np.isnan(synchronized_rank(arr([1]))).all()


def test_volume_zeros_and_obv_convention():
    assert obv(arr([10, 11, 11, 9, 12]), arr([100, 200, 50, 40, 70])).tolist() == [
        0,
        200,
        200,
        160,
        230,
    ]
    np.testing.assert_allclose(relative_volume(arr([10, 20, 30]), 3)[-1], 1.5)
    assert volume_zscore(arr([10, 20, 30]), 3)[-1] == pytest.approx(1)
    assert np.isnan(relative_volume(np.zeros(5), 3)[-1])
    assert np.isnan(volume_zscore(np.zeros(5), 3)[-1])


def test_zscore_extremes_and_crossing():
    assert zscore(arr([1, 2, 3]), 3)[-1] == 1
    assert distance_from_extreme(arr([1, 3, 2]), 3, True)[-1] == pytest.approx(-1 / 3)
    assert distance_from_extreme(arr([1, 3, 2]), 3, False)[-1] == 1
    np.testing.assert_allclose(
        crossover(arr([1, 3, 2, 1]), arr([2, 2, 2, 2])), [np.nan, 1, 0, -1], equal_nan=True
    )

"""Per-asset memoized formula dispatch, isolated from persistence and execution."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from sentientalpha.features import momentum, statistics, trend, volatility, volume
from sentientalpha.features.frames import Frame
from sentientalpha.features.registry import Resolved

Array = NDArray[np.float64]


class Calculator:
    def __init__(self, frame: Frame, benchmark: Frame | None = None) -> None:
        self.frame = frame
        self.benchmark = benchmark
        self.cache: dict[str, Array] = {}

    def cached(self, key: str, calculation: Callable[[], Array]) -> Array:
        if key not in self.cache:
            self.cache[key] = calculation()
        return self.cache[key]

    def returns(self) -> Array:
        return self.cached(
            "return", lambda: momentum.trailing_return(self.frame.prices["close"], 1)
        )

    def std(self, window: int) -> Array:
        return self.cached(
            f"return_std_{window}", lambda: volatility.rolling_std(self.returns(), window)
        )

    def average(self, window: int, exponential: bool = False) -> Array:
        key = f"average_{window}_{exponential}"
        return self.cached(
            key,
            lambda: (trend.ema if exponential else trend.sma)(self.frame.prices["close"], window),
        )

    def calculate(self, item: Resolved) -> dict[str, Array]:
        name, p = item.definition.name, item.parameters
        window, close = int(p.get("window", 1)), self.frame.prices["close"]
        if name == "macd":
            line = self.average(int(p["fast"]), True) - self.average(int(p["slow"]), True)
            signal = self.cached(item.key + ".signal", lambda: trend.ema(line, int(p["signal"])))
            return {"line": line, "signal": signal, "histogram": line - signal}
        if name == "bollinger":
            return volatility.bollinger(close, window, float(p["width"]))
        if name == "sma":
            result = self.average(window)
        elif name == "ema":
            result = self.average(window, True)
        elif name in {"price_to_sma", "price_to_ema"}:
            result = volatility.divide(close, self.average(window, name == "price_to_ema")) - 1
        elif name in {"ma_crossover", "trend_direction", "trend_strength"}:
            fast, slow = self.average(int(p["fast"])), self.average(int(p["slow"]))
            result = (
                trend.crossover(fast, slow)
                if name == "ma_crossover"
                else np.sign(fast - slow)
                if name == "trend_direction"
                else np.abs(volatility.divide(fast - slow, close))
            )
        elif name == "rsi":
            result = momentum.rsi(close, window)
        elif name in {"roc", "trailing_return", "cross_sectional_momentum_rank"}:
            result = momentum.trailing_return(close, window)
        elif name == "momentum":
            result = momentum.log_return(close, window)
        elif name == "return":
            result = self.returns()
        elif name == "log_return":
            result = momentum.log_return(close)
        elif name == "lagged_return":
            result = momentum.shift(self.returns(), int(p["lag"]))
        elif name == "realized_volatility":
            result = self.std(window) * np.sqrt(int(p["annualization"]))
        elif name == "atr":
            result = volatility.atr(
                self.frame.prices["high"], self.frame.prices["low"], close, window
            )
        elif name == "downside_volatility":
            result = volatility.downside_volatility(self.returns(), window, int(p["annualization"]))
        elif name == "vol_normalized_momentum":
            result = volatility.divide(
                momentum.trailing_return(close, window), self.std(window) * np.sqrt(window)
            )
        elif name == "volume_sma":
            result = trend.sma(self.frame.prices["volume"], window)
        elif name == "relative_volume":
            result = volume.relative_volume(self.frame.prices["volume"], window)
        elif name == "volume_zscore":
            result = volume.volume_zscore(self.frame.prices["volume"], window)
        elif name == "obv":
            result = volume.obv(close, self.frame.prices["volume"])
        elif name == "rolling_return_mean":
            result = trend.sma(self.returns(), window)
        elif name == "rolling_return_std":
            result = self.std(window)
        elif name == "rolling_skewness":
            result = statistics.skewness(self.returns(), window)
        elif name == "rolling_kurtosis":
            result = statistics.kurtosis(self.returns(), window)
        elif name == "rolling_zscore":
            result = statistics.zscore(close, window)
        elif name == "vol_adjusted_return":
            result = volatility.divide(self.returns(), self.std(window))
        elif name == "rolling_max_drawdown":
            result = statistics.maximum_drawdown(close, window)
        elif name in {"distance_from_high", "distance_from_low"}:
            result = statistics.distance_from_extreme(close, window, name == "distance_from_high")
        elif "benchmark_close" in item.definition.inputs:
            if self.benchmark is None:
                result = np.full(len(close), np.nan)
            else:
                other = self.benchmark.prices["close"]
                other_returns = momentum.trailing_return(other, 1)
                if name == "relative_strength":
                    result = (
                        volatility.divide(
                            close / momentum.shift(close, window),
                            other / momentum.shift(other, window),
                        )
                        - 1
                    )
                else:
                    method = {
                        "rolling_covariance": statistics.covariance,
                        "rolling_correlation": statistics.correlation,
                        "rolling_beta": statistics.beta,
                    }[name]
                    result = method(self.returns(), other_returns, window)
        else:
            raise ValueError(f"No registered kernel for {name}")
        return {"value": result}

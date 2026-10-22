"""Declarative feature catalog. Requests select known formulas, never code."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from sentientalpha.features import ENGINE_VERSION
from sentientalpha.features.contracts import (
    MAX_COLUMNS,
    MAX_WINDOW,
    FeatureError,
    FeatureSpec,
    digest,
)


@dataclass(frozen=True)
class Definition:
    name: str
    group: str
    description: str
    defaults: dict[str, int | float]
    inputs: tuple[str, ...] = ("close",)
    version: str = "1.0.0"
    recursive: bool = False
    outputs: tuple[str, ...] = ("value",)
    minimum_window: int = 1
    undefined_reason: str = "undefined_ratio"

    def warmups(self, parameters: dict[str, int | float]) -> dict[str, int]:
        window = int(parameters.get("window", 1))
        if self.name == "macd":
            slow, signal = int(parameters["slow"]), int(parameters["signal"])
            return {"line": slow, "signal": slow + signal - 1, "histogram": slow + signal - 1}
        if self.name in {"ma_crossover", "trend_direction", "trend_strength"}:
            return {"value": int(parameters["slow"]) + (self.name == "ma_crossover")}
        if self.name in {"return", "log_return"}:
            return {"value": 2}
        if self.name == "lagged_return":
            return {"value": int(parameters["lag"]) + 2}
        if self.name in {
            "rsi",
            "roc",
            "momentum",
            "trailing_return",
            "relative_strength",
            "realized_volatility",
            "downside_volatility",
            "vol_normalized_momentum",
            "rolling_return_mean",
            "rolling_return_std",
            "rolling_skewness",
            "rolling_kurtosis",
            "rolling_covariance",
            "rolling_correlation",
            "rolling_beta",
            "vol_adjusted_return",
            "cross_sectional_momentum_rank",
        }:
            return {"value": window + 1}
        return {output: window for output in self.outputs}


CATALOG = [
    Definition("sma", "trend", "Arithmetic mean of trailing closing prices", {"window": 20}),
    Definition(
        "ema", "trend", "SMA-seeded EMA, alpha=2/(window+1)", {"window": 20}, recursive=True
    ),
    Definition(
        "macd",
        "trend",
        "Fast EMA minus slow EMA; EMA signal and histogram",
        {"fast": 12, "slow": 26, "signal": 9},
        recursive=True,
        outputs=("line", "signal", "histogram"),
    ),
    Definition("price_to_sma", "trend", "Close/SMA minus one", {"window": 20}),
    Definition("price_to_ema", "trend", "Close/EMA minus one", {"window": 20}, recursive=True),
    Definition(
        "ma_crossover",
        "trend",
        "SMA crossing event: +1 up, -1 down, 0 otherwise",
        {"fast": 10, "slow": 50},
    ),
    Definition(
        "trend_direction", "trend", "Sign of fast SMA minus slow SMA", {"fast": 10, "slow": 50}
    ),
    Definition(
        "trend_strength",
        "trend",
        "Absolute SMA spread divided by current close",
        {"fast": 10, "slow": 50},
    ),
    Definition(
        "rsi",
        "momentum",
        "Wilder RSI; flat gain/loss=0 convention is 50",
        {"window": 14},
        recursive=True,
    ),
    Definition("roc", "momentum", "Decimal trailing simple return", {"window": 20}),
    Definition("momentum", "momentum", "Log price momentum over window sessions", {"window": 20}),
    Definition(
        "trailing_return", "momentum", "Multi-horizon trailing simple return", {"window": 20}
    ),
    Definition(
        "realized_volatility",
        "volatility",
        "Sample daily-return SD times sqrt(annualization)",
        {"window": 20, "annualization": 252},
        minimum_window=2,
    ),
    Definition(
        "atr",
        "volatility",
        "Wilder-smoothed true range; first range is high-low",
        {"window": 14},
        inputs=("high", "low", "close"),
        recursive=True,
    ),
    Definition(
        "bollinger",
        "volatility",
        "Mean +/- width*population SD, width and percent B",
        {"window": 20, "width": 2.0},
        outputs=("middle", "upper", "lower", "bandwidth", "percent_b"),
    ),
    Definition(
        "downside_volatility",
        "volatility",
        "Annualized RMS of negative daily returns",
        {"window": 20, "annualization": 252},
    ),
    Definition(
        "vol_normalized_momentum",
        "volatility",
        "Trailing return / (daily sample SD*sqrt(window))",
        {"window": 20},
        minimum_window=2,
        undefined_reason="zero_variance",
    ),
    Definition(
        "volume_sma",
        "volume",
        "Mean volume including zero-volume observations",
        {"window": 20},
        inputs=("volume",),
    ),
    Definition(
        "relative_volume",
        "volume",
        "Current volume / trailing mean volume",
        {"window": 20},
        inputs=("volume",),
        undefined_reason="zero_volume_mean",
    ),
    Definition(
        "volume_zscore",
        "volume",
        "Volume deviation / sample volume SD",
        {"window": 20},
        inputs=("volume",),
        minimum_window=2,
        undefined_reason="zero_variance",
    ),
    Definition(
        "obv",
        "volume",
        "Cumulative signed volume; segment starts at zero",
        {},
        inputs=("close", "volume"),
        recursive=True,
    ),
    Definition("return", "statistics", "Close-to-close simple daily price return", {}),
    Definition("log_return", "statistics", "Log close-to-close daily price return", {}),
    Definition(
        "lagged_return",
        "statistics",
        "Daily return lagged by an explicit past-session lag",
        {"lag": 1},
    ),
    Definition(
        "rolling_return_mean", "statistics", "Mean trailing daily price returns", {"window": 20}
    ),
    Definition(
        "rolling_return_std",
        "statistics",
        "Sample trailing daily-return SD (ddof=1)",
        {"window": 20},
        minimum_window=2,
    ),
    Definition(
        "rolling_skewness",
        "statistics",
        "Adjusted Fisher-Pearson sample skewness",
        {"window": 20},
        minimum_window=3,
        undefined_reason="zero_variance",
    ),
    Definition(
        "rolling_kurtosis",
        "statistics",
        "Unbiased Fisher excess sample kurtosis",
        {"window": 20},
        minimum_window=4,
        undefined_reason="zero_variance",
    ),
    Definition(
        "rolling_zscore",
        "statistics",
        "Close deviation / trailing sample close SD",
        {"window": 20},
        minimum_window=2,
        undefined_reason="zero_variance",
    ),
    Definition(
        "vol_adjusted_return",
        "statistics",
        "Current daily return / trailing daily sample SD",
        {"window": 20},
        minimum_window=2,
        undefined_reason="zero_variance",
    ),
    Definition(
        "rolling_max_drawdown",
        "statistics",
        "Worst ordered peak/trough decline within window",
        {"window": 20},
    ),
    Definition(
        "distance_from_high",
        "statistics",
        "Close / trailing highest close minus one",
        {"window": 20},
    ),
    Definition(
        "distance_from_low", "statistics", "Close / trailing lowest close minus one", {"window": 20}
    ),
    Definition(
        "relative_strength",
        "relative",
        "Asset gross trailing return / benchmark gross return - 1",
        {"window": 20},
        inputs=("close", "benchmark_close"),
    ),
    Definition(
        "rolling_covariance",
        "relative",
        "Sample covariance of aligned asset/benchmark daily returns",
        {"window": 20},
        inputs=("close", "benchmark_close"),
        minimum_window=2,
    ),
    Definition(
        "rolling_correlation",
        "relative",
        "Aligned sample covariance / SD product",
        {"window": 20},
        inputs=("close", "benchmark_close"),
        minimum_window=2,
        undefined_reason="zero_variance",
    ),
    Definition(
        "rolling_beta",
        "relative",
        "Aligned return covariance / benchmark sample variance",
        {"window": 20},
        inputs=("close", "benchmark_close"),
        minimum_window=2,
        undefined_reason="zero_variance",
    ),
    Definition(
        "cross_sectional_momentum_rank",
        "relative",
        "Complete fixed-cohort trailing-return rank [0,1]",
        {"window": 20},
        inputs=("close", "cross_section"),
    ),
]


@dataclass(frozen=True)
class Resolved:
    definition: Definition
    parameters: dict[str, int | float]
    warmups: dict[str, int]
    key: str

    def output_name(self, output: str) -> str:
        return self.key if output == "value" else f"{self.key}.{output}"

    def metadata(self) -> dict[str, Any]:
        sentiment = self.definition.name.startswith("sent_")
        from sentientalpha.sentiment import VERSION as SENTIMENT_VERSION

        return {
            "name": self.definition.name,
            "group": self.definition.group,
            "description": self.definition.description,
            "parameters": self.parameters,
            "inputs": self.definition.inputs,
            "calculation_version": self.definition.version,
            "lookback": "full_contiguous_segment" if self.definition.recursive else "finite_window",
            "warmup_sessions": {self.output_name(k): v for k, v in self.warmups.items()},
            "outputs": [self.output_name(k) for k in self.warmups],
            "dtype": "float64",
            "availability": "max(required input availability, session close + processing delay)",
            "missing_policy": "preserve null + reason; reset at session gaps; never fill",
            "price_basis": "not_applicable" if sentiment else "raw",
            **(
                {
                    "subsystem_version": SENTIMENT_VERSION,
                    "missing_policy": "preserve null + coverage reason; no-news is not neutral",
                    "availability": (
                        "max(article availability, coverage evidence, session close + delay); "
                        "online additionally requires inference"
                    ),
                }
                if sentiment
                else {}
            ),
        }


class Registry:
    def __init__(self, definitions: list[Definition] | None = None) -> None:
        self.definitions = {item.name: item for item in definitions or CATALOG}

    def resolve(self, specs: list[FeatureSpec], groups: list[str] | None = None) -> list[Resolved]:
        if not specs:
            wanted = set(groups or {item.group for item in self.definitions.values()})
            if wanted - {item.group for item in self.definitions.values()}:
                raise FeatureError("unknown_group", "Unsupported feature group")
            specs = [
                FeatureSpec(name=item.name)
                for item in self.definitions.values()
                if item.group in wanted
            ]
        resolved: list[Resolved] = []
        for spec in specs:
            definition = self.definitions.get(spec.name)
            if definition is None:
                raise FeatureError(
                    "unknown_feature", "Unsupported feature; labels are not input features"
                )
            if set(spec.parameters) - set(definition.defaults):
                raise FeatureError("invalid_parameters", "Unknown feature parameter")
            parameters = {**definition.defaults, **spec.parameters}
            for key, value in parameters.items():
                if not math.isfinite(value):
                    raise FeatureError("invalid_parameters", "Parameters must be finite")
                if key == "width":
                    if not 0 < value <= 10:
                        raise FeatureError(
                            "invalid_parameters", "Bollinger width must be in (0,10]"
                        )
                elif type(value) is not int or not 1 <= value <= (
                    365 if key == "annualization" else MAX_WINDOW
                ):
                    raise FeatureError(
                        "invalid_parameters", "Session parameters must be bounded integers"
                    )
            if int(parameters.get("window", 1)) < definition.minimum_window:
                raise FeatureError("invalid_parameters", "Window is too short for this statistic")
            if "fast" in parameters and parameters["fast"] >= parameters["slow"]:
                raise FeatureError(
                    "invalid_parameters", "Fast window must be smaller than slow window"
                )
            if "width" in parameters:
                parameters["width"] = float(parameters["width"])
            key = definition.name + "".join(
                f"__{name}_{value:g}" for name, value in sorted(parameters.items())
            )
            resolved.append(Resolved(definition, parameters, definition.warmups(parameters), key))
        names = [item.output_name(output) for item in resolved for output in item.warmups]
        if len(set(names)) != len(names) or len(names) > MAX_COLUMNS:
            raise FeatureError(
                "invalid_feature_set", "Duplicate outputs or too many feature columns"
            )
        return sorted(resolved, key=lambda item: item.key)

    def definitions_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                **self.resolve([FeatureSpec(name=name)])[0].metadata(),
                "parameter_defaults": self.definitions[name].defaults,
                "maximum_session_parameter": MAX_WINDOW,
            }
            for name in sorted(self.definitions)
        ]


def definition_hash(resolved: list[Resolved]) -> str:
    return digest(
        {
            "engine": ENGINE_VERSION,
            "definitions": [item.metadata() for item in resolved],
            "numpy": np.__version__,
            "pandas": pd.__version__,
        }
    )

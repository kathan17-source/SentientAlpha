"""Closed, bounded configurations; no executable model parameters."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Frozen
from sentientalpha.data.contracts import ticker_symbol, utc
from sentientalpha.optimization.estimation import OptimizationError

MLException = OptimizationError
ModelName = Literal[
    "majority",
    "prevalence",
    "momentum",
    "logistic",
    "forest_classifier",
    "boost_classifier",
    "zero",
    "mean",
    "historical_volatility",
    "ridge",
    "elastic_net",
    "forest_regressor",
    "boost_regressor",
]


class Target(Frozen):
    task: Literal["direction", "return", "volatility"] = "direction"
    horizon: Literal[1, 5, 10] = 1
    convention: Literal["next_open_to_close", "close_to_close_research"] = "next_open_to_close"


class Candidate(Frozen):
    model: ModelName = "logistic"
    strength: float = Field(default=1.0, ge=0.0001, le=10000)
    trees: int = Field(default=40, ge=5, le=150, strict=True)
    depth: int = Field(default=3, ge=1, le=6, strict=True)
    leaf: int = Field(default=10, ge=2, le=100, strict=True)
    learning_rate: float = Field(default=0.05, ge=0.005, le=0.3)


class Window(Frozen):
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    calibration_start: date
    calibration_end: date
    test_start: date
    test_end: date

    @model_validator(mode="after")
    def chronology(self) -> "Window":
        if not (
            self.train_start
            <= self.train_end
            < self.validation_start
            <= self.validation_end
            < self.calibration_start
            <= self.calibration_end
            < self.test_start
            <= self.test_end
        ):
            raise ValueError("Four strictly disjoint chronological windows are required")
        return self


class ResearchRequest(Frozen):
    dataset_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    sentiment_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    tickers: list[str] = Field(min_length=1, max_length=50)
    columns: list[str] = Field(min_length=1, max_length=48)
    source_as_of: datetime
    information_policy: Literal["online", "research_replay", "retrospective"] = "online"
    target: Target = Field(default_factory=Target)
    windows: list[Window] = Field(min_length=1, max_length=12)
    candidates: list[Candidate] = Field(
        default_factory=lambda: [Candidate()], min_length=1, max_length=12
    )
    selection_tolerance: float = Field(default=0.001, ge=0, le=0.1)
    seed: int = Field(default=61, ge=0, le=2**31 - 1, strict=True)
    minimum_train: int = Field(default=60, ge=20, le=10000, strict=True)
    minimum_evaluation: int = Field(default=20, ge=5, le=1000, strict=True)
    calibration: Literal["none", "sigmoid", "isotonic"] = "sigmoid"
    missing: Literal["drop", "median_indicator"] = "drop"
    clip_quantile: float = Field(default=0.01, ge=0, le=0.1)
    select_features: int | None = Field(default=None, ge=1, le=48, strict=True)
    embargo_sessions: int = Field(default=0, ge=0, le=20, strict=True)
    training_mode: Literal["rolling", "expanding"] = "rolling"
    threshold: float = Field(default=0.5, ge=0.05, le=0.95)
    seconds: int = Field(default=120, ge=1, le=300, strict=True)
    sentiment_provenance: Literal["genuine", "synthetic_fixture"] = "genuine"

    @field_validator("source_as_of")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

    @field_validator("tickers")
    @classmethod
    def symbols(cls, v: list[str]) -> list[str]:
        values = sorted(ticker_symbol(t) for t in v)
        if len(set(values)) != len(values):
            raise ValueError("Duplicate assets")
        return values

    @model_validator(mode="after")
    def bounded(self) -> "ResearchRequest":
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Duplicate features")
        classification = {
            "majority",
            "prevalence",
            "momentum",
            "logistic",
            "forest_classifier",
            "boost_classifier",
        }
        if any(
            (c.model in classification) != (self.target.task == "direction")
            for c in self.candidates
        ):
            raise ValueError("Model and target task incompatible")
        if self.target.task != "direction" and self.calibration != "none":
            raise ValueError("Calibration is for directional probabilities only")
        if self.target.task != "volatility" and any(
            c.model == "historical_volatility" for c in self.candidates
        ):
            raise ValueError("Volatility baseline requires volatility target")
        for i, w in enumerate(self.windows):
            if not date(2000, 1, 1) <= w.train_start < w.test_end <= date(2034, 12, 31):
                raise ValueError("Unsupported date range")
            if (w.test_end - self.windows[0].train_start).days > 3660:
                raise ValueError("At most ten years")
            if i and (
                w.test_start <= self.windows[i - 1].test_end
                or w.train_end <= self.windows[i - 1].train_end
            ):
                raise ValueError("Retraining must advance; test windows cannot overlap")
        if self.training_mode == "expanding" and any(
            w.train_start != self.windows[0].train_start for w in self.windows
        ):
            raise ValueError("Expanding windows must retain their original start")
        if len(self.windows) * len(self.candidates) > 48:
            raise ValueError("Training budget exceeded")
        return self


class PredictRequest(Frozen):
    model_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    decision_at: datetime
    tickers: list[str] = Field(min_length=1, max_length=50)

    @field_validator("decision_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return utc(v)

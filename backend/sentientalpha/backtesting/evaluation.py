"""Chronological splits and independent-capital walk-forward evaluation."""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from sentientalpha.backtesting.contracts import Frozen, Request


class Split(Frozen):
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    test_start: date
    test_end: date
    label_horizon_sessions: int = Field(default=0, ge=0, le=252, strict=True)
    embargo_sessions: int = Field(default=0, ge=0, le=252, strict=True)

    @model_validator(mode="after")
    def chronological(self) -> "Split":
        if (
            not self.train_start
            <= self.train_end
            < self.validation_start
            <= self.validation_end
            < self.test_start
            <= self.test_end
        ):
            raise ValueError(
                "Train, validation and held-out test must be disjoint chronological ranges"
            )
        if self.embargo_sessions and not self.label_horizon_sessions:
            raise ValueError("Embargo needs a declared label overlap rationale")
        return self

    def indices(self, days: list[date]) -> dict[str, list[int]]:
        groups = {
            "train": [i for i, d in enumerate(days) if self.train_start <= d <= self.train_end],
            "validation": [
                i for i, d in enumerate(days) if self.validation_start <= d <= self.validation_end
            ],
            "test": [i for i, d in enumerate(days) if self.test_start <= d <= self.test_end],
        }
        for earlier, later in (("train", "validation"), ("validation", "test")):
            if groups[later]:
                boundary = groups[later][0]
                groups[earlier] = [
                    i
                    for i in groups[earlier]
                    if i + self.label_horizon_sessions < boundary - self.embargo_sessions
                ]
        return groups


class WalkRequest(Frozen):
    backtest: Request
    train_sessions: int = Field(default=252, ge=1, le=2520, strict=True)
    validation_sessions: int = Field(default=63, ge=1, le=1260, strict=True)
    test_sessions: int = Field(default=63, ge=2, le=1260, strict=True)
    step_sessions: int = Field(default=63, ge=1, le=1260, strict=True)
    mode: Literal["rolling", "expanding"] = "rolling"
    maximum_folds: int = Field(default=20, ge=1, le=50, strict=True)

    @model_validator(mode="after")
    def no_overlap(self) -> "WalkRequest":
        if self.step_sessions < self.test_sessions:
            raise ValueError("Overlapping out-of-sample windows are refused")
        if self.backtest.benchmarks:
            raise ValueError("Walk-forward folds require benchmarks disabled to bound nested work")
        return self

    def folds(self, days: list[date]) -> list[Split]:
        folds = []
        offset = 0
        while offset + self.train_sessions + self.validation_sessions + self.test_sessions <= len(
            days
        ):
            v = offset + self.train_sessions
            t = v + self.validation_sessions
            folds.append(
                Split(
                    train_start=days[0 if self.mode == "expanding" else offset],
                    train_end=days[v - 1],
                    validation_start=days[v],
                    validation_end=days[t - 1],
                    test_start=days[t],
                    test_end=days[t + self.test_sessions - 1],
                )
            )
            offset += self.step_sessions
            if len(folds) > self.maximum_folds:
                raise ValueError("Fold budget exceeded; shorten range or increase step")
        if not folds:
            raise ValueError("Insufficient sessions for a complete fold")
        return folds

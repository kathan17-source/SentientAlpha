"""Pure batch engine: values, exact input dependency spans and causal availability clocks."""

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.features.calculator import Calculator
from sentientalpha.features.contracts import (
    MAX_OUTPUT_CELLS,
    FeatureError,
    GenerationRequest,
    Observation,
)
from sentientalpha.features.frames import Frame
from sentientalpha.features.registry import Resolved
from sentientalpha.features.statistics import synchronized_rank

IntArray = NDArray[np.int64]


def running_max(values: IntArray, width: int) -> IntArray:
    result = np.zeros(len(values), dtype=np.int64)
    candidates: deque[int] = deque()
    for i, value in enumerate(values):
        while candidates and candidates[0] <= i - width:
            candidates.popleft()
        while candidates and values[candidates[-1]] <= value:
            candidates.pop()
        candidates.append(i)
        result[i] = values[candidates[0]]
    return result


@dataclass
class ClockCache:
    frame: Frame
    memo: dict[tuple[int, bool], tuple[IntArray, IntArray]] = field(default_factory=dict)

    def get(self, width: int, recursive: bool) -> tuple[IntArray, IntArray]:
        key = (0 if recursive else width, recursive)
        if key not in self.memo:
            if recursive:
                outputs = []
                for values in (self.frame.availability, self.frame.ingestion):
                    output = np.zeros(len(values), dtype=np.int64)
                    maximum = 0
                    for i, value in enumerate(values):
                        if self.frame.segment_start[i] == i or i not in self.frame.observations:
                            maximum = 0
                        maximum = max(maximum, int(value))
                        output[i] = maximum
                    outputs.append(output)
                self.memo[key] = (outputs[0], outputs[1])
            else:
                self.memo[key] = (
                    running_max(self.frame.availability, width),
                    running_max(self.frame.ingestion, width),
                )
        return self.memo[key]


@dataclass(frozen=True)
class EngineResult:
    frames: dict[str, Frame]
    rows: list[dict[str, Any]]
    columns: list[str]
    diagnostics: dict[str, Any]


def calculate(
    observations: dict[str, list[Observation]], request: GenerationRequest, resolved: list[Resolved]
) -> EngineResult:
    observations = {
        ticker: [item for item in items if item.bar.session_date <= request.end]
        for ticker, items in observations.items()
    }
    if request.as_of is not None:
        observations = {
            ticker: [
                item
                for item in items
                if item.bar.available_at <= request.as_of and item.ingested_at <= request.as_of
            ]
            for ticker, items in observations.items()
        }
    if any(
        item.bar.provider != request.provider for items in observations.values() for item in items
    ):
        raise FeatureError(
            "source_conflict", "All inputs must use the explicitly selected provider"
        )
    selected = [item for ticker in request.tickers for item in observations.get(ticker, [])]
    if not selected:
        raise FeatureError("no_data", "No source observations are visible at the requested cutoff")
    for ticker in request.tickers:
        if not observations.get(ticker):
            raise FeatureError("no_data", f"No visible prices for {ticker}")
    calendars = {item.bar.calendar for items in observations.values() for item in items}
    if len(calendars) != 1:
        raise FeatureError(
            "mixed_calendars", "Align one explicitly declared source calendar per dataset"
        )
    calendar = calendars.pop()
    first_day = min(item.bar.session_date for items in observations.values() for item in items)
    if calendar == "XNYS" and request.end.year > 2035:
        raise FeatureError("calendar_range", "XNYS calendar is supported through 2035")
    dates = sessions_in_range(calendar, first_day, request.end)
    selected_positions = [i for i, day in enumerate(dates) if request.start <= day <= request.end]
    columns = sorted(item.output_name(output) for item in resolved for output in item.warmups)
    if not selected_positions:
        raise FeatureError("empty_range", "Requested dates contain no supported sessions")
    if len(selected_positions) * len(request.tickers) * len(columns) > MAX_OUTPUT_CELLS:
        raise FeatureError("resource_limit", "Feature output exceeds the configured cell budget")
    frames = {
        ticker: Frame.build(ticker, items, dates) for ticker, items in observations.items() if items
    }
    gaps = {
        ticker: [str(day) for day in frame.missing_sessions] for ticker, frame in frames.items()
    }
    if request.gap_policy == "reject" and any(gaps.values()):
        raise FeatureError(
            "missing_sessions", "Missing trading sessions require explicit reset policy"
        )
    flagged = Counter(
        flag for items in observations.values() for item in items for flag in item.quality_flags
    )
    if request.quality_policy == "reject_flagged" and flagged:
        raise FeatureError(
            "flagged_source", "Review source quality flags or explicitly allow flagged inputs"
        )
    benchmark = frames.get(request.benchmark)
    calculators = {ticker: Calculator(frames[ticker], benchmark) for ticker in request.tickers}
    clocks = {ticker: ClockCache(frame) for ticker, frame in frames.items()}
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    missing_counts: Counter[str] = Counter()
    for ticker in request.tickers:
        frame = frames[ticker]
        for i in selected_positions:
            observation = frame.observations.get(i)
            rows[ticker, i] = {
                "asset_id": frame.asset_id,
                "ticker": ticker,
                "session_date": dates[i],
                "position": i,
                "market_at": observation.bar.session_close_at if observation else None,
                "values": {},
                "reasons": {},
                "timing": {},
            }
    for item in resolved:
        calculated = {ticker: calculators[ticker].calculate(item) for ticker in request.tickers}
        cross_section = "cross_section" in item.definition.inputs
        needs_benchmark = "benchmark_close" in item.definition.inputs
        if cross_section:
            base = np.stack([calculated[ticker]["value"] for ticker in request.tickers])
            # Disallow endpoint-only momentum bridging across an absent session.
            width = item.warmups["value"]
            for j, ticker in enumerate(request.tickers):
                length = np.arange(len(dates)) - frames[ticker].segment_start + 1
                base[j, length < width] = np.nan
            rank = np.column_stack([synchronized_rank(base[:, i]) for i in range(len(dates))])
            for j, ticker in enumerate(request.tickers):
                calculated[ticker]["value"] = rank[j]
        for output, warmup in item.warmups.items():
            name = item.output_name(output)
            own_times = {
                ticker: clocks[ticker].get(warmup, item.definition.recursive)
                for ticker in request.tickers
            }
            for ticker in request.tickers:
                frame = frames[ticker]
                vector = calculated[ticker][output]
                available, ingested = own_times[ticker]
                for i in selected_positions:
                    row = rows[ticker, i]
                    count = i - int(frame.segment_start[i]) + 1
                    reason = None
                    if i not in frame.observations:
                        reason = "missing_observation"
                    elif count < warmup:
                        reason = (
                            "insufficient_history_after_gap"
                            if frame.segment_start[i] > 0
                            else "insufficient_history"
                        )
                    elif needs_benchmark and benchmark is None:
                        reason = "missing_benchmark"
                    elif (
                        needs_benchmark
                        and benchmark is not None
                        and i not in benchmark.observations
                    ):
                        reason = "missing_benchmark_observation"
                    elif (
                        needs_benchmark
                        and benchmark is not None
                        and i - benchmark.segment_start[i] + 1 < warmup
                    ):
                        reason = "insufficient_benchmark_history"
                    elif cross_section and not np.isfinite(vector[i]):
                        reason = "incomplete_cross_section"
                    elif not np.isfinite(vector[i]):
                        reason = item.definition.undefined_reason
                    if reason is not None:
                        row["values"][name] = None
                        row["reasons"][name] = reason
                        missing_counts[reason] += 1
                        continue
                    first = (
                        int(frame.segment_start[i]) if item.definition.recursive else i - warmup + 1
                    )
                    input_available, input_ingested = int(available[i]), int(ingested[i])
                    if needs_benchmark and benchmark is not None:
                        other_available, other_ingested = clocks[request.benchmark].get(
                            warmup, False
                        )
                        input_available = max(input_available, int(other_available[i]))
                        input_ingested = max(input_ingested, int(other_ingested[i]))
                    if cross_section:
                        input_available = max(int(times[0][i]) for times in own_times.values())
                        input_ingested = max(int(times[1][i]) for times in own_times.values())
                    if not 0 <= first <= i or input_available <= 0:
                        raise FeatureError(
                            "invalid_lineage", "A feature dependency points outside past inputs"
                        )
                    row["values"][name] = float(vector[i])
                    row["timing"][name] = [input_available, input_ingested, first]
    diagnostics = {
        "is_synthetic": request.provider == "synthetic",
        "availability_kinds": dict(
            Counter(item.bar.availability_kind for items in observations.values() for item in items)
        ),
        "missing_sessions": gaps,
        "source_quality_flags": dict(flagged),
        "null_counts": dict(missing_counts),
        "calendar": calendar,
        "benchmark_present": benchmark is not None,
        "input_order": "sorted by session; duplicate sessions rejected",
        "price_return_basis": "raw price return; excludes corporate-action distributions",
    }
    return EngineResult(frames, [rows[key] for key in sorted(rows)], columns, diagnostics)

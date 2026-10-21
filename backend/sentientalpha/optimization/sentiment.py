"""Training-only pooled one-signal slope; no positive-lambda assumption or filling."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np

from sentientalpha.backtesting.contracts import Snapshot
from sentientalpha.data.calendar import session_open, sessions_in_range
from sentientalpha.optimization.contracts import Sentiment
from sentientalpha.optimization.estimation import OptimizationError


@dataclass(frozen=True)
class SentimentCell:
    ticker: str
    day: date
    value: float | None
    ready: datetime | None
    coverage: str | None
    reason: str | None
    dataset_id: str
    column: str


def fit(
    config: Sentiment,
    cells: tuple[SentimentCell, ...],
    snapshot: Snapshot,
    calendar: str,
    fit_at: datetime,
    policy: str,
) -> dict[str, Any]:
    bars = {(b.ticker, b.day): b for b in snapshot.bars}
    days = sessions_in_range(calendar, config.train_start, config.train_end)
    next_day = {d: days[i + 1] for i, d in enumerate(days[:-1])}
    pairs = []
    lineage = []
    for s in cells:
        if (
            s.dataset_id != config.dataset_id
            or s.column != config.column
            or s.day not in next_day
            or s.value is None
            or s.ready is None
            or s.coverage != "complete"
        ):
            continue
        target = bars.get((s.ticker, next_day[s.day]))
        if target is None or target.opening is None or target.close is None:
            continue
        known = max(target.available, target.ingested) if policy == "online" else target.available
        if s.ready >= session_open(calendar, target.day) or known > fit_at:
            continue
        pairs.append((s.value, float(target.close / target.opening - 1)))
        lineage.append(
            {
                "ticker": s.ticker,
                "signal_day": str(s.day),
                "signal_ready": s.ready.isoformat(),
                "label_day": str(target.day),
                "label_known_at": known.isoformat(),
                "target_source_id": target.source_id,
            }
        )
    if len(pairs) < config.minimum_samples:
        raise OptimizationError(
            "Insufficient complete, eligible sentiment training pairs", "insufficient_sentiment"
        )
    x, y = np.array(pairs).T
    center = float(x.mean())
    scale = float(x.std(ddof=1))
    if scale < 1e-12:
        raise OptimizationError(
            "Constant sentiment has no estimable slope", "insufficient_sentiment"
        )
    z = np.clip((x - center) / scale, -3, 3)
    z_center = float(z.mean())
    y_center = float(y.mean())
    ss = float(np.sum((z - z_center) ** 2))
    slope = float((z - z_center) @ (y - y_center) / ss)
    intercept = y_center - slope * z_center
    residual = y - intercept - slope * z
    se = float(np.sqrt(np.sum(residual**2) / (len(y) - 2) / ss))
    return {
        "status": "fitted",
        "method": "pooled_OLS_training_only",
        "samples": len(y),
        "normalization_mean": center,
        "normalization_std": scale,
        "clip_z": 3,
        "lambda_daily": slope,
        "lambda_annual": slope * 252,
        "intercept_daily_diagnostic_only": intercept,
        "slope_standard_error_daily_iid_descriptive": se,
        "train_start": str(config.train_start),
        "train_end": str(config.train_end),
        "fit_at": fit_at.isoformat(),
        "label": (
            "next eligible session raw open-to-close simple return; future "
            "one-session drift component"
        ),
        "lineage": lineage,
        "warnings": [
            "Pooled IID standard error is descriptive; overlapping "
            "panels/cross-asset dependence preclude a significance claim.",
            "Drift coefficient adds a next-session intraday component to the "
            "historical daily expected-return proxy; no alpha assumption.",
            "Synthetic fitting is software validation only.",
        ]
        if config.provenance == "synthetic_fixture"
        else ["No robust significance, calibration or investment improvement is established."],
    }


def adjustment(
    config: Sentiment,
    model: dict[str, Any],
    cells: tuple[SentimentCell, ...],
    tickers: tuple[str, ...],
    at: datetime,
    day: date,
) -> tuple[np.ndarray, dict[str, Any]]:
    output = []
    details = {}
    for ticker in tickers:
        eligible = [
            s
            for s in cells
            if s.ticker == ticker
            and s.day == day
            and s.dataset_id == config.dataset_id
            and s.column == config.column
        ]
        s = eligible[0] if eligible else None
        if (
            s is None
            or s.value is None
            or s.ready is None
            or s.ready > at
            or s.coverage != "complete"
        ):
            raise OptimizationError(
                "Sentiment missing, late or unverified at current decision; not neutral",
                "insufficient_sentiment",
            )
        z = float(
            np.clip((s.value - model["normalization_mean"]) / model["normalization_std"], -3, 3)
        )
        delta = z * model["lambda_annual"]
        output.append(delta)
        details[ticker] = {
            "raw_signal": s.value,
            "standardized_clipped_signal": z,
            "adjustment_annual": delta,
            "coverage": s.coverage,
            "ready": s.ready.isoformat(),
            "column": config.column,
            "dataset_id": s.dataset_id,
        }
    return np.array(output), details

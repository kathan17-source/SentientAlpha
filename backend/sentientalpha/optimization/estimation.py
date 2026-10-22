"""Past-available M2 return panels, interpretable means and audited PSD covariance."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sentientalpha.optimization.contracts import Estimator


class OptimizationError(ValueError):
    def __init__(self, message: str, code: str = "invalid_optimization", status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass(frozen=True)
class ReturnRow:
    day: date
    values: tuple[float | None, ...]
    ready: tuple[datetime | None, ...]


@dataclass(frozen=True)
class Panel:
    tickers: tuple[str, ...]
    rows: tuple[ReturnRow, ...]
    calendar: str

    def eligible(
        self, at: datetime, start: date, end: date, config: Estimator
    ) -> tuple[NDArray[np.float64], dict[str, Any]]:
        available = [
            r
            for r in self.rows
            if start <= r.day <= min(end, at.date())
            and all(
                v is not None and t is not None and t <= at
                for v, t in zip(r.values, r.ready, strict=True)
            )
        ]
        if config.history == "rolling":
            available = available[-config.lookback :]
        elif len(available) > 1260:
            raise OptimizationError(
                "Expanding estimation exceeds 1260-row budget", "history_budget"
            )
        if len(available) < config.minimum_observations:
            raise OptimizationError(
                "Insufficient complete, past-available return observations", "insufficient_data"
            )
        x = np.array([r.values for r in available], dtype=float)
        if not np.all(np.isfinite(x)) or np.any(x <= -1):
            raise OptimizationError("Invalid simple returns")
        return x, {
            "observations": len(available),
            "start": str(available[0].day),
            "end": str(available[-1].day),
            "earliest_availability": max(
                t for r in available for t in r.ready if t is not None
            ).isoformat(),
            "dates": [str(r.day) for r in available],
            "missing_policy": "listwise complete rows; M2 gaps remain missing, never bridged",
            "annualization": 252,
            "units": "annual arithmetic returns / annual covariance",
        }


@dataclass(frozen=True)
class Estimates:
    tickers: tuple[str, ...]
    mean: NDArray[np.float64]
    covariance: NDArray[np.float64]
    metadata: dict[str, Any]
    units: str = "annual"


def covariance_checked(
    matrix: NDArray[np.float64], floor: float
) -> tuple[NDArray[np.float64], dict[str, Any]]:
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or not np.all(np.isfinite(matrix)):
        raise OptimizationError("Invalid covariance shape or values")
    asymmetry = float(np.max(np.abs(matrix - matrix.T)))
    if asymmetry > 1e-9:
        raise OptimizationError("Covariance is not symmetric")
    symmetric = (matrix + matrix.T) / 2
    eigen, vectors = np.linalg.eigh(symmetric)
    if eigen[0] < -1e-8:
        raise OptimizationError("Materially indefinite covariance refused")
    adjusted = np.maximum(eigen, floor)
    result = (vectors * adjusted) @ vectors.T
    return result, {
        "minimum_eigenvalue_before": float(eigen[0]),
        "eigenvalue_floor": floor,
        "eigenvalue_adjustment_total": float(np.sum(adjusted - eigen)),
        "symmetry_residual_before": asymmetry,
        "condition_number_after": float(adjusted[-1] / adjusted[0]) if adjusted[0] > 0 else None,
        "zero_variance_assets": int(np.sum(np.diag(matrix) <= 1e-14)),
    }


def estimate(panel: Panel, at: datetime, start: date, end: date, config: Estimator) -> Estimates:
    x, metadata = panel.eligible(at, start, end, config)
    n = len(x)
    weights = config.decay ** np.arange(n - 1, -1, -1, dtype=float)
    weights /= weights.sum()
    effective = float(1 / (weights @ weights))
    if (
        config.mean == "exponential" or config.covariance == "exponential"
    ) and effective <= 1 + 1e-8:
        raise OptimizationError(
            "Insufficient effective exponentially weighted history", "insufficient_data"
        )
    historical = x.mean(axis=0)
    if config.mean == "exponential":
        mean = weights @ x
    elif config.mean == "shrinkage":
        mean = (
            1 - config.shrinkage
        ) * historical + config.shrinkage * config.prior_annual_return / 252
    else:
        mean = historical
    if config.covariance == "exponential":
        centered = x - weights @ x
        cov = (centered.T * weights) @ centered / (1 - float(weights @ weights))
    else:
        centered = x - historical
        cov = centered.T @ centered / (n - 1)
        if config.covariance == "diagonal_shrinkage":
            cov = (1 - config.shrinkage) * cov + config.shrinkage * np.diag(np.diag(cov))
    cov, audit = covariance_checked(cov * 252, config.eigenvalue_floor)
    warnings = ["Historical estimates are noisy; expected returns are not realized future returns."]
    if (
        config.mean == "exponential" or config.covariance == "exponential"
    ) and effective < config.minimum_observations:
        warnings.append(
            "Effective EW sample size is below the nominal minimum; estimates are unstable."
        )
    if n < max(60, 3 * len(panel.tickers)):
        warnings.append("Limited observations relative to universe dimension.")
    if audit["eigenvalue_adjustment_total"] > 0:
        warnings.append("Explicit eigenvalue regularization applied.")
    metadata.update(
        estimator=config.model_dump(mode="json"),
        covariance_audit=audit,
        warnings=warnings,
        historical_mean_standard_error_annual=(
            np.std(x, axis=0, ddof=1) / np.sqrt(n) * 252
        ).tolist(),
        effective_ew_observations=float(1 / (weights @ weights)),
    )
    return Estimates(panel.tickers, mean * 252, cov, metadata)

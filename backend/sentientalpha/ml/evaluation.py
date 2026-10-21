"""Computed metrics, held-out calibration and dependent-outcome uncertainty."""

from typing import Any

import numpy as np
from scipy.special import expit, logit
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from sentientalpha.ml.models import Array


def correlation(y: Array, p: Array, rank: bool = False) -> float | None:
    if len(y) < 3 or np.ptp(y) < 1e-14 or np.ptp(p) < 1e-14:
        return None
    value = float(spearmanr(y, p).statistic if rank else np.corrcoef(y, p)[0, 1])
    return value if np.isfinite(value) else None


def metrics(y: Array, p: Array, task: str) -> dict[str, Any]:
    n = len(y)
    if not n:
        return {"n": 0, "status": "insufficient_data"}
    result: dict[str, Any] = {
        "n": n,
        "prediction_mean": float(p.mean()),
        "prediction_std": float(p.std()),
        "correlation": correlation(y, p),
        "rank_ic": correlation(y, p, True),
    }
    if task != "direction":
        error = p - y
        denominator = float(np.sum((y - y.mean()) ** 2))
        result.update(
            mae=float(np.mean(abs(error))),
            rmse=float(np.sqrt(np.mean(error**2))),
            bias=float(error.mean()),
            r2=1 - float(np.sum(error**2)) / denominator if n > 1 and denominator > 0 else None,
            information_coefficient=correlation(y, p),
        )
        return result
    p = np.clip(p, 1e-15, 1 - 1e-15)
    labels = p >= 0.5
    tp, tn = int(np.sum(labels & (y == 1))), int(np.sum(~labels & (y == 0)))
    fp, fn = int(np.sum(labels & (y == 0))), int(np.sum(~labels & (y == 1)))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    specificity = tn / (tn + fp) if tn + fp else None
    bins: list[dict[str, Any]] = []
    for i in range(10):
        mask = (p >= i / 10) & (p < (i + 1) / 10)
        bins.append(
            {
                "lower": i / 10,
                "upper": (i + 1) / 10,
                "n": int(mask.sum()),
                "probability": float(p[mask].mean()) if mask.any() else None,
                "frequency": float(y[mask].mean()) if mask.any() else None,
            }
        )
    result.update(
        accuracy=(tp + tn) / n,
        balanced_accuracy=(recall + specificity) / 2
        if recall is not None and specificity is not None
        else None,
        precision=precision,
        recall=recall,
        f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        roc_auc=float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        pr_auc_average_precision=float(average_precision_score(y, p))
        if len(np.unique(y)) == 2
        else None,
        brier=float(np.mean((p - y) ** 2)),
        log_loss=float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        confusion_matrix=[[tn, fp], [fn, tp]],
        prevalence=float(y.mean()),
        reliability=bins,
        calibration_error=sum(
            b["n"] / n * abs(float(b["probability"]) - float(b["frequency"]))
            for b in bins
            if b["n"]
        ),
    )
    return result


def fit_calibration(p: Array, y: Array, method: str) -> dict[str, Any]:
    minimum = 1000 if method == "isotonic" else 40
    if method == "none":
        return {"method": "none", "status": "not_requested", "n": len(y)}
    if len(y) < minimum or min(np.sum(y == 0), np.sum(y == 1)) < 10:
        return {
            "method": "none",
            "requested": method,
            "status": "insufficient_data",
            "n": len(y),
            "minimum": minimum,
        }
    if method == "sigmoid":
        model = LogisticRegression(C=1, max_iter=1000).fit(
            logit(np.clip(p, 1e-7, 1 - 1e-7)).reshape(-1, 1), y
        )
        return {
            "method": method,
            "status": "completed",
            "n": len(y),
            "coefficient": float(model.coef_[0, 0]),
            "intercept": float(model.intercept_[0]),
        }
    iso = IsotonicRegression(out_of_bounds="clip").fit(p, y)
    return {
        "method": method,
        "status": "completed",
        "n": len(y),
        "x": iso.X_thresholds_.tolist(),
        "y": iso.y_thresholds_.tolist(),
    }


def calibrate(state: dict[str, Any], p: Array) -> Array:
    if state["method"] == "sigmoid":
        return expit(state["coefficient"] * logit(np.clip(p, 1e-7, 1 - 1e-7)) + state["intercept"])
    if state["method"] == "isotonic":
        return np.interp(p, state["x"], state["y"])
    return p.copy()


def block_interval(daily_errors: Array, horizon: int, seed: int) -> dict[str, Any]:
    # One daily cross-sectional mean per timestamp, contiguous moving-block resampling.
    n, length = len(daily_errors), max(10, horizon)
    if n < 4 * length:
        return {"status": "insufficient_data", "sessions": n, "block_sessions": length}
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(300):
        starts = rng.integers(0, n - length + 1, size=int(np.ceil(n / length)))
        samples.append(np.concatenate([daily_errors[s : s + length] for s in starts])[:n].mean())
    low, high = np.quantile(samples, [0.025, 0.975])
    return {
        "status": "descriptive",
        "sessions": n,
        "block_sessions": length,
        "replicates": 300,
        "mean_loss_difference": float(daily_errors.mean()),
        "interval95": [float(low), float(high)],
        "warning": (
            "Conditional historical uncertainty; excludes model-selection "
            "and structural-break uncertainty."
        ),
    }

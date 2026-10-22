"""Train-only preprocessing and safe numeric inference artifacts (no pickle loader)."""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.special import expit
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from threadpoolctl import threadpool_limits

from sentientalpha.ml.contracts import Candidate, MLException, ResearchRequest

Array = NDArray[np.float64]


def preprocess(x: Array, y: Array, request: ResearchRequest) -> tuple[dict[str, Any], Array]:
    if np.isinf(x).any() or not np.isfinite(y).all():
        raise MLException("Nonfinite training data")
    keep: list[int] = []
    seen: list[int] = []
    for j in range(x.shape[1]):
        col = x[:, j]
        finite = col[np.isfinite(col)]
        if not len(finite) or np.ptp(finite) <= 1e-14:
            continue
        if any(np.array_equal(col, x[:, k], equal_nan=True) for k in seen):
            continue
        keep.append(j)
        seen.append(j)
    if not keep:
        raise MLException("No nonconstant training features", "insufficient_data")
    z = x[:, keep].copy()
    median = np.nanmedian(z, axis=0)
    indicators = np.isnan(z).astype(float)
    z = np.where(np.isnan(z), median, z)
    q = request.clip_quantile
    low, high = np.quantile(z, [q, 1 - q], axis=0)
    z = np.clip(z, low, high)
    mean, scale = z.mean(axis=0), z.std(axis=0)
    scale[scale < 1e-14] = 1
    z = (z - mean) / scale
    names = [request.columns[j] for j in keep]
    if request.missing == "median_indicator":
        z = np.column_stack([z, indicators])
        names += ["missing:" + n for n in names]
    selected = list(range(z.shape[1]))
    if request.select_features and request.select_features < len(selected):
        scores = [
            abs(float(np.corrcoef(z[:, j], y)[0, 1]))
            if np.std(z[:, j]) > 0 and np.std(y) > 0
            else 0
            for j in selected
        ]
        selected = sorted(
            sorted(selected, key=lambda j: (-scores[j], j))[: request.select_features]
        )
        z = z[:, selected]
    state = {
        "columns": request.columns,
        "keep": keep,
        "median": median.tolist(),
        "low": low.tolist(),
        "high": high.tolist(),
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "indicators": request.missing == "median_indicator",
        "selected": selected,
        "names": [names[j] for j in selected],
        "training_rows": len(x),
        "drift_reference": {"mean": z.mean(axis=0).tolist(), "std": z.std(axis=0).tolist()},
    }
    return state, z


def transform(state: dict[str, Any], x: Array, columns: list[str]) -> Array:
    if (
        columns != state["columns"]
        or x.ndim != 2
        or x.shape[1] != len(columns)
        or np.isinf(x).any()
    ):
        raise MLException("Inference feature schema/order or finite-value mismatch")
    z = x[:, state["keep"]].copy()
    indicators = np.isnan(z).astype(float)
    z = np.where(np.isnan(z), state["median"], z)
    z = (np.clip(z, state["low"], state["high"]) - state["mean"]) / state["scale"]
    if state["indicators"]:
        z = np.column_stack([z, indicators])
    return z[:, state["selected"]]


def tree_export(tree: Any, classification: bool) -> dict[str, Any]:
    t = tree.tree_
    value = t.value[:, 0, :]
    if classification:
        value = value[:, 1] / value.sum(axis=1)
    else:
        value = value[:, 0]
    return {
        "left": t.children_left.tolist(),
        "right": t.children_right.tolist(),
        "feature": t.feature.tolist(),
        "threshold": t.threshold.tolist(),
        "value": value.tolist(),
    }


def tree_predict(t: dict[str, Any], x: Array) -> Array:
    size = len(t["left"])
    if not 1 <= size <= 127 or any(
        len(t[k]) != size for k in ("right", "feature", "threshold", "value")
    ):
        raise MLException("Invalid bounded tree artifact")
    result = []
    # Explicit traversal bound also refuses cycles in corrupted JSON.
    for row in x:
        node = 0
        for _ in range(size + 1):
            if not 0 <= node < size:
                raise MLException("Invalid tree child")
            left = t["left"][node]
            if left == -1:
                result.append(t["value"][node])
                break
            j = t["feature"][node]
            if not 0 <= j < x.shape[1]:
                raise MLException("Invalid tree feature")
            node = left if row[j] <= t["threshold"][node] else t["right"][node]
        else:
            raise MLException("Cyclic tree artifact")
    return np.asarray(result, dtype=float)


def train(candidate: Candidate, x: Array, y: Array, request: ResearchRequest) -> dict[str, Any]:
    state, z = preprocess(x, y, request)
    name = candidate.model
    classification = request.target.task == "direction"
    if (
        classification
        and len(np.unique(y)) < 2
        and name not in {"majority", "prevalence", "momentum"}
    ):
        raise MLException("Classifier training needs both classes", "insufficient_data")
    artifact: dict[str, Any] = {
        "format": "numeric-json-v1",
        "preprocessing": state,
        "model": name,
        "task": request.target.task,
        "parameters": candidate.model_dump(),
    }
    if name in {"majority", "prevalence", "zero", "mean", "historical_volatility"}:
        value = float(y.mean())
        if name == "majority":
            value = float(value >= 0.5)
        if name == "zero":
            value = 0.0
        if name == "historical_volatility":
            if "return" not in request.columns:
                raise MLException("Historical volatility baseline needs daily return feature")
            value = float(np.sqrt(np.nanmean(x[:, request.columns.index("return")] ** 2) * 252))
        artifact.update(kind="constant", value=value)
        return artifact
    if name == "momentum":
        if "return" not in request.columns:
            raise MLException("Momentum baseline needs daily return feature")
        artifact.update(kind="momentum", column=request.columns.index("return"))
        return artifact
    estimators = {
        "logistic": lambda: LogisticRegression(
            C=candidate.strength, max_iter=1000, random_state=request.seed
        ),
        "ridge": lambda: Ridge(alpha=candidate.strength),
        "elastic_net": lambda: ElasticNet(
            alpha=candidate.strength, l1_ratio=0.5, max_iter=5000, random_state=request.seed
        ),
        "forest_classifier": lambda: RandomForestClassifier(
            n_estimators=candidate.trees,
            max_depth=candidate.depth,
            min_samples_leaf=candidate.leaf,
            n_jobs=1,
            random_state=request.seed,
        ),
        "forest_regressor": lambda: RandomForestRegressor(
            n_estimators=candidate.trees,
            max_depth=candidate.depth,
            min_samples_leaf=candidate.leaf,
            n_jobs=1,
            random_state=request.seed,
        ),
        "boost_classifier": lambda: GradientBoostingClassifier(
            n_estimators=candidate.trees,
            max_depth=candidate.depth,
            min_samples_leaf=candidate.leaf,
            learning_rate=candidate.learning_rate,
            random_state=request.seed,
        ),
        "boost_regressor": lambda: GradientBoostingRegressor(
            n_estimators=candidate.trees,
            max_depth=candidate.depth,
            min_samples_leaf=candidate.leaf,
            learning_rate=candidate.learning_rate,
            random_state=request.seed,
        ),
    }
    with threadpool_limits(limits=1):
        model = estimators[name]()
        model.fit(z, y)
    if name in {"logistic", "ridge", "elastic_net"}:
        artifact.update(
            kind="linear",
            coefficients=np.asarray(model.coef_).reshape(-1).tolist(),
            intercept=float(np.asarray(model.intercept_).reshape(-1)[0]),
        )
        importance = np.asarray(model.coef_).reshape(-1)
    else:
        boosting = name.startswith("boost")
        trees = list(model.estimators_.reshape(-1)) if boosting else model.estimators_
        artifact.update(
            kind="boost" if boosting else "forest",
            trees=[tree_export(t, classification and not boosting) for t in trees],
        )
        if boosting:
            if classification:
                p = float(model.init_.class_prior_[1])
                initial = float(np.log(p / (1 - p)))
            else:
                initial = float(model.init_.constant_[0, 0])
            artifact.update(initial=initial, learning_rate=candidate.learning_rate)
        importance = model.feature_importances_
    artifact["importance"] = [
        {
            "feature": n,
            "value": float(v),
            "measure": "coefficient_standardized"
            if name in {"logistic", "ridge", "elastic_net"}
            else "impurity_importance",
            "causal": False,
        }
        for n, v in zip(state["names"], importance, strict=True)
    ]
    expected = model.predict_proba(z)[:, 1] if classification else model.predict(z)
    if request.target.task == "volatility":
        expected = np.maximum(expected, 0)
    if not np.allclose(infer(artifact, x, request.columns), expected, rtol=1e-7, atol=1e-9):
        raise MLException(
            "Numeric artifact disagrees with trained estimator", "artifact_mismatch", 500
        )
    return artifact


def infer(artifact: dict[str, Any], x: Array, columns: list[str]) -> Array:
    if artifact.get("format") != "numeric-json-v1":
        raise MLException("Unknown model format")
    z = transform(artifact["preprocessing"], x, columns)
    kind = artifact["kind"]
    if kind == "constant":
        result = np.full(len(x), artifact["value"], dtype=float)
    elif kind == "momentum":
        result = (np.nan_to_num(x[:, artifact["column"]], nan=0) > 0).astype(float)
    elif kind == "linear":
        result = z @ np.array(artifact["coefficients"]) + artifact["intercept"]
        if artifact["task"] == "direction":
            result = expit(result)
    elif kind in {"forest", "boost"}:
        trees = artifact["trees"]
        if not 1 <= len(trees) <= 150:
            raise MLException("Tree count exceeds artifact bound")
        # sklearn trees compare float32 inputs.
        outputs = np.array([tree_predict(t, z.astype(np.float32).astype(float)) for t in trees])
        result = (
            outputs.mean(axis=0)
            if kind == "forest"
            else artifact["initial"] + artifact["learning_rate"] * outputs.sum(axis=0)
        )
        if kind == "boost" and artifact["task"] == "direction":
            result = expit(result)
    else:
        raise MLException("Unknown numeric model")
    if not np.isfinite(result).all():
        raise MLException("Nonfinite inference")
    if artifact["task"] == "direction" and ((result < 0).any() or (result > 1).any()):
        raise MLException("Invalid probability artifact output")
    if artifact["task"] == "volatility":
        result = np.maximum(result, 0)
    return np.asarray(result, dtype=float)

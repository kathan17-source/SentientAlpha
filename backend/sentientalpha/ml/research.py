"""Purged chronological selection, separate calibration, frozen OOS inference."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from time import monotonic
from typing import Any, cast

import numpy as np

from sentientalpha.backtesting.storage import digest
from sentientalpha.data.calendar import session_open, sessions_in_range
from sentientalpha.ml.contracts import Candidate, MLException, ResearchRequest, Window
from sentientalpha.ml.dataset import Dataset, Observation
from sentientalpha.ml.evaluation import (
    block_interval,
    calibrate,
    correlation,
    fit_calibration,
    metrics,
)
from sentientalpha.ml.models import infer, train, transform


def matrix(rows: list[Observation]) -> np.ndarray:
    return np.array([[np.nan if v is None else v for v in r.values] for r in rows], dtype=float)


def eligible(rows: list[Observation], request: ResearchRequest) -> list[Observation]:
    return [
        r
        for r in rows
        if (request.missing != "drop" or all(v is not None for v in r.values))
        and any(v is not None for v in r.values)
    ]


def partition(
    ds: Dataset, request: ResearchRequest, w: Window
) -> tuple[dict[str, list[Observation]], dict[str, Any]]:
    ranges = {
        "train": (w.train_start, w.train_end, w.validation_start),
        "validation": (w.validation_start, w.validation_end, w.calibration_start),
        "calibration": (w.calibration_start, w.calibration_end, w.test_start),
    }
    result, audit = {}, {}
    for name, (start, end, boundary) in ranges.items():
        cutoff = session_open(ds.calendar, boundary) - timedelta(microseconds=1)
        dates = sessions_in_range(ds.calendar, start, end)
        if request.embargo_sessions:
            dates = dates[: -request.embargo_sessions]
        allowed = set(dates)
        raw = [r for r in ds.rows if start <= r.day <= end]
        result[name] = eligible(
            [
                r
                for r in raw
                if r.day in allowed
                and r.decision < cutoff
                and r.target is not None
                and r.target_available is not None
                and r.target_available <= cutoff
                and r.target_end is not None
                and r.target_end < cutoff
            ],
            request,
        )
        audit[name] = {
            "cutoff": cutoff.isoformat(),
            "raw_rows": len(raw),
            "eligible_rows": len(result[name]),
            "purged_or_missing": len(raw) - len(result[name]),
            "last_label_available": max(
                (
                    r.target_available.isoformat()
                    for r in result[name]
                    if r.target_available is not None
                ),
                default=None,
            ),
        }
    result["test"] = eligible([r for r in ds.rows if w.test_start <= r.day <= w.test_end], request)
    return result, audit


def score(y: np.ndarray, p: np.ndarray, task: str) -> float:
    m = metrics(y, p, task)
    return float(m["log_loss"] if task == "direction" else m["rmse"])


def inference_guard(model: dict[str, Any], at: datetime, columns: list[str]) -> None:
    if columns != model["artifact"]["preprocessing"]["columns"]:
        raise MLException("Feature schema/order mismatch")
    if at < datetime.fromisoformat(model["effective_at"]):
        raise MLException("Model trained or calibrated after the requested prediction time")
    if digest(model["artifact"]) != model["artifact_hash"]:
        raise MLException("Model artifact hash mismatch", "artifact_mismatch", 409)


def evaluate(request: ResearchRequest, ds: Dataset) -> dict[str, Any]:
    if list(ds.columns) != request.columns:
        raise MLException("Feature order mismatch")
    start_clock = monotonic()
    folds, models, predictions = [], [], []
    for fold_index, w in enumerate(request.windows):
        if monotonic() - start_clock > request.seconds:
            raise MLException("ML cooperative time budget exceeded", "time_budget", 429)
        groups, audit = partition(ds, request, w)
        tr, va, ca, te = (groups[k] for k in ("train", "validation", "calibration", "test"))
        fold: dict[str, Any] = {
            "fold": fold_index,
            "window": w.model_dump(mode="json"),
            "eligibility": audit,
            "candidates": [],
        }
        folds.append(fold)
        if (
            len(tr) < request.minimum_train
            or len(va) < request.minimum_evaluation
            or len(te) < request.minimum_evaluation
        ):
            fold.update(
                status="insufficient_data",
                reason="Insufficient eligible chronological observations",
            )
            continue
        x, y = matrix(tr), np.array([r.target for r in tr], dtype=float)
        xv, yv = matrix(va), np.array([r.target for r in va], dtype=float)
        fitted = []
        for i, candidate in enumerate(request.candidates):
            if monotonic() - start_clock > request.seconds:
                raise MLException("ML cooperative time budget exceeded", "time_budget", 429)
            try:
                art = train(candidate, x, y, request)
                p = infer(art, xv, request.columns)
                loss = score(yv, p, request.target.task)
                fold["candidates"].append(
                    {
                        "candidate": candidate.model_dump(),
                        "validation_loss": loss,
                        "status": "completed",
                    }
                )
                fitted.append((loss, i, art))
            except (MLException, ValueError) as exc:
                fold["candidates"].append(
                    {
                        "candidate": candidate.model_dump(),
                        "status": "failed",
                        "reason": str(exc)[:200],
                    }
                )
        if not fitted:
            fold.update(status="failed", reason="No fitted candidate")
            continue
        # Exact ties prefer the earlier declared candidate. No test outcomes enter selection.
        best_loss = min(item[0] for item in fitted)

        def complexity(item: tuple[float, int, dict[str, Any]]) -> tuple[float, int]:
            candidate = request.candidates[item[1]]
            value = (
                candidate.trees * 2**candidate.depth
                if "forest" in candidate.model or "boost" in candidate.model
                else candidate.strength
                if candidate.model == "logistic"
                else 1
            )
            return float(value), item[1]

        loss, chosen, art = min(
            [item for item in fitted if item[0] <= best_loss + request.selection_tolerance],
            key=complexity,
        )
        fold["selection_rule"] = {
            "best_validation_loss": best_loss,
            "minimum_advantage": request.selection_tolerance,
            "rule": "Prefer lower configured complexity inside tolerance; no test use",
        }
        cal = (
            fit_calibration(
                infer(art, matrix(ca), request.columns),
                np.array([r.target for r in ca], dtype=float),
                request.calibration,
            )
            if ca
            else {"method": "none", "status": "insufficient_data", "n": 0}
        )
        effective = session_open(ds.calendar, w.test_start) - timedelta(microseconds=1)
        model = {
            "fold": fold_index,
            "selected": request.candidates[chosen].model_dump(),
            "artifact": art,
            "artifact_hash": digest(art),
            "effective_at": effective.isoformat(),
            "training_cutoff": audit["train"]["cutoff"],
            "calibration": cal,
            "target": request.target.model_dump(),
            "feature_schema": request.columns,
            "training_ids_hash": digest([(r.ticker, str(r.day), r.target) for r in tr]),
            "selection_metric": "log_loss" if request.target.task == "direction" else "rmse",
        }
        models.append(model)
        raw = infer(art, matrix(te), request.columns)
        p = calibrate(cal, raw) if request.target.task == "direction" else raw
        baselines = [
            Candidate.model_validate({"model": m})
            for m in (
                ["majority", "prevalence", "momentum"]
                if request.target.task == "direction"
                else (
                    ["mean", "historical_volatility"]
                    if request.target.task == "volatility"
                    else ["zero", "mean"]
                )
            )
        ]
        evaluated = [
            (j, r)
            for j, r in enumerate(te)
            if r.target is not None
            and r.target_available is not None
            and r.target_available <= request.source_as_of
        ]
        indices = [j for j, _ in evaluated]
        yt = np.array([r.target for _, r in evaluated], dtype=float)
        test_metrics = metrics(yt, p[indices], request.target.task)
        base_metrics, base_values = {}, {}
        for baseline in baselines:
            try:
                ba = train(baseline, x, y, request)
                bp = infer(ba, matrix(te), request.columns)
                base_values[baseline.model] = bp
                base_metrics[baseline.model] = metrics(yt, bp[indices], request.target.task)
            except MLException as exc:
                base_metrics[baseline.model] = {"status": "unavailable", "reason": str(exc)}
        importance = []
        # Row permutation is a descriptive association diagnostic, never selection or causality.
        if len(indices) >= request.minimum_evaluation:
            rng = np.random.default_rng(request.seed)
            xt = matrix([r for _, r in evaluated])
            reference = score(yt, p[indices], request.target.task)
            for j, name in enumerate(request.columns):
                xp = xt.copy()
                xp[:, j] = xp[rng.permutation(len(xp)), j]
                pp = infer(art, xp, request.columns)
                if request.target.task == "direction":
                    pp = calibrate(cal, pp)
                importance.append(
                    {
                        "feature": name,
                        "loss_increase": score(yt, pp, request.target.task) - reference,
                        "measure": "held_out_row_permutation_descriptive",
                        "n": len(yt),
                        "causal": False,
                    }
                )
        by_ticker = {}
        for ticker in request.tickers:
            ii = [k for k, (_, r) in enumerate(evaluated) if r.ticker == ticker]
            by_ticker[ticker] = metrics(
                yt[ii], p[np.array(indices, dtype=int)[ii]], request.target.task
            )
        drift = transform(art["preprocessing"], matrix(te), request.columns)
        train_z = transform(art["preprocessing"], x, request.columns)
        drift_mean = (drift.mean(axis=0) - train_z.mean(axis=0)) / np.maximum(
            train_z.std(axis=0), 1e-8
        )
        comparator = "prevalence" if request.target.task == "direction" else "mean"
        daily: dict[date, list[float]] = {}
        if comparator in base_values:
            for k, r in evaluated:
                a, b = p[k], base_values[comparator][k]
                assert r.target is not None
                yy = float(r.target)
                if request.target.task == "direction":
                    a, b = np.clip(a, 1e-15, 1 - 1e-15), np.clip(b, 1e-15, 1 - 1e-15)
                    difference = -(yy * np.log(a) + (1 - yy) * np.log(1 - a)) + (
                        yy * np.log(b) + (1 - yy) * np.log(1 - b)
                    )
                else:
                    difference = (a - yy) ** 2 - (b - yy) ** 2
                daily.setdefault(r.day, []).append(difference)
        regimes: dict[str, Any] = {}
        periods: dict[str, Any] = {}
        cross_sectional = []
        if "return" in request.columns:
            jret = request.columns.index("return")
            training_magnitudes = [
                abs(cast(float, r.values[jret])) for r in tr if r.values[jret] is not None
            ]
            boundary = float(np.median(training_magnitudes))
            for regime in (
                "positive_daily_return",
                "negative_daily_return",
                "high_absolute_return",
                "low_absolute_return",
            ):
                ii = [
                    k
                    for k, (_, r) in enumerate(evaluated)
                    if r.values[jret] is not None
                    and (
                        cast(float, r.values[jret]) >= 0
                        if regime == "positive_daily_return"
                        else cast(float, r.values[jret]) < 0
                        if regime == "negative_daily_return"
                        else abs(cast(float, r.values[jret])) > boundary
                        if regime == "high_absolute_return"
                        else abs(cast(float, r.values[jret])) <= boundary
                    )
                ]
                regimes[regime] = {
                    "metrics": metrics(
                        yt[ii], p[np.array(indices, dtype=int)[ii]], request.target.task
                    ),
                    "definition": (
                        "Decision-available daily-return sign or magnitude; "
                        "train median magnitude threshold"
                    ),
                    "threshold": boundary,
                    "warning": "Descriptive proxy, not a fitted latent regime",
                }
        for period in sorted({str(r.day)[:7] for _, r in evaluated}):
            ii = [k for k, (_, r) in enumerate(evaluated) if str(r.day).startswith(period)]
            periods[period] = metrics(
                yt[ii], p[np.array(indices, dtype=int)[ii]], request.target.task
            )
        for day in sorted({r.day for _, r in evaluated}):
            ii = [k for k, (_, r) in enumerate(evaluated) if r.day == day]
            cross_sectional.append(
                {
                    "day": str(day),
                    "n": len(ii),
                    "rank_ic": correlation(yt[ii], p[np.array(indices, dtype=int)[ii]], True),
                }
            )
        for j, r in enumerate(te):
            inference_guard(model, r.decision, request.columns)
            predictions.append(
                {
                    "fold": fold_index,
                    "ticker": r.ticker,
                    "asset_id": r.asset_id,
                    "day": str(r.day),
                    "decision_at": r.decision.isoformat(),
                    "earliest_execution_at": r.execution.isoformat(),
                    "model_hash": model["artifact_hash"],
                    "model_version": digest(model),
                    "training_cutoff": model["training_cutoff"],
                    "prediction_type": request.target.task,
                    "units": "probability"
                    if request.target.task == "direction"
                    else "simple_return_horizon"
                    if request.target.task == "return"
                    else "annualized_intraday_log_rms",
                    "calibration": cal,
                    "feature_set_hash": digest(ds.metadata),
                    "snapshot_references": ds.metadata.get("datasets", []),
                    "value": float(p[j]),
                    "raw_value": float(raw[j]),
                    "horizon": request.target.horizon,
                    "target_convention": request.target.convention,
                    "origin": "retrospective_research"
                    if request.information_policy == "retrospective"
                    else "historical_walk_forward",
                    "evaluation_eligible": j in indices,
                    "realized": r.target if j in indices else None,
                    "inference_status": "completed",
                    "warnings": [
                        "Research generated after historical decisions; never issued live."
                    ],
                }
            )
        fold.update(
            status="completed",
            selected_candidate=chosen,
            validation_loss=loss,
            calibration=cal,
            metrics=test_metrics,
            raw_metrics=metrics(yt, raw[indices], request.target.task),
            baselines=base_metrics,
            native_importance=art.get("importance", []),
            permutation_importance=importance,
            by_ticker=by_ticker,
            by_period=periods,
            regimes=regimes,
            cross_sectional_ic=cross_sectional,
            monitoring={
                "standardized_feature_mean_shift": drift_mean.tolist(),
                "missing_rate_train": np.isnan(x).mean(axis=0).tolist(),
                "missing_rate_test": np.isnan(matrix(te)).mean(axis=0).tolist(),
                "window": "current OOS fold vs its training window",
                "automatic_retraining": False,
            },
            uncertainty=block_interval(
                np.array([np.mean(v) for _, v in sorted(daily.items())]),
                request.target.horizon,
                request.seed,
            ),
        )
    return {
        "status": "completed"
        if folds and all(f["status"] == "completed" for f in folds)
        else "insufficient_data"
        if all(f["status"] == "insufficient_data" for f in folds)
        else "failed"
        if all(f["status"] == "failed" for f in folds)
        else "partial",
        "folds": folds,
        "models": models,
        "predictions": predictions,
        "sentiment_alpha": "UNVERIFIED",
        "execution_certified": False,
    }


def ablations(request: ResearchRequest, ds: Dataset) -> dict[str, Any]:
    price = [c for c in request.columns if not c.startswith("sent_")]
    level = [c for c in request.columns if c.startswith("sent_mean")]
    dynamics = [c for c in request.columns if c.startswith(("sent_momentum", "sent_surprise"))]
    if not price or not level or not dynamics:
        return {
            "status": "insufficient_data",
            "reason": "Price, level and dynamics columns required",
            "sentiment_alpha": "UNVERIFIED",
        }
    # Lock common observations before fitting any variant, including price-only.
    common = tuple(r for r in ds.rows if all(v is not None for v in r.values))
    outputs = {}
    for name, cols, selection in [
        ("price_only", price, None),
        ("level", price + level, None),
        ("dynamics", price + dynamics, None),
        (
            "selected_sentiment",
            list(ds.columns),
            request.select_features or min(5, len(ds.columns)),
        ),
    ]:
        indices = [ds.columns.index(c) for c in cols]
        sub = Dataset(
            tuple(cols),
            tuple(replace(r, values=tuple(r.values[i] for i in indices)) for r in common),
            ds.prices,
            ds.calendar,
            ds.metadata,
        )
        cfg = request.model_copy(update={"columns": cols, "select_features": selection})
        outputs[name] = evaluate(cfg, sub)
    return {
        "status": "completed",
        "common_rows": len(common),
        "variants": outputs,
        "provenance": request.sentiment_provenance,
        "sentiment_alpha": "UNVERIFIED",
    }

"""Original versioned forecasts and locked, validation-selected strategy evidence."""

from datetime import datetime
from math import isfinite
from typing import Any, Literal

from sentientalpha.committee.agents import unavailable
from sentientalpha.committee.contracts import AgentRecommendation, Evidence
from sentientalpha.committee.requests import Request


def quant(
    request: Request, source: dict[str, Any] | None, ticker: str, at: datetime, day: str
) -> AgentRecommendation:
    if source is None:
        return unavailable("quant", ticker, at, "No configured immutable M6 model")
    m = source["model"]
    selected = [
        p
        for p in source["predictions"]
        if p["payload"]["ticker"] == ticker and p["payload"]["day"] == day
    ]
    if len(selected) != 1:
        return unavailable("quant", ticker, at, "No unique original forecast for this session")
    row = selected[0]
    p = row["payload"]
    training = datetime.fromisoformat(p["training_cutoff"])
    effective = datetime.fromisoformat(m["effective_at"])
    ready = datetime.fromisoformat(p["decision_at"])
    generated = datetime.fromisoformat(row["generated_at"])
    created = datetime.fromisoformat(source["created_at"])
    if (
        datetime.fromisoformat(m["training_cutoff"]) != training
        or m["target"]["horizon"] != request.horizon
        or p["calibration"] != m["calibration"]
    ):
        return unavailable(
            "quant", ticker, at, "Model/forecast cutoff, horizon or calibration mismatch", "invalid"
        )
    if training >= at or effective > at or ready > at:
        return unavailable(
            "quant", ticker, at, "Future-trained/effective/unavailable model forecast", "invalid"
        )
    if (
        p["horizon"] != request.horizon
        or p["model_version"] != source["version"]
        or p["model_hash"] != m["artifact_hash"]
        or p["inference_status"] != "completed"
    ):
        return unavailable(
            "quant", ticker, at, "Forecast version/horizon/status mismatch", "invalid"
        )
    if request.information_policy != "retrospective" and p["origin"] == "retrospective_research":
        return unavailable(
            "quant", ticker, at, "Retrospective forecast is not historical live evidence"
        )
    if request.information_policy == "online" and max(generated, created) > at:
        return unavailable("quant", ticker, at, "Forecast/model not actually issued by decision")
    value = float(p["value"])
    units = p["units"]
    expected_units = {
        "direction": "probability",
        "return": "simple_return_horizon",
        "volatility": "annualized_intraday_log_rms",
    }[m["target"]["task"]]
    if (
        units != expected_units
        or p["prediction_type"] != m["target"]["task"]
        or p["feature_set_hash"] != source["feature_set_hash"]
    ):
        return unavailable(
            "quant", ticker, at, "Forecast feature/type/units incompatibility", "invalid"
        )
    if not isfinite(value) or units not in {
        "probability",
        "simple_return_horizon",
        "annualized_intraday_log_rms",
    }:
        return unavailable("quant", ticker, at, "Nonfinite or incompatible forecast", "invalid")
    if units == "probability" and not 0 <= value <= 1:
        return unavailable("quant", ticker, at, "Probability outside valid bounds", "invalid")
    if units == "annualized_intraday_log_rms":
        return unavailable(
            "quant", ticker, at, "Volatility forecast is risk description, not a directional vote"
        )
    matured = {
        (o["ticker"], o["day"]): o
        for o in source["outcomes"]
        if o["target_available"] is not None and datetime.fromisoformat(o["target_available"]) <= at
    }
    past = [
        (r["payload"]["value"], matured[(r["payload"]["ticker"], r["payload"]["day"])]["target"])
        for r in source["predictions"]
        if r["payload"].get("evaluation_eligible")
        and datetime.fromisoformat(r["payload"]["decision_at"]) < at
        and (r["payload"]["ticker"], r["payload"]["day"]) in matured
    ]
    accuracy = (
        sum((v > 0.5) == (y > 0.5) for v, y in past) / len(past)
        if past and units == "probability"
        else None
    )
    baseline = source["baseline_probability"]
    brier = (
        sum((v - y) ** 2 for v, y in past) / len(past) if past and units == "probability" else None
    )
    baseline_brier = (
        sum((baseline - y) ** 2 for _, y in past) / len(past)
        if past and baseline is not None
        else None
    )
    past_summary = (
        f"Past matured OOS n={len(past)}, accuracy={accuracy}, Brier={brier}; "
        f"training-prevalence Brier={baseline_brier}."
    )
    signal = max(-1.0, min(1.0, 2 * (value - 0.5) if units == "probability" else value / 0.05))
    if abs(signal) <= request.policy.neutral_region:
        signal = 0.0
    # This remains a forecast; aggregation must explicitly opt into capped experimental voting.
    provenance: Literal["genuine", "retrospective"] = (
        "retrospective"
        if request.information_policy == "retrospective" or max(generated, created) > at
        else "genuine"
    )
    return AgentRecommendation(
        agent_id="quant",
        ticker=ticker,
        decision_at=at,
        data_cutoff=at,
        status="positive" if signal > 0 else "negative" if signal < 0 else "neutral",
        signal=signal,
        strength=abs(signal),
        interpretation="forecast",
        horizon_sessions=request.horizon,
        diagnostics={
            "matured_oos_samples": len(past),
            "direction_accuracy": accuracy,
            "brier": brier,
            "training_prevalence_brier": baseline_brier,
            "calibration": p["calibration"],
            "training_rows": m["artifact"]["preprocessing"].get("training_rows"),
            "skill_status": "insufficient_data" if len(past) < 60 else "descriptive_only",
            "generated_at": row["generated_at"],
            "model_created_at": source["created_at"],
        },
        prediction=value,
        prediction_units=units,
        coverage=1,
        evidence=(
            Evidence(
                reference="ml_prediction:" + row["id"],
                version=source["version"],
                available_at=ready,
                observed_at=training,
                ingested_at=ready if provenance == "retrospective" else generated,
                kind="forecast",
                provenance=provenance,
                dependencies=("market_prices:" + ticker,),
            ),
        ),
        limitations=(
            "Experimental forecast; no demonstrated prior OOS skill or calibrated confidence",
            "Actual model/forecast creation clocks retained separately in frozen source manifest",
            "Calibration: " + str(p["calibration"]),
            past_summary,
        ),
        reasoning=f"Original M6 {p['prediction_type']} forecast {value} {units}; "
        f"horizon={p['horizon']}; "
        f"training rows={m['artifact']['preprocessing'].get('training_rows')}; "
        "probability is never converted to expected return. Baseline advantage is unproven.",
    )


def strategy(
    request: Request,
    source: dict[str, Any] | None,
    ticker: str,
    at: datetime,
    signal: float | None,
    evidence_ready: datetime | None,
) -> AgentRecommendation:
    if source is None:
        return unavailable("strategy", ticker, at, "No configured existing M7 selected strategy")
    from datetime import date

    if date.fromisoformat(source["validation_end"]) >= at.date():
        return unavailable(
            "strategy", ticker, at, "Future validation selection is unavailable", "invalid"
        )
    frozen = datetime.fromisoformat(source["selection_frozen_at"])
    if request.information_policy != "retrospective" and frozen > at:
        return unavailable("strategy", ticker, at, "Strategy selection not frozen by decision")
    v = source["payload"]["validation"]
    if (
        not source["selected"]
        or source["payload"]["status"] != "eligible"
        or not v["fitness"]["eligible"]
        or v["metrics"]["turnover"] > source["fitness"]["maximum_turnover"]
        or source["payload"]["complexity"]["normalized"] > 1
    ):
        return unavailable(
            "strategy",
            ticker,
            at,
            "Strategy fails locked selection/validation/complexity/turnover policy",
        )
    if signal is None or evidence_ready is None or evidence_ready > at:
        return unavailable(
            "strategy", ticker, at, "Current strategy inputs are missing or unavailable"
        )
    signal = 0.5 if signal > 0 else 0.0
    return AgentRecommendation(
        agent_id="strategy",
        ticker=ticker,
        decision_at=at,
        data_cutoff=at,
        status="positive" if signal else "neutral",
        signal=signal,
        strength=abs(signal),
        interpretation="heuristic",
        coverage=1,
        evidence=(
            Evidence(
                reference="strategy_candidate:" + source["id"],
                version=source["version"],
                available_at=evidence_ready,
                observed_at=evidence_ready,
                ingested_at=evidence_ready,
                kind="strategy",
                provenance="retrospective"
                if request.information_policy == "retrospective"
                else "genuine",
                dependencies=("market_prices:" + ticker,),
            ),
        ),
        limitations=(
            "Validation-selected hypothesis, not proven profitable OOS",
            "Past validation fragility: " + str(v["fragility"]),
            source["robustness_scope"],
        ),
        diagnostics={
            "validation": v,
            "complexity": source["payload"]["complexity"],
            "selection_hash": source["selection_hash"],
        },
        reasoning="Existing M7 rule evaluated by its authoritative stateful RuleStrategy adapter; "
        "only the locked validation selection and current eligible inputs determine this vote.",
    )

"""Prior-issued one-session exception diagnostics with explicit independence/sample limits."""

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator
from scipy.stats import binomtest

from sentientalpha.backtesting.contracts import Frozen
from sentientalpha.data.contracts import utc


class ForecastOutcome(Frozen):
    portfolio_id: str
    policy_version: str
    forecast_at: datetime
    outcome_at: datetime
    available_at: datetime
    confidence: float = Field(ge=0.5, lt=1)
    var_loss_fraction: float
    realized_loss_fraction: float = Field(le=1)
    reliable_sample: bool

    @model_validator(mode="after")
    def valid(self) -> "ForecastOutcome":
        for at in [self.forecast_at, self.outcome_at, self.available_at]:
            utc(at)
        if not self.forecast_at < self.outcome_at <= self.available_at:
            raise ValueError("Outcome must follow forecast and mature")
        return self


def exception_diagnostics(records: list[ForecastOutcome], as_of: datetime) -> dict[str, Any]:
    utc(as_of)
    if len(records) > 100000:
        raise ValueError("Exception evaluation budget exceeded")
    matured = [r for r in records if r.available_at <= as_of]
    if len({(r.portfolio_id, r.policy_version, r.forecast_at) for r in matured}) != len(matured):
        raise ValueError("Duplicate risk forecasts")
    if len({(r.portfolio_id, r.policy_version, r.confidence) for r in matured}) > 1:
        raise ValueError("Evaluate one portfolio/policy/confidence at a time")
    reliable = [r for r in matured if r.reliable_sample]
    raw_exceptions = sum(r.realized_loss_fraction > r.var_loss_fraction for r in matured)
    n = len(reliable)
    exceptions = sum(r.realized_loss_fraction > r.var_loss_fraction for r in reliable)
    alpha = matured[0].confidence if matured else None
    result = {
        "status": "INSUFFICIENT_VALIDATION_SAMPLE",
        "matured": len(matured),
        "reliable_forecasts": n,
        "raw_exceptions": raw_exceptions,
        "raw_exception_frequency": raw_exceptions / len(matured) if matured else None,
        "qualified_exceptions": exceptions,
        "qualified_exception_frequency": exceptions / n if n else None,
        "nominal_exception_probability": 1 - alpha if alpha is not None else None,
        "binomial_pvalue": None,
        "exact_binomial_interval": None,
        "assumptions": "IID exceptions unverified; no clustering or production validation claim",
        "scope": "One-session static weights; not dynamic trading P&L or worst-case loss",
    }
    if alpha is not None and n >= 250 and n * (1 - alpha) >= 5:
        test = binomtest(exceptions, n, 1 - alpha)
        interval = test.proportion_ci(confidence_level=0.95, method="exact")
        result.update(
            status="DESCRIPTIVE_BINOMIAL_DIAGNOSTIC",
            binomial_pvalue=float(test.pvalue),
            exact_binomial_interval=[float(interval.low), float(interval.high)],
        )
    return result

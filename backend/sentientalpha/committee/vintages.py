"""Point-in-time statement and macro interfaces; no acquisition or genuine coverage claim."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from sentientalpha.backtesting.contracts import Frozen
from sentientalpha.data.contracts import ticker_symbol, utc


class ReleasedObservation(Frozen):
    reference: str = Field(min_length=1, max_length=240)
    source_version: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=160)
    series: str = Field(min_length=1, max_length=160)
    observation_date: date
    released_at: datetime
    available_at: datetime
    ingested_at: datetime
    revision: int = Field(ge=1, strict=True)
    supersedes: str | None = Field(default=None, max_length=240)
    value: float
    units: str = Field(min_length=1, max_length=80)
    provenance: Literal["genuine", "synthetic_fixture"]
    ticker: str | None = None
    kind: Literal["filing", "macro_vintage"]
    fiscal_period_end: date | None = None
    filing_type: Literal["original", "amendment", "restatement"] | None = None

    @field_validator("released_at", "available_at", "ingested_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("ticker")
    @classmethod
    def symbol(cls, value: str | None) -> str | None:
        return ticker_symbol(value) if value else None

    @model_validator(mode="after")
    def clocks(self) -> "ReleasedObservation":
        if self.observation_date > self.released_at.date() or self.released_at > self.available_at:
            raise ValueError("Observation/release/availability clocks are inconsistent")
        if (self.revision == 1) != (self.supersedes is None):
            raise ValueError("Revisions must reference the prior release")
        if self.kind == "filing":
            if self.ticker is None or self.fiscal_period_end is None or self.filing_type is None:
                raise ValueError("Statement requires issuer, fiscal period and filing type")
            if self.fiscal_period_end != self.observation_date:
                raise ValueError("Statement observation date must be its fiscal period end")
            if self.revision == 1 and self.filing_type != "original":
                raise ValueError("First statement release must be original")
        elif any(v is not None for v in (self.ticker, self.fiscal_period_end, self.filing_type)):
            raise ValueError("Macro vintages describe broad series, not issuer valuation")
        return self


def as_of(observations: list[ReleasedObservation], at: datetime) -> list[ReleasedObservation]:
    """Choose latest eligible revision per source/series/period, never latest final value."""
    utc(at)
    if len(observations) > 100_000:
        raise ValueError("Vintage input budget exceeded")
    seen: set[str] = set()
    groups: dict[tuple[str, str, date, str | None], list[ReleasedObservation]] = {}
    for observation in observations:
        o = ReleasedObservation.model_validate(observation.model_dump())
        if o.reference in seen:
            raise ValueError("Duplicate release reference")
        seen.add(o.reference)
        if max(o.available_at, o.ingested_at) <= at:
            groups.setdefault((o.source, o.series, o.observation_date, o.ticker), []).append(o)
    result = []
    for key in sorted(groups, key=str):
        versions = groups[key]
        if len({o.revision for o in versions}) != len(versions):
            raise ValueError("Conflicting eligible revisions")
        versions.sort(key=lambda o: o.revision)
        for earlier, later in zip(versions, versions[1:], strict=False):
            if later.released_at < earlier.released_at or later.supersedes != earlier.reference:
                raise ValueError("Broken or nonchronological release lineage")
        result.append(versions[-1])
    return result

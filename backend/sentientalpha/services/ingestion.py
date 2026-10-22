"""Validate whole batches, serialize writers and preserve auditable immutable revisions."""

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.data.contracts import (
    MarketDataProvider,
    PriceBar,
    ProviderError,
    ticker_symbol,
    validate_range,
)
from sentientalpha.data.quality import assess_batch
from sentientalpha.database.models import Asset, IngestionRun, MarketPrice, now
from sentientalpha.database.repository import prices_as_of
from sentientalpha.database.session import serialize_writer
from sentientalpha.features.invalidation import invalidate_sources

log = logging.getLogger(__name__)


class IngestionError(Exception):
    def __init__(self, run_id: str, code: str) -> None:
        super().__init__(f"Ingestion failed: {code}; run_id={run_id}")
        self.run_id = run_id
        self.code = code


def _require_run(session: Session, run_id: str) -> IngestionRun:
    run = session.get(IngestionRun, run_id)
    if run is None:
        raise ValueError("Ingestion audit record is missing")
    return run


def _source_conflicts(
    session: Session,
    asset_id: str,
    source: str,
    start: date,
    end: date,
    incoming: dict[date, PriceBar],
) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    seen: set[tuple[str, date]] = set()
    rows = session.scalars(
        select(MarketPrice)
        .where(
            MarketPrice.asset_id == asset_id,
            MarketPrice.provider != source,
            MarketPrice.is_synthetic.is_(False),
            MarketPrice.session_date.between(start, end),
        )
        .order_by(MarketPrice.revision_no.desc())
    )
    for row in rows:
        key = (row.provider, row.session_date)
        if key in seen:
            continue
        seen.add(key)
        bar = incoming.get(row.session_date)
        if bar is not None and any(
            getattr(row, name) != getattr(bar, name)
            for name in ("open", "high", "low", "close", "volume")
        ):
            conflicts.append(
                {"session_date": str(row.session_date), "other_provider": row.provider}
            )
    return conflicts


def ingest(
    sessions: sessionmaker[Session],
    provider: MarketDataProvider,
    ticker: str,
    start: date,
    end: date,
) -> IngestionRun:
    validate_range(start, end)
    ticker = ticker_symbol(ticker)
    if end >= now().date():
        raise ValueError("Ingest only completed dates before today (UTC)")
    with sessions.begin() as session:
        attempt = IngestionRun(
            provider=provider.name,
            ticker=ticker,
            requested_start=start,
            requested_end=end,
            parameters=dict(provider.parameters),
        )
        session.add(attempt)
        session.flush()
        run_id = attempt.id
    report: dict[str, Any] | None = None
    try:
        bars = provider.fetch(ticker, start, end)
        observed_at = now()
        if not bars:
            raise ProviderError("empty_range", "No prices in requested range")
        seen: set[date] = set()
        for bar in bars:
            if (
                bar.ticker != ticker
                or bar.provider != provider.name
                or not start <= bar.session_date <= end
            ):
                raise ProviderError("contract_mismatch", "Provider violated request boundaries")
            if bar.available_at > observed_at:
                raise ProviderError("future_availability", "Provider returned unavailable data")
            if bar.session_date in seen:
                raise ProviderError(
                    "duplicate_session", "Provider returned duplicate session dates"
                )
            seen.add(bar.session_date)
        with sessions.begin() as session:
            serialize_writer(session, ticker)
            run = _require_run(session, run_id)
            asset = session.scalar(select(Asset).where(Asset.ticker == ticker))
            if asset is None:
                asset = Asset(ticker=ticker, name=ticker)
                session.add(asset)
                session.flush()
            if asset.currency != "USD":
                raise ProviderError("currency_conflict", "Asset metadata conflicts with USD source")
            visible = prices_as_of(session, ticker, provider.name, start, end, now(), limit=12000)
            latest = {row.session_date: row for row in visible}
            prior = (
                prices_as_of(
                    session,
                    ticker,
                    provider.name,
                    date(2000, 1, 1),
                    start - timedelta(days=1),
                    now(),
                    limit=12000,
                )
                if start > date(2000, 1, 1)
                else []
            )
            previous = (prior[-1].session_date, prior[-1].close) if prior else None
            report, flags = assess_batch(bars, start, end, previous)
            if not bars[0].is_synthetic:
                report["source_conflicts"] = _source_conflicts(
                    session,
                    asset.id,
                    provider.name,
                    start,
                    end,
                    {bar.session_date: bar for bar in bars},
                )
                if report["source_conflicts"]:
                    report["state"] = "warnings"
                    for conflict in report["source_conflicts"]:
                        day = date.fromisoformat(conflict["session_date"])
                        flags.setdefault(day, []).append("source_conflict")
            changed_dates: list[date] = []
            for bar in sorted(bars, key=lambda item: item.session_date):
                previous_revision = latest.get(bar.session_date)
                if previous_revision is not None and previous_revision.checksum == bar.checksum:
                    run.deduplicated += 1
                    continue
                session.add(
                    MarketPrice(
                        asset_id=asset.id,
                        ingestion_run_id=run_id,
                        session_date=bar.session_date,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        adjusted_close=bar.adjusted_close,
                        volume=bar.volume,
                        available_at=bar.available_at,
                        observed_at=observed_at,
                        ingested_at=now(),
                        session_close_at=bar.session_close_at,
                        availability_kind=bar.availability_kind,
                        calendar=bar.calendar,
                        adjustment_status=bar.adjustment_status,
                        currency=bar.currency,
                        provider=bar.provider,
                        is_synthetic=bar.is_synthetic,
                        checksum=bar.checksum,
                        revision_no=previous_revision.revision_no + 1 if previous_revision else 1,
                        quality_flags=sorted(set(flags.get(bar.session_date, []))),
                    )
                )
                run.inserted += 1
                changed_dates.append(bar.session_date)
            if changed_dates:
                invalidate_sources(session, asset.id, provider.name, min(changed_dates))
            run.quality_report = report
            run.status = "completed"
            run.completed_at = now()
        log.info("ingestion_completed", extra={"run_id": run_id, "rows": run.inserted})
        return run
    except Exception as exc:
        code = (
            exc.code
            if isinstance(exc, ProviderError)
            else "concurrent_conflict"
            if isinstance(exc, IntegrityError)
            else "database_error"
            if isinstance(exc, SQLAlchemyError)
            else "validation_error"
            if isinstance(exc, ValueError)
            else "internal_error"
        )
        try:
            with sessions.begin() as session:
                failed = _require_run(session, run_id)
                failed.status = "failed"
                failed.error_code = code
                failed.quality_report = report
                failed.completed_at = now()
        except SQLAlchemyError:
            # Preserve the original public failure; audit recovery may need operator attention.
            log.error("ingestion_audit_unavailable", extra={"run_id": run_id})
            code = "database_error"
        log.warning("ingestion_failed", extra={"run_id": run_id, "error_code": code})
        raise IngestionError(run_id, code) from None

"""Latest-visible snapshot queries, isolated by provider."""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sentientalpha.data.contracts import ticker_symbol, utc, validate_range
from sentientalpha.database.models import Asset, MarketPrice


def prices_as_of(
    session: Session,
    ticker: str,
    provider: str,
    start: date,
    end: date,
    as_of: datetime,
    limit: int = 500,
    offset: int = 0,
) -> list[MarketPrice]:
    validate_range(start, end)
    if not 1 <= limit <= 12000 or offset < 0:
        raise ValueError("Invalid repository pagination bounds")
    cutoff = utc(as_of)
    ranked = (
        select(
            MarketPrice.id,
            func.row_number()
            .over(
                partition_by=MarketPrice.session_date,
                order_by=MarketPrice.revision_no.desc(),
            )
            .label("revision_rank"),
        )
        .join(Asset, Asset.id == MarketPrice.asset_id)
        .where(
            Asset.ticker == ticker_symbol(ticker),
            MarketPrice.provider == provider,
            MarketPrice.session_date.between(start, end),
            MarketPrice.available_at <= cutoff,
            MarketPrice.ingested_at <= cutoff,
        )
        .subquery()
    )
    return list(
        session.scalars(
            select(MarketPrice)
            .join(ranked, ranked.c.id == MarketPrice.id)
            .where(ranked.c.revision_rank == 1)
            .order_by(MarketPrice.session_date)
            .offset(offset)
            .limit(limit)
        )
    )

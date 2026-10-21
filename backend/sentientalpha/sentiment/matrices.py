"""Join immutable price and sentiment snapshots without moving sentiment clocks backwards."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.database.models import FeatureRow, FeatureSourceAsset
from sentientalpha.features.contracts import FeatureError
from sentientalpha.features.matrices import Matrix, MatrixRequest, cell
from sentientalpha.features.matrices import assemble as price_matrix
from sentientalpha.features.storage import get_dataset


def combined(session: Session, request: MatrixRequest) -> Matrix:
    assert request.sentiment_dataset_id is not None
    price = get_dataset(session, request.dataset_id, request.allow_stale)
    sentiment = get_dataset(session, request.sentiment_dataset_id, request.allow_stale)
    if (
        price.configuration.get("kind") == "sentiment"
        or sentiment.configuration.get("kind") != "sentiment"
    ):
        raise FeatureError(
            "matrix_kind", "Specify price snapshot first and sentiment snapshot second"
        )
    if price.diagnostics["calendar"] != sentiment.diagnostics["calendar"]:
        raise FeatureError(
            "mixed_calendars", "Combined snapshots must share their declared calendar"
        )
    if sentiment.configuration["scope"] != "security":
        raise FeatureError("matrix_scope", "Combined matrices require security-level sentiment")
    all_columns = sorted(price.columns + sentiment.columns)
    wanted = sorted(request.columns or all_columns)
    if set(wanted) - set(all_columns):
        raise FeatureError(
            "unknown_column", "Only persisted price and sentiment inputs are allowed"
        )
    if len(wanted) * request.limit > 100000:
        raise FeatureError("response_limit", "Reduce combined matrix size")
    symbols = request.tickers or price.configuration["tickers"]
    if set(symbols) - set(sentiment.configuration["tickers"]):
        raise FeatureError(
            "missing_sentiment_asset", "Sentiment snapshot must include every selected price asset"
        )
    # Fetch one bounded price-grid page and exact matching sentiment rows; no sentiment fill.
    raw = request.model_copy(
        update={
            "sentiment_dataset_id": None,
            "columns": [name for name in wanted if name in price.columns] or [price.columns[0]],
            "missing_policy": "preserve",
            "decision_at": None,
        }
    )
    matrix = price_matrix(session, raw)
    dates = [r["session_date"] for r in matrix.rows]
    stored = list(
        session.execute(
            select(FeatureRow, FeatureSourceAsset.ticker)
            .join(
                FeatureSourceAsset,
                (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
                & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
            )
            .where(
                FeatureRow.dataset_id == sentiment.id,
                FeatureSourceAsset.ticker.in_(symbols),
                FeatureRow.session_date.in_(dates),
            )
        )
    )
    lookup = {(ticker, row.session_date): row for row, ticker in stored}
    price_stored = session.execute(
        select(FeatureRow, FeatureSourceAsset.ticker)
        .join(
            FeatureSourceAsset,
            (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id)
            & (FeatureSourceAsset.asset_id == FeatureRow.asset_id),
        )
        .where(
            FeatureRow.dataset_id == price.id,
            FeatureSourceAsset.ticker.in_(symbols),
            FeatureRow.session_date.in_(dates),
        )
    )
    price_lookup = {(ticker, row.session_date): row for row, ticker in price_stored}
    output = []
    for row in matrix.rows:
        sentiment_row = lookup.get((row["ticker"], row["session_date"]))
        values: dict[str, float | None] = {}
        reasons = {}
        times = []
        # Preserve each source cell's readiness and its own materialization time.
        with_price = price_lookup.get((row["ticker"], row["session_date"]))
        for name in wanted:
            dataset, record = (
                (price, with_price) if name in price.columns else (sentiment, sentiment_row)
            )
            if record is None:
                values[name] = None
                reasons[name] = "missing_sentiment_observation"
                continue
            item = cell(dataset, record, name)
            value = item["value"]
            ready = (
                item["online_ready_at"]
                if request.availability_mode == "online"
                else item["decision_ready_at"]
            )
            reason = item["missing_reason"]
            if (
                value is not None
                and request.decision_at is not None
                and ready > request.decision_at
            ):
                value = None
                reason = "not_available_at_decision"
            values[name] = value
            if value is None:
                reasons[name] = reason
            else:
                times.append(ready)
        if reasons and request.missing_policy == "raise":
            raise FeatureError("missing_features", "Combined matrix has missing/unavailable inputs")
        if reasons and request.missing_policy == "drop_row":
            continue
        output.append(
            {
                **row,
                "features": [values[name] for name in wanted],
                "missing_reasons": reasons,
                "decision_ready_at": max(times) if times else None,
                "calculated_at": max(price.calculated_at, sentiment.calculated_at),
            }
        )
    return Matrix(
        price.id,
        wanted,
        output,
        matrix.next_offset,
        request.missing_policy,
        request.availability_mode,
        sentiment.id,
    )

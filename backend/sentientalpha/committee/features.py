"""Online M2/M3 source resolver; no recomputed indicators or historical backdating."""

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.committee.agents import heuristic, unavailable
from sentientalpha.committee.contracts import AgentRecommendation, Evidence
from sentientalpha.database.models import FeatureRow, FeatureSourceAsset
from sentientalpha.features.matrices import cell
from sentientalpha.features.storage import get_dataset


def analyze_feature(
    session: Session,
    *,
    agent: Literal["technical", "sentiment"],
    ticker: str,
    dataset_id: str,
    column: str,
    at: datetime,
    policy_effective_at: datetime,
    scale: float,
    neutral_region: float,
    maximum_age_days: int = 7,
) -> AgentRecommendation:
    """Resolve a persisted cell and retain the exact snapshot/row/column source identity."""
    if agent not in {"technical", "sentiment"}:
        raise ValueError("Feature resolver supports technical and sentiment agents")
    if policy_effective_at > at:
        raise ValueError("Transform policy must be fixed before the decision")
    if not 1 <= maximum_age_days <= 30:
        raise ValueError("Feature freshness must be within one to 30 days")
    dataset = get_dataset(session, dataset_id)
    if dataset.calculated_at > at:
        return unavailable(agent, ticker, at, "Snapshot calculated after decision")
    if column not in dataset.columns:
        raise ValueError("Feature not in persisted dataset")
    is_sentiment = dataset.configuration.get("kind") == "sentiment"
    if (agent == "sentiment") != is_sentiment:
        raise ValueError("Agent and feature engine disagree")
    if agent == "technical" and not column.startswith("price_to_sma__"):
        raise ValueError("Technical v8 foundation accepts registered price-to-SMA deviations")
    if agent == "sentiment" and not column.startswith("sent_mean__"):
        raise ValueError("Sentiment v8 foundation accepts cached descriptive sentiment means")
    row = session.scalar(
        select(FeatureRow)
        .join(
            FeatureSourceAsset,
            (FeatureSourceAsset.asset_id == FeatureRow.asset_id)
            & (FeatureSourceAsset.dataset_id == FeatureRow.dataset_id),
        )
        .where(
            FeatureRow.dataset_id == dataset_id,
            FeatureSourceAsset.ticker == ticker,
            FeatureRow.session_date <= at.date(),
            FeatureRow.session_date >= (at - timedelta(days=maximum_age_days)).date(),
        )
        .order_by(FeatureRow.session_date.desc())
        .limit(1)
    )
    if row is None:
        return unavailable(agent, ticker, at, "No fresh persisted feature row")
    item = cell(dataset, row, column)
    ready = item["online_ready_at"]
    if item["value"] is None or ready is None or ready > at:
        return unavailable(agent, ticker, at, "Feature unavailable at decision")
    if agent == "sentiment" and item["coverage_state"] != "complete":
        return unavailable("sentiment", ticker, at, "News coverage is not complete")
    # Conservatively declare every price-dependent column to share a market-price dependency.
    dependencies = ("market_prices:" + ticker,) if agent == "technical" else ("news:" + ticker,)
    evidence = Evidence(
        reference=f"dataset:{dataset.id}/asset:{row.asset_id}/date:{row.session_date}/column:{column}",
        version=dataset.source_hash + ":" + dataset.definition_hash,
        available_at=ready,
        observed_at=item["observation_at"],
        ingested_at=item["inputs_ingested_at"],
        kind="feature",
        provenance="synthetic_fixture" if dataset.provider == "synthetic" else "genuine",
        dependencies=dependencies,
    )
    return heuristic(
        agent,
        ticker,
        at,
        item["value"],
        evidence,
        scale=scale,
        neutral_region=neutral_region,
    )

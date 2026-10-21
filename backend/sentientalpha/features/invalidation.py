"""Invalidate latest-use feature snapshots without destroying historical evidence."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentientalpha.database.models import Asset, FeatureDataset, FeatureSourceAsset, now


def invalidate_sources(session: Session, asset_id: str, provider: str, first_changed: date) -> None:
    linked = set(
        session.scalars(
            select(FeatureSourceAsset.dataset_id).where(FeatureSourceAsset.asset_id == asset_id)
        )
    )
    asset = session.get(Asset, asset_id)
    candidates = session.scalars(
        select(FeatureDataset).where(
            FeatureDataset.provider == provider,
            FeatureDataset.end_date >= first_changed,
            FeatureDataset.status == "current",
        )
    )
    for dataset in candidates:
        # Missing benchmarks have no price FK; creation must invalidate their null outputs.
        missing_benchmark = (
            asset is not None
            and dataset.configuration.get("benchmark") == asset.ticker
            and any("benchmark_close" in item["inputs"] for item in dataset.definitions)
        )
        if dataset.id in linked or missing_benchmark:
            dataset.status = "stale"
            dataset.invalidated_at = now()
            dataset.invalidation_reason = "source_revision_changed"

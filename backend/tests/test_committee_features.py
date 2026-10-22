"""Resolve real persisted M2 calculations over explicitly synthetic source prices."""

from datetime import date, timedelta

import pytest
from sentientalpha.committee.features import analyze_feature
from sentientalpha.database.base import now
from sentientalpha.features.contracts import FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from test_feature_integration import seed
from test_integration import database as database


def test_m2_resolver_retains_source_clock_and_identity(database):
    _, sessions, _ = database
    seed(sessions)
    saved = generate(
        sessions,
        GenerationRequest(
            tickers=["AAA"],
            provider="synthetic",
            start=date(2023, 1, 2),
            end=date(2024, 3, 1),
            features=[FeatureSpec(name="price_to_sma", parameters={"window": 5})],
        ),
    ).dataset
    # Today is far beyond the final historical observation: online analysis must abstain.
    with sessions() as session:
        result = analyze_feature(
            session,
            agent="technical",
            ticker="AAA",
            dataset_id=saved.id,
            column=saved.columns[0],
            at=now(),
            policy_effective_at=now() - timedelta(days=1),
            scale=0.05,
            neutral_region=0.05,
        )
        assert result.status == "insufficient_data"
        # The historical cell cannot become an online signal before the snapshot existed.
        result = analyze_feature(
            session,
            agent="technical",
            ticker="AAA",
            dataset_id=saved.id,
            column=saved.columns[0],
            at=saved.calculated_at - timedelta(seconds=1),
            policy_effective_at=saved.calculated_at - timedelta(days=1),
            scale=0.05,
            neutral_region=0.05,
        )
        assert "calculated after" in result.reasoning
        with pytest.raises(ValueError, match="fixed before"):
            analyze_feature(
                session,
                agent="technical",
                ticker="AAA",
                dataset_id=saved.id,
                column=saved.columns[0],
                at=now(),
                policy_effective_at=now() + timedelta(days=1),
                scale=0.05,
                neutral_region=0.05,
            )


def test_fresh_m2_cell_produces_source_linked_synthetic_recommendation(database):
    from sentientalpha.data.synthetic import SyntheticProvider
    from sentientalpha.services.ingestion import ingest

    _, sessions, _ = database
    end = now().date() - timedelta(days=1)
    start = end - timedelta(days=30)
    ingest(sessions, SyntheticProvider(), "AAA", start, end)
    saved = generate(
        sessions,
        GenerationRequest(
            tickers=["AAA"],
            provider="synthetic",
            start=start,
            end=end,
            features=[FeatureSpec(name="price_to_sma", parameters={"window": 5})],
        ),
    ).dataset
    at = now() + timedelta(seconds=1)
    with sessions() as session:
        result = analyze_feature(
            session,
            agent="technical",
            ticker="AAA",
            dataset_id=saved.id,
            column=saved.columns[0],
            at=at,
            policy_effective_at=at - timedelta(days=1),
            scale=0.05,
            neutral_region=0.05,
        )
    assert result.status in {"positive", "neutral", "negative"}
    assert saved.id in result.evidence[0].reference
    assert result.evidence[0].provenance == "synthetic_fixture"
    assert result.evidence[0].available_at <= at
    assert result.confidence is None and result.expected_return is None

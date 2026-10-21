"""Actual migrations/SQLite/API integration; controlled NLP outputs are explicitly test doubles."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import Asset, FeatureRow, now
from sentientalpha.database.sentiment_models import (
    ArticleAssociation,
    NewsArticle,
    NewsStory,
    NewsVersion,
    SentimentInference,
    SentimentInput,
    SentimentRun,
)
from sentientalpha.features.contracts import FeatureError, FeatureSpec, GenerationRequest
from sentientalpha.features.matrices import MatrixRequest, assemble, cell
from sentientalpha.features.storage import generate, get_dataset
from sentientalpha.sentiment.datasets import SentimentGenerationRequest, generate_sentiment
from sentientalpha.sentiment.inference import infer
from sentientalpha.sentiment.ingestion import ingest_news
from sentientalpha.services.ingestion import ingest
from sentiment_fixtures import ControlledNews, TestModel, article
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_integration import database as database

START, END = date(2024, 1, 2), date(2024, 4, 30)
PUB_START = datetime(2024, 1, 1, tzinfo=UTC)
PUB_END = datetime(2024, 5, 1, tzinfo=UTC)


def seed(sessions, days=60):
    for ticker in ("AAPL", "MSFT"):
        ingest(sessions, SyntheticProvider(), ticker, START, END)
    news = []
    for i, day in enumerate(sessions_in_range("weekday", START, END)[:days]):
        pub = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=15)
        news.append(
            article(
                i,
                headline=f"Company {'profit rises' if i % 2 else 'loss widens'} on report {i}",
                published=pub,
            )
        )
    run = ingest_news(sessions, ControlledNews(news), PUB_START, PUB_END, ["AAPL"])
    model = TestModel()
    inferred = infer(sessions, model, "synthetic_news", max_items=1000)
    return news, model, run, inferred


def request(model, features=None, **kwargs):
    return SentimentGenerationRequest(
        tickers=["AAPL"],
        provider="synthetic",
        news_provider="synthetic_news",
        model_key=model.key,
        start=START,
        end=END,
        calendar="weekday",
        availability_policy="research_assumed",
        feed_delay_seconds=300,
        features=features
        or [
            FeatureSpec(name="sent_mean", parameters={"window": 1, "min_articles": 1}),
            FeatureSpec(name="sent_news_volume", parameters={"window": 1}),
        ],
        **kwargs,
    )


def test_ingestion_inference_cache_and_persistence(database):
    _, sessions, _ = database
    news, model, run, scored = seed(sessions)
    assert run.inserted == 60 and scored.inserted == 120
    first_calls = model.calls
    again = infer(sessions, model, "synthetic_news", max_items=1000)
    assert again.inserted == 0 and model.calls == first_calls
    repeated = ingest_news(sessions, ControlledNews(news), PUB_START, PUB_END, ["AAPL"])
    assert repeated.inserted == 0 and repeated.reused == 60
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(NewsVersion)) == 60
        assert session.scalar(select(func.count()).select_from(SentimentInference)) == 120
        assert all(
            p.model_metadata["is_test_double"] for p in session.scalars(select(SentimentInference))
        )


def test_news_revisions_and_reversions_retained(database):
    _, sessions, _ = database
    news, model, _, _ = seed(sessions, 1)
    original = news[0]
    corrected = replace(
        original,
        headline="Company profit rises after correction",
        updated_at=original.published_at + timedelta(hours=2),
        observed_at=original.published_at + timedelta(hours=3),
    )
    ingest_news(sessions, ControlledNews([corrected]), PUB_START, PUB_END, ["AAPL"])
    ingest_news(sessions, ControlledNews([original]), PUB_START, PUB_END, ["AAPL"])
    with sessions() as session:
        versions = list(session.scalars(select(NewsVersion).order_by(NewsVersion.revision_no)))
        assert [v.revision_no for v in versions] == [1, 2, 3]
        assert versions[0].headline == versions[2].headline != versions[1].headline


def test_exact_syndication_vs_distinct_followup(database):
    _, sessions, _ = database
    news, _, _, _ = seed(sessions, 1)
    duplicate = replace(
        news[0],
        external_id="other-feed-id",
        url="https://example.invalid/syndicated",
        publisher="Other synthetic publisher",
    )
    followup = replace(
        news[0],
        external_id="followup",
        url="https://example.invalid/followup",
        headline=news[0].headline + " with new guidance",
    )
    ingest_news(sessions, ControlledNews([duplicate, followup]), PUB_START, PUB_END, ["AAPL"])
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(NewsArticle)) == 3
        assert session.scalar(select(func.count()).select_from(NewsStory)) == 2
        assert "exact_content_48h" in list(session.scalars(select(NewsArticle.dedup_reason)))


def test_generation_cache_registry_cell_clocks_and_lineage(database):
    _, sessions, _ = database
    _, model, _, _ = seed(sessions)
    first = generate_sentiment(sessions, request(model))
    second = generate_sentiment(sessions, request(model))
    assert second.reused and first.dataset.id == second.dataset.id
    with sessions() as session:
        assert get_dataset(session, first.dataset.id).id == first.dataset.id
        assert session.scalar(select(func.count()).select_from(SentimentInput)) > 0
        row = session.scalar(
            select(FeatureRow)
            .where(FeatureRow.dataset_id == first.dataset.id)
            .order_by(FeatureRow.session_date)
        )
        name = next(n for n in first.dataset.columns if n.startswith("sent_mean"))
        value = cell(first.dataset, row, name)
        assert value["value"] == pytest.approx(-0.6)
        assert value["coverage_state"] == "complete"
        assert value["decision_ready_at"] >= value["observation_at"] + timedelta(seconds=1)
        assert value["online_ready_at"] >= value["inputs_ingested_at"]
        assert value["earliest_execution_at"] > value["online_ready_at"]
        assert first.dataset.diagnostics["model_metadata"]["is_test_double"]


def test_observed_backfill_never_influences_original_session(database):
    _, sessions, _ = database
    _, model, _, _ = seed(sessions, 1)
    result = generate_sentiment(
        sessions, request(model).model_copy(update={"availability_policy": "observed"})
    )
    with sessions() as session:
        # Synthetic observation is modeled in 2024; actual ingestion/scoring today masks it online.
        matrix = assemble(
            session,
            MatrixRequest(
                dataset_id=result.dataset.id,
                start=START,
                end=END,
                decision_at=datetime(2024, 6, 1, tzinfo=UTC),
            ),
        )
        assert all(v is None for r in matrix.rows for v in r["features"])
    historical = generate_sentiment(
        sessions, request(model).model_copy(update={"as_of": datetime(2024, 6, 1, tzinfo=UTC)})
    )
    with sessions() as session:
        assert all(
            value is None
            for row in session.scalars(
                select(FeatureRow).where(FeatureRow.dataset_id == historical.dataset.id)
            )
            for value in row.values.values()
        )


def test_later_articles_invalidate_without_retroactive_values(database):
    _, sessions, _ = database
    news, model, _, _ = seed(sessions, 10)
    first = generate_sentiment(sessions, request(model))
    cutoff = now()
    later = article(
        99, headline="Company profit rises late", published=datetime(2024, 4, 1, 15, tzinfo=UTC)
    )
    ingest_news(sessions, ControlledNews([later]), PUB_START, PUB_END, ["AAPL"])
    infer(sessions, model, "synthetic_news", max_items=1000)
    with sessions() as session:
        with pytest.raises(FeatureError, match="Regenerate"):
            get_dataset(session, first.dataset.id)
    fresh = generate_sentiment(sessions, request(model))
    assert fresh.dataset.id != first.dataset.id
    historical = generate_sentiment(sessions, request(model).model_copy(update={"as_of": cutoff}))
    assert historical.dataset.id == first.dataset.id and historical.reused
    with sessions() as session:
        old = {
            r.session_date: r.values
            for r in session.scalars(
                select(FeatureRow).where(
                    FeatureRow.dataset_id == first.dataset.id,
                    FeatureRow.session_date < date(2024, 4, 1),
                )
            )
        }
        new = {
            r.session_date: r.values
            for r in session.scalars(
                select(FeatureRow).where(
                    FeatureRow.dataset_id == fresh.dataset.id,
                    FeatureRow.session_date < date(2024, 4, 1),
                )
            )
        }
        assert old == new


def test_combined_price_sentiment_matrix(database):
    _, sessions, _ = database
    _, model, _, _ = seed(sessions)
    price = generate(
        sessions,
        GenerationRequest(
            tickers=["AAPL"],
            provider="synthetic",
            start=START,
            end=END,
            features=[FeatureSpec(name="return")],
        ),
    )
    sentiment = generate_sentiment(sessions, request(model))
    with sessions() as session:
        req = MatrixRequest(
            dataset_id=price.dataset.id,
            sentiment_dataset_id=sentiment.dataset.id,
            start=START,
            end=END,
            limit=20,
        )
        joined = assemble(session, req)
        assert joined.columns == sorted(price.dataset.columns + sentiment.dataset.columns)
        assert joined.sentiment_dataset_id == sentiment.dataset.id and len(joined.rows) == 20
        assert joined.rows[-1]["decision_ready_at"] >= sentiment.dataset.calculated_at
        past = assemble(
            session, req.model_copy(update={"decision_at": datetime(2024, 6, 1, tzinfo=UTC)})
        )
        assert all(v is None for r in past.rows for v in r["features"])
        with pytest.raises(FeatureError, match="persisted"):
            assemble(session, req.model_copy(update={"columns": ["future_target"]}))


def test_sector_universe_broad_scopes(database):
    _, sessions, _ = database
    _, model, _, _ = seed(sessions)
    with sessions.begin() as session:
        for asset in session.scalars(select(Asset)):
            asset.sector = "Technology"
    for scope in ["universe", "sector"]:
        result = generate_sentiment(
            sessions,
            request(model, scope=scope, sector="Technology" if scope == "sector" else None),
        )
        assert result.dataset.row_count == len(sessions_in_range("weekday", START, END))
        assert result.dataset.configuration["tickers"][0].startswith("SENT.")
    broad = replace(
        article(100, headline="Central bank financial stability announcement"),
        tickers=(),
        scope="broad_market",
    )
    ingest_news(sessions, ControlledNews([broad]), PUB_START, PUB_END, [])
    infer(sessions, model, "synthetic_news", max_items=1000)
    result = generate_sentiment(sessions, request(model, scope="broad_market"))
    assert result.dataset.configuration["tickers"] == ["SENT.MKT"]


def test_empty_language_and_model_failure_statuses(database):
    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    inputs = [
        article(1, headline=""),
        article(2, headline="Foreign financial news", language="fr"),
        article(3, headline="Company profit"),
    ]
    ingest_news(sessions, ControlledNews(inputs), PUB_START, PUB_END, ["AAPL"])
    model = TestModel()
    with patch.object(model, "predict", side_effect=RuntimeError("private model error")):
        infer(sessions, model, "synthetic_news", max_items=1000)
    with sessions() as session:
        statuses = set(session.scalars(select(SentimentInference.status)))
        assert {"empty_text", "unsupported_language", "inference_failed"} <= statuses
        assert all(p.score is None for p in session.scalars(select(SentimentInference)))


def test_provider_failure_audit_atomicity_and_no_fabrication(database):
    _, sessions, _ = database

    class Broken(ControlledNews):
        def fetch(self, *args):
            raise RuntimeError("private secret")

    with pytest.raises(FeatureError) as caught:
        ingest_news(sessions, Broken([]), PUB_START, PUB_END, [])
    assert "private" not in str(caught.value)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(NewsVersion)) == 0
        assert session.scalar(select(SentimentRun)).status == "failed"


def test_probability_database_constraint(database):
    _, sessions, _ = database
    _, _, _, _ = seed(sessions, 1)
    with sessions.begin() as session, pytest.raises(IntegrityError):
        p = session.scalar(select(SentimentInference))
        p.positive = None
        session.flush()


def test_typed_apis_and_no_copyrighted_text_response(database):
    url, sessions, _ = database
    _, model, _, _ = seed(sessions)
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert len(client.get("/api/features/definitions").json()) == 38
        assert len(client.get("/api/sentiment/definitions").json()) == 28
        assert len(client.get("/api/features/all-definitions").json()) == 66
        news = client.get("/api/news/AAPL").json()
        assert news and news[0]["headline"] is not None and "description" not in news[0]
        assert client.get("/api/sentiment/articles/" + news[0]["version_id"]).status_code == 200
        response = client.post(
            "/api/sentiment/generate", json=request(model).model_dump(mode="json")
        )
        assert response.status_code == 201
        data = response.json()["dataset"]
        assert (
            client.get(
                "/api/features/AAPL",
                params={"dataset_id": data["id"], "start": str(START), "end": str(END), "limit": 3},
            ).status_code
            == 200
        )
        feature = data["columns"][0]
        contribution = client.get(
            "/api/sentiment/" + data["id"] + "/contributors",
            params={"ticker": "AAPL", "session_date": str(START), "feature": feature},
        )
        assert contribution.status_code == 200
        assert (
            client.post("/api/sentiment/infer", json={"provider": "synthetic_news"}).status_code
            == 503
        )
        assert client.post("/api/sentiment/model/initialize", json={}).status_code == 503
        assert (
            client.post(
                "/api/news/ingest",
                json={"provider": "invalid", "start": str(PUB_START), "end": str(PUB_END)},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/sentiment/generate",
                json={**request(model).model_dump(mode="json"), "feed_delay_seconds": 0},
            ).status_code
            == 422
        )


def test_failed_inference_retry_retains_original_evidence(database):
    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    ingest_news(sessions, ControlledNews([article(1)]), PUB_START, PUB_END, ["AAPL"])
    model = TestModel()
    with patch.object(model, "predict", side_effect=RuntimeError("controlled failure")):
        first = infer(sessions, model, "synthetic_news", max_items=100)
    assert first.status == "completed_errors"
    second = infer(sessions, model, "synthetic_news", max_items=100)
    assert second.inserted == 2
    with sessions() as session:
        rows = list(
            session.scalars(select(SentimentInference).order_by(SentimentInference.attempt))
        )
        assert [p.attempt for p in rows] == [1, 1, 2, 2]
        assert rows[0].status == "inference_failed" and rows[0].score is None
        assert rows[-1].status == "success" and rows[-1].score == pytest.approx(0.6)


def test_multi_company_contexts_are_scored_independently(database):
    _, sessions, _ = database
    for ticker in ("AAPL", "MSFT"):
        ingest(sessions, SyntheticProvider(), ticker, START, END)
    with sessions.begin() as session:
        for asset in session.scalars(select(Asset)):
            asset.name = "Apple Inc." if asset.ticker == "AAPL" else "Microsoft"
    text = "Apple Inc. reports a profit. Microsoft reports a loss."
    item = replace(article(1, headline=text), tickers=("AAPL", "MSFT"))
    ingest_news(sessions, ControlledNews([item]), PUB_START, PUB_END, [])
    model = TestModel()
    infer(sessions, model, "synthetic_news", max_items=100)
    with sessions() as session:
        contexts = list(
            session.execute(
                select(Asset.ticker, SentimentInference.score)
                .join(ArticleAssociation, ArticleAssociation.asset_id == Asset.id)
                .join(SentimentInference, SentimentInference.context_key == ArticleAssociation.id)
            )
        )
        assert dict(contexts) == {"AAPL": pytest.approx(0.6), "MSFT": pytest.approx(-0.6)}


def test_news_actual_insert_failure_rolls_back_and_audits(database):
    from sqlalchemy import event

    _, sessions, _ = database
    ingest(sessions, SyntheticProvider(), "AAPL", START, END)
    emitted = []

    def fail_after_insert(mapper, connection, target):
        emitted.append(target.id)
        raise RuntimeError("controlled post-insert failure")

    event.listen(NewsVersion, "after_insert", fail_after_insert)
    try:
        with pytest.raises(FeatureError):
            ingest_news(sessions, ControlledNews([article(1)]), PUB_START, PUB_END, ["AAPL"])
    finally:
        event.remove(NewsVersion, "after_insert", fail_after_insert)
    assert emitted
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(NewsVersion)) == 0
        assert session.scalar(select(func.count()).select_from(NewsArticle)) == 0
        assert session.scalar(select(SentimentRun)).status == "failed"


def test_quality_clock_metadata_changes_revise_and_require_explicit_policy(database):
    _, sessions, _ = database
    news, model, _, _ = seed(sessions, 1)
    changed = replace(
        news[0],
        first_seen_at=news[0].published_at + timedelta(minutes=5),
        quality_flags=("uncertain_delivery",),
    )
    run = ingest_news(sessions, ControlledNews([changed]), PUB_START, PUB_END, ["AAPL"])
    assert run.inserted == 1
    infer(sessions, model, "synthetic_news", max_items=100)
    with pytest.raises(FeatureError, match="quality flags"):
        generate_sentiment(sessions, request(model))
    allowed = generate_sentiment(
        sessions, request(model).model_copy(update={"quality_policy": "allow_flagged"})
    )
    assert allowed.dataset.row_count > 0


def test_revision_without_update_time_never_backdates_even_in_research_mode(database):
    _, sessions, _ = database
    news, model, _, _ = seed(sessions, 1)
    original = generate_sentiment(sessions, request(model))
    changed = replace(news[0], headline="Company profit after previously undisclosed correction")
    ingest_news(sessions, ControlledNews([changed]), PUB_START, PUB_END, ["AAPL"])
    infer(sessions, model, "synthetic_news", max_items=100)
    corrected = generate_sentiment(sessions, request(model))
    with sessions() as session:
        old = session.scalar(
            select(FeatureRow).where(
                FeatureRow.dataset_id == original.dataset.id, FeatureRow.session_date == START
            )
        )
        new = session.scalar(
            select(FeatureRow).where(
                FeatureRow.dataset_id == corrected.dataset.id, FeatureRow.session_date == START
            )
        )
        assert old.values == new.values
        assert next(
            value for name, value in new.values.items() if name.startswith("sent_mean")
        ) == pytest.approx(-0.6)

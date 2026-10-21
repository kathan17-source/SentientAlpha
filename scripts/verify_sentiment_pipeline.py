"""Opt-in real CPU FinBERT pipeline: public Fed feed or explicitly synthetic throughput workload."""

import argparse
import json
import os
import platform
import resource
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import FeatureRow, now
from sentientalpha.database.sentiment_models import NewsVersion, SentimentInference
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.sentiment.contracts import Article, NewsBatch
from sentientalpha.sentiment.datasets import SentimentGenerationRequest, generate_sentiment
from sentientalpha.sentiment.inference import infer
from sentientalpha.sentiment.ingestion import ingest_news
from sentientalpha.sentiment.model import FinBERT
from sentientalpha.sentiment.providers import AlphaVantageNewsProvider, FederalReserveProvider
from sentientalpha.services.ingestion import ingest
from sqlalchemy import inspect, select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--alpha-demo", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    engine = make_engine("sqlite:///" + str(args.database.resolve()))
    if inspect(engine).get_table_names():
        raise ValueError("Verification database must be empty; no existing data is deleted")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(args.database.resolve())
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    sessions = session_factory(engine)
    initialized = perf_counter()
    model = FinBERT(str(args.model_cache), local_only=True)
    init_seconds = perf_counter() - initialized
    if args.synthetic:
        days = sessions_in_range("weekday", date(2024, 1, 2), date(2024, 4, 1))[:50]
        tickers = [f"SYN{i:02d}" for i in range(20)]
        items = []
        for ticker in tickers:
            ingest(sessions, SyntheticProvider(), ticker, days[0], date(2024, 4, 1))
            for i, day in enumerate(days):
                text = [
                    "reported higher operating profit and raised its sales outlook",
                    "reported a loss and reduced its sales forecast",
                    "announced the date of its annual shareholder meeting",
                ][i % 3]
                published = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=15)
                items.append(
                    Article(
                        provider="synthetic_news",
                        external_id=f"{ticker}-{i}",
                        publisher="Synthetic Financial Research Fixture",
                        url=f"https://example.invalid/{ticker}/{i}",
                        headline=f"{ticker} {text}, report {i}.",
                        published_at=published,
                        observed_at=published + timedelta(minutes=10),
                        tickers=(ticker,),
                        is_synthetic=True,
                        text_rights="synthetic",
                    )
                )

        class SyntheticNews:
            name = "synthetic_news"

            def fetch(self, start, end, tickers, limit):
                return NewsBatch(items, "complete", {"synthetic": True})

        provider = SyntheticNews()
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 5, 1, tzinfo=UTC)
    else:
        provider = AlphaVantageNewsProvider("demo") if args.alpha_demo else FederalReserveProvider()
        tickers = ["AAPL"] if args.alpha_demo else ["SPY"]
        if args.alpha_demo:
            ingest(sessions, SyntheticProvider(), "AAPL", date(2024, 1, 2), date(2024, 1, 3))
            with sessions.begin() as session:
                from sentientalpha.database.models import Asset

                asset = session.scalar(select(Asset).where(Asset.ticker == "AAPL"))
                asset.name = "Apple Inc."
        end = now()
        start = end - timedelta(days=365)
    clock = perf_counter()
    run = ingest_news(
        sessions, provider, start, end, tickers if args.synthetic or args.alpha_demo else [], 1000
    )
    news_seconds = perf_counter() - clock
    clock = perf_counter()
    inference_runs = []
    for _ in range(4):
        scored = infer(sessions, model, provider.name, max_items=1000, batch_size=16, seconds=300)
        inference_runs.append(
            {
                "id": scored.id,
                "inserted": scored.inserted,
                "cache_reused": scored.reused,
                "status": scored.status,
                "diagnostics": scored.diagnostics,
            }
        )
        if scored.inserted == 0:
            break
    inference_seconds = perf_counter() - clock
    with sessions() as session:
        versions = list(session.scalars(select(NewsVersion).order_by(NewsVersion.published_at)))
        preds = list(
            session.scalars(
                select(SentimentInference)
                .where(SentimentInference.context_key == "article")
                .order_by(SentimentInference.version_id)
            )
        )
    if not versions:
        raise RuntimeError("Provider supplied no eligible articles; no demonstration fabricated")
    first, last = (
        min(v.published_at.date() for v in versions),
        max(v.published_at.date() for v in versions),
    )
    request = SentimentGenerationRequest(
        tickers=tickers,
        news_provider=provider.name,
        model_key=model.key,
        calendar="weekday" if args.synthetic else "XNYS",
        scope="security" if args.synthetic or args.alpha_demo else "broad_market",
        start=first,
        end=last,
        availability_policy="research_assumed",
        feed_delay_seconds=300,
    )
    assumed = generate_sentiment(sessions, request)
    observed = generate_sentiment(
        sessions, request.model_copy(update={"availability_policy": "observed"})
    )
    repeat = generate_sentiment(sessions, request)
    assert repeat.reused and repeat.dataset.id == assumed.dataset.id
    with sessions() as session:
        values = list(
            session.scalars(select(FeatureRow).where(FeatureRow.dataset_id == assumed.dataset.id))
        )
        online_rows = list(
            session.scalars(select(FeatureRow).where(FeatureRow.dataset_id == observed.dataset.id))
        )
        nonnull = sum(v is not None for r in values for v in r.values.values())
        observed_nonnull = sum(v is not None for r in online_rows for v in r.values.values())
    report = {
        "mode": "synthetic financial news with REAL FinBERT"
        if args.synthetic
        else (
            "real Alpha Vantage public AAPL headline snapshot with REAL FinBERT"
            if args.alpha_demo
            else "real Federal Reserve public financial press-release HEADLINES with REAL FinBERT"
        ),
        "collection_at": now().isoformat(),
        "provider": provider.name,
        "articles": len(versions),
        "publication_start": str(first),
        "publication_end": str(last),
        "model": model.metadata,
        "model_key": model.key,
        "model_init_seconds": init_seconds,
        "news_ingestion_seconds": news_seconds,
        "news_run_id": run.id,
        "inference_seconds": inference_seconds,
        "unique_text_throughput_per_second": len(versions) / inference_seconds,
        "inference_runs": inference_runs,
        "generation_seconds": assumed.elapsed_seconds,
        "repeat_seconds": repeat.elapsed_seconds,
        "repeat_reused": repeat.reused,
        "output_rows": assumed.dataset.row_count,
        "columns": len(assumed.dataset.columns),
        "nonnull_assumed_cells": nonnull,
        "nonnull_observed_cells": observed_nonnull,
        "nonnull_observed_prior_session_cells": sum(
            v is not None
            for r in online_rows
            if r.session_date < now().date()
            for v in r.values.values()
        ),
        "research_availability": (
            "explicit assumed publication/update plus 300-second delay; "
            "not verified historical delivery"
        ),
        "coverage": "synthetic complete fixture"
        if args.synthetic
        else "current public demo news snapshot; no historical entitlement claim"
        if args.alpha_demo
        else "current RSS snapshot only; incomplete historical broad-market composition",
        "dataset_ids": {"assumed": assumed.dataset.id, "observed": observed.dataset.id},
        "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if platform.system() == "Darwin" else 1024),
        "rss_scope": (
            "isolated full process including model load, inference, SQL persistence "
            "and feature generation"
        ),
        "samples": [
            {
                "version_id": p.version_id,
                "positive": p.positive,
                "negative": p.negative,
                "neutral": p.neutral,
                "score": p.score,
                "status": p.status,
                "inferred_at": p.inferred_at.isoformat(),
            }
            for p in preds[:5]
        ],
        "limits": (
            "descriptive model outputs; no calibration, predictive alpha "
            "or 2018–2026 coverage claim"
        ),
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()

"""Incremental bounded inference with per-batch transactions and reusable input caches."""

from time import perf_counter
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.database.models import now
from sentientalpha.database.sentiment_models import (
    ArticleAssociation,
    NewsArticle,
    NewsVersion,
    SentimentInference,
    SentimentRun,
)
from sentientalpha.database.session import serialize_writer
from sentientalpha.features.contracts import FeatureError, digest
from sentientalpha.sentiment.ingestion import begin_run, failed, invalidate
from sentientalpha.sentiment.model import Model, preprocess


def infer(
    sessions: sessionmaker[Session],
    model: Model,
    provider: str,
    max_items: int = 100,
    batch_size: int = 16,
    seconds: int = 120,
) -> SentimentRun:
    if not 1 <= max_items <= 1000 or not 1 <= batch_size <= 32 or not 1 <= seconds <= 300:
        raise FeatureError("inference_bounds", "Inference bounds exceeded")
    started = perf_counter()
    run_id = begin_run(
        sessions,
        "inference",
        provider,
        {
            "model_key": model.key,
            "model": model.metadata,
            "max_items": max_items,
            "batch_size": batch_size,
            "seconds": seconds,
        },
    )
    inserted = reused = processed = failures = 0
    try:
        with sessions() as session:
            pending_global = ~exists(
                select(SentimentInference.id).where(
                    SentimentInference.version_id == NewsVersion.id,
                    SentimentInference.context_key == "article",
                    SentimentInference.status.in_(
                        ["success", "empty_text", "unsupported_language"]
                    ),
                    SentimentInference.model_key == model.key,
                )
            )
            versions = list(
                session.scalars(
                    select(NewsVersion)
                    .join(NewsArticle)
                    .where(NewsArticle.provider == provider, pending_global)
                    .order_by(NewsVersion.ingested_at, NewsVersion.id)
                    .limit(max_items)
                )
            )
            targets = [
                (v, "article", v.headline + (". " + v.description if v.description else ""))
                for v in versions
            ]
            pending_context = ~exists(
                select(SentimentInference.id).where(
                    SentimentInference.version_id == NewsVersion.id,
                    SentimentInference.context_key == ArticleAssociation.id,
                    SentimentInference.status.in_(
                        ["success", "empty_text", "unsupported_language"]
                    ),
                    SentimentInference.model_key == model.key,
                )
            )
            associations = session.execute(
                select(NewsVersion, ArticleAssociation)
                .join(ArticleAssociation, ArticleAssociation.version_id == NewsVersion.id)
                .join(NewsArticle, NewsArticle.id == NewsVersion.article_id)
                .where(
                    NewsArticle.provider == provider,
                    ArticleAssociation.status == "resolved",
                    pending_context,
                )
                .order_by(NewsVersion.ingested_at, ArticleAssociation.id)
                .limit(max_items - len(targets))
            )
            targets.extend((v, a.id, a.context or "") for v, a in associations)
        for start in range(0, len(targets), batch_size):
            if perf_counter() - started >= seconds:
                break
            batch = targets[start : start + batch_size]
            records = []
            fresh = []
            with sessions() as session:
                for version, context, text in batch:
                    clean = preprocess(text)
                    input_hash = digest(clean)
                    base: dict[str, Any] = {
                        "version_id": version.id,
                        "context_key": context,
                        "model_key": model.key,
                        "model_metadata": model.metadata,
                        "input_hash": input_hash,
                        "inferred_at": now(),
                        "tokens": 0,
                        "truncated": False,
                    }
                    if version.language.lower() not in {"en", "en-us", "en-gb"}:
                        records.append({**base, "status": "unsupported_language"})
                        continue
                    if not clean:
                        records.append({**base, "status": "empty_text"})
                        continue
                    cached = session.scalar(
                        select(SentimentInference)
                        .where(
                            SentimentInference.model_key == model.key,
                            SentimentInference.input_hash == input_hash,
                            SentimentInference.status == "success",
                        )
                        .order_by(SentimentInference.inferred_at)
                        .limit(1)
                    )
                    if cached is not None:
                        records.append(
                            {
                                **base,
                                **{
                                    name: getattr(cached, name)
                                    for name in (
                                        "positive",
                                        "negative",
                                        "neutral",
                                        "score",
                                        "tokens",
                                        "truncated",
                                    )
                                },
                                "status": "success",
                            }
                        )
                        reused += 1
                    else:
                        fresh.append((base, clean))
            if fresh:
                try:
                    unique_texts = list(dict.fromkeys(text for _, text in fresh))
                    predictions = model.predict(unique_texts)
                    if len(predictions) != len(unique_texts):
                        raise FeatureError("model_contract", "Model output length differs")
                    mapped = dict(zip(unique_texts, predictions, strict=True))
                    reused += len(fresh) - len(unique_texts)
                    for base, text in fresh:
                        p = mapped[text]
                        records.append(
                            {
                                **base,
                                "inferred_at": now(),
                                "positive": p.positive,
                                "negative": p.negative,
                                "neutral": p.neutral,
                                "score": p.score,
                                "tokens": p.tokens,
                                "truncated": p.truncated,
                                "status": "success",
                            }
                        )
                except Exception:
                    # Persist failures honestly; explicit retry by a new model key/run is required.
                    records.extend({**base, "status": "inference_failed"} for base, _ in fresh)
            failures += sum(record["status"] == "inference_failed" for record in records)
            processed += len(records)
            with sessions.begin() as session:
                serialize_writer(session, "sentiment")
                for record in records:
                    existing = session.scalar(
                        select(SentimentInference)
                        .where(
                            SentimentInference.version_id == record["version_id"],
                            SentimentInference.context_key == record["context_key"],
                            SentimentInference.model_key == model.key,
                        )
                        .order_by(SentimentInference.attempt.desc())
                        .limit(1)
                    )
                    if existing is None or existing.status == "inference_failed":
                        record["attempt"] = 1 if existing is None else existing.attempt + 1
                        session.add(SentimentInference(**record))
                        inserted += 1
                    else:
                        reused += 1
                invalidate(session, provider)
        with sessions.begin() as session:
            run = session.get(SentimentRun, run_id)
            assert run is not None
            run.status = (
                ("completed_errors" if failures else "completed")
                if processed >= len(targets)
                else "partial"
            )
            run.completed_at = now()
            run.inserted = inserted
            run.reused = reused
            run.diagnostics = {
                "elapsed_seconds": perf_counter() - started,
                "selected_targets": len(targets),
                "processed_targets": processed,
                "inference_failures": failures,
                "model_probabilities_calibrated": False,
                "memory_policy": (
                    "bounded targets and inference batches; no all-corpus model outputs"
                ),
            }
        return run
    except Exception:
        failed(sessions, run_id, "sentiment_pipeline_failed")
        raise FeatureError(
            "sentiment_pipeline_failed", "Inference pipeline failed; inspect its audit", 503
        ) from None

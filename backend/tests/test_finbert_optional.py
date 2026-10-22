"""Opt-in REAL CPU model integration, strictly local cached weights. Never counted if skipped."""

import os

import pytest
from sentientalpha.sentiment.model import FinBERT


@pytest.mark.skipif(
    os.getenv("RUN_FINBERT") != "1",
    reason="Optional real FinBERT; set RUN_FINBERT=1 and FINBERT_CACHE_DIR",
)
def test_real_finbert_probabilities_batch_consistency_and_truncation():
    model = FinBERT(os.environ["FINBERT_CACHE_DIR"], local_only=True)
    texts = [
        "The company reported record profits.",
        "The company reported heavy losses.",
        "The board scheduled a meeting.",
    ]
    batch = model.predict(texts)
    single = [model.predict([t])[0] for t in texts]
    for left, right in zip(batch, single, strict=True):
        assert left.positive + left.negative + left.neutral == pytest.approx(1, abs=1e-6)
        assert left.score == pytest.approx(right.score, abs=1e-6)
    assert batch[0].positive > batch[0].negative and batch[1].negative > batch[1].positive
    long = model.predict(["Financial results were announced. " * 500])[0]
    assert long.truncated and long.tokens > 512
    assert len(model.metadata["revision"]) == 40 and not model.metadata["probabilities_calibrated"]

"""Explicit pinned CPU FinBERT inference, full probabilities and deterministic preprocessing."""

import logging
import re
import threading
import unicodedata
from importlib.metadata import version
from typing import Any, Protocol

from sentientalpha.features.contracts import FeatureError, digest
from sentientalpha.sentiment.contracts import Prediction

MODEL_ID = "ProsusAI/finbert"
MODEL_REVISION = "0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031"
PREPROCESS_VERSION = "nfkc-whitespace-v1"
log = logging.getLogger(__name__)


def preprocess(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


class Model(Protocol):
    metadata: dict[str, Any]

    @property
    def key(self) -> str: ...
    def predict(self, texts: list[str]) -> list[Prediction]: ...


class FinBERT:
    def __init__(
        self, cache_dir: str, *, local_only: bool = True, max_tokens: int = 512, threads: int = 2
    ) -> None:
        if not 8 <= max_tokens <= 512 or not 1 <= threads <= 8:
            raise FeatureError("model_bounds", "Invalid CPU/token bounds")
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            raise FeatureError(
                "nlp_not_installed", "Install the optional NLP dependency lock", 503
            ) from None
        torch.set_num_threads(threads)
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                MODEL_ID,
                revision=MODEL_REVISION,
                cache_dir=cache_dir,
                local_files_only=local_only,
                trust_remote_code=False,
            )
            self.model = (
                AutoModelForSequenceClassification.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    cache_dir=cache_dir,
                    local_files_only=local_only,
                    trust_remote_code=False,
                )
                .to("cpu")
                .eval()
            )
        except Exception:
            raise FeatureError(
                "model_unavailable", "Pinned FinBERT files unavailable; no fallback classifier", 503
            ) from None
        self.torch = torch
        self.max_tokens = max_tokens
        self.threads = threads
        self.lock = threading.Lock()
        self.labels = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        if set(self.labels.values()) != {"positive", "negative", "neutral"}:
            raise FeatureError("model_labels", "Unexpected FinBERT label map", 503)
        self.metadata = {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "tokenizer_revision": MODEL_REVISION,
            "transformers": version("transformers"),
            "torch": version("torch"),
            "preprocessing": PREPROCESS_VERSION,
            "max_tokens": max_tokens,
            "device": "cpu",
            "cpu_threads": threads,
            "deterministic": True,
            "probabilities_calibrated": False,
            "license": (
                "CC-BY-NC-SA-4.0; research only; review model card before commercial deployment"
            ),
        }

    @property
    def key(self) -> str:
        return digest(self.metadata)

    def predict(self, texts: list[str]) -> list[Prediction]:
        if not 1 <= len(texts) <= 32:
            raise FeatureError("batch_bounds", "Inference batch must contain 1–32 texts")
        clean = [preprocess(t) for t in texts]
        if any(not t for t in clean):
            raise FeatureError("empty_text", "Empty text is not model input")
        lengths = [
            len(self.tokenizer.encode(t, add_special_tokens=True, truncation=False)) for t in clean
        ]
        with self.lock, self.torch.inference_mode():
            encoded = self.tokenizer(
                clean,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_tokens,
            )
            probabilities = self.torch.softmax(self.model(**encoded).logits, dim=-1).cpu().tolist()
        result = []
        for p, n in zip(probabilities, lengths, strict=True):
            mapped = {self.labels[i]: float(v) for i, v in enumerate(p)}
            if n > self.max_tokens:
                log.info("sentiment_input_truncated", extra={"tokens": n})
            result.append(
                Prediction(
                    mapped["positive"],
                    mapped["negative"],
                    mapped["neutral"],
                    n,
                    n > self.max_tokens,
                )
            )
        return result

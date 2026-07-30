"""Pure-Python inference for the trained medication normalizer.

The model is a character n-gram TF-IDF vectoriser feeding multinomial logistic
regression, fitted by `ml/train.py` and exported to JSON. Scoring it is a sparse dot
product, so it is reimplemented here in about forty lines and the deployed service keeps
its zero-dependency install: **scikit-learn is a training-time tool only.**

The model is used as a second opinion on fuzzy dictionary matches, never as an
independent authority. See DECISIONS.md (#9) and docs/NORMALIZER.md.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "normalizer_model.json"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class NormalizerModel:
    def __init__(self, payload: dict) -> None:
        self.classes: list[str] = payload["classes"]
        self.vocabulary: dict[str, int] = payload["vocabulary"]
        self.idf: list[float] = payload["idf"]
        self.coef: list[list[float]] = payload["coef"]
        self.intercept: list[float] = payload["intercept"]
        self.threshold: float = payload["threshold"]
        low, high = payload["config"]["ngram_range"]
        self.ngram_range = (low, high)

    def _features(self, text: str) -> dict[int, float]:
        """Replicate TfidfVectorizer(analyzer="char_wb") for one document.

        char_wb pads each whitespace-separated token with spaces and takes n-grams inside
        that padded token, so word boundaries get their own grams.
        """
        cleaned = _NON_ALNUM.sub(" ", text.lower()).strip()
        counts: Counter[str] = Counter()
        for token in cleaned.split():
            padded = f" {token} "
            for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
                if len(padded) < n:
                    # Short tokens still contribute one padded gram, as sklearn does.
                    counts[padded] += 1
                    break
                for i in range(len(padded) - n + 1):
                    counts[padded[i : i + n]] += 1

        raw: dict[int, float] = {}
        for gram, count in counts.items():
            index = self.vocabulary.get(gram)
            if index is not None:
                # sublinear_tf=True
                raw[index] = (1.0 + math.log(count)) * self.idf[index]
        norm = math.sqrt(sum(v * v for v in raw.values()))
        return {i: v / norm for i, v in raw.items()} if norm else {}

    def predict(self, text: str) -> tuple[str | None, float]:
        """Return (class, probability), or (None, prob) below the confidence threshold."""
        features = self._features(text)
        if not features:
            return None, 0.0

        scores = [
            self.intercept[c] + sum(value * self.coef[c][i] for i, value in features.items())
            for c in range(len(self.classes))
        ]
        # Softmax for the multinomial case, shifted for numerical stability.
        peak = max(scores)
        exps = [math.exp(s - peak) for s in scores]
        total = sum(exps)
        best = max(range(len(scores)), key=lambda i: scores[i])
        probability = exps[best] / total

        label = self.classes[best]
        if probability < self.threshold or label == "unknown":
            return None, probability
        return label, probability


@lru_cache(maxsize=1)
def load_model() -> NormalizerModel | None:
    """Load the exported model once, or None if it has not been trained."""
    if not MODEL_PATH.exists():  # pragma: no cover - model is committed
        return None
    return NormalizerModel(json.loads(MODEL_PATH.read_text(encoding="utf-8")))

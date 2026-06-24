"""Evidence retrieval - the *retrieval* half of RAG.

The default backend is a from-scratch **BM25 (Okapi)** index: no dependencies, no cost,
and it runs comfortably on a free-tier instance. An optional **embedding** backend
(semantic vector search via an embeddings API) activates when
``SLEEPWISE_RETRIEVER=embedding`` and ``OPENAI_API_KEY`` are set, and falls back to BM25
on any problem. See DECISIONS.md (#7).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import config
from .models import EvidenceItem

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "to",
    "for",
    "in",
    "on",
    "is",
    "are",
    "with",
    "that",
    "this",
    "it",
    "as",
    "be",
    "by",
    "may",
    "can",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on word characters, and drop a few stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass
class CorpusChunk:
    id: str
    supplement_id: str
    text: str
    source: str
    source_url: str
    verified: bool

    def to_evidence(self) -> EvidenceItem:
        return EvidenceItem(
            claim=self.text,
            source=self.source,
            source_url=self.source_url,
            verified=self.verified,
        )


class BM25Index:
    """A small, dependency-free BM25 (Okapi) index over pre-tokenized documents."""

    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_len = [len(d) for d in documents]
        self.n_docs = len(documents)
        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0
        self.term_freq = [Counter(d) for d in documents]
        doc_freq: Counter[str] = Counter()
        for doc in documents:
            doc_freq.update(set(doc))
        self.idf = {
            term: math.log(1 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in doc_freq.items()
        }

    def scores(self, query: list[str]) -> list[float]:
        result = [0.0] * self.n_docs
        for term in query:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i in range(self.n_docs):
                freq = self.term_freq[i].get(term, 0)
                if not freq:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                result[i] += idf * (freq * (self.k1 + 1)) / denom
        return result


class Retriever(Protocol):
    def search(self, query: str, supplement_id: str, k: int = 3) -> list[EvidenceItem]: ...


class BM25Retriever:
    """Default retriever: ranks a supplement's evidence chunks by BM25 relevance."""

    def __init__(self, corpus: list[CorpusChunk]) -> None:
        self.corpus = corpus
        self.index = BM25Index([tokenize(f"{c.text} {c.supplement_id}") for c in corpus])

    def search(self, query: str, supplement_id: str, k: int = 3) -> list[EvidenceItem]:
        scores = self.index.scores(tokenize(query))
        candidates = [i for i, c in enumerate(self.corpus) if c.supplement_id == supplement_id]
        candidates.sort(key=lambda i: scores[i], reverse=True)
        return [self.corpus[i].to_evidence() for i in candidates[:k]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class EmbeddingRetriever:
    """Optional semantic retriever using an embeddings API. Activated via env vars."""

    def __init__(self, corpus: list[CorpusChunk]) -> None:  # pragma: no cover - needs API key
        self.corpus = corpus
        self.vectors = self._embed([c.text for c in corpus])

    def _embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - network
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"authorization": f"Bearer {config.openai_api_key()}"},
            json={"model": config.embedding_model(), "input": texts},
            timeout=20.0,
        )
        response.raise_for_status()
        return [row["embedding"] for row in response.json()["data"]]

    def search(  # pragma: no cover - needs API key
        self, query: str, supplement_id: str, k: int = 3
    ) -> list[EvidenceItem]:
        query_vec = self._embed([query])[0]
        candidates = [i for i, c in enumerate(self.corpus) if c.supplement_id == supplement_id]
        candidates.sort(key=lambda i: _cosine(query_vec, self.vectors[i]), reverse=True)
        return [self.corpus[i].to_evidence() for i in candidates[:k]]


def load_corpus(data_dir: Path = DATA_DIR) -> list[CorpusChunk]:
    raw = json.loads((data_dir / "evidence_corpus.json").read_text(encoding="utf-8"))
    return [CorpusChunk(**chunk) for chunk in raw]


def get_retriever(corpus: list[CorpusChunk] | None = None) -> Retriever:
    """Return the configured retriever, defaulting to BM25 and falling back to it."""
    if corpus is None:
        corpus = load_corpus()
    if config.embeddings_enabled():
        try:  # pragma: no cover - needs API key + network
            return EmbeddingRetriever(corpus)
        except Exception:  # pragma: no cover
            return BM25Retriever(corpus)
    return BM25Retriever(corpus)

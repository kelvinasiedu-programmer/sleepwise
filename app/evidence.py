"""Evidence retrieval entry point.

Delegates to a pluggable retriever (BM25 by default) over the curated evidence corpus in
``data/evidence_corpus.json``. This is the *retrieval* half of RAG; app/explain.py does
the optional *generation* half.
"""

from __future__ import annotations

from .models import EvidenceItem, Supplement
from .retrieval import Retriever, get_retriever

# Built once at import. The default BM25 backend has no external dependencies, so this is
# cheap and safe to do eagerly.
_retriever: Retriever = get_retriever()


def retrieve(supplement: Supplement, goal: str = "sleep", k: int = 3) -> list[EvidenceItem]:
    """Return up to ``k`` evidence chunks most relevant to the goal for this supplement."""
    query = f"{goal} {supplement.name} benefits dose risks interactions"
    return _retriever.search(query, supplement.id, k)

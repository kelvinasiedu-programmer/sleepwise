"""Evidence retrieval.

v1 returns the curated, already-goal-specific EvidenceItems attached to each
supplement. The interface is deliberately tiny so it can be swapped for true RAG
(embeddings over the full ODS + MedlinePlus corpus) without changing any caller —
see the roadmap in README.md.
"""
from __future__ import annotations

from .models import EvidenceItem, Supplement


def retrieve(supplement: Supplement, goal: str = "sleep", k: int = 3) -> list[EvidenceItem]:
    """Return up to ``k`` evidence items supporting this supplement for the goal.

    Today this is a simple slice of curated evidence. The signature matches what a
    vector-search retriever would expose, so upgrading is a drop-in replacement.
    """
    return supplement.evidence[:k]

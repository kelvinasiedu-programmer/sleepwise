"""Evaluation metrics.

Retrieval quality (recall@k, reciprocal rank → MRR) and explanation faithfulness
(coverage of the cited facts + detection of hallucinated numbers).
"""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of relevant items found in the top-k retrieved ids."""
    if not relevant_ids:
        return 0.0
    top = set(retrieved_ids[:k])
    return len(top & relevant_ids) / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """1 / rank of the first relevant id (0 if none retrieved)."""
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def coverage(explanation: str, facts: list[str]) -> float:
    """Fraction of cited facts that appear verbatim in the explanation."""
    if not facts:
        return 1.0
    present = sum(1 for fact in facts if fact in explanation)
    return present / len(facts)


def hallucinated_numbers(explanation: str, allowed_facts: str) -> list[str]:
    """Numbers in the explanation that do not appear in the source facts."""
    allowed = set(_NUMBER_RE.findall(allowed_facts))
    return [n for n in _NUMBER_RE.findall(explanation) if n not in allowed]

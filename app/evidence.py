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
    """Return up to ``k`` verified evidence chunks for this supplement.

    Publication gate: a chunk whose claim has not been confirmed against its cited
    source is never rendered. Showing an unconfirmed statement next to a citation
    implies a substantiation that does not exist, so the honest output for a supplement
    with no verified evidence is no evidence at all.

    Retrieval quality is measured over the whole corpus (see evals/); this filter is
    about what may be published, not about how well the retriever ranks.
    """
    query = f"{goal} {supplement.name} benefits dose risks interactions"
    found = _retriever.search(query, supplement.id, k)
    return [item for item in found if item.verified]

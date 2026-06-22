"""Retrieval tests: tokenizer, BM25 ranking, cosine, and the retriever wiring."""

from app import evidence, retrieval
from app.models import Supplement
from app.retrieval import BM25Index, BM25Retriever, _cosine, load_corpus, tokenize


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("The Melatonin DOSE for sleep") == ["melatonin", "dose", "sleep"]


def test_bm25_ranks_the_more_relevant_document_higher():
    docs = [tokenize("magnesium dose upper limit"), tokenize("melatonin jet lag circadian")]
    index = BM25Index(docs)
    scores = index.scores(tokenize("jet lag"))
    assert scores[1] > scores[0]


def test_cosine_handles_identical_and_orthogonal_vectors():
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_retriever_returns_only_the_requested_supplements_chunks():
    corpus = load_corpus()
    retriever = BM25Retriever(corpus)
    results = retriever.search("sleep dose risks", "melatonin", k=3)
    melatonin_texts = {c.text for c in corpus if c.supplement_id == "melatonin"}
    assert 1 <= len(results) <= 3
    assert all(item.claim in melatonin_texts for item in results)


def test_get_retriever_defaults_to_bm25():
    assert isinstance(retrieval.get_retriever(load_corpus()), BM25Retriever)


def test_evidence_retrieve_returns_relevant_items():
    supplement = Supplement(
        id="melatonin",
        name="Melatonin",
        dose_low=0.5,
        dose_high=5,
        unit="mg",
        evidence_grade="moderate",
        summary="x",
        buy_query="melatonin",
    )
    items = evidence.retrieve(supplement, goal="sleep", k=2)
    assert 1 <= len(items) <= 2

"""Tests for the evaluation metric functions."""

from evals import metrics


def test_recall_at_k():
    assert metrics.recall_at_k(["a", "b", "c"], {"b"}, 3) == 1.0
    assert metrics.recall_at_k(["a", "b", "c"], {"z"}, 3) == 0.0
    assert metrics.recall_at_k(["a", "b", "c"], {"a", "x"}, 1) == 0.5
    assert metrics.recall_at_k(["a"], set(), 1) == 0.0


def test_reciprocal_rank():
    assert metrics.reciprocal_rank(["a", "b", "c"], {"b"}) == 0.5
    assert metrics.reciprocal_rank(["a", "b"], {"z"}) == 0.0


def test_mean():
    assert metrics.mean([1.0, 0.5]) == 0.75
    assert metrics.mean([]) == 0.0


def test_coverage():
    assert metrics.coverage("the dose is 5 mg and it helps", ["5 mg", "helps"]) == 1.0
    assert metrics.coverage("only this", ["missing"]) == 0.0
    assert metrics.coverage("anything", []) == 1.0


def test_hallucinated_numbers():
    assert metrics.hallucinated_numbers("take 50 mg", "facts say 5 mg") == ["50"]
    assert metrics.hallucinated_numbers("take 5 mg", "facts say 5 mg") == []

"""Explanation-layer tests: it must lead with warnings, cite sources, and never
overstate safety."""

from app import explain
from app.models import EvidenceItem, SafetyReason, SafetyResult, Supplement


def _supplement() -> Supplement:
    return Supplement(
        id="x",
        name="X",
        dose_low=1,
        dose_high=2,
        unit="mg",
        evidence_grade="limited",
        summary="a test supplement",
        buy_query="x",
    )


def test_explanation_leads_with_warning_and_cites_source():
    result = SafetyResult(
        status="WARN",
        reasons=[SafetyReason(severity="WARN", message="be careful", source_url="http://src")],
    )
    text = explain.explain(_supplement(), result, [])
    assert "WARN" in text
    assert "be careful" in text
    assert "http://src" in text


def test_unverified_evidence_is_flagged():
    result = SafetyResult(status="ALLOW")
    evidence = [
        EvidenceItem(claim="helps sleep", source="X", source_url="http://x", verified=False)
    ]
    text = explain.explain(_supplement(), result, evidence)
    assert "unverified" in text.lower()


def test_no_interactions_is_not_presented_as_a_guarantee():
    text = explain.explain(_supplement(), SafetyResult(status="ALLOW"), [])
    assert "not a guarantee" in text.lower()


def test_explain_falls_back_to_template_without_a_key():
    supplement = _supplement()
    result = SafetyResult(
        status="WARN",
        reasons=[SafetyReason(severity="WARN", message="x", source_url="http://s")],
    )
    # With no ANTHROPIC_API_KEY (cleared by conftest), the output is exactly the template.
    assert explain.explain(supplement, result, []) == explain._render_template(
        supplement, result, []
    )


def test_call_llm_returns_none_without_a_key():
    assert explain._call_llm(_supplement(), SafetyResult(status="ALLOW"), []) is None

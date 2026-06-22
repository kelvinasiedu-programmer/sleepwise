"""Explanation layer.

Turns the *already-vetted* safety result + retrieved evidence into a short, readable
paragraph. By default this is a deterministic, citation-locked template so the project
runs with no API key. If you wire a real model, reuse SYSTEM_PROMPT and pass the same
structured inputs with JSON/structured output so the model cannot introduce a claim
that was not in its input.

The cardinal rule: the model never asserts a safety fact the rule engine did not
produce.
"""

from __future__ import annotations

from .models import EvidenceItem, SafetyResult, Supplement

SYSTEM_PROMPT = (
    "You are a careful health-information assistant. You may ONLY restate facts from "
    "the provided evidence and warnings. Never add a supplement, dose, claim, or "
    "interaction that is not in the input. Always include the citation. If a warning "
    "is present, lead with it. You do not give medical advice; you point users to "
    "professionals."
)


def explain(
    supplement: Supplement,
    safety_result: SafetyResult,
    evidence_items: list[EvidenceItem],
) -> str:
    """Build a citation-grounded explanation. Deterministic; no network required."""
    parts: list[str] = []

    if safety_result.defer_to_pro:
        parts.append("⚠ Talk to a clinician or pharmacist before using this.")

    # Warnings first — safety leads.
    for reason in safety_result.reasons:
        parts.append(f"[{reason.severity}] {reason.message} (source: {reason.source_url})")

    # Then the supporting evidence.
    for item in evidence_items:
        suffix = "" if item.verified else " [unverified — confirm against source]"
        parts.append(f"{item.claim} (source: {item.source}){suffix}")

    if not safety_result.reasons:
        parts.append(
            "No interactions were found against the medications and conditions you "
            "entered — but this only reflects the rules in this tool and is not a "
            "guarantee of safety."
        )

    return " ".join(parts)

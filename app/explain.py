"""Explanation layer.

Turns the *already-vetted* safety result + retrieved evidence into a short, readable
paragraph.

By default - and whenever no API key is set or the call fails - this is a deterministic,
citation-locked template, so the project runs with no secrets. When ``ANTHROPIC_API_KEY``
is present, an LLM rewrites the same vetted facts into friendlier prose.

The cardinal rule: this layer only affects the prose. The authoritative ALLOW/WARN/BLOCK
status and the structured ``warnings`` come from the rule engine and are returned
separately (see app/recommend.py) - the model can never alter them.
"""

from __future__ import annotations

from . import config
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
    """Return a citation-grounded explanation, LLM-written when configured."""
    template = _render_template(supplement, safety_result, evidence_items)
    if not config.llm_enabled():
        return template
    return _call_llm(supplement, safety_result, evidence_items) or template


def _render_template(
    supplement: Supplement,
    safety_result: SafetyResult,
    evidence_items: list[EvidenceItem],
) -> str:
    """The deterministic, no-network explanation. Always available as a fallback."""
    parts: list[str] = []

    if safety_result.defer_to_pro:
        parts.append("⚠ Talk to a clinician or pharmacist before using this.")

    # Warnings first - safety leads.
    for reason in safety_result.reasons:
        parts.append(f"[{reason.severity}] {reason.message} (source: {reason.source_url})")

    # Then the supporting evidence.
    for item in evidence_items:
        suffix = "" if item.verified else " [unverified - confirm against source]"
        parts.append(f"{item.claim} (source: {item.source}){suffix}")

    if not safety_result.reasons:
        parts.append(
            "No interactions were found against the medications and conditions you "
            "entered - but this only reflects the rules in this tool and is not a "
            "guarantee of safety."
        )

    return " ".join(parts)


def _facts_block(
    supplement: Supplement,
    safety_result: SafetyResult,
    evidence_items: list[EvidenceItem],
) -> str:
    """The structured, citation-bearing facts handed to the model - nothing else."""
    lines = [
        f"Supplement: {supplement.name} ({supplement.dose_low}-{supplement.dose_high} "
        f"{supplement.unit})."
    ]
    for reason in safety_result.reasons:
        lines.append(f"WARNING [{reason.severity}]: {reason.message} (cite: {reason.source_url})")
    for item in evidence_items:
        tag = "verified" if item.verified else "unverified"
        lines.append(f"EVIDENCE ({tag}): {item.claim} (cite: {item.source})")
    if safety_result.defer_to_pro:
        lines.append("NOTE: advise the user to consult a clinician or pharmacist.")
    return "\n".join(lines)


def _call_llm(
    supplement: Supplement,
    safety_result: SafetyResult,
    evidence_items: list[EvidenceItem],
) -> str | None:
    """Ask the model to rewrite the vetted facts. Returns None on any problem."""
    api_key = config.anthropic_api_key()
    if not api_key:
        return None
    try:  # pragma: no cover - exercised only with a live API key
        import httpx

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.llm_model(),
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": _facts_block(supplement, safety_result, evidence_items),
                    }
                ],
            },
            timeout=20.0,
        )
        response.raise_for_status()
        return str(response.json()["content"][0]["text"]).strip()
    except Exception:  # pragma: no cover - network/parse failures fall back to the template
        return None

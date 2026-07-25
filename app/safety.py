"""Deterministic safety layer - the heart of SleepWise.

This module decides whether each candidate supplement is ALLOW / WARN / BLOCK for a
given user, using the curated interaction rules ONLY. No language model is involved.
Rules carry a `verified` flag recording whether their claim has been confirmed against
the cited source; not all of them have been, and none have had licensed clinical review.
The LLM (see app/explain.py) may *describe* this output but must never override or
invent it.

Keeping this layer pure and deterministic is what makes it unit-testable and what keeps
a hallucination from ever reaching a safety decision.
"""

from __future__ import annotations

from .models import InteractionRule, SafetyReason, SafetyResult, Severity, Supplement, UserInput

_SEVERITY_ORDER: dict[Severity, int] = {"ALLOW": 0, "WARN": 1, "BLOCK": 2}

# Profile flags that always warrant a professional conversation before supplementing,
# regardless of the specific supplement.
# Profile flags that always warrant a professional conversation before supplementing,
# whatever the supplement. Kidney disease is included because impaired renal clearance
# affects far more than the one supplement that has an explicit rule; treating it as a
# per-supplement rule only (as an earlier version did) let other items through clean.
HARD_GATE_CONDITIONS = {"pregnancy", "breastfeeding", "under_18", "kidney_disease"}


# Free-text and UI spellings that mean the same flag. Without this, "kidney disease"
# (typed with a space) missed the canonical "kidney_disease" rule entirely.
CONDITION_ALIASES = {
    "pregnant": "pregnancy",
    "pregnancy": "pregnancy",
    "breastfeeding": "breastfeeding",
    "breast feeding": "breastfeeding",
    "nursing": "breastfeeding",
    "lactating": "breastfeeding",
    "under 18": "under_18",
    "under_18": "under_18",
    "minor": "under_18",
    "kidney disease": "kidney_disease",
    "kidney_disease": "kidney_disease",
    "renal disease": "kidney_disease",
    "renal impairment": "kidney_disease",
    "ckd": "kidney_disease",
}


def normalize_conditions(conditions: list[str]) -> set[str]:
    """Map entered condition flags onto canonical keys, keeping unknown ones as-is."""
    normalized: set[str] = set()
    for raw in conditions:
        key = " ".join(raw.strip().lower().replace("-", " ").split())
        normalized.add(CONDITION_ALIASES.get(key, key.replace(" ", "_")))
    return normalized


def _escalate(current: Severity, candidate: Severity) -> Severity:
    """Return whichever severity is more severe."""
    return candidate if _SEVERITY_ORDER[candidate] > _SEVERITY_ORDER[current] else current


def evaluate(
    user: UserInput,
    supplement: Supplement,
    rules: list[InteractionRule],
    drug_classes: set[str],
) -> SafetyResult:
    """Evaluate one supplement against the user's meds and conditions.

    Args:
        user: the user's input (meds/conditions/supplements they already take).
        supplement: the candidate supplement.
        rules: the full interaction-rule table.
        drug_classes: the user's medications already mapped to drug classes.
    """
    status: Severity = "ALLOW"
    reasons: list[SafetyReason] = []
    defer_to_pro = False

    user_conditions = normalize_conditions(user.conditions)
    user_supplements = {s.strip().lower() for s in user.current_supplements}

    for rule in rules:
        if rule.supplement_id != supplement.id:
            continue

        matched = (
            (rule.target_type == "drug_class" and rule.target in drug_classes)
            or (rule.target_type == "condition" and rule.target in user_conditions)
            or (rule.target_type == "supplement" and rule.target in user_supplements)
        )
        if matched:
            status = _escalate(status, rule.severity)
            reasons.append(
                SafetyReason(
                    severity=rule.severity,
                    message=rule.message,
                    source_url=rule.source_url,
                )
            )

    # Hard gates: never block silently - always route to a professional.
    if user_conditions & HARD_GATE_CONDITIONS:
        defer_to_pro = True
        status = _escalate(status, "WARN")
        reasons.append(
            SafetyReason(
                severity="WARN",
                message=(
                    "Your profile includes a flag (pregnancy, breastfeeding, under 18, or "
                    "kidney disease) where supplement safety data is limited or clearance "
                    "may be affected. Talk to a clinician before starting anything."
                ),
                source_url="https://ods.od.nih.gov/factsheets/list-all/",
            )
        )

    if status == "BLOCK":
        defer_to_pro = True

    return SafetyResult(status=status, reasons=reasons, defer_to_pro=defer_to_pro)

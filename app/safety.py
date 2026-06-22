"""Deterministic safety layer — the heart of SleepWise.

This module decides whether each candidate supplement is ALLOW / WARN / BLOCK for
a given user, using hand-verified interaction rules ONLY. No language model is
involved. The LLM (see app/explain.py) may *describe* this output but must never
override or invent it.

Keeping this layer pure and deterministic is what makes it unit-testable and what
keeps a hallucination from ever reaching a safety decision.
"""
from __future__ import annotations

from .models import InteractionRule, SafetyReason, SafetyResult, Supplement, UserInput

_SEVERITY_ORDER: dict[str, int] = {"ALLOW": 0, "WARN": 1, "BLOCK": 2}

# Profile flags that always warrant a professional conversation before supplementing,
# regardless of the specific supplement.
HARD_GATE_CONDITIONS = {"pregnancy", "breastfeeding", "under_18"}


def _escalate(current: str, candidate: str) -> str:
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
    status = "ALLOW"
    reasons: list[SafetyReason] = []
    defer_to_pro = False

    user_conditions = {c.strip().lower() for c in user.conditions}
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

    # Hard gates: never block silently — always route to a professional.
    if user_conditions & HARD_GATE_CONDITIONS:
        defer_to_pro = True
        status = _escalate(status, "WARN")
        reasons.append(
            SafetyReason(
                severity="WARN",
                message=(
                    "Your profile includes a flag (pregnancy, breastfeeding, or under 18) "
                    "where supplement safety data is limited. Talk to a clinician before "
                    "starting anything."
                ),
                source_url="https://ods.od.nih.gov/factsheets/list-all/",
            )
        )

    if status == "BLOCK":
        defer_to_pro = True

    return SafetyResult(status=status, reasons=reasons, defer_to_pro=defer_to_pro)

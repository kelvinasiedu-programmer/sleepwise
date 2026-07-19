"""Orchestration: input -> resolve -> assess profile -> safety -> evidence -> result.

This module wires the deterministic safety layer to the evidence and explanation steps
and decides what the response is allowed to claim about the user:

* personalized - every entered medication resolved to a known drug class, so the
  safety engine's ALLOW/WARN/BLOCK output honestly reflects the profile.
* incomplete - at least one medication was not recognized. Personalized classification
  is withheld (a missed match must never masquerade as a clean result); the response
  carries the unrecognized names and general information only.
* general - nothing was entered; the response is a labeled educational overview.

Commerce gating is absolute: a purchase link only ever appears on an ALLOW item with no
defer-to-professional flag, and never in an incomplete profile.

The only safety logic here is cross-supplement additive-sedation stacking; per-supplement
safety lives in app/safety.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import evidence, explain, normalize, safety
from .models import (
    InteractionRule,
    MedicationResolution,
    ProfileStatus,
    Recommendation,
    RecommendationResponse,
    SafetyReason,
    SafetyResult,
    Supplement,
    UserInput,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Versioned so every response can be traced to the logic and data that produced it.
SAFETY_ENGINE_VERSION = "1.1.0"
DATASET_VERSION = "2026-06-24"

DISCLAIMER = (
    "This tool provides general educational information from public health databases. "
    "It is not medical advice, not a diagnosis, and not a substitute for a doctor or "
    "pharmacist. Always consult a qualified professional before starting any supplement, "
    "especially if you take medication or have a health condition."
)

GENERAL_NOTICE = (
    "This is a general educational overview, not personalized guidance. Enter your "
    "medications and health flags to see interaction concerns relevant to you."
)
INCOMPLETE_NOTICE = (
    "We could not recognize: {names}. Because a missed medication could hide a real "
    "interaction, the information below is general only - not personalized to you. "
    "Check the spelling, or bring your medication list to a pharmacist."
)

# Affiliate note: append your tag (e.g. ?rcode=XXXX) and disclose per FTC rules before
# treating these as monetized links.
IHERB_SEARCH = "https://www.iherb.com/search?kw={q}"
STACKING_SOURCE = "https://ods.od.nih.gov/factsheets/list-all/"


def load_catalog(data_dir: Path = DATA_DIR) -> tuple[list[Supplement], list[InteractionRule]]:
    """Load the curated supplement catalog and interaction-rule table from disk."""
    supplements = [
        Supplement(**row)
        for row in json.loads((data_dir / "supplements.json").read_text(encoding="utf-8"))
    ]
    rules = [
        InteractionRule(**row)
        for row in json.loads((data_dir / "interaction_rules.json").read_text(encoding="utf-8"))
    ]
    return supplements, rules


def _format_dose(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _buy_link(supplement: Supplement, result: SafetyResult, profile: ProfileStatus) -> str | None:
    """Commerce gating invariant: ALLOW only, never deferred, never on incomplete profiles."""
    if profile == "incomplete":
        return None
    if result.status != "ALLOW" or result.defer_to_pro:
        return None
    return IHERB_SEARCH.format(q=supplement.buy_query)


def _flag_sedative_stacking(evaluated: list[tuple[Supplement, SafetyResult]]) -> None:
    """Warn when two or more sedating supplements would be suggested together.

    Deterministic and rule-based - it operates on the candidate set rather than a single
    supplement. BLOCKed items are excluded. Mutates the SafetyResults in place so the
    warning flows through to both the structured response and the explanation.
    """
    sedating = [(s, r) for s, r in evaluated if s.sedating and r.status != "BLOCK"]
    if len(sedating) < 2:
        return
    names = ", ".join(s.name for s, _ in sedating)
    for _, result in sedating:
        result.reasons.append(
            SafetyReason(
                severity="WARN",
                message=(
                    f"Combining multiple sedating supplements ({names}) can have an "
                    "additive drowsiness / CNS-depressant effect. Choose one, or check "
                    "with a clinician or pharmacist before stacking them."
                ),
                source_url=STACKING_SOURCE,
            )
        )
        if result.status == "ALLOW":
            result.status = "WARN"


def _assess_profile(
    user: UserInput, resolutions: list[MedicationResolution]
) -> tuple[ProfileStatus, list[str]]:
    unrecognized = [r.input for r in resolutions if r.status == "unrecognized"]
    if unrecognized:
        return "incomplete", unrecognized
    if not resolutions and not user.conditions and not user.current_supplements:
        return "general", []
    return "personalized", []


def _build_items(
    user: UserInput,
    supplements: list[Supplement],
    rules: list[InteractionRule],
    drug_classes: set[str],
    profile: ProfileStatus,
) -> tuple[list[Recommendation], list[Recommendation]]:
    evaluated = [(supp, safety.evaluate(user, supp, rules, drug_classes)) for supp in supplements]
    _flag_sedative_stacking(evaluated)

    recommended: list[Recommendation] = []
    not_recommended: list[Recommendation] = []
    for supp, result in evaluated:
        ev = evidence.retrieve(supp, goal=user.goal)
        rec = Recommendation(
            supplement=supp.name,
            status=result.status,
            dose=f"{_format_dose(supp.dose_low)}-{_format_dose(supp.dose_high)} {supp.unit}",
            timing=supp.timing,
            summary=supp.summary,
            rationale=ev,
            warnings=result.reasons,
            defer_to_pro=result.defer_to_pro,
            buy_link=_buy_link(supp, result, profile),
            explanation=explain.explain(supp, result, ev),
        )
        if result.status == "BLOCK":
            not_recommended.append(rec)
        else:
            recommended.append(rec)

    # Clean (ALLOW) options first, warnings after.
    recommended.sort(key=lambda r: 0 if r.status == "ALLOW" else 1)
    return recommended, not_recommended


def recommend(
    user: UserInput,
    supplements: list[Supplement],
    rules: list[InteractionRule],
    use_network: bool = False,
) -> RecommendationResponse:
    """Produce a full recommendation response for the user."""
    resolutions = normalize.resolve_medications(user.meds)
    profile, unrecognized = _assess_profile(user, resolutions)

    if profile == "personalized":
        drug_classes = {r.drug_class for r in resolutions if r.drug_class is not None}
        if use_network:
            drug_classes |= normalize._resolve_via_rxnorm(user.meds)
        effective_user = user
        notice = None
    else:
        # Incomplete and general profiles get the same treatment: no personalized
        # classification. Items are evaluated against an empty profile, so what remains
        # is general education (including generic cautions like sedative stacking).
        drug_classes = set()
        effective_user = UserInput(goal=user.goal)
        notice = (
            INCOMPLETE_NOTICE.format(names=", ".join(unrecognized))
            if profile == "incomplete"
            else GENERAL_NOTICE
        )

    recommended, not_recommended = _build_items(
        effective_user, supplements, rules, drug_classes, profile
    )

    return RecommendationResponse(
        goal=user.goal,
        disclaimer=DISCLAIMER,
        profile_status=profile,
        medications=resolutions,
        unrecognized_meds=unrecognized,
        notice=notice,
        engine_version=SAFETY_ENGINE_VERSION,
        dataset_version=DATASET_VERSION,
        recommended=recommended,
        not_recommended=not_recommended,
    )

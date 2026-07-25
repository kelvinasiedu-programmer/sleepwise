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
    "We could not confirm these entries: {names}. Because an unread medication or "
    "supplement could hide a real interaction, the information below is general only - "
    "not personalized to you. Check the spelling, enter one item per field, or bring "
    "your full list to a pharmacist."
)

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


def _resolve_supplements(
    entries: list[str], supplements: list[Supplement]
) -> tuple[list[Supplement], list[str]]:
    """Match entered supplements against the catalog by id, name, or alias.

    Anything we cannot place is returned as unrecognized so the caller can mark the
    profile incomplete. Previously this input was accepted and then ignored, which meant
    an unknown entry produced a confident-looking personalized result.
    """
    lookup: dict[str, Supplement] = {}
    for supplement in supplements:
        for key in (supplement.id, supplement.name, *supplement.aliases):
            lookup[" ".join(key.lower().split())] = supplement

    recognized: list[Supplement] = []
    unrecognized: list[str] = []
    for raw in entries:
        key = " ".join(raw.strip().lower().split())
        if not key:
            continue
        match = lookup.get(key)
        if match is None:
            match = next(
                (s for known, s in lookup.items() if len(known) > 3 and known in key), None
            )
        if match is None:
            unrecognized.append(raw.strip())
        elif match not in recognized:
            recognized.append(match)
    return recognized, unrecognized


def _flag_sedative_stacking(
    evaluated: list[tuple[Supplement, SafetyResult]], already_taking: list[Supplement]
) -> None:
    """Warn when a candidate would be added on top of a sedating supplement in use.

    This is measured against what the user actually reports taking, not against the other
    candidates on the page: the alternatives are options to choose between, so treating
    them as one simultaneous stack produced warnings unrelated to the user's situation.
    """
    existing_sedating = [s.name for s in already_taking if s.sedating]
    if not existing_sedating:
        return
    existing = ", ".join(existing_sedating)
    for supplement, result in evaluated:
        if not supplement.sedating or result.status == "BLOCK":
            continue
        result.reasons.append(
            SafetyReason(
                severity="WARN",
                message=(
                    f"You reported already taking {existing}. Adding another sedating "
                    "supplement can have an additive drowsiness / CNS-depressant effect. "
                    "Check with a clinician or pharmacist before combining them."
                ),
                source_url=STACKING_SOURCE,
            )
        )
        if result.status == "ALLOW":
            result.status = "WARN"


def _assess_profile(
    user: UserInput,
    resolutions: list[MedicationResolution],
    unresolved_supplements: list[str],
) -> tuple[ProfileStatus, list[str]]:
    # Anything we could not resolve - unrecognized OR ambiguous, medication or
    # supplement - makes the picture incomplete. Only a fully resolved profile earns a
    # personalized classification.
    unresolved = [r.input for r in resolutions if r.status != "recognized"]
    unresolved += unresolved_supplements
    if unresolved:
        return "incomplete", unresolved
    if not resolutions and not user.conditions and not user.current_supplements:
        return "general", []
    return "personalized", []


def _build_items(
    user: UserInput,
    supplements: list[Supplement],
    rules: list[InteractionRule],
    drug_classes: set[str],
    already_taking: list[Supplement],
) -> tuple[list[Recommendation], list[Recommendation]]:
    evaluated = [(supp, safety.evaluate(user, supp, rules, drug_classes)) for supp in supplements]
    _flag_sedative_stacking(evaluated, already_taking)

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
            # Commerce is switched off across the checker. Purchase prompts next to
            # guidance that is not clinician-reviewed put a buying nudge where a
            # professional conversation belongs; the field stays for API compatibility.
            buy_link=None,
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
    taking, unresolved_supplements = _resolve_supplements(user.current_supplements, supplements)
    profile, unrecognized = _assess_profile(user, resolutions, unresolved_supplements)

    if profile == "personalized":
        drug_classes = {r.drug_class for r in resolutions if r.drug_class is not None}
        if use_network:
            drug_classes |= normalize._resolve_via_rxnorm(user.meds)
        effective_user = user
        already_taking = taking
        notice = None
    else:
        # Incomplete and general profiles get the same treatment: no personalized
        # classification. Items are evaluated against an empty profile, so what remains
        # is general education (including generic cautions like sedative stacking).
        drug_classes = set()
        effective_user = UserInput(goal=user.goal)
        already_taking = []
        notice = (
            INCOMPLETE_NOTICE.format(names=", ".join(unrecognized))
            if profile == "incomplete"
            else GENERAL_NOTICE
        )

    recommended, not_recommended = _build_items(
        effective_user, supplements, rules, drug_classes, already_taking
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

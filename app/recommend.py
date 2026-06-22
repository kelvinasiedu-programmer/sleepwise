"""Orchestration: input -> normalize -> safety -> evidence -> explanation -> result.

This module wires the deterministic safety layer to the evidence and explanation steps.
The only safety logic here is cross-supplement: additive-sedation stacking, which is
still rule-based and deterministic (see `_flag_sedative_stacking`). Per-supplement safety
lives in app/safety.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import evidence, explain, normalize, safety
from .models import (
    InteractionRule,
    Recommendation,
    RecommendationResponse,
    SafetyReason,
    SafetyResult,
    Supplement,
    UserInput,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DISCLAIMER = (
    "This tool provides general educational information from public health databases. "
    "It is not medical advice, not a diagnosis, and not a substitute for a doctor or "
    "pharmacist. Always consult a qualified professional before starting any supplement, "
    "especially if you take medication or have a health condition."
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


def _build_buy_link(supplement: Supplement) -> str:
    return IHERB_SEARCH.format(q=supplement.buy_query)


def _flag_sedative_stacking(evaluated: list[tuple[Supplement, SafetyResult]]) -> None:
    """Warn when two or more sedating supplements would be suggested together.

    Deterministic and rule-based — it operates on the candidate set rather than a single
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


def recommend(
    user: UserInput,
    supplements: list[Supplement],
    rules: list[InteractionRule],
    use_network: bool = False,
) -> RecommendationResponse:
    """Produce a full recommendation response for the user."""
    drug_classes = normalize.to_drug_classes(user.meds, use_network=use_network)

    # Pass 1: per-supplement safety.
    evaluated = [(supp, safety.evaluate(user, supp, rules, drug_classes)) for supp in supplements]

    # Pass 2: cross-supplement additive sedation.
    _flag_sedative_stacking(evaluated)

    # Pass 3: build the response.
    recommended: list[Recommendation] = []
    not_recommended: list[Recommendation] = []
    for supp, result in evaluated:
        ev = evidence.retrieve(supp, goal=user.goal)
        rec = Recommendation(
            supplement=supp.name,
            status=result.status,
            dose=f"{_format_dose(supp.dose_low)}–{_format_dose(supp.dose_high)} {supp.unit}",
            timing=supp.timing,
            summary=supp.summary,
            rationale=ev,
            warnings=result.reasons,
            defer_to_pro=result.defer_to_pro,
            buy_link=None if result.status == "BLOCK" else _build_buy_link(supp),
            explanation=explain.explain(supp, result, ev),
        )
        if result.status == "BLOCK":
            not_recommended.append(rec)
        else:
            recommended.append(rec)

    # Clean (ALLOW) options first, warnings after.
    recommended.sort(key=lambda r: 0 if r.status == "ALLOW" else 1)

    return RecommendationResponse(
        goal=user.goal,
        disclaimer=DISCLAIMER,
        recommended=recommended,
        not_recommended=not_recommended,
    )

"""Map user-entered medication names to drug classes.

The offline map below is the source of truth today. A live NIH RxNorm / RxClass
resolver is the planned upgrade (see the roadmap in README.md); the `use_network` hook
and `_resolve_via_rxnorm` exist so it can be added without changing this module's public
signature. Graceful degradation is intentional — see DECISIONS.md (#3).
"""

from __future__ import annotations

# Minimal, hand-maintained generic-name -> drug-class map. Brand names and misspellings
# are deliberately out of scope for v1 (a documented limitation, not an oversight).
LOCAL_DRUG_CLASSES: dict[str, str] = {
    # anticoagulants / antiplatelets
    "warfarin": "anticoagulant",
    "apixaban": "anticoagulant",
    "rivaroxaban": "anticoagulant",
    "heparin": "anticoagulant",
    "aspirin": "antiplatelet",
    "clopidogrel": "antiplatelet",
    # CNS depressants
    "lorazepam": "benzodiazepine",
    "diazepam": "benzodiazepine",
    "alprazolam": "benzodiazepine",
    "clonazepam": "benzodiazepine",
    "temazepam": "benzodiazepine",
    "zolpidem": "sedative_hypnotic",
    "eszopiclone": "sedative_hypnotic",
    "oxycodone": "opioid",
    "hydrocodone": "opioid",
    "tramadol": "opioid",
    # cardiovascular
    "lisinopril": "antihypertensive",
    "amlodipine": "antihypertensive",
    "metoprolol": "antihypertensive",
    "losartan": "antihypertensive",
    # endocrine / metabolic
    "metformin": "antidiabetic",
    "insulin": "antidiabetic",
    "glipizide": "antidiabetic",
    "levothyroxine": "thyroid_hormone",
    # psychiatric
    "sertraline": "ssri",
    "fluoxetine": "ssri",
    "escitalopram": "ssri",
    "citalopram": "ssri",
    "paroxetine": "ssri",
    "clozapine": "antipsychotic_clozapine",
    # antibiotics that bind minerals
    "ciprofloxacin": "quinolone_antibiotic",
    "levofloxacin": "quinolone_antibiotic",
    "doxycycline": "tetracycline_antibiotic",
    "minocycline": "tetracycline_antibiotic",
    # immune / bone
    "prednisone": "immunosuppressant",
    "tacrolimus": "immunosuppressant",
    "cyclosporine": "immunosuppressant",
    "alendronate": "bisphosphonate",
}

# RxNorm REST base for the planned live resolver.
RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


def to_drug_classes(meds: list[str], use_network: bool = False) -> set[str]:
    """Resolve medication names to a set of drug classes.

    The offline map always runs. When ``use_network`` is True we additionally consult
    RxNorm; that path is a documented hook today and returns nothing, so the offline
    result is never blocked by network behavior.
    """
    classes = {
        LOCAL_DRUG_CLASSES[key]
        for med in meds
        if (key := med.strip().lower()) in LOCAL_DRUG_CLASSES
    }
    if use_network:
        classes |= _resolve_via_rxnorm(meds)
    return classes


def _resolve_via_rxnorm(meds: list[str]) -> set[str]:
    """Hook for live RxNorm/RxClass resolution.

    Not yet implemented: the offline map is authoritative for v1. This exists so the
    network path can be added later without touching ``to_drug_classes``'s signature.
    """
    return set()

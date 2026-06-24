"""Map user-entered medication names to drug classes.

A missed match is a safety problem - it surfaces as a false ALLOW - so beyond the
generic-name map the matcher also:

  * strips dosage/strength tokens   ("warfarin 5mg" -> "warfarin"),
  * recognizes common brand names   ("Xanax" -> benzodiazepine), and
  * does conservative fuzzy matching ("lorazepan" -> lorazepam).

A live NIH RxNorm/RxClass resolver remains the planned upgrade (the `use_network` hook).
See DECISIONS.md (#3).
"""

from __future__ import annotations

import difflib
import re

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
    # common US brand names -> class
    "xanax": "benzodiazepine",
    "ativan": "benzodiazepine",
    "valium": "benzodiazepine",
    "klonopin": "benzodiazepine",
    "restoril": "benzodiazepine",
    "ambien": "sedative_hypnotic",
    "lunesta": "sedative_hypnotic",
    "coumadin": "anticoagulant",
    "jantoven": "anticoagulant",
    "eliquis": "anticoagulant",
    "xarelto": "anticoagulant",
    "plavix": "antiplatelet",
    "oxycontin": "opioid",
    "percocet": "opioid",
    "vicodin": "opioid",
    "norco": "opioid",
    "ultram": "opioid",
    "norvasc": "antihypertensive",
    "prinivil": "antihypertensive",
    "zestril": "antihypertensive",
    "lopressor": "antihypertensive",
    "cozaar": "antihypertensive",
    "glucophage": "antidiabetic",
    "synthroid": "thyroid_hormone",
    "zoloft": "ssri",
    "prozac": "ssri",
    "lexapro": "ssri",
    "celexa": "ssri",
    "paxil": "ssri",
    "cipro": "quinolone_antibiotic",
    "levaquin": "quinolone_antibiotic",
    "clozaril": "antipsychotic_clozapine",
    "fosamax": "bisphosphonate",
}

# RxNorm REST base for the planned live resolver.
RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"

_STRENGTH_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|units?)\b", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")
_FUZZY_CUTOFF = 0.85


def _clean(med: str) -> str:
    text = _STRENGTH_RE.sub(" ", med.lower())
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def _match(med: str) -> str | None:
    cleaned = _clean(med)
    if not cleaned:
        return None
    # Exact match on the whole cleaned name or any single token.
    for candidate in [cleaned, *cleaned.split()]:
        if candidate in LOCAL_DRUG_CLASSES:
            return LOCAL_DRUG_CLASSES[candidate]
    # Conservative fuzzy match (typos), token by token.
    known = list(LOCAL_DRUG_CLASSES)
    for token in cleaned.split():
        close = difflib.get_close_matches(token, known, n=1, cutoff=_FUZZY_CUTOFF)
        if close:
            return LOCAL_DRUG_CLASSES[close[0]]
    return None


def to_drug_classes(meds: list[str], use_network: bool = False) -> set[str]:
    """Resolve medication names to a set of drug classes."""
    classes = {cls for med in meds if (cls := _match(med)) is not None}
    if use_network:
        classes |= _resolve_via_rxnorm(meds)
    return classes


def _resolve_via_rxnorm(meds: list[str]) -> set[str]:
    """Hook for live RxNorm/RxClass resolution.

    Not yet implemented: the offline matcher above is authoritative for v1. This exists
    so the network path can be added later without touching ``to_drug_classes``.
    """
    return set()

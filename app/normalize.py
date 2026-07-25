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

from .models import MedicationResolution

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


# Words that flip or qualify the meaning of an entry ("stopped warfarin", "no aspirin").
# We cannot safely interpret these, so they make the entry ambiguous rather than being
# read as a current medication.
_NEGATION_TOKENS = {
    "no",
    "not",
    "none",
    "never",
    "stopped",
    "stopping",
    "quit",
    "former",
    "formerly",
    "past",
    "previously",
    "discontinued",
    "off",
    "avoid",
    "avoiding",
    "allergic",
}


def _matched_entities(med: str) -> list[str]:
    """Every distinct known drug name an entry matches, in order.

    Returning all matches (instead of the first) is what stops a second medication in
    the same field from disappearing silently.
    """
    cleaned = _clean(med)
    if not cleaned:
        return []
    # A whole-string hit wins outright, so multi-word brand names stay intact.
    if cleaned in LOCAL_DRUG_CLASSES:
        return [cleaned]
    known = list(LOCAL_DRUG_CLASSES)
    found: list[str] = []
    for token in cleaned.split():
        if token in LOCAL_DRUG_CLASSES:
            if token not in found:
                found.append(token)
            continue
        close = difflib.get_close_matches(token, known, n=1, cutoff=_FUZZY_CUTOFF)
        if close and close[0] not in found:
            found.append(close[0])
    return found


def _resolve_one(med: str) -> MedicationResolution:
    """Resolve a single entry to exactly one drug entity, or refuse to guess."""
    name = med.strip()
    cleaned = _clean(name)

    if cleaned and _NEGATION_TOKENS & set(cleaned.split()):
        return MedicationResolution(
            input=name,
            status="ambiguous",
            detail="This entry contains a word we cannot interpret safely (such as 'stopped' "
            "or 'no'). Enter only medications you currently take, one per entry.",
        )

    entities = _matched_entities(name)
    if not entities:
        return MedicationResolution(input=name, status="unrecognized")

    classes = {LOCAL_DRUG_CLASSES[entity] for entity in entities}
    if len(classes) > 1:
        # Several distinct drug classes in one field: resolving to any single one would
        # discard the others, so refuse and ask the user to split the entry.
        return MedicationResolution(
            input=name,
            status="ambiguous",
            detail="This looks like more than one medication (" + ", ".join(entities) + "). "
            "Please enter each medication as its own entry.",
        )

    return MedicationResolution(
        input=name, status="recognized", drug_class=LOCAL_DRUG_CLASSES[entities[0]]
    )


def _match(med: str) -> str | None:
    """Back-compatible single-class lookup; None unless the entry resolves cleanly."""
    return _resolve_one(med).drug_class


def resolve_medications(meds: list[str]) -> list[MedicationResolution]:
    """Resolve every entered medication to an explicit outcome.

    A non-empty entry is never dropped. It comes back recognized (with its drug class),
    unrecognized, or ambiguous. Callers must treat anything other than recognized as
    making the profile incomplete: an unread medication must never silently produce a
    reassuring personalized result.
    """
    return [_resolve_one(med) for med in meds if med.strip()]


def to_drug_classes(meds: list[str], use_network: bool = False) -> set[str]:
    """Resolve medication names to a set of drug classes."""
    classes = {r.drug_class for r in resolve_medications(meds) if r.drug_class is not None}
    if use_network:
        classes |= _resolve_via_rxnorm(meds)
    return classes


def _resolve_via_rxnorm(meds: list[str]) -> set[str]:
    """Hook for live RxNorm/RxClass resolution.

    Not yet implemented: the offline matcher above is authoritative for v1. This exists
    so the network path can be added later without touching ``to_drug_classes``.
    """
    return set()

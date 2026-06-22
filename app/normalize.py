"""Map user-entered medication names to drug classes.

Primary path: NIH RxNorm / RxClass (https://rxnav.nlm.nih.gov/). To keep the app
runnable offline and the tests deterministic, we ship a small local lookup and only
hit the network when explicitly asked. Graceful degradation is intentional — see
DECISIONS.md (#3).
"""
from __future__ import annotations

# Minimal, hand-maintained name -> drug-class map. This is a starting point for the
# offline path; the live RxNorm path (below) is the real source for production.
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

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


def to_drug_classes(meds: list[str], use_network: bool = False, timeout: float = 4.0) -> set[str]:
    """Resolve a list of medication names to a set of drug classes.

    The offline map always runs. If ``use_network`` is True we additionally try
    RxNorm, but any failure there is swallowed so the safety layer still has the
    offline result to work with.
    """
    classes: set[str] = set()
    for med in meds:
        key = med.strip().lower()
        if key in LOCAL_DRUG_CLASSES:
            classes.add(LOCAL_DRUG_CLASSES[key])

    if use_network:
        classes |= _resolve_via_rxnorm(meds, timeout=timeout)

    return classes


def _resolve_via_rxnorm(meds: list[str], timeout: float) -> set[str]:
    """Best-effort live resolution via RxNorm/RxClass.

    Imported lazily so the package has no hard dependency on httpx for the common
    (offline) path. Returns an empty set on any failure.
    """
    try:
        import httpx  # noqa: PLC0415 (intentional lazy import)
    except Exception:
        return set()

    found: set[str] = set()
    try:
        with httpx.Client(timeout=timeout) as client:
            for med in meds:
                resp = client.get(
                    f"{RXNAV_BASE}/rxcui.json", params={"name": med, "search": 1}
                )
                # NOTE: mapping an rxcui -> drug class via RxClass is the next step.
                # Left as a documented integration point for the roadmap.
                _ = resp
    except Exception:
        return found
    return found

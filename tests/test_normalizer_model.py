"""Trained-normalizer tests.

The model is only ever a second opinion. These tests pin that arrangement down: the
dictionary stays authoritative, the model can veto a fuzzy guess but never override an
exact hit, and an uncovered drug is still refused.
"""

from app import normalize
from app.normalizer_model import load_model


def test_model_loads_and_infers_without_sklearn():
    # Runtime inference is pure Python; sklearn is a training-time tool only.
    model = load_model()
    assert model is not None
    label, prob = model.predict("lorazepam")
    assert label == "benzodiazepine"
    assert prob > 0.9


def test_model_declines_below_threshold():
    model = load_model()
    # A near-miss of a covered drug: the model must not confidently claim it.
    label, _ = model.predict("warfarina")
    assert label is None


def test_model_rejects_drugs_outside_coverage():
    model = load_model()
    for drug in ("ibuprofen", "quetiapine", "atorvastatin", "omeprazole"):
        label, _ = model.predict(drug)
        assert label is None, drug


def test_exact_dictionary_hit_is_authoritative():
    # No model opinion can change an exact name.
    for entry, expected in (
        ("warfarin", "anticoagulant"),
        ("Xanax", "benzodiazepine"),
        ("ciprofloxacin", "quinolone_antibiotic"),
        ("levothyroxine", "thyroid_hormone"),
    ):
        resolution = normalize.resolve_medications([entry])[0]
        assert resolution.status == "recognized", entry
        assert resolution.drug_class == expected, entry


def test_typo_still_resolves_when_model_agrees():
    resolution = normalize.resolve_medications(["lorazepan"])[0]
    assert resolution.status == "recognized"
    assert resolution.drug_class == "benzodiazepine"


def test_near_miss_is_refused_rather_than_guessed():
    """The regression this model was added for.

    Fuzzy matching alone resolved "warfarina" to warfarin, turning a drug the project does
    not cover into a confident anticoagulant result. The model now has to second the fuzzy
    guess, and it declines.
    """
    resolution = normalize.resolve_medications(["warfarina"])[0]
    assert resolution.status == "unrecognized"
    assert resolution.detail and "could not confirm" in resolution.detail


def test_uncovered_drugs_stay_unrecognized_end_to_end():
    for drug in ("ibuprofen", "quetiapine", "atorvastatin"):
        resolution = normalize.resolve_medications([drug])[0]
        assert resolution.status == "unrecognized", drug
        assert resolution.drug_class is None, drug


def test_multi_entity_entry_still_ambiguous_with_model_present():
    resolution = normalize.resolve_medications(["warfarin lorazepam"])[0]
    assert resolution.status == "ambiguous"

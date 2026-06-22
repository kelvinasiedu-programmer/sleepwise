"""Medication-to-drug-class mapping tests."""

from app import normalize


def test_known_generic_name_maps_to_class():
    assert normalize.to_drug_classes(["Warfarin"]) == {"anticoagulant"}


def test_unknown_med_maps_to_empty():
    assert normalize.to_drug_classes(["totally-made-up-drug"]) == set()


def test_multiple_meds_map_to_multiple_classes():
    assert normalize.to_drug_classes(["lorazepam", "ciprofloxacin"]) == {
        "benzodiazepine",
        "quinolone_antibiotic",
    }


def test_matching_is_case_and_whitespace_insensitive():
    assert normalize.to_drug_classes(["  LORAZEPAM "]) == {"benzodiazepine"}


def test_brand_name_resolves_to_class():
    assert normalize.to_drug_classes(["Xanax"]) == {"benzodiazepine"}
    assert normalize.to_drug_classes(["Coumadin"]) == {"anticoagulant"}


def test_dosage_strength_is_stripped():
    assert normalize.to_drug_classes(["warfarin 5mg"]) == {"anticoagulant"}
    assert normalize.to_drug_classes(["Coumadin 5 mg"]) == {"anticoagulant"}


def test_typo_resolves_via_fuzzy_match():
    assert normalize.to_drug_classes(["lorazepan"]) == {"benzodiazepine"}


def test_unrelated_drug_does_not_false_match():
    assert normalize.to_drug_classes(["ibuprofen"]) == set()

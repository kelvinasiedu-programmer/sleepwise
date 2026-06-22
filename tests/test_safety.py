"""Safety-rule tests.

These encode the requirement that matters most: known-dangerous pairs must be caught.
If a future change ever lets one through, the suite goes red.
"""
from app import normalize, recommend, safety
from app.models import UserInput

SUPPLEMENTS, RULES = recommend.load_catalog()
BY_ID = {s.id: s for s in SUPPLEMENTS}


def _evaluate(supp_id, meds=None, conditions=None):
    user = UserInput(meds=meds or [], conditions=conditions or [])
    drug_classes = normalize.to_drug_classes(user.meds)
    return safety.evaluate(user, BY_ID[supp_id], RULES, drug_classes)


def test_valerian_with_benzodiazepine_is_blocked():
    result = _evaluate("valerian", meds=["lorazepam"])
    assert result.status == "BLOCK"
    assert result.defer_to_pro is True


def test_melatonin_with_anticoagulant_warns():
    result = _evaluate("melatonin", meds=["warfarin"])
    assert result.status == "WARN"


def test_magnesium_with_quinolone_antibiotic_warns():
    result = _evaluate("magnesium", meds=["ciprofloxacin"])
    assert result.status == "WARN"


def test_magnesium_with_kidney_disease_is_blocked():
    result = _evaluate("magnesium", conditions=["kidney_disease"])
    assert result.status == "BLOCK"
    assert result.defer_to_pro is True


def test_ashwagandha_in_pregnancy_is_blocked():
    result = _evaluate("ashwagandha", conditions=["pregnancy"])
    assert result.status == "BLOCK"
    assert result.defer_to_pro is True


def test_glycine_with_clozapine_warns():
    result = _evaluate("glycine", meds=["clozapine"])
    assert result.status == "WARN"


def test_clean_profile_allows_melatonin():
    result = _evaluate("melatonin")
    assert result.status == "ALLOW"
    assert result.defer_to_pro is False


def test_pregnancy_flag_defers_even_without_a_block_rule():
    # Melatonin has no pregnancy BLOCK rule, but the hard gate must still defer.
    result = _evaluate("melatonin", conditions=["pregnancy"])
    assert result.defer_to_pro is True
    assert result.status in {"WARN", "BLOCK"}

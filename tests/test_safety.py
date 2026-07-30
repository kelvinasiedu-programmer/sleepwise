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


def test_unsourced_rules_stay_removed():
    """Rules removed by the citation audit must not creep back.

    glycine/clozapine and l-theanine/antihypertensive both cited a MedlinePlus index that
    carries no entry for either supplement. The clozapine literature also used 30-60 g of
    glycine, against a 3-5 g sleep dose, so warning at that dose was misleading rather
    than merely unsourced. See docs/CITATION_AUDIT.md.
    """
    assert _evaluate("glycine", meds=["clozapine"]).status == "ALLOW"
    assert _evaluate("l_theanine", meds=["lisinopril"]).status == "ALLOW"


def test_ashwagandha_rules_are_source_confirmed():
    # Re-cited from the dead index to the NCCIH ashwagandha page, which supports all four.
    for med in ("levothyroxine", "prednisone", "metformin", "amlodipine"):
        result = _evaluate("ashwagandha", meds=[med])
        assert result.status == "WARN", med
        assert all(r.verified for r in result.reasons), med


def test_clean_profile_allows_melatonin():
    result = _evaluate("melatonin")
    assert result.status == "ALLOW"
    assert result.defer_to_pro is False


def test_pregnancy_flag_defers_even_without_a_block_rule():
    # Melatonin has no pregnancy BLOCK rule, but the hard gate must still defer.
    result = _evaluate("melatonin", conditions=["pregnancy"])
    assert result.defer_to_pro is True
    assert result.status in {"WARN", "BLOCK"}

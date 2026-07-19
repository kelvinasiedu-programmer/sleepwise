"""End-to-end recommendation tests, including the profile-safety invariants:

* no entered medication is ever silently dropped,
* unrecognized medications make the profile incomplete (no personalized results),
* empty profiles get a labeled general overview,
* purchase links only appear on ALLOW items with no defer flag, never on incomplete
  profiles.
"""

from app import recommend
from app.models import UserInput

SUPPLEMENTS, RULES = recommend.load_catalog()


def _run(user: UserInput):
    return recommend.recommend(user, SUPPLEMENTS, RULES)


def _all_items(response):
    return [*response.recommended, *response.not_recommended]


# --- personalized profiles ---------------------------------------------------------


def test_blocked_supplement_is_separated_and_has_no_buy_link():
    response = _run(UserInput(meds=["lorazepam"]))  # valerian should be blocked
    assert response.profile_status == "personalized"
    blocked_names = {r.supplement for r in response.not_recommended}
    assert "Valerian" in blocked_names
    for rec in response.not_recommended:
        assert rec.buy_link is None


def test_allow_options_are_sorted_before_warnings():
    response = _run(UserInput(meds=["warfarin"]))  # melatonin -> WARN, others stay ALLOW
    statuses = [r.status for r in response.recommended]
    assert statuses == sorted(statuses, key=lambda s: 0 if s == "ALLOW" else 1)


def test_recognized_variants_stay_personalized():
    for med in ("Xanax", "warfarin 5mg", "lorazepan"):  # brand, dosage, typo
        response = _run(UserInput(meds=[med]))
        assert response.profile_status == "personalized", med
        assert response.unrecognized_meds == [], med


def test_resolutions_echo_every_entry():
    response = _run(UserInput(meds=["warfarin", "Xanax"]))
    assert [m.input for m in response.medications] == ["warfarin", "Xanax"]
    assert all(m.status == "recognized" for m in response.medications)


# --- incomplete profiles -----------------------------------------------------------


def test_unknown_med_makes_profile_incomplete():
    response = _run(UserInput(meds=["quetiapine"]))
    assert response.profile_status == "incomplete"
    assert response.unrecognized_meds == ["quetiapine"]
    assert response.notice is not None and "quetiapine" in response.notice
    # No personalized classification: nothing is BLOCKed in the general view.
    assert response.not_recommended == []


def test_mixed_known_and_unknown_is_incomplete():
    response = _run(UserInput(meds=["warfarin", "notarealdrug"]))
    assert response.profile_status == "incomplete"
    assert "notarealdrug" in response.unrecognized_meds
    by_input = {m.input: m for m in response.medications}
    assert by_input["warfarin"].status == "recognized"
    assert by_input["notarealdrug"].status == "unrecognized"


def test_incomplete_profile_has_no_buy_links_at_all():
    response = _run(UserInput(meds=["notarealdrug"]))
    assert all(rec.buy_link is None for rec in _all_items(response))


# --- empty profiles ----------------------------------------------------------------


def test_empty_profile_is_labeled_general_overview():
    response = _run(UserInput())
    assert response.profile_status == "general"
    assert response.notice is not None
    assert "general educational overview" in response.notice.lower()


def test_sedative_stacking_warns_in_general_overview():
    response = _run(UserInput())
    by_name = {r.supplement: r for r in response.recommended}
    melatonin = by_name["Melatonin"]
    assert melatonin.status == "WARN"
    assert any("additive" in w.message.lower() for w in melatonin.warnings)
    assert by_name["Magnesium glycinate"].status == "ALLOW"


# --- commerce gating ---------------------------------------------------------------


def test_no_buy_link_on_warn_items():
    response = _run(UserInput(meds=["warfarin"]))  # melatonin -> WARN
    by_name = {r.supplement: r for r in response.recommended}
    assert by_name["Melatonin"].status == "WARN"
    assert by_name["Melatonin"].buy_link is None
    # ALLOW items without defer keep their link.
    assert by_name["Magnesium glycinate"].status == "ALLOW"
    assert by_name["Magnesium glycinate"].buy_link is not None


def test_hard_gate_conditions_remove_every_buy_link():
    for condition in ("pregnancy", "breastfeeding", "under_18"):
        response = _run(UserInput(conditions=[condition]))
        assert response.profile_status == "personalized"
        assert all(rec.buy_link is None for rec in _all_items(response)), condition
        assert all(rec.defer_to_pro for rec in _all_items(response)), condition


def test_kidney_disease_blocks_magnesium_without_link():
    response = _run(UserInput(conditions=["kidney_disease"]))
    blocked = {r.supplement: r for r in response.not_recommended}
    assert "Magnesium glycinate" in blocked
    assert blocked["Magnesium glycinate"].buy_link is None


# --- response metadata -------------------------------------------------------------


def test_disclaimer_and_versions_are_present():
    response = _run(UserInput(meds=["warfarin"]))
    assert "not medical advice" in response.disclaimer.lower()
    assert response.engine_version
    assert response.dataset_version

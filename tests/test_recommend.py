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


def test_multiple_medications_in_one_field_are_ambiguous_not_dropped():
    # Regression: this used to resolve to the first match (anticoagulant) and silently
    # discard lorazepam, yielding a confident personalized result that missed a
    # benzodiazepine interaction entirely.
    response = _run(UserInput(meds=["warfarin lorazepam"]))
    assert response.profile_status == "incomplete"
    assert response.medications[0].status == "ambiguous"
    assert "warfarin lorazepam" in response.unrecognized_meds


def test_negated_entry_is_ambiguous():
    response = _run(UserInput(meds=["stopped warfarin"]))
    assert response.profile_status == "incomplete"
    assert response.medications[0].status == "ambiguous"


def test_same_class_synonyms_still_resolve():
    # Two names for one drug class lose no information, so this stays personalized.
    response = _run(UserInput(meds=["lorazepam ativan"]))
    assert response.profile_status == "personalized"
    assert response.medications[0].drug_class == "benzodiazepine"


def test_unknown_existing_supplement_makes_profile_incomplete():
    response = _run(UserInput(current_supplements=["kratom"]))
    assert response.profile_status == "incomplete"
    assert "kratom" in response.unrecognized_meds


def test_existing_sedating_supplement_drives_stacking_warning():
    response = _run(UserInput(current_supplements=["melatonin"]))
    assert response.profile_status == "personalized"
    valerian = next(r for r in _all_items(response) if r.supplement == "Valerian")
    assert valerian.status == "WARN"
    assert any("already taking" in w.message.lower() for w in valerian.warnings)


def test_candidates_alone_do_not_trigger_stacking():
    # Alternatives on the page are options to choose between, not a simultaneous stack.
    response = _run(UserInput(meds=["warfarin"]))
    valerian = next(r for r in _all_items(response) if r.supplement == "Valerian")
    assert not any("already taking" in w.message.lower() for w in valerian.warnings)


# --- empty profiles ----------------------------------------------------------------


def test_empty_profile_is_labeled_general_overview():
    response = _run(UserInput())
    assert response.profile_status == "general"
    assert response.notice is not None
    assert "general educational overview" in response.notice.lower()


def test_empty_profile_does_not_invent_stacking_warnings():
    # Nothing was entered, so there is no stack to warn about.
    response = _run(UserInput())
    by_name = {r.supplement: r for r in response.recommended}
    assert by_name["Melatonin"].status == "ALLOW"
    assert by_name["Magnesium glycinate"].status == "ALLOW"


# --- commerce gating ---------------------------------------------------------------


def test_commerce_is_off_everywhere():
    # Commerce is disabled across the checker, so no profile of any shape yields a link.
    for user in (
        UserInput(),
        UserInput(meds=["warfarin"]),
        UserInput(meds=["lorazepam"]),
        UserInput(meds=["notarealdrug"]),
        UserInput(conditions=["kidney_disease"]),
    ):
        assert all(rec.buy_link is None for rec in _all_items(_run(user)))


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


def test_only_source_confirmed_evidence_is_published():
    # Publication gate: an unconfirmed claim must never render next to a citation.
    for user in (UserInput(), UserInput(meds=["warfarin"])):
        for rec in _all_items(_run(user)):
            assert all(item.verified for item in rec.rationale), rec.supplement


def test_unconfirmed_warnings_still_fire_but_are_labelled():
    # Suppressing a plausible caution to tidy up a citation would make the tool less
    # safe, so the warning stays and carries verified=False for the UI to label.
    response = _run(UserInput(meds=["oxycodone"]))
    valerian = next(r for r in _all_items(response) if r.supplement == "Valerian")
    opioid = [w for w in valerian.warnings if "opioid" in w.message.lower()]
    assert opioid, "valerian/opioid caution must still be shown"
    assert opioid[0].verified is False


def test_disclaimer_and_versions_are_present():
    response = _run(UserInput(meds=["warfarin"]))
    assert "not medical advice" in response.disclaimer.lower()
    assert response.engine_version
    assert response.dataset_version

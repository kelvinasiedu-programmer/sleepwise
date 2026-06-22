"""End-to-end recommendation tests."""
from app import recommend
from app.models import UserInput

SUPPLEMENTS, RULES = recommend.load_catalog()


def test_blocked_supplement_is_separated_and_has_no_buy_link():
    user = UserInput(meds=["lorazepam"])  # valerian should be blocked
    response = recommend.recommend(user, SUPPLEMENTS, RULES)

    blocked_names = {r.supplement for r in response.not_recommended}
    assert "Valerian" in blocked_names
    for rec in response.not_recommended:
        assert rec.buy_link is None


def test_clean_user_gets_multiple_recommendations_with_buy_links():
    response = recommend.recommend(UserInput(), SUPPLEMENTS, RULES)
    assert len(response.recommended) >= 4
    assert all(r.buy_link for r in response.recommended)


def test_allow_options_are_sorted_before_warnings():
    user = UserInput(meds=["warfarin"])  # melatonin -> WARN, others stay ALLOW
    response = recommend.recommend(user, SUPPLEMENTS, RULES)
    statuses = [r.status for r in response.recommended]
    assert statuses == sorted(statuses, key=lambda s: 0 if s == "ALLOW" else 1)


def test_disclaimer_is_present():
    response = recommend.recommend(UserInput(), SUPPLEMENTS, RULES)
    assert "not medical advice" in response.disclaimer.lower()

"""Symptom organizer safety tests.

These encode the design constraints as requirements, so a later change that turns the
organizer into something diagnostic fails the build.
"""

import json
import re
from pathlib import Path

from app import symptoms
from app.models import SymptomSelection

CARDS, TOPICS, RED_FLAGS = symptoms.load_symptom_data()
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _run(answers: dict[str, str]):
    return symptoms.evaluate(SymptomSelection(answers=answers), CARDS, TOPICS, RED_FLAGS)


# --- escalation --------------------------------------------------------------------


def test_drowsy_driving_escalates_urgently():
    response = _run({"drowsy-driving": "applies"})
    assert [f.urgency for f in response.red_flags] == ["urgent"]
    assert "driving" in response.red_flags[0].message.lower()


def test_witnessed_pauses_and_sleep_attacks_escalate():
    for card in ("witnessed-pauses", "sleep-attacks"):
        response = _run({card: "applies"})
        assert response.red_flags, card
        assert response.red_flags[0].urgency == "prompt", card


def test_red_flags_are_separate_from_topics():
    # Escalation must not be buried inside the topic list.
    response = _run({"drowsy-driving": "applies", "daytime-sleepiness": "applies"})
    assert response.red_flags
    topic_text = " ".join(t.summary for t in response.topics)
    assert "driving" not in topic_text.lower()


# --- no diagnosis, no ranking, no reassurance --------------------------------------


def test_no_probability_or_ranking_language_anywhere():
    response = _run({c.id: "applies" for c in CARDS})
    blob = response.model_dump_json().lower()
    for banned in ("%", "percent", "likelihood", "probability", "most likely", "rank"):
        assert banned not in blob, banned


def test_never_asserts_or_excludes_a_condition():
    response = _run({c.id: "applies" for c in CARDS})
    blob = response.model_dump_json().lower()
    for banned in ("you have", "you do not have", "you don't have", "you are safe", "ruled out"):
        assert banned not in blob, banned


def test_no_answers_still_does_not_reassure():
    response = _run({c.id: "not_applies" for c in CARDS})
    assert response.topics == []
    assert response.notice is not None
    assert "does not mean nothing is going on" in response.notice.lower()


def test_unsure_does_not_count_as_a_match():
    # Hesitation must not manufacture a topic.
    unsure = _run(dict.fromkeys(["trouble-falling-asleep", "mind-racing"], "unsure"))
    applies = _run(dict.fromkeys(["trouble-falling-asleep", "mind-racing"], "applies"))
    assert unsure.topics == []
    assert applies.topics


def test_topics_carry_their_reason_and_questions():
    response = _run({"leg-urge": "applies", "leg-relief-movement": "applies"})
    match = next(t for t in response.topics if "leg" in t.topic.lower())
    assert match.because, "a topic must show why it appeared"
    assert match.discuss, "a topic must give questions to bring to an appointment"


def test_no_medication_change_advice():
    response = _run({c.id: "applies" for c in CARDS})
    blob = response.model_dump_json().lower()
    for banned in ("stop taking", "start taking", "increase your dose", "lower your dose"):
        assert banned not in blob, banned


# --- data integrity ----------------------------------------------------------------


def test_every_trigger_refers_to_a_real_card():
    ids = {c.id for c in CARDS}
    for topic in TOPICS:
        assert set(topic.triggers) <= ids, topic.id
    for flag in RED_FLAGS:
        assert set(flag.triggers) <= ids, flag.id


def test_cards_ask_for_no_identifying_information():
    # The card set must stay free of name, contact, or identity prompts.
    blob = " ".join(c.prompt.lower() for c in CARDS)
    for banned in ("your name", "email", "phone", "address", "date of birth", "insurance"):
        assert banned not in blob, banned


def test_sample_data_is_labelled_as_unreviewed():
    raw = json.loads((DATA_DIR / "symptom_topics.json").read_text(encoding="utf-8"))
    note = raw["_note"].lower()
    assert "sample data" in note
    assert "not" in note and "clinician" in note


def test_card_count_is_a_reasonable_mvp_size():
    assert 15 <= len(CARDS) <= 25
    assert 4 <= len(TOPICS) <= 8


def test_api_serves_cards_and_organizes_selections():
    import pytest
    from fastapi.testclient import TestClient

    from app import main
    from app.main import app
    from app.ratelimit import RateLimiter

    main._limiter = RateLimiter(limit=10000, window=60)
    client = TestClient(app)

    cards = client.get("/api/symptom-cards").json()
    assert len(cards["cards"]) == len(CARDS)

    body = client.post("/symptoms", json={"answers": {"drowsy-driving": "applies"}}).json()
    assert body["red_flags"][0]["urgency"] == "urgent"

    page = client.get("/organizer")
    assert page.status_code == 200
    # The demonstration framing must be on the page itself, not only in the docs.
    assert "demonstration built on sample data" in page.text
    assert 'name="robots" content="noindex"' in page.text
    assert pytest  # imported for parity with the rest of the suite


def test_no_scoring_arithmetic_in_output_model():
    # Guard against a future "score" or "confidence" field creeping into the response.
    fields = symptoms.SymptomResponse.model_fields.keys()
    assert not any(re.search(r"score|confidence|percent|rank", f) for f in fields)

"""Symptom organizer: fixed cards, fixed rules, no model in the loop.

This turns a set of "applies to me" selections into an organized summary a person can
take to an appointment. It is deliberately NOT a diagnostic instrument:

* Topics are surfaced, never ranked, scored, or expressed as a likelihood. There is no
  arithmetic anywhere that could be read as "how likely" something is.
* Nothing is ever ruled out. "Doesn't apply" removes support for a topic; it never
  produces a reassuring statement, because absence of a symptom is not absence of a
  condition.
* Red flags are evaluated BEFORE topics and are reported separately. A person who is
  falling asleep at the wheel needs escalation, not a tidy list of discussion topics.
* No language model is involved at any point. Every string a user sees comes from the
  curated data file.

The card and topic data is illustrative sample data for a demonstration; it has not been
reviewed by a sleep-medicine clinician. See docs and the on-page framing.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    RedFlag,
    SymptomCard,
    SymptomResponse,
    SymptomSelection,
    SymptomTopic,
    TopicMatch,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ORGANIZER_VERSION = "1.0.0"

INTRO = (
    "SleepWise organizes what you select and points you at things worth raising with a "
    "clinician. It does not diagnose, and it cannot rule anything out."
)

NO_MATCH_NOTICE = (
    "Your selections did not group into any of the topics in this demonstration. That "
    "does not mean nothing is going on. If your sleep is affecting your daily life, it "
    "is still worth raising with a clinician."
)

CLOSING = (
    "These topics overlap and are listed in no particular order. Symptoms like these can "
    "have many different causes, and only a qualified clinician can work out which apply "
    "to you."
)


def load_symptom_data(
    data_dir: Path = DATA_DIR,
) -> tuple[list[SymptomCard], list[SymptomTopic], list[RedFlag]]:
    """Load the fixed card set, topic rules, and red-flag rules from disk."""
    cards = [
        SymptomCard(**row)
        for row in json.loads((data_dir / "symptom_cards.json").read_text(encoding="utf-8"))
    ]
    raw = json.loads((data_dir / "symptom_topics.json").read_text(encoding="utf-8"))
    topics = [SymptomTopic(**row) for row in raw["topics"]]
    red_flags = [RedFlag(**row) for row in raw["red_flags"]]
    return cards, topics, red_flags


def _applies(selection: SymptomSelection) -> set[str]:
    """Only explicit "applies to me" answers support a topic.

    "Not sure" deliberately does not count toward a match. Treating uncertainty as a yes
    would manufacture topics out of hesitation.
    """
    return {card_id for card_id, answer in selection.answers.items() if answer == "applies"}


def evaluate(
    selection: SymptomSelection,
    cards: list[SymptomCard],
    topics: list[SymptomTopic],
    red_flags: list[RedFlag],
) -> SymptomResponse:
    """Organize selections into red flags and unranked discussion topics."""
    selected = _applies(selection)
    unsure = {card_id for card_id, answer in selection.answers.items() if answer == "unsure"}
    by_id = {card.id: card for card in cards}

    # Red flags first: escalation must not be buried underneath a list of topics.
    flags = [flag for flag in red_flags if selected & set(flag.triggers)]

    matches: list[TopicMatch] = []
    for topic in topics:
        hits = [card_id for card_id in topic.triggers if card_id in selected]
        if len(hits) < topic.min_matches:
            continue
        matches.append(
            TopicMatch(
                topic=topic.name,
                summary=topic.summary,
                # "Why this appeared" is just the selections that produced it, so the
                # user can see the rule rather than trust a black box.
                because=[by_id[card_id].prompt for card_id in hits if card_id in by_id],
                discuss=topic.discuss,
            )
        )

    return SymptomResponse(
        intro=INTRO,
        selected=[by_id[card_id].prompt for card_id in selected if card_id in by_id],
        unsure=[by_id[card_id].prompt for card_id in unsure if card_id in by_id],
        red_flags=flags,
        topics=matches,
        notice=None if matches else NO_MATCH_NOTICE,
        closing=CLOSING,
        organizer_version=ORGANIZER_VERSION,
    )

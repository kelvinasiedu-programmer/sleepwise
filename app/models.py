"""Typed data model for SleepWise.

Pydantic gives us validation, automatic API docs, and a single source of truth
for the shapes that flow through the pipeline.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Severity = Literal["ALLOW", "WARN", "BLOCK"]

# How much the response can honestly claim to be about *this* user:
#   personalized - every entered medication was recognized, so the safety engine ran
#   incomplete   - at least one medication was not recognized; personalized
#                  classification is withheld so a missed match can never masquerade
#                  as a clean result
#   general      - nothing was entered; output is a labeled educational overview
ProfileStatus = Literal["personalized", "incomplete", "general"]


class MedicationResolution(BaseModel):
    """The fate of one entered medication. Nothing is ever dropped silently.

    `ambiguous` means the entry matched more than one distinct drug entity (for example
    "warfarin lorazepam" typed into a single field). Resolving it to the first match
    would silently discard the rest, so it is treated as unresolved.
    """

    input: str
    status: Literal["recognized", "unrecognized", "ambiguous"]
    drug_class: str | None = None
    detail: str | None = None


class EvidenceItem(BaseModel):
    claim: str
    source: str
    source_url: str
    verified: bool = False


class Supplement(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    dose_low: float
    dose_high: float
    unit: str
    timing: str | None = None
    evidence_grade: str
    summary: str
    sedating: bool = False
    # False when no cited source states the displayed range. Currently false for every
    # supplement; see docs/CITATION_AUDIT.md.
    dose_verified: bool = False
    evidence: list[EvidenceItem] = Field(default_factory=list)
    buy_query: str


class InteractionRule(BaseModel):
    supplement_id: str
    target_type: Literal["drug_class", "condition", "supplement"]
    target: str
    severity: Severity
    message: str
    source_url: str
    verified: bool = False


# Bounded free-text to cap payload size (defense against abusive input).
_FreeText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class UserInput(BaseModel):
    goal: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] = "sleep"
    meds: list[_FreeText] = Field(default_factory=list, max_length=50)
    conditions: list[_FreeText] = Field(default_factory=list, max_length=50)
    current_supplements: list[_FreeText] = Field(default_factory=list, max_length=50)


class SafetyReason(BaseModel):
    severity: Severity
    message: str
    source_url: str
    # False when the underlying rule's claim has not been confirmed against its cited
    # source. Such a warning still fires - suppressing a plausible caution to tidy up a
    # citation would make the tool less safe - but it is labelled as precautionary
    # rather than presented as substantiated.
    verified: bool = True


class SafetyResult(BaseModel):
    status: Severity
    reasons: list[SafetyReason] = Field(default_factory=list)
    defer_to_pro: bool = False


class Recommendation(BaseModel):
    supplement: str
    status: Severity
    dose: str
    timing: str | None = None
    summary: str
    rationale: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[SafetyReason] = Field(default_factory=list)
    defer_to_pro: bool = False
    buy_link: str | None = None
    explanation: str


class RecommendationResponse(BaseModel):
    goal: str
    disclaimer: str
    profile_status: ProfileStatus = "personalized"
    medications: list[MedicationResolution] = Field(default_factory=list)
    unrecognized_meds: list[str] = Field(default_factory=list)
    notice: str | None = None
    engine_version: str = ""
    dataset_version: str = ""
    recommended: list[Recommendation] = Field(default_factory=list)
    not_recommended: list[Recommendation] = Field(default_factory=list)


# --- Symptom organizer -------------------------------------------------------------
# Fixed cards and fixed rules. Nothing here is ranked, scored, or probabilistic, and
# there is no "ruled out" state: absence of a symptom is not absence of a condition.

SymptomAnswer = Literal["applies", "not_applies", "unsure"]


class SymptomCard(BaseModel):
    id: str
    prompt: str
    group: str
    followups: list[str] = Field(default_factory=list)


class SymptomTopic(BaseModel):
    id: str
    name: str
    summary: str
    triggers: list[str] = Field(default_factory=list)
    min_matches: int = 1
    discuss: list[str] = Field(default_factory=list)


class RedFlag(BaseModel):
    id: str
    triggers: list[str] = Field(default_factory=list)
    urgency: Literal["urgent", "prompt"]
    message: str


class TopicMatch(BaseModel):
    topic: str
    summary: str
    because: list[str] = Field(default_factory=list)
    discuss: list[str] = Field(default_factory=list)


class SymptomSelection(BaseModel):
    # Card id -> answer. Bounded to the fixed card set size; no free text is accepted,
    # so no identifying information can reach the server.
    answers: dict[str, SymptomAnswer] = Field(default_factory=dict, max_length=60)


class SymptomResponse(BaseModel):
    intro: str
    selected: list[str] = Field(default_factory=list)
    unsure: list[str] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    topics: list[TopicMatch] = Field(default_factory=list)
    notice: str | None = None
    closing: str
    organizer_version: str = ""


class Feedback(BaseModel):
    useful: Literal["yes", "somewhat", "no"]
    note: str | None = Field(default=None, max_length=500)

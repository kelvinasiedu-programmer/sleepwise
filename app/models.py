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
    """The fate of one entered medication. Nothing is ever dropped silently."""

    input: str
    status: Literal["recognized", "unrecognized"]
    drug_class: str | None = None


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


class Feedback(BaseModel):
    useful: Literal["yes", "somewhat", "no"]
    note: str | None = Field(default=None, max_length=500)

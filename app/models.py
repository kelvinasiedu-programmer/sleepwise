"""Typed data model for SleepWise.

Pydantic gives us validation, automatic API docs, and a single source of truth
for the shapes that flow through the pipeline.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["ALLOW", "WARN", "BLOCK"]


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


class UserInput(BaseModel):
    goal: str = "sleep"
    meds: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    current_supplements: list[str] = Field(default_factory=list)


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
    recommended: list[Recommendation] = Field(default_factory=list)
    not_recommended: list[Recommendation] = Field(default_factory=list)

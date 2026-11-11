"""Request payloads (validated by pydantic before any business logic runs)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from domain.schema import EVIDENCE_TYPES, GOAL_CATEGORIES, METRIC_TYPES


class KeyResultIn(BaseModel):
    description: str = Field(min_length=3, max_length=200)
    metric_type: Literal[tuple(METRIC_TYPES)]  # type: ignore[valid-type]
    unit: str = Field(min_length=1, max_length=20)
    start_value: float
    target_value: float
    weight_pct: int = Field(ge=1, le=100)

    @field_validator("target_value")
    @classmethod
    def target_differs(cls, v, info):
        if "start_value" in info.data and v == info.data["start_value"]:
            raise ValueError("target_value must differ from start_value")
        return v


class GoalCreate(BaseModel):
    employee_id: str = Field(pattern=r"^EMP-\d{6}$")
    cycle_id: str = Field(pattern=r"^CYCLE-\d{4}-H[12]$")
    title: str = Field(min_length=5, max_length=200)
    category: Literal[tuple(GOAL_CATEGORIES)]  # type: ignore[valid-type]
    weight_pct: int = Field(ge=5, le=100)
    key_results: list[KeyResultIn] = Field(min_length=1, max_length=4)


class KRTargetChange(BaseModel):
    kr_id: str
    target_value: float


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=5, max_length=200)
    kr_targets: Optional[list[KRTargetChange]] = None
    rationale: Optional[str] = Field(default=None, max_length=500)


class GoalTransition(BaseModel):
    to_status: Literal["draft", "pending_approval", "in_progress", "closed", "cancelled"]
    rationale: Optional[str] = None


class KRUpdateIn(BaseModel):
    kr_id: str
    reported_value: float
    over_scale_rationale: Optional[str] = Field(default=None, max_length=500)


class EvidenceIn(BaseModel):
    evidence_type: Literal[tuple(EVIDENCE_TYPES)]  # type: ignore[valid-type]
    uri: str = Field(pattern=r"^https?://", max_length=300)
    kr_id: Optional[str] = None


class CheckInCreate(BaseModel):
    confidence: Literal["low", "medium", "high"]
    note: str = Field(min_length=3, max_length=1000)
    updates: list[KRUpdateIn] = Field(min_length=1)
    evidence: list[EvidenceIn] = Field(default_factory=list)


class FeedbackCreate(BaseModel):
    feedback_type: Literal["self", "manager", "peer"]
    competency_id: str = Field(pattern=r"^COMP-\d{2}$")
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=1000)
    linked_goal_id: Optional[str] = None


class ReviewTransition(BaseModel):
    to_status: Literal["self_submitted", "manager_submitted", "finalized"]


class PlanDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: Optional[str] = Field(default=None, max_length=500)

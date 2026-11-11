"""SQLAlchemy ORM models. Columns mirror domain/schema.py (a test enforces parity)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def FK(target: str, **kw):
    # Deferrable so the employees <-> managers cycle can be loaded in one transaction (PostgreSQL)
    return ForeignKey(target, deferrable=True, initially="DEFERRED", **kw)


class Employee(Base):
    __tablename__ = "employees"
    employee_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    department: Mapped[str] = mapped_column(String(40), index=True)
    job_title: Mapped[str] = mapped_column(String(120))
    job_level: Mapped[str] = mapped_column(String(4))
    role: Mapped[str] = mapped_column(String(20))
    location: Mapped[str] = mapped_column(String(40))
    hire_date: Mapped[date] = mapped_column(Date)
    termination_date: Mapped[Optional[date]] = mapped_column(Date)
    employment_status: Mapped[str] = mapped_column(String(20))
    current_manager_id: Mapped[Optional[str]] = mapped_column(
        FK("managers.manager_id", use_alter=True, name="fk_employees_current_manager"), index=True)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Manager(Base):
    __tablename__ = "managers"
    manager_id: Mapped[str] = mapped_column(FK("employees.employee_id"), primary_key=True)
    management_level: Mapped[str] = mapped_column(String(20))
    max_span: Mapped[int] = mapped_column(Integer)
    manager_since: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean)


class ManagerAssignment(Base):
    __tablename__ = "manager_assignments"
    assignment_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"), index=True)
    manager_id: Mapped[str] = mapped_column(FK("managers.manager_id"), index=True)
    department: Mapped[str] = mapped_column(String(40))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    change_reason: Mapped[str] = mapped_column(String(20))


class ReviewCycle(Base):
    __tablename__ = "review_cycles"
    cycle_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    goal_setting_deadline: Mapped[date] = mapped_column(Date)
    review_deadline: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Goal(Base):
    __tablename__ = "goals"
    goal_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"), index=True)
    cycle_id: Mapped[str] = mapped_column(FK("review_cycles.cycle_id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20))
    weight_pct: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)
    approved_by: Mapped[Optional[str]] = mapped_column(FK("managers.manager_id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    current_version: Mapped[int] = mapped_column(Integer)
    progress_pct: Mapped[float] = mapped_column(Float)

    key_results: Mapped[list["KeyResult"]] = relationship(back_populates="goal", order_by="KeyResult.kr_id")


class KeyResult(Base):
    __tablename__ = "key_results"
    kr_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    goal_id: Mapped[str] = mapped_column(FK("goals.goal_id"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    metric_type: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(10))
    start_value: Mapped[float] = mapped_column(Float)
    target_value: Mapped[float] = mapped_column(Float)
    weight_pct: Mapped[int] = mapped_column(Integer)
    current_value: Mapped[float] = mapped_column(Float)
    raw_progress_pct: Mapped[float] = mapped_column(Float)
    scoring_progress_pct: Mapped[float] = mapped_column(Float)

    goal: Mapped[Goal] = relationship(back_populates="key_results")


class GoalVersion(Base):
    __tablename__ = "goal_versions"
    __table_args__ = (UniqueConstraint("goal_id", "version_no"),)
    version_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    goal_id: Mapped[str] = mapped_column(FK("goals.goal_id"), index=True)
    kr_id: Mapped[Optional[str]] = mapped_column(FK("key_results.kr_id"))
    version_no: Mapped[int] = mapped_column(Integer)
    change_type: Mapped[str] = mapped_column(String(30))
    field_name: Mapped[Optional[str]] = mapped_column(String(40))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(FK("employees.employee_id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    approved_by: Mapped[Optional[str]] = mapped_column(FK("employees.employee_id"))


class CheckIn(Base):
    __tablename__ = "checkins"
    checkin_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    goal_id: Mapped[str] = mapped_column(FK("goals.goal_id"), index=True)
    cycle_id: Mapped[str] = mapped_column(FK("review_cycles.cycle_id"))
    submitted_by: Mapped[str] = mapped_column(FK("employees.employee_id"))
    checkin_date: Mapped[date] = mapped_column(Date)
    sequence_no: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text)
    goal_progress_pct: Mapped[float] = mapped_column(Float)


class KRUpdate(Base):
    __tablename__ = "kr_updates"
    __table_args__ = (UniqueConstraint("checkin_id", "kr_id"),)
    update_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    checkin_id: Mapped[str] = mapped_column(FK("checkins.checkin_id"), index=True)
    kr_id: Mapped[str] = mapped_column(FK("key_results.kr_id"), index=True)
    reported_value: Mapped[float] = mapped_column(Float)
    raw_progress_pct: Mapped[float] = mapped_column(Float)
    over_scale_rationale: Mapped[Optional[str]] = mapped_column(Text)


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    evidence_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    checkin_id: Mapped[str] = mapped_column(FK("checkins.checkin_id"), index=True)
    kr_id: Mapped[Optional[str]] = mapped_column(FK("key_results.kr_id"))
    evidence_type: Mapped[str] = mapped_column(String(20))
    uri: Mapped[str] = mapped_column(String(300))
    added_by: Mapped[str] = mapped_column(FK("employees.employee_id"))
    added_at: Mapped[datetime] = mapped_column(DateTime)


class Competency(Base):
    __tablename__ = "competencies"
    competency_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))
    scale_min: Mapped[int] = mapped_column(Integer)
    scale_max: Mapped[int] = mapped_column(Integer)
    applies_to: Mapped[str] = mapped_column(String(10))


class PeerNomination(Base):
    __tablename__ = "peer_nominations"
    __table_args__ = (UniqueConstraint("cycle_id", "subject_employee_id", "peer_employee_id"),)
    nomination_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    cycle_id: Mapped[str] = mapped_column(FK("review_cycles.cycle_id"))
    subject_employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"), index=True)
    peer_employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"), index=True)
    nominated_by: Mapped[str] = mapped_column(FK("employees.employee_id"))
    status: Mapped[str] = mapped_column(String(10))
    nominated_at: Mapped[datetime] = mapped_column(DateTime)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (Index("ix_feedback_subject_cycle", "subject_employee_id", "cycle_id"),)
    feedback_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    cycle_id: Mapped[str] = mapped_column(FK("review_cycles.cycle_id"))
    subject_employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"))
    giver_employee_id: Mapped[Optional[str]] = mapped_column(FK("employees.employee_id"))
    feedback_type: Mapped[str] = mapped_column(String(10))
    competency_id: Mapped[str] = mapped_column(FK("competencies.competency_id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)
    linked_goal_id: Mapped[Optional[str]] = mapped_column(FK("goals.goal_id"))
    source: Mapped[str] = mapped_column(String(20))
    submitted_at: Mapped[datetime] = mapped_column(DateTime)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("employee_id", "cycle_id"),)
    review_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    cycle_id: Mapped[str] = mapped_column(FK("review_cycles.cycle_id"), index=True)
    employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(FK("managers.manager_id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    self_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    manager_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    manager_summary: Mapped[Optional[str]] = mapped_column(Text)
    goal_score_pct: Mapped[Optional[float]] = mapped_column(Float)
    goal_rating: Mapped[Optional[float]] = mapped_column(Float)
    competency_rating: Mapped[Optional[float]] = mapped_column(Float)
    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    overall_rating: Mapped[Optional[str]] = mapped_column(String(20))
    is_complete: Mapped[bool] = mapped_column(Boolean)
    missing_inputs: Mapped[Optional[str]] = mapped_column(Text)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    event_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    review_id: Mapped[str] = mapped_column(FK("reviews.review_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[Optional[str]] = mapped_column(String(20))
    field_name: Mapped[Optional[str]] = mapped_column(String(40))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(FK("employees.employee_id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    approved_by: Mapped[Optional[str]] = mapped_column(FK("employees.employee_id"))


class DevelopmentPlan(Base):
    __tablename__ = "development_plans"
    plan_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    employee_id: Mapped[str] = mapped_column(FK("employees.employee_id"), index=True)
    cycle_id: Mapped[str] = mapped_column(FK("review_cycles.cycle_id"))
    review_id: Mapped[str] = mapped_column(FK("reviews.review_id"), index=True)
    competency_id: Mapped[str] = mapped_column(FK("competencies.competency_id"))
    objective: Mapped[str] = mapped_column(String(200))
    training_cost: Mapped[float] = mapped_column(Float)
    requires_hr_approval: Mapped[bool] = mapped_column(Boolean)
    target_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), index=True)


class PlanApproval(Base):
    __tablename__ = "plan_approvals"
    approval_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    plan_id: Mapped[str] = mapped_column(FK("development_plans.plan_id"), index=True)
    approver_id: Mapped[str] = mapped_column(FK("employees.employee_id"))
    approver_role: Mapped[str] = mapped_column(String(20))
    decision: Mapped[str] = mapped_column(String(10))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    comment: Mapped[Optional[str]] = mapped_column(Text)


class DatasetInfo(Base):
    """Operational metadata about the loaded dataset (not part of the domain model)."""
    __tablename__ = "dataset_info"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


MODEL_BY_TABLE = {m.__tablename__: m for m in Base.__subclasses__()}

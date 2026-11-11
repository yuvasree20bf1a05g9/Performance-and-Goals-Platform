"""Review, feedback and development-plan use cases."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain import rules

from ..deps import Clock
from ..errors import Conflict, Forbidden, NotFound, RuleViolation
from ..models import (CheckIn, Competency, DevelopmentPlan, Employee, Feedback, Goal, Manager, PlanApproval, Review,
                      ReviewCycle, ReviewEvent)
from .common import bump_data_version, has_feedback_relationship, next_id


def recompute_review(db: Session, employee_id: str, cycle_id: str) -> Review | None:
    """Completeness + scores derived from goals, check-ins and feedback (same rules as generator)."""
    r = db.scalar(select(Review).where(Review.employee_id == employee_id, Review.cycle_id == cycle_id))
    if r is None:
        return None
    comps = [{"competency_id": c.competency_id, "applies_to": c.applies_to} for c in db.scalars(select(Competency))]
    required = rules.applicable_competencies(comps, db.get(Manager, employee_id) is not None)
    fb = db.scalars(select(Feedback).where(Feedback.subject_employee_id == employee_id,
                                           Feedback.cycle_id == cycle_id)).all()
    self_c = {f.competency_id for f in fb if f.feedback_type == "self" and f.giver_employee_id == employee_id}
    mgr = [f for f in fb if f.feedback_type == "manager" and f.giver_employee_id == r.reviewer_id]
    goals = db.scalars(select(Goal).where(Goal.employee_id == employee_id, Goal.cycle_id == cycle_id)).all()
    active = [g.goal_id for g in goals if g.status not in rules.INACTIVE_GOAL_STATUSES]
    with_ci = set(db.scalars(select(CheckIn.goal_id).where(CheckIn.goal_id.in_(active)))) if active else set()
    missing = rules.review_missing_inputs(required, self_c, {f.competency_id for f in mgr}, active, with_ci)
    r.is_complete = not missing
    r.missing_inputs = ";".join(missing) or None
    r.goal_score_pct = rules.goal_score_pct([(g.weight_pct, g.progress_pct, g.status) for g in goals])
    r.goal_rating = rules.goal_rating(r.goal_score_pct)
    r.competency_rating = rules.competency_rating([f.rating for f in mgr if f.competency_id in required])
    r.overall_score = rules.overall_score(r.goal_rating, r.competency_rating) if r.is_complete else None
    r.overall_rating = rules.rating_label(r.overall_score)
    db.flush()
    return r


def get_review(db: Session, review_id: str) -> Review:
    r = db.get(Review, review_id)
    if r is None:
        raise NotFound(f"review {review_id} not found")
    return r


def _event(db, review, actor_id, at, etype, frm=None, to=None, field=None, old=None, new=None, rationale=None,
           approved_by=None):
    db.add(ReviewEvent(event_id=next_id(db, ReviewEvent.event_id, "REVEV-", 7), review_id=review.review_id,
                       event_type=etype, from_status=frm, to_status=to, field_name=field, old_value=old,
                       new_value=new, actor_id=actor_id, occurred_at=at, rationale=rationale, approved_by=approved_by))
    db.flush()


def submit_feedback(db: Session, actor: Employee, clock: Clock, review_id: str, payload) -> Feedback:
    review = get_review(db, review_id)
    cycle = db.get(ReviewCycle, review.cycle_id)
    if cycle.status == "closed":
        raise Conflict(f"{cycle.cycle_id} is closed; feedback is locked")
    if review.status == "finalized":
        raise Conflict("review is finalized")
    comp = db.get(Competency, payload.competency_id)
    if comp is None:
        raise NotFound(f"competency {payload.competency_id} not found")
    if comp.applies_to == "managers" and db.get(Manager, review.employee_id) is None:
        raise RuleViolation(f"{comp.name} only applies to people managers")
    if not has_feedback_relationship(db, cycle, payload.feedback_type, actor.employee_id, review.employee_id, clock.today()):
        raise Forbidden(f"reviewer lacks relationship for {payload.feedback_type} feedback",
                        {"rule": "self=same person, manager=managed during cycle, peer=accepted nomination"})
    if payload.linked_goal_id:
        g = db.get(Goal, payload.linked_goal_id)
        if g is None or g.employee_id != review.employee_id or g.cycle_id != review.cycle_id:
            raise RuleViolation("linked goal must belong to the reviewed employee in this cycle")
    dup = db.scalar(select(Feedback).where(Feedback.cycle_id == review.cycle_id,
                                          Feedback.subject_employee_id == review.employee_id,
                                          Feedback.giver_employee_id == actor.employee_id,
                                          Feedback.feedback_type == payload.feedback_type,
                                          Feedback.competency_id == payload.competency_id))
    if dup:
        raise Conflict("feedback for this competency was already submitted", {"feedback_id": dup.feedback_id})
    fb = Feedback(feedback_id=next_id(db, Feedback.feedback_id, f"FB-{review.cycle_id[6:10]}-", 7),
                  cycle_id=review.cycle_id, subject_employee_id=review.employee_id,
                  giver_employee_id=actor.employee_id,       # always traceable: giver comes from the actor
                  feedback_type=payload.feedback_type, competency_id=payload.competency_id, rating=payload.rating,
                  comment=payload.comment, linked_goal_id=payload.linked_goal_id, source="in_app",
                  submitted_at=clock.now())
    db.add(fb)
    db.flush()
    recompute_review(db, review.employee_id, review.cycle_id)
    db.commit()
    bump_data_version()
    return fb


def transition_review(db: Session, actor: Employee, clock: Clock, review_id: str, to_status: str) -> Review:
    review = get_review(db, review_id)
    cycle = db.get(ReviewCycle, review.cycle_id)
    if cycle.status == "closed":
        raise Conflict(f"{cycle.cycle_id} is closed; reviews are locked")
    if not rules.can_transition(rules.REVIEW_TRANSITIONS, review.status, to_status):
        raise Conflict(f"cannot move review from {review.status} to {to_status}",
                       {"allowed": sorted(rules.REVIEW_TRANSITIONS[review.status])})
    if to_status == "self_submitted" and actor.employee_id != review.employee_id:
        raise Forbidden("only the employee can submit the self assessment")
    if to_status in ("manager_submitted", "finalized") and actor.employee_id != review.reviewer_id:
        raise Forbidden("only the assigned reviewer can submit or finalize")
    recompute_review(db, review.employee_id, review.cycle_id)
    missing = (review.missing_inputs or "").split(";")
    if to_status == "self_submitted" and "self_feedback" in missing:
        raise RuleViolation("self assessment incomplete", {"missing_inputs": missing})
    if to_status == "manager_submitted" and "manager_feedback" in missing:
        raise RuleViolation("manager assessment incomplete", {"missing_inputs": missing})
    if to_status == "finalized" and not review.is_complete:
        raise RuleViolation("review cannot be finalized until all required inputs exist", {"missing_inputs": missing})
    now = clock.now()
    _event(db, review, actor.employee_id, now, "status_change", review.status, to_status)
    review.status = to_status
    if to_status == "self_submitted":
        review.self_submitted_at = now
    elif to_status == "manager_submitted":
        review.manager_submitted_at = now
    else:
        review.finalized_at = now
    db.commit()
    bump_data_version()
    return review


def decide_plan(db: Session, actor: Employee, clock: Clock, plan_id: str, decision: str, comment: str | None):
    plan = db.get(DevelopmentPlan, plan_id)
    if plan is None:
        raise NotFound(f"plan {plan_id} not found")
    pending = db.scalars(select(PlanApproval).where(PlanApproval.plan_id == plan_id,
                                                    PlanApproval.decision == "pending")).all()
    mine = [a for a in pending if a.approver_id == actor.employee_id]
    if not mine:
        raise Forbidden("you have no pending approval on this plan",
                        {"pending_approvers": [a.approver_id for a in pending]})
    now = clock.now()
    a = mine[0]
    a.decision, a.decided_at, a.comment = decision, now, comment
    db.flush()
    if a.approver_role == "manager" and decision == "approved" and plan.requires_hr_approval:
        hr = db.scalar(select(Employee).where(Employee.role == "hr_partner", Employee.employment_status == "active")
                       .order_by(Employee.employee_id))
        db.add(PlanApproval(approval_id=next_id(db, PlanApproval.approval_id, "DPA-", 6), plan_id=plan_id,
                            approver_id=hr.employee_id, approver_role="hr_partner", decision="pending"))
        db.flush()
    approvals = db.scalars(select(PlanApproval).where(PlanApproval.plan_id == plan_id)).all()
    plan.status = rules.plan_status([{"decision": x.decision, "approver_role": x.approver_role} for x in approvals],
                                    plan.requires_hr_approval, plan.completed_at)
    db.commit()
    bump_data_version()
    return plan

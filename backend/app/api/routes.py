"""HTTP layer: thin controllers -> services. Reads are open; writes need X-Actor-Id."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from domain.schema import DEPARTMENTS

from ..deps import Clock, get_actor, get_clock, get_db
from ..errors import NotFound
from ..models import (CheckIn, Competency, DatasetInfo, DevelopmentPlan, Employee, EvidenceLink, Feedback, Goal,
                      GoalVersion, KRUpdate, ManagerAssignment, PlanApproval, Review, ReviewCycle, ReviewEvent)
from ..schemas import (CheckInCreate, FeedbackCreate, GoalCreate, GoalTransition, GoalUpdate, PlanDecision,
                       ReviewTransition)
from ..services import analytics, goals as goal_svc, reviews as review_svc
from ..services.common import employee_brief, to_dict

router = APIRouter(prefix="/api")


def page(stmt, db: Session, page_no: int, size: int):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return total, db.execute(stmt.limit(size).offset((page_no - 1) * size)).all()


# ------------------------------------------------------------------ meta
@router.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "employees": db.scalar(select(func.count()).select_from(Employee))}


@router.get("/meta", tags=["meta"])
def meta(db: Session = Depends(get_db)):
    return {"dataset": {r.key: r.value for r in db.scalars(select(DatasetInfo))},
            "cycles": [to_dict(c) for c in db.scalars(select(ReviewCycle).order_by(ReviewCycle.start_date))],
            "departments": DEPARTMENTS,
            "competencies": [to_dict(c) for c in db.scalars(select(Competency))],
            "demo_actors": _demo_actors(db)}


def _demo_actors(db: Session) -> list[dict]:
    """A few handy identities for trying permission rules from the UI."""
    out = []
    r = db.scalar(select(Review).join(Goal, (Goal.employee_id == Review.employee_id) & (Goal.cycle_id == Review.cycle_id))
                  .where(Review.cycle_id == "CYCLE-2026-H2", Goal.status == "in_progress").order_by(Review.review_id))
    if r:
        out.append({**employee_brief(db.get(Employee, r.employee_id)), "label": "Employee (has active goals)"})
        out.append({**employee_brief(db.get(Employee, r.reviewer_id)), "label": "Their manager"})
    for role, label in (("hr_partner", "HR partner"), ("admin", "System admin")):
        e = db.scalar(select(Employee).where(Employee.role == role, Employee.employment_status == "active")
                      .order_by(Employee.employee_id))
        if e:
            out.append({**employee_brief(e), "label": label})
    return out


# ------------------------------------------------------------------ employees
@router.get("/employees", tags=["employees"])
def list_employees(q: Optional[str] = None, department: Optional[str] = None, role: Optional[str] = None,
                   status: Optional[str] = None, page_no: int = Query(1, ge=1, alias="page"),
                   size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(Employee).order_by(Employee.employee_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Employee.first_name + " " + Employee.last_name).like(like),
                              func.lower(Employee.employee_id).like(like), func.lower(Employee.email).like(like)))
    if department:
        stmt = stmt.where(Employee.department == department)
    if role:
        stmt = stmt.where(Employee.role == role)
    if status:
        stmt = stmt.where(Employee.employment_status == status)
    total, rows = page(stmt, db, page_no, size)
    return {"total": total, "page": page_no, "size": size,
            "items": [{**to_dict(e), "name": e.full_name} for (e,) in rows]}


@router.get("/employees/{employee_id}", tags=["employees"])
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    e = db.get(Employee, employee_id)
    if e is None:
        raise NotFound(f"employee {employee_id} not found")
    chain, cur, seen = [], e.current_manager_id, set()
    while cur and cur not in seen:
        seen.add(cur)
        m = db.get(Employee, cur)
        chain.append(employee_brief(m))
        cur = m.current_manager_id
    reports = db.scalars(select(Employee).where(Employee.current_manager_id == employee_id)
                         .order_by(Employee.employee_id)).all()
    assignments = db.scalars(select(ManagerAssignment).where(ManagerAssignment.employee_id == employee_id)
                             .order_by(ManagerAssignment.effective_from)).all()
    goals = db.scalars(select(Goal).where(Goal.employee_id == employee_id).order_by(Goal.cycle_id, Goal.goal_id)).all()
    reviews = db.scalars(select(Review).where(Review.employee_id == employee_id).order_by(Review.cycle_id)).all()
    plans = db.scalars(select(DevelopmentPlan).where(DevelopmentPlan.employee_id == employee_id)).all()
    return {**to_dict(e), "name": e.full_name, "manager_chain": chain,
            "direct_reports": [employee_brief(r) for r in reports],
            "assignments": [{**to_dict(a), "manager": employee_brief(db.get(Employee, a.manager_id))} for a in assignments],
            "goals": [to_dict(g) for g in goals], "reviews": [to_dict(r) for r in reviews],
            "development_plans": [to_dict(p) for p in plans]}


# ------------------------------------------------------------------ goals
@router.get("/goals", tags=["goals"])
def list_goals(cycle_id: Optional[str] = None, status: Optional[str] = None, employee_id: Optional[str] = None,
               department: Optional[str] = None, q: Optional[str] = None,
               page_no: int = Query(1, ge=1, alias="page"), size: int = Query(25, ge=1, le=200),
               db: Session = Depends(get_db)):
    stmt = select(Goal, Employee).join(Employee, Employee.employee_id == Goal.employee_id).order_by(Goal.goal_id)
    for col, val in ((Goal.cycle_id, cycle_id), (Goal.status, status), (Goal.employee_id, employee_id),
                     (Employee.department, department)):
        if val:
            stmt = stmt.where(col == val)
    if q:
        stmt = stmt.where(or_(func.lower(Goal.title).like(f"%{q.lower()}%"), Goal.goal_id.like(f"%{q.upper()}%")))
    total, rows = page(stmt, db, page_no, size)
    return {"total": total, "page": page_no, "size": size,
            "items": [{**to_dict(g), "owner_name": e.full_name, "department": e.department} for g, e in rows]}


@router.get("/goals/{goal_id}", tags=["goals"])
def get_goal(goal_id: str, db: Session = Depends(get_db)):
    g = goal_svc.get_goal(db, goal_id)
    checkins = db.scalars(select(CheckIn).where(CheckIn.goal_id == goal_id)
                          .order_by(CheckIn.checkin_date, CheckIn.sequence_no)).all()
    ids = [c.checkin_id for c in checkins]
    ups = db.scalars(select(KRUpdate).where(KRUpdate.checkin_id.in_(ids))).all() if ids else []
    evs = db.scalars(select(EvidenceLink).where(EvidenceLink.checkin_id.in_(ids))).all() if ids else []
    versions = db.scalars(select(GoalVersion).where(GoalVersion.goal_id == goal_id).order_by(GoalVersion.version_no)).all()
    by_ci = lambda rows, cid: [to_dict(x) for x in rows if x.checkin_id == cid]  # noqa: E731
    return {**to_dict(g), "owner": employee_brief(db.get(Employee, g.employee_id)),
            "approver": employee_brief(db.get(Employee, g.approved_by)) if g.approved_by else None,
            "cycle": to_dict(db.get(ReviewCycle, g.cycle_id)),
            "key_results": [to_dict(k) for k in g.key_results],
            "checkins": [{**to_dict(c), "submitted_by_name": db.get(Employee, c.submitted_by).full_name,
                          "updates": by_ci(ups, c.checkin_id), "evidence": by_ci(evs, c.checkin_id)} for c in checkins],
            "versions": [to_dict(v) for v in versions],
            "flags": analytics.quality_cache.for_entities(db, {goal_id, *ids, *[u.update_id for u in ups],
                                                               *[v.version_id for v in versions]})}


@router.post("/goals", status_code=201, tags=["goals"])
def create_goal(body: GoalCreate, db: Session = Depends(get_db), actor: Employee = Depends(get_actor),
                clock: Clock = Depends(get_clock)):
    return to_dict(goal_svc.create_goal(db, actor, clock, body))


@router.patch("/goals/{goal_id}", tags=["goals"])
def update_goal(goal_id: str, body: GoalUpdate, db: Session = Depends(get_db), actor: Employee = Depends(get_actor),
                clock: Clock = Depends(get_clock)):
    return to_dict(goal_svc.update_goal(db, actor, clock, goal_id, body))


@router.post("/goals/{goal_id}/transition", tags=["goals"])
def transition_goal(goal_id: str, body: GoalTransition, db: Session = Depends(get_db),
                    actor: Employee = Depends(get_actor), clock: Clock = Depends(get_clock)):
    return to_dict(goal_svc.transition_goal(db, actor, clock, goal_id, body.to_status, body.rationale))


@router.post("/goals/{goal_id}/checkins", status_code=201, tags=["goals"])
def create_checkin(goal_id: str, body: CheckInCreate, db: Session = Depends(get_db),
                   actor: Employee = Depends(get_actor), clock: Clock = Depends(get_clock)):
    ci = goal_svc.submit_checkin(db, actor, clock, goal_id, body)
    g = db.get(Goal, goal_id)
    return {"checkin": to_dict(ci), "goal_progress_pct": g.progress_pct,
            "key_results": [to_dict(k) for k in g.key_results]}


# ------------------------------------------------------------------ reviews
@router.get("/reviews", tags=["reviews"])
def list_reviews(cycle_id: Optional[str] = None, status: Optional[str] = None, complete: Optional[bool] = None,
                 department: Optional[str] = None, rating: Optional[str] = None,
                 page_no: int = Query(1, ge=1, alias="page"), size: int = Query(25, ge=1, le=200),
                 db: Session = Depends(get_db)):
    stmt = select(Review, Employee).join(Employee, Employee.employee_id == Review.employee_id).order_by(Review.review_id)
    for col, val in ((Review.cycle_id, cycle_id), (Review.status, status), (Employee.department, department),
                     (Review.overall_rating, rating)):
        if val:
            stmt = stmt.where(col == val)
    if complete is not None:
        stmt = stmt.where(Review.is_complete == complete)
    total, rows = page(stmt, db, page_no, size)
    return {"total": total, "page": page_no, "size": size,
            "items": [{**to_dict(r), "employee_name": e.full_name, "department": e.department} for r, e in rows]}


@router.get("/reviews/{review_id}", tags=["reviews"])
def get_review(review_id: str, db: Session = Depends(get_db)):
    r = review_svc.get_review(db, review_id)
    comps = {c.competency_id: c.name for c in db.scalars(select(Competency))}
    fb = db.scalars(select(Feedback).where(Feedback.subject_employee_id == r.employee_id,
                                           Feedback.cycle_id == r.cycle_id)
                    .order_by(Feedback.feedback_type, Feedback.competency_id)).all()
    goals = db.scalars(select(Goal).where(Goal.employee_id == r.employee_id, Goal.cycle_id == r.cycle_id)).all()
    events = db.scalars(select(ReviewEvent).where(ReviewEvent.review_id == review_id)
                        .order_by(ReviewEvent.occurred_at)).all()
    plans = db.scalars(select(DevelopmentPlan).where(DevelopmentPlan.review_id == review_id)).all()
    approvals = db.scalars(select(PlanApproval).where(PlanApproval.plan_id.in_([p.plan_id for p in plans]))).all()
    conflicts = [c[2] for c in analytics.quality_cache.conflicts(db) if c[0] == r.cycle_id and c[1] == r.employee_id]
    return {**to_dict(r), "employee": employee_brief(db.get(Employee, r.employee_id)),
            "reviewer": employee_brief(db.get(Employee, r.reviewer_id)),
            "cycle": to_dict(db.get(ReviewCycle, r.cycle_id)),
            "feedback": [{**to_dict(f), "competency": comps[f.competency_id],
                          "giver": employee_brief(db.get(Employee, f.giver_employee_id)) if f.giver_employee_id else None}
                         for f in fb],
            "goals": [to_dict(g) for g in goals],
            "events": [to_dict(e) for e in events],
            "development_plans": [{**to_dict(p), "approvals": [to_dict(a) for a in approvals if a.plan_id == p.plan_id]}
                                  for p in plans],
            "conflicting_competencies": conflicts,
            "flags": analytics.quality_cache.for_entities(db, {review_id, *[f.feedback_id for f in fb],
                                                               *[e.event_id for e in events]})}


@router.post("/reviews/{review_id}/feedback", status_code=201, tags=["reviews"])
def create_feedback(review_id: str, body: FeedbackCreate, db: Session = Depends(get_db),
                    actor: Employee = Depends(get_actor), clock: Clock = Depends(get_clock)):
    fb = review_svc.submit_feedback(db, actor, clock, review_id, body)
    return {"feedback": to_dict(fb), "review": to_dict(db.get(Review, review_id))}


@router.post("/reviews/{review_id}/transition", tags=["reviews"])
def transition_review(review_id: str, body: ReviewTransition, db: Session = Depends(get_db),
                      actor: Employee = Depends(get_actor), clock: Clock = Depends(get_clock)):
    return to_dict(review_svc.transition_review(db, actor, clock, review_id, body.to_status))


# ------------------------------------------------------------------ development plans
@router.get("/development-plans", tags=["development plans"])
def list_plans(cycle_id: Optional[str] = None, status: Optional[str] = None,
               page_no: int = Query(1, ge=1, alias="page"), size: int = Query(25, ge=1, le=200),
               db: Session = Depends(get_db)):
    stmt = select(DevelopmentPlan, Employee).join(Employee, Employee.employee_id == DevelopmentPlan.employee_id) \
        .order_by(DevelopmentPlan.plan_id)
    if cycle_id:
        stmt = stmt.where(DevelopmentPlan.cycle_id == cycle_id)
    if status:
        stmt = stmt.where(DevelopmentPlan.status == status)
    total, rows = page(stmt, db, page_no, size)
    ids = [p.plan_id for p, _ in rows]
    approvals = db.scalars(select(PlanApproval).where(PlanApproval.plan_id.in_(ids))).all() if ids else []
    return {"total": total, "page": page_no, "size": size,
            "items": [{**to_dict(p), "employee_name": e.full_name,
                       "approvals": [to_dict(a) for a in approvals if a.plan_id == p.plan_id]} for p, e in rows]}


@router.post("/development-plans/{plan_id}/decisions", tags=["development plans"])
def decide_plan(plan_id: str, body: PlanDecision, db: Session = Depends(get_db),
                actor: Employee = Depends(get_actor), clock: Clock = Depends(get_clock)):
    return to_dict(review_svc.decide_plan(db, actor, clock, plan_id, body.decision, body.comment))


# ------------------------------------------------------------------ metrics & quality
@router.get("/metrics/overview", tags=["metrics"])
def metrics_overview(cycle_id: str = "CYCLE-2026-H1", db: Session = Depends(get_db), clock: Clock = Depends(get_clock)):
    return analytics.overview(db, clock, cycle_id)


@router.get("/metrics/departments", tags=["metrics"])
def metrics_departments(cycle_id: str = "CYCLE-2026-H1", db: Session = Depends(get_db)):
    return analytics.departments(db, cycle_id)


@router.get("/quality/summary", tags=["data quality"])
def quality_summary(db: Session = Depends(get_db)):
    return analytics.quality_summary(db)


@router.get("/quality/findings", tags=["data quality"])
def quality_findings(issue_type: Optional[str] = None, page_no: int = Query(1, ge=1, alias="page"),
                     size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db)):
    f = analytics.quality_cache.findings(db)
    if issue_type:
        f = [x for x in f if x["issue_type"] == issue_type]
    return {"total": len(f), "page": page_no, "size": size, "items": f[(page_no - 1) * size: page_no * size]}


@router.get("/quality/evaluation", tags=["data quality"])
def quality_evaluation(db: Session = Depends(get_db)):
    return analytics.evaluation(db)

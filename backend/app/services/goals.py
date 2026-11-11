"""Goal, key-result and check-in use cases.

Rules enforced here (acceptance criteria):
* progress always derives from key results (never accepted from the client);
* only the goal owner or the owner's current manager may check in;
* progress above 100% requires a rationale;
* every change is versioned in goal_versions (history is never overwritten);
* closed cycles are locked - only HR/admin may correct, with rationale, as an audited event.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain import rules

from ..deps import Clock
from ..errors import Conflict, Forbidden, NotFound, RuleViolation
from ..models import (CheckIn, EvidenceLink, Employee, Goal, GoalVersion, KeyResult, KRUpdate, ReviewCycle)
from .common import bump_data_version, is_privileged, manager_at, next_id
from .reviews import recompute_review


def get_goal(db: Session, goal_id: str) -> Goal:
    g = db.get(Goal, goal_id)
    if g is None:
        raise NotFound(f"goal {goal_id} not found")
    return g


def _version(db: Session, goal: Goal, actor_id: str, at: datetime, change_type: str, field: str | None,
             old, new, kr_id: str | None = None, rationale: str | None = None, approved_by: str | None = None):
    goal.current_version += 1
    db.add(GoalVersion(version_id=next_id(db, GoalVersion.version_id, "GV-", 7), goal_id=goal.goal_id, kr_id=kr_id,
                       version_no=goal.current_version, change_type=change_type, field_name=field,
                       old_value=None if old is None else str(old), new_value=None if new is None else str(new),
                       changed_by=actor_id, changed_at=at, rationale=rationale, approved_by=approved_by))
    db.flush()


def _target_history(db: Session, kr_id: str) -> list[tuple[datetime, float, float]]:
    rows = db.scalars(select(GoalVersion).where(GoalVersion.kr_id == kr_id,
                                                GoalVersion.field_name == "target_value")).all()
    return sorted((v.changed_at, float(v.old_value), float(v.new_value)) for v in rows)


def recompute_goal(db: Session, goal: Goal) -> None:
    """Recalculate KR + goal progress from source updates (same rules as the generator)."""
    rows = db.execute(select(KRUpdate, CheckIn).join(CheckIn, KRUpdate.checkin_id == CheckIn.checkin_id)
                      .where(CheckIn.goal_id == goal.goal_id)).all()
    by_kr = defaultdict(list)
    for u, c in rows:
        by_kr[u.kr_id].append(((c.checkin_date, c.sequence_no, u.update_id), u))
    for kr in goal.key_results:
        ups = sorted(by_kr.get(kr.kr_id, []), key=lambda x: x[0])
        latest = ups[-1][1] if ups else None
        kr.current_value = latest.reported_value if latest else kr.start_value
        kr.raw_progress_pct = rules.kr_raw_progress(kr.start_value, kr.target_value, kr.current_value)
        kr.scoring_progress_pct = rules.kr_scoring_progress(kr.raw_progress_pct,
                                                            bool(latest and latest.over_scale_rationale))
    goal.progress_pct = rules.goal_progress([(k.weight_pct, k.scoring_progress_pct) for k in goal.key_results])
    db.flush()
    recompute_review(db, goal.employee_id, goal.cycle_id)


def _require_open_cycle(cycle: ReviewCycle):
    if cycle.status == "closed":
        raise Conflict(f"{cycle.cycle_id} is closed; changes are locked",
                       {"hint": "HR partners/admins can submit an approved post-close correction with a rationale"})
    if cycle.status == "planned":
        raise Conflict(f"{cycle.cycle_id} has not started yet")


def _can_manage(db: Session, actor: Employee, owner_id: str, clock: Clock) -> bool:
    return actor.employee_id == manager_at(db, owner_id, clock.today()) or is_privileged(actor)


# --------------------------------------------------------------------------- create
def create_goal(db: Session, actor: Employee, clock: Clock, payload) -> Goal:
    cycle = db.get(ReviewCycle, payload.cycle_id)
    if cycle is None:
        raise NotFound(f"cycle {payload.cycle_id} not found")
    _require_open_cycle(cycle)
    owner = db.get(Employee, payload.employee_id)
    if owner is None:
        raise NotFound(f"employee {payload.employee_id} not found")
    if actor.employee_id != owner.employee_id and not _can_manage(db, actor, owner.employee_id, clock):
        raise Forbidden("only the employee, their manager or HR can create goals for them")
    existing = db.scalars(select(Goal).where(Goal.employee_id == owner.employee_id, Goal.cycle_id == cycle.cycle_id,
                                             Goal.status != "cancelled")).all()
    used = sum(g.weight_pct for g in existing)
    if used + payload.weight_pct > 100:
        raise RuleViolation("goal weights for a cycle cannot exceed 100%",
                            {"already_allocated": used, "requested": payload.weight_pct})
    if sum(k.weight_pct for k in payload.key_results) != 100:
        raise RuleViolation("key-result weights must sum to 100")
    seq = len(db.scalars(select(Goal.goal_id).where(Goal.goal_id.like(f"GOAL-{owner.employee_id}-%"))).all()) + 1
    now = clock.now()
    goal = Goal(goal_id=f"GOAL-{owner.employee_id}-{seq:03d}", employee_id=owner.employee_id, cycle_id=cycle.cycle_id,
                title=payload.title, category=payload.category, weight_pct=payload.weight_pct, status="draft",
                created_at=now, current_version=0, progress_pct=0.0)
    db.add(goal)
    db.flush()
    for i, k in enumerate(payload.key_results, start=1):
        db.add(KeyResult(kr_id=f"KR-{goal.goal_id}-{i:02d}", goal_id=goal.goal_id, description=k.description,
                         metric_type=k.metric_type, unit=k.unit, direction="increase" if k.target_value >= k.start_value
                         else "decrease", start_value=k.start_value, target_value=k.target_value,
                         weight_pct=k.weight_pct, current_value=k.start_value, raw_progress_pct=0.0,
                         scoring_progress_pct=0.0))
    _version(db, goal, actor.employee_id, now, "created", "title", None, goal.title)
    db.flush()
    db.refresh(goal)
    recompute_goal(db, goal)
    db.commit()
    bump_data_version()
    return goal


# --------------------------------------------------------------------------- lifecycle
def transition_goal(db: Session, actor: Employee, clock: Clock, goal_id: str, to_status: str, rationale: str | None):
    goal = get_goal(db, goal_id)
    _require_open_cycle(db.get(ReviewCycle, goal.cycle_id))
    if not rules.can_transition(rules.GOAL_TRANSITIONS, goal.status, to_status):
        raise Conflict(f"cannot move goal from {goal.status} to {to_status}",
                       {"allowed": sorted(rules.GOAL_TRANSITIONS[goal.status])})
    is_owner = actor.employee_id == goal.employee_id
    is_mgr = _can_manage(db, actor, goal.employee_id, clock)
    if to_status == "in_progress" and not is_mgr:
        raise Forbidden("only the owner's manager can approve a goal")
    if to_status in ("pending_approval", "draft") and not (is_owner or is_mgr):
        raise Forbidden("only the owner or manager can submit/return a goal")
    if to_status in ("cancelled", "closed") and not is_mgr:
        raise Forbidden("only the manager can cancel or close a goal")
    if to_status == "in_progress" and sum(k.weight_pct for k in goal.key_results) != 100:
        raise RuleViolation("key-result weights must sum to 100 before approval")
    now = clock.now()
    old = goal.status
    goal.status = to_status
    if to_status == "in_progress":
        goal.approved_by, goal.approved_at = actor.employee_id, now
    _version(db, goal, actor.employee_id, now, "status_changed", "status", old, to_status, rationale=rationale)
    recompute_goal(db, goal)
    db.commit()
    bump_data_version()
    return goal


# --------------------------------------------------------------------------- edits
def update_goal(db: Session, actor: Employee, clock: Clock, goal_id: str, payload) -> Goal:
    goal = get_goal(db, goal_id)
    cycle = db.get(ReviewCycle, goal.cycle_id)
    now = clock.now()
    post_close = cycle.status == "closed"
    if post_close:
        if not is_privileged(actor):
            raise Conflict(f"{cycle.cycle_id} is closed; only HR partners/admins can make an approved correction")
        if not payload.rationale:
            raise RuleViolation("post-close corrections require a rationale")
    elif actor.employee_id != goal.employee_id and not _can_manage(db, actor, goal.employee_id, clock):
        raise Forbidden("only the owner, their manager or HR can edit this goal")
    if goal.status in ("closed", "cancelled") and not post_close:
        raise Conflict(f"goal is {goal.status}")
    approved_by = actor.employee_id if (post_close or _can_manage(db, actor, goal.employee_id, clock)) else None
    change = "post_close_correction" if post_close else None
    changed = False
    if payload.title and payload.title != goal.title:
        _version(db, goal, actor.employee_id, now, change or "title_changed", "title", goal.title, payload.title,
                 rationale=payload.rationale, approved_by=approved_by)
        goal.title, changed = payload.title, True
    for kt in payload.kr_targets or []:
        kr = db.get(KeyResult, kt.kr_id)
        if kr is None or kr.goal_id != goal.goal_id:
            raise NotFound(f"key result {kt.kr_id} not on {goal.goal_id}")
        if kt.target_value == kr.target_value:
            continue
        if not payload.rationale:
            raise RuleViolation("changing a key-result target requires a rationale")
        if goal.status == "in_progress" and approved_by is None:
            raise Forbidden("target changes on approved goals must be made or approved by the manager")
        _version(db, goal, actor.employee_id, now, change or "target_changed", "target_value",
                 f"{kr.target_value:.2f}", f"{kt.target_value:.2f}", kr_id=kr.kr_id,
                 rationale=payload.rationale, approved_by=approved_by)
        kr.target_value, changed = kt.target_value, True
    if not changed:
        raise RuleViolation("no changes supplied")
    recompute_goal(db, goal)
    db.commit()
    bump_data_version()
    return goal


# --------------------------------------------------------------------------- check-ins
def submit_checkin(db: Session, actor: Employee, clock: Clock, goal_id: str, payload) -> CheckIn:
    goal = get_goal(db, goal_id)
    cycle = db.get(ReviewCycle, goal.cycle_id)
    _require_open_cycle(cycle)
    today = clock.today()
    owner_mgr = manager_at(db, goal.employee_id, today)
    if actor.employee_id not in (goal.employee_id, owner_mgr):
        raise Forbidden("goal owner mismatch: only the goal owner or their current manager can check in",
                        {"goal_owner": goal.employee_id, "owner_manager": owner_mgr, "actor": actor.employee_id})
    if goal.status != "in_progress":
        raise Conflict(f"check-ins are only accepted on approved goals (status is {goal.status})")
    krs = {k.kr_id: k for k in goal.key_results}
    if {u.kr_id for u in payload.updates} != set(krs):
        raise RuleViolation("a check-in must report every key result of the goal", {"expected": sorted(krs)})
    problems = []
    for u in payload.updates:
        kr = krs[u.kr_id]
        tgt = rules.target_at(kr.target_value, _target_history(db, kr.kr_id), datetime.combine(today, time.max))
        raw = rules.kr_raw_progress(kr.start_value, tgt, u.reported_value)
        if rules.is_over_scale(raw) and not (u.over_scale_rationale and u.over_scale_rationale.strip()):
            problems.append({"kr_id": u.kr_id, "raw_progress_pct": raw})
    if problems:
        raise RuleViolation("progress exceeds 100% of target; an over_scale_rationale is required", problems)

    seq = (db.scalar(select(CheckIn.sequence_no).where(CheckIn.goal_id == goal_id)
                     .order_by(CheckIn.sequence_no.desc()).limit(1)) or 0) + 1
    now = clock.now()
    ci = CheckIn(checkin_id=next_id(db, CheckIn.checkin_id, "CHK-", 7), goal_id=goal_id, cycle_id=goal.cycle_id,
                 submitted_by=actor.employee_id, checkin_date=today, sequence_no=seq,
                 confidence=payload.confidence, note=payload.note, goal_progress_pct=0.0)
    db.add(ci)
    db.flush()
    pairs = []
    for u in payload.updates:
        kr = krs[u.kr_id]
        tgt = rules.target_at(kr.target_value, _target_history(db, kr.kr_id), datetime.combine(today, time.max))
        raw = rules.kr_raw_progress(kr.start_value, tgt, u.reported_value)
        db.add(KRUpdate(update_id=next_id(db, KRUpdate.update_id, "KRU-", 7), checkin_id=ci.checkin_id, kr_id=u.kr_id,
                        reported_value=u.reported_value, raw_progress_pct=raw,
                        over_scale_rationale=u.over_scale_rationale if rules.is_over_scale(raw) else None))
        db.flush()
        pairs.append((kr.weight_pct, rules.kr_scoring_progress(raw, rules.is_over_scale(raw))))
    for ev in payload.evidence or []:
        db.add(EvidenceLink(evidence_id=next_id(db, EvidenceLink.evidence_id, "EVD-", 7), checkin_id=ci.checkin_id,
                            kr_id=ev.kr_id, evidence_type=ev.evidence_type, uri=ev.uri,
                            added_by=actor.employee_id, added_at=now))
        db.flush()
    ci.goal_progress_pct = rules.goal_progress(pairs)
    recompute_goal(db, goal)
    db.commit()
    bump_data_version()
    return ci

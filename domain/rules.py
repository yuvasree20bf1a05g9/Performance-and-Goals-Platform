"""Pure business rules shared by the generator, the validator and the API.

Keeping these as small, side-effect-free functions means the same rule is
used to *generate* derived values, to *validate* them and to *recompute* them
when the API receives a write - one implementation, three consumers.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Iterable, Optional, Sequence

# ---- Progress ----------------------------------------------------------------
SCORING_CAP_DEFAULT = 100.0          # progress counted for scoring without rationale
SCORING_CAP_WITH_RATIONALE = 120.0   # stretch credit when over-achievement is justified
INACTIVE_GOAL_STATUSES = {"draft", "pending_approval", "cancelled"}


def r2(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(float(x) + 0.0, 2)


def kr_raw_progress(start: float, target: float, value: float) -> float:
    """Linear progress from start to target; works for increase and decrease KRs."""
    if target == start:
        return 100.0 if value == target else 0.0
    return r2((value - start) / (target - start) * 100.0)


def kr_scoring_progress(raw: float, has_rationale: bool) -> float:
    cap = SCORING_CAP_WITH_RATIONALE if has_rationale else SCORING_CAP_DEFAULT
    return r2(max(0.0, min(raw, cap)))


def is_over_scale(raw: float) -> bool:
    return raw > 100.0


def weighted_average(pairs: Iterable[tuple[float, float]]) -> Optional[float]:
    # math.fsum is exactly rounded, so results are identical on every Python version
    # (the built-in sum() changed float precision in 3.12, which flips half-cent roundings)
    pairs = list(pairs)
    total_w = math.fsum(w for w, _ in pairs)
    if not pairs or total_w == 0:
        return None
    return r2(math.fsum(w * v for w, v in pairs) / total_w)


def goal_progress(kr_pairs: Sequence[tuple[int, float]]) -> float:
    """kr_pairs = [(kr_weight_pct, kr_scoring_progress)]"""
    return weighted_average(kr_pairs) or 0.0


def goal_score_pct(goals: Sequence[tuple[int, float, str]]) -> Optional[float]:
    """goals = [(weight_pct, progress_pct, status)]; inactive goals are excluded and
    the remaining weights are re-normalised."""
    return weighted_average((w, p) for w, p, s in goals if s not in INACTIVE_GOAL_STATUSES)


def target_at(current_target: float, history: Sequence[tuple[datetime, float, float]], when: datetime) -> float:
    """Target effective at ``when``. history = sorted [(changed_at, old, new)] of target changes.
    Progress is always measured against the target that was in force at that moment, so a
    later re-baseline never rewrites the meaning of earlier check-ins."""
    if not history:
        return current_target
    value = history[0][1]
    for changed_at, _old, new in history:
        if changed_at <= when:
            value = new
        else:
            break
    return value


# ---- Ratings -----------------------------------------------------------------
GOAL_WEIGHT_IN_OVERALL = 0.6
COMPETENCY_WEIGHT_IN_OVERALL = 0.4
RATING_BANDS = [(4.5, "Exceptional"), (3.75, "Exceeds"), (2.75, "Meets"), (2.0, "Partially Meets")]


def goal_rating(score_pct: Optional[float]) -> Optional[float]:
    """0% -> 1.0, 100%+ -> 5.0"""
    if score_pct is None:
        return None
    return r2(1 + 4 * min(max(score_pct, 0.0), 100.0) / 100.0)


def competency_rating(manager_ratings: Sequence[int]) -> Optional[float]:
    if not manager_ratings:
        return None
    return r2(math.fsum(manager_ratings) / len(manager_ratings))


def overall_score(g_rating: Optional[float], c_rating: Optional[float]) -> Optional[float]:
    if g_rating is None or c_rating is None:
        return None
    return r2(GOAL_WEIGHT_IN_OVERALL * g_rating + COMPETENCY_WEIGHT_IN_OVERALL * c_rating)


def rating_label(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    for threshold, label in RATING_BANDS:
        if score >= threshold:
            return label
    return "Below"


# ---- Review completeness -----------------------------------------------------
def applicable_competencies(competencies: Sequence[dict], is_manager: bool) -> list[str]:
    return sorted(c["competency_id"] for c in competencies
                  if c["applies_to"] == "all" or (is_manager and c["applies_to"] == "managers"))


def review_missing_inputs(required_comps: Sequence[str], self_comps: set, manager_comps: set,
                          active_goal_ids: Sequence[str], goals_with_checkins: set) -> list[str]:
    """Completion metrics reflect *required inputs*: full self assessment, full manager
    assessment, and at least one check-in on every active goal."""
    missing = []
    if not set(required_comps) <= self_comps:
        missing.append("self_feedback")
    if not set(required_comps) <= manager_comps:
        missing.append("manager_feedback")
    if not active_goal_ids:
        missing.append("active_goal")
    for gid in sorted(active_goal_ids):
        if gid not in goals_with_checkins:
            missing.append(f"checkin:{gid}")
    return missing


# ---- Lifecycles --------------------------------------------------------------
REVIEW_TRANSITIONS = {
    "not_started": {"self_submitted"},
    "self_submitted": {"manager_submitted"},
    "manager_submitted": {"finalized"},
    "finalized": set(),
}
GOAL_TRANSITIONS = {
    "draft": {"pending_approval", "cancelled"},
    "pending_approval": {"in_progress", "draft", "cancelled"},
    "in_progress": {"closed", "cancelled"},
    "closed": set(),
    "cancelled": set(),
}


def can_transition(transitions: dict, current: str, new: str) -> bool:
    return new in transitions.get(current, set())


# ---- Development plans -------------------------------------------------------
HR_APPROVAL_COST_THRESHOLD = 1000.0
DEV_PLAN_TRIGGER_RATING = 2        # ratings at or below this are "development needed"


def plan_mandatory(manager_ratings: Sequence[int]) -> bool:
    """Mandatory development plan: any competency rated 1, or two or more rated <= 2."""
    low = [r for r in manager_ratings if r <= DEV_PLAN_TRIGGER_RATING]
    return 1 in manager_ratings or len(low) >= 2


def plan_requires_hr(cost: float) -> bool:
    return float(cost) > HR_APPROVAL_COST_THRESHOLD


def plan_status(approvals: Sequence[dict], requires_hr: bool, completed_at) -> str:
    """Derive plan status from its approval records (no independent random status)."""
    if not approvals:
        return "draft"
    if any(a["decision"] == "rejected" for a in approvals):
        return "rejected"
    roles_approved = {a["approver_role"] for a in approvals if a["decision"] == "approved"}
    needed = {"manager", "hr_partner"} if requires_hr else {"manager"}
    if needed <= roles_approved:
        return "completed" if completed_at else "approved"
    return "submitted"


# ---- Closed cycle edit policy ------------------------------------------------
def is_silent_post_close_edit(cycle_closed_at: Optional[datetime], changed_at: datetime,
                              rationale: Optional[str], approved_by: Optional[str]) -> bool:
    """After a cycle closes, any change must carry a rationale AND an approver."""
    if cycle_closed_at is None or changed_at <= cycle_closed_at:
        return False
    return not (rationale and approved_by)


# ---- Conflicting feedback ----------------------------------------------------
CONFLICT_GAP = 2   # |self - manager| >= 2 on the same competency


def to_date(v) -> Optional[date]:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v

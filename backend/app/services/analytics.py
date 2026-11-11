"""Read-side: KPIs, department breakdowns and data-quality findings / evaluation."""
from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from data_generator.io import read_ground_truth
from domain import quality_rules
from domain.schema import TABLE_BY_NAME

from ..deps import Clock
from ..models import (CheckIn, DatasetInfo, DevelopmentPlan, Employee, EvidenceLink, Feedback, Goal, Manager,
                      MODEL_BY_TABLE, PeerNomination, PlanApproval, Review)
from .common import data_version


def pct(n, d) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def overview(db: Session, clock: Clock, cycle_id: str) -> dict:
    goals_by_status = dict(db.execute(select(Goal.status, func.count()).where(Goal.cycle_id == cycle_id)
                                      .group_by(Goal.status)).all())
    active_statuses = ("in_progress", "closed")
    n_active = sum(goals_by_status.get(s, 0) for s in active_statuses)
    avg_progress = db.scalar(select(func.avg(Goal.progress_pct)).where(Goal.cycle_id == cycle_id,
                                                                      Goal.status.in_(active_statuses))) or 0
    with_ci = db.scalar(select(func.count(func.distinct(CheckIn.goal_id))).join(Goal, Goal.goal_id == CheckIn.goal_id)
                        .where(Goal.cycle_id == cycle_id, Goal.status.in_(active_statuses))) or 0
    n_ci = db.scalar(select(func.count()).select_from(CheckIn).where(CheckIn.cycle_id == cycle_id)) or 0
    recent = db.scalar(select(func.count(func.distinct(CheckIn.goal_id))).where(
        CheckIn.cycle_id == cycle_id, CheckIn.checkin_date >= clock.today() - timedelta(days=30))) or 0
    ci_with_ev = db.scalar(select(func.count(func.distinct(EvidenceLink.checkin_id))).join(
        CheckIn, CheckIn.checkin_id == EvidenceLink.checkin_id).where(CheckIn.cycle_id == cycle_id)) or 0
    month = (func.strftime("%Y-%m", CheckIn.checkin_date) if db.bind.dialect.name == "sqlite"
             else func.to_char(CheckIn.checkin_date, "YYYY-MM")).label("month")
    monthly = db.execute(select(month, func.count()).where(CheckIn.cycle_id == cycle_id)
                         .group_by(month).order_by(month)).all()

    reviews = db.scalars(select(Review).where(Review.cycle_id == cycle_id)).all()
    missing = Counter()
    for r in reviews:
        for m in (r.missing_inputs or "").split(";"):
            if m:
                missing["missing_checkin" if m.startswith("checkin:") else m] += 1
    ratings = Counter(r.overall_rating for r in reviews if r.overall_rating)

    fb_types = dict(db.execute(select(Feedback.feedback_type, func.count()).where(Feedback.cycle_id == cycle_id)
                               .group_by(Feedback.feedback_type)).all())
    accepted = db.scalar(select(func.count()).select_from(PeerNomination).where(
        PeerNomination.cycle_id == cycle_id, PeerNomination.status == "accepted")) or 0
    responded = db.scalar(select(func.count()).select_from(
        select(Feedback.subject_employee_id, Feedback.giver_employee_id).where(
            Feedback.cycle_id == cycle_id, Feedback.feedback_type == "peer").distinct().subquery())) or 0
    plans = dict(db.execute(select(DevelopmentPlan.status, func.count()).where(DevelopmentPlan.cycle_id == cycle_id)
                            .group_by(DevelopmentPlan.status)).all())
    decided = db.execute(select(DevelopmentPlan.created_at, PlanApproval.decided_at).join(
        PlanApproval, PlanApproval.plan_id == DevelopmentPlan.plan_id).where(
        DevelopmentPlan.cycle_id == cycle_id, PlanApproval.approver_role == "manager",
        PlanApproval.decided_at.is_not(None))).all()
    days = [(d - c).total_seconds() / 86400 for c, d in decided]
    return {
        "cycle_id": cycle_id, "as_of": clock.today().isoformat(),
        "people": {"employees": db.scalar(select(func.count()).select_from(Employee).where(
            Employee.employment_status != "terminated")),
                   "managers": db.scalar(select(func.count()).select_from(Manager))},
        "goals": {"total": sum(goals_by_status.values()), "by_status": goals_by_status,
                  "avg_progress_pct": round(avg_progress, 1),
                  "with_checkin_pct": pct(with_ci, n_active)},
        "checkins": {"total": n_ci, "per_active_goal": round(n_ci / n_active, 2) if n_active else 0,
                     "goals_updated_last_30d_pct": pct(recent, n_active),
                     "evidence_coverage_pct": pct(ci_with_ev, n_ci),
                     "monthly": [{"month": m, "count": c} for m, c in monthly]},
        "reviews": {"total": len(reviews), "by_status": dict(Counter(r.status for r in reviews)),
                    "completion_pct": pct(sum(r.is_complete for r in reviews), len(reviews)),
                    "finalized_pct": pct(sum(r.status == "finalized" for r in reviews), len(reviews)),
                    "missing_inputs": dict(missing),
                    "rating_distribution": {k: ratings.get(k, 0) for k in
                                            ["Exceptional", "Exceeds", "Meets", "Partially Meets", "Below"]},
                    "avg_overall_score": round(sum(r.overall_score for r in reviews if r.overall_score) /
                                               max(1, sum(1 for r in reviews if r.overall_score)), 2)},
        "feedback": {"by_type": fb_types, "peer_response_pct": pct(responded, accepted),
                     "conflicting": len([c for c in quality_cache.conflicts(db) if c[0] == cycle_id])},
        "development_plans": {"by_status": plans, "total": sum(plans.values()),
                              "avg_days_to_manager_decision": round(sum(days) / len(days), 1) if days else None},
    }


def departments(db: Session, cycle_id: str) -> list[dict]:
    goal_rows = db.execute(select(Employee.department, func.count(Goal.goal_id), func.avg(Goal.progress_pct))
                           .join(Goal, Goal.employee_id == Employee.employee_id)
                           .where(Goal.cycle_id == cycle_id, Goal.status.in_(("in_progress", "closed")))
                           .group_by(Employee.department)).all()
    rev_rows = db.execute(select(Employee.department, func.count(Review.review_id),
                                 func.sum(case((Review.is_complete, 1), else_=0)), func.avg(Review.overall_score))
                          .join(Review, Review.employee_id == Employee.employee_id)
                          .where(Review.cycle_id == cycle_id).group_by(Employee.department)).all()
    revs = {d: (n, c, s) for d, n, c, s in rev_rows}
    out = []
    for dept, n_goals, avg_p in sorted(goal_rows):
        n, c, s = revs.get(dept, (0, 0, None))
        out.append({"department": dept, "active_goals": n_goals, "avg_progress_pct": round(avg_p or 0, 1),
                    "reviews": n, "completion_pct": pct(c or 0, n), "avg_overall_score": round(s, 2) if s else None})
    return out


# ------------------------------------------------------------------ data quality
class QualityCache:
    """Runs the shared rule detectors over the live database; recomputed only after writes."""

    def __init__(self):
        self._lock = threading.Lock()
        self._version = -1
        self._findings: list[dict] = []
        self._conflicts: list = []

    def _load(self, db: Session):
        from datetime import date
        names = ["employees", "review_cycles", "goals", "key_results", "checkins", "kr_updates", "reviews",
                 "manager_assignments", "peer_nominations", "feedback", "goal_versions", "review_events"]
        ds = {}
        for n in names:
            cols = TABLE_BY_NAME[n].field_names()
            model = MODEL_BY_TABLE[n]
            ds[n] = [dict(zip(cols, row)) for row in db.execute(select(*[getattr(model, c) for c in cols]))]
        as_of = date.fromisoformat(db.get(DatasetInfo, "as_of").value)
        return ds, as_of

    def refresh(self, db: Session):
        with self._lock:
            if self._version == data_version():
                return
            ds, as_of = self._load(db)
            self._findings = quality_rules.run_all(ds, as_of)
            self._conflicts = quality_rules.conflicting_feedback(ds)
            self._version = data_version()

    def findings(self, db: Session) -> list[dict]:
        self.refresh(db)
        return self._findings

    def for_entities(self, db: Session, ids: set) -> list[dict]:
        """Findings that reference any of the given ids (used to flag records in detail views)."""
        return [f for f in self.findings(db) if f["entity_id"] in ids or ids & set(f["related_ids"])]

    def conflicts(self, db: Session) -> list:
        self.refresh(db)
        return self._conflicts


quality_cache = QualityCache()


def quality_summary(db: Session) -> dict:
    f = quality_cache.findings(db)
    by_type = defaultdict(Counter)
    for x in f:
        by_type[x["issue_type"]][x["sub_type"]] += 1
    return {"total_findings": len(f),
            "by_issue_type": {k: {"total": sum(v.values()), "by_sub_type": dict(v)} for k, v in sorted(by_type.items())},
            "conflicting_feedback": len(quality_cache.conflicts(db))}


def evaluation(db: Session) -> dict:
    data_dir = Path(db.get(DatasetInfo, "data_dir").value)
    labels = [l for l in read_ground_truth(data_dir) if l["label_kind"] == "anomaly"]
    validation_file = data_dir / "validation_summary.json"
    validation = json.loads(validation_file.read_text(encoding="utf-8")) if validation_file.exists() else None
    return {"source": "ground_truth/ground_truth.csv (kept outside the database; never used as a feature)",
            "detectors_vs_ground_truth": quality_rules.evaluate(quality_cache.findings(db), labels),
            "validation": None if validation is None else {
                "overall_status": validation["overall_status"], "checks_passed": validation["checks_passed"],
                "checks_total": validation["checks_total"],
                "checks": [{k: c[k] for k in ("check", "category", "rows_checked", "violations",
                                               "explained_by_ground_truth", "unexplained", "status")}
                           for c in validation["checks"]]}}

"""Shared helpers: serialisation, ID allocation, reporting-line lookups, change tracking."""
from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Employee, ManagerAssignment, PeerNomination, ReviewCycle

_version_lock = threading.Lock()
_data_version = 0


def bump_data_version() -> None:
    """Called after every committed write; caches (e.g. quality findings) key off it."""
    global _data_version
    with _version_lock:
        _data_version += 1


def data_version() -> int:
    return _data_version


def to_dict(obj, exclude: tuple = ()) -> dict:
    out = {}
    for col in obj.__table__.columns:
        if col.key in exclude:
            continue
        v = getattr(obj, col.key)
        out[col.key] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return out


def next_id(db: Session, column, prefix: str, width: int) -> str:
    """IDs are zero-padded, so the lexicographic max is also the numeric max."""
    current = db.scalar(select(func.max(column)).where(column.like(f"{prefix}%")))
    n = int(current[len(prefix):]) + 1 if current else 1
    return f"{prefix}{n:0{width}d}"


def manager_at(db: Session, employee_id: str, on: date) -> Optional[str]:
    return db.scalar(select(ManagerAssignment.manager_id).where(
        ManagerAssignment.employee_id == employee_id, ManagerAssignment.effective_from <= on,
        or_(ManagerAssignment.effective_to.is_(None), ManagerAssignment.effective_to >= on)))


def managers_during(db: Session, employee_id: str, start: date, end: date) -> set[str]:
    return set(db.scalars(select(ManagerAssignment.manager_id).where(
        ManagerAssignment.employee_id == employee_id, ManagerAssignment.effective_from <= end,
        or_(ManagerAssignment.effective_to.is_(None), ManagerAssignment.effective_to >= start))))


def cycle_window(cycle: ReviewCycle, today: date) -> tuple[date, date]:
    return cycle.start_date, min(cycle.end_date, today)


def has_feedback_relationship(db: Session, cycle: ReviewCycle, feedback_type: str, giver_id: str,
                              subject_id: str, today: date) -> bool:
    """Same rule as domain.quality_rules: self = same person; manager = managed the subject
    during the cycle; peer = holds an accepted nomination for this cycle."""
    if feedback_type == "self":
        return giver_id == subject_id
    if feedback_type == "manager":
        return giver_id in managers_during(db, subject_id, *cycle_window(cycle, today))
    return db.scalar(select(PeerNomination.nomination_id).where(
        PeerNomination.cycle_id == cycle.cycle_id, PeerNomination.subject_employee_id == subject_id,
        PeerNomination.peer_employee_id == giver_id, PeerNomination.status == "accepted")) is not None


def is_privileged(actor: Employee) -> bool:
    return actor.role in ("hr_partner", "admin")


def employee_brief(e: Optional[Employee]) -> Optional[dict]:
    if e is None:
        return None
    return {"employee_id": e.employee_id, "name": e.full_name, "job_title": e.job_title,
            "department": e.department, "role": e.role}

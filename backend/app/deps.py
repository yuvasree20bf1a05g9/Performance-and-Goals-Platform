"""FastAPI dependencies: DB session, simulated authentication, business clock."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterator, Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from .errors import Unauthenticated
from .models import DatasetInfo, Employee


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def get_actor(x_actor_id: Optional[str] = Header(default=None, description="Acting employee id, e.g. EMP-000123"),
              db: Session = Depends(get_db)) -> Employee:
    """Simulated auth: the caller states who they are via X-Actor-Id. In production this
    would be replaced by an SSO/JWT middleware that resolves the same Employee object."""
    if not x_actor_id:
        raise Unauthenticated("X-Actor-Id header is required for write operations")
    actor = db.get(Employee, x_actor_id)
    if actor is None or actor.employment_status == "terminated":
        raise Unauthenticated(f"unknown or inactive actor {x_actor_id}")
    return actor


class Clock:
    """The dataset is a snapshot frozen at ``as_of``; new events are stamped on that business
    date (with the real time of day) so lifecycle rules stay consistent with the data."""

    def __init__(self, as_of: date):
        self.as_of = as_of

    def today(self) -> date:
        return self.as_of

    def now(self) -> datetime:
        t = datetime.now().time().replace(microsecond=0)
        return datetime.combine(self.as_of, t)


def get_clock(db: Session = Depends(get_db)) -> Clock:
    row = db.get(DatasetInfo, "as_of")
    return Clock(date.fromisoformat(row.value) if row else date.today())

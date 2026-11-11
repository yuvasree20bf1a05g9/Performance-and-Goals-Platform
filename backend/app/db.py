"""Engine / session management. SQLite by default, PostgreSQL via DATABASE_URL."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):          # enforce FKs + better concurrency
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            try:
                cur.execute("PRAGMA journal_mode=WAL")
            except Exception:  # e.g. network / synced folders without shared-memory locking
                pass           # fall back to SQLite's default rollback journal
            cur.close()
    return engine


class Database:
    def __init__(self, url: str):
        self.url = url
        self.engine = make_engine(url)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

"""Shared fixtures: one starter dataset per session, a fresh database copy per test."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.db import Database  # noqa: E402
from backend.app.loader import load_dataset  # noqa: E402
from data_generator.config import config_for  # noqa: E402
from data_generator.pipeline import generate  # noqa: E402


@pytest.fixture(scope="session")
def starter_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("data") / "starter"
    generate(config_for("starter"), out, log=lambda *_: None)
    return out


@pytest.fixture(scope="session")
def template_db(starter_dir, tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("db") / "template.db"
    db = Database(f"sqlite:///{path.as_posix()}")
    load_dataset(db, starter_dir, log=lambda *_: None)
    db.engine.dispose()
    return path


@pytest.fixture()
def client(template_db, tmp_path):
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.services import common

    path = tmp_path / "test.db"
    # Use SQLite's backup API rather than a file copy: with WAL journaling part of the data can
    # live in a side file (-wal), so a raw copy is not a consistent snapshot on every filesystem.
    src, dst = sqlite3.connect(template_db), sqlite3.connect(path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    url = f"sqlite:///{path.as_posix()}"
    app = create_app(Settings(database_url=url, data_profile="starter", frontend_dist=tmp_path / "no-dist",
                              cors_origins=[]), Database(url))
    common.bump_data_version()       # invalidate caches between tests
    with TestClient(app) as c:
        yield c
    app.state.db.engine.dispose()


@pytest.fixture()
def actors(client):
    return {a["label"]: a["employee_id"] for a in client.get("/api/meta").json()["demo_actors"]}

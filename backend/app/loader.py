"""Loads a generated dataset (CSV) into the database: drop -> create -> bulk insert.

Runs in one transaction with deferred FK checks, so either the whole dataset
lands or nothing does.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import insert, text

from data_generator.io import read_table
from domain.schema import TABLE_ORDER

from .db import Base, Database
from .models import DatasetInfo, MODEL_BY_TABLE


def load_dataset(db: Database, data_dir: Path, log=print, chunk: int = 5000) -> dict:
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    with db.engine.connect() as conn:
        if db.engine.dialect.name == "sqlite":
            # employees <-> managers reference each other; let SQLite drop the cycle
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(conn)
        conn.commit()
        if db.engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(db.engine)
    counts = {}
    with db.engine.begin() as conn:
        if db.engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA defer_foreign_keys=ON"))
        for name in TABLE_ORDER:
            rows = read_table(data_dir / "csv", name)
            model = MODEL_BY_TABLE[name]
            for i in range(0, len(rows), chunk):
                conn.execute(insert(model), rows[i:i + chunk])
            counts[name] = len(rows)
            log(f"  loaded {name:<20} {len(rows):>7,} rows")
        info = {"profile": manifest["profile"], "seed": str(manifest["seed"]), "as_of": manifest["as_of"],
                "data_dir": str(data_dir), "generator_version": manifest["generator_version"]}
        conn.execute(insert(DatasetInfo), [{"key": k, "value": v} for k, v in info.items()])
    log(f"  database ready in {time.perf_counter() - t0:.1f}s ({db.engine.dialect.name})")
    return counts

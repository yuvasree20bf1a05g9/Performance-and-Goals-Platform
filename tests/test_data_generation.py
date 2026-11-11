"""Data generation: validation, volumes, ground-truth separation, reproducibility."""
import csv
import json

from data_generator.config import config_for
from data_generator.io import read_dataset, read_ground_truth
from data_generator.pipeline import generate
from data_generator.validate import validate
from domain.schema import ANOMALY_TYPES, SCENARIO_TYPES, TABLES


def test_validation_suite_passes(starter_dir):
    summary = validate(starter_dir)
    failed = [c for c in summary["checks"] if c["status"] != "PASS"]
    assert summary["overall_status"] == "PASS", failed
    assert (starter_dir / "validation_summary.md").exists()


def test_volumes_follow_scale(starter_dir):
    m = json.loads((starter_dir / "manifest.json").read_text(encoding="utf-8"))
    assert m["row_counts"]["employees"] == 150
    assert m["row_counts"]["managers"] == 25
    assert m["row_counts"]["goals"] == 500
    assert m["row_counts"]["checkins"] == 1000


def test_every_anomaly_and_scenario_is_labelled(starter_dir):
    kinds = {l["issue_type"] for l in read_ground_truth(starter_dir)}
    assert set(ANOMALY_TYPES) <= kinds
    assert set(SCENARIO_TYPES) <= kinds


def test_ground_truth_never_leaks_into_inputs(starter_dir):
    label_ids = {l["label_id"] for l in read_ground_truth(starter_dir)}
    for t in TABLES:
        with (starter_dir / "csv" / f"{t.name}.csv").open(encoding="utf-8") as fh:
            header = next(csv.reader(fh))
            assert not any(w in h for h in header for w in ("label", "anomal", "ground", "issue")), t.name
            body = fh.read()
            assert not any(lid in body for lid in list(label_ids)[:50])


def test_ids_are_consistent_across_files(starter_dir):
    ds = read_dataset(starter_dir)
    for g in ds["goals"]:
        if g["goal_id"].startswith("GOAL-"):
            assert g["goal_id"][5:15].startswith("EMP-")
    for k in ds["key_results"]:
        assert k["kr_id"].startswith(f"KR-{k['goal_id']}-")
    assert all(r["review_id"].startswith("REV-2026-") for r in ds["reviews"])


def test_progress_derives_from_key_results(starter_dir):
    ds = read_dataset(starter_dir)
    krs = {}
    for k in ds["key_results"]:
        krs.setdefault(k["goal_id"], []).append(k)
    for g in ds["goals"][:200]:
        ks = krs[g["goal_id"]]
        expected = round(sum(k["weight_pct"] * k["scoring_progress_pct"] for k in ks) / sum(k["weight_pct"] for k in ks), 2)
        assert abs(g["progress_pct"] - expected) <= 0.011


def test_same_seed_is_byte_identical_and_new_seed_differs(tmp_path):
    a = generate(config_for("starter"), tmp_path / "a", formats=("csv",), log=lambda *_: None)
    b = generate(config_for("starter"), tmp_path / "b", formats=("csv",), log=lambda *_: None)
    c = generate(config_for("starter", seed=7), tmp_path / "c", formats=("csv",), log=lambda *_: None)
    assert a["files"] == b["files"]
    assert a["files"]["csv/goals.csv"]["sha256"] != c["files"]["csv/goals.csv"]["sha256"]


def test_loader_is_idempotent(starter_dir, tmp_path):
    """Re-loading into an existing database must work (employees <-> managers FK cycle)."""
    from sqlalchemy import text

    from backend.app.db import Database
    from backend.app.loader import load_dataset
    db = Database(f"sqlite:///{(tmp_path / 'reload.db').as_posix()}")
    load_dataset(db, starter_dir, log=lambda *_: None)
    counts = load_dataset(db, starter_dir, log=lambda *_: None)
    with db.engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM employees")).scalar() == counts["employees"] == 150
        assert c.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    db.engine.dispose()


# Golden fingerprint of the starter dataset (CSV + ground truth). It must be identical on every
# machine and Python version; if a deliberate generator change alters it, update the constant.
STARTER_FINGERPRINT = "ccdc60d22570fc072698a06446e589ffb0a019db2b04f9aa193d43995fc1ff0a"


def test_starter_dataset_matches_golden_fingerprint(starter_dir):
    import hashlib
    m = json.loads((starter_dir / "manifest.json").read_text(encoding="utf-8"))
    blob = "".join(f"{k}={v['sha256']};" for k, v in sorted(m["files"].items())
                   if k.startswith("csv/") or k.startswith("ground_truth/"))
    assert hashlib.sha256(blob.encode()).hexdigest() == STARTER_FINGERPRINT

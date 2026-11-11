"""Generate -> export -> manifest, and the reproducibility proof (Step 9 and 10)."""
from __future__ import annotations

import json
import platform
import tempfile
import time
from pathlib import Path

from domain.schema import TABLES

from . import io
from .config import GENERATOR_VERSION, GeneratorConfig
from .docs import write_data_dictionary
from .generator import Generator


def generate(cfg: GeneratorConfig, out_dir: Path, formats=("csv", "json", "sql"), log=print) -> dict:
    # Files are overwritten in place (no folder wipe), and the manifest lists exactly the
    # files written by this run - so stale files from older runs can never leak into it.
    out_dir = Path(out_dir)
    for sub in ("csv", "json", "sql", "ground_truth"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    ds, labels, outcomes = Generator(cfg).run()
    log(f"  generated {sum(len(v) for v in ds.values()):,} rows in {time.perf_counter() - t0:.1f}s")

    for t in TABLES:
        io.write_csv(out_dir / "csv" / f"{t.name}.csv", t, ds[t.name])
        if "json" in formats:
            io.write_json(out_dir / "json" / f"{t.name}.json", t, ds[t.name])
    if "sql" in formats:
        io.write_sql(out_dir / "sql" / "seed_sqlite.sql", ds, "sqlite")
        io.write_sql(out_dir / "sql" / "seed_postgres.sql", ds, "postgres")
    gt = out_dir / "ground_truth"
    io.write_plain_csv(gt / "ground_truth.csv", io.GT_COLUMNS, labels)
    (gt / "ground_truth.json").write_text(json.dumps(labels, indent=1) + "\n", encoding="utf-8", newline="\n")
    io.write_plain_csv(gt / "review_outcomes.csv", io.OUTCOME_COLUMNS, outcomes)

    written = [out_dir / "csv" / f"{t.name}.csv" for t in TABLES]
    if "json" in formats:
        written += [out_dir / "json" / f"{t.name}.json" for t in TABLES]
    if "sql" in formats:
        written += [out_dir / "sql" / "seed_sqlite.sql", out_dir / "sql" / "seed_postgres.sql"]
    written += [gt / "ground_truth.csv", gt / "ground_truth.json", gt / "review_outcomes.csv"]
    files = sorted(written)
    manifest = {
        "generator": "data_generator", "generator_version": GENERATOR_VERSION,
        "profile": cfg.profile, "scale": cfg.scale, "seed": cfg.seed, "as_of": cfg.as_of.isoformat(),
        "command": f"python manage.py generate --profile {cfg.profile} --seed {cfg.seed}",
        "python_version": platform.python_version(),
        "data_provenance": {
            "source": "100% synthetic, produced by this repository's code with a fixed seed",
            "external_datasets_used": [],
            "personal_data": "none - names are drawn from a generic list and e-mails use example.com",
            "license": "MIT (same as the code)",
        },
        "expected_counts": {"employees": cfg.n(cfg.base_employees, 20), "managers": cfg.n(cfg.base_managers, 12),
                            "goals": cfg.n(cfg.base_goals, 10), "checkins": cfg.n(cfg.base_checkins, 20)},
        "row_counts": {t.name: len(ds[t.name]) for t in TABLES},
        "ground_truth_counts": _label_counts(labels),
        "files": {str(p.relative_to(out_dir)).replace("\\", "/"): {"sha256": io.sha256(p), "bytes": p.stat().st_size}
                  for p in files},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_data_dictionary(Path(__file__).resolve().parents[1] / "docs" / "data_dictionary.md")
    log(f"  wrote {len(files)} files to {out_dir}")
    return manifest


def _label_counts(labels):
    out = {}
    for l in labels:
        key = f"{l['label_kind']}:{l['issue_type']}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def reproduce(cfg: GeneratorConfig, report_path: Path, log=print) -> dict:
    """Generate twice in isolated folders and compare row counts + SHA-256 of every file."""
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in (1, 2):
            log(f"  run {i}/2 ...")
            runs.append(generate(cfg, Path(tmp) / f"run{i}", log=lambda *_: None))
    a, b = runs
    mismatched = sorted(f for f in set(a["files"]) | set(b["files"])
                        if a["files"].get(f, {}).get("sha256") != b["files"].get(f, {}).get("sha256"))
    report = {"profile": cfg.profile, "seed": cfg.seed, "identical": not mismatched and a["row_counts"] == b["row_counts"],
              "files_compared": len(a["files"]), "mismatched_files": mismatched,
              "row_counts_run1": a["row_counts"], "row_counts_run2": b["row_counts"],
              "checksums": {f: {"run1": a["files"][f]["sha256"], "run2": b["files"].get(f, {}).get("sha256")}
                            for f in sorted(a["files"])}}
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report

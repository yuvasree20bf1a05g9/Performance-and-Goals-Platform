#!/usr/bin/env python
"""One entry point for the whole pipeline.

    python manage.py all                    # generate -> validate -> load DB -> start app (full dataset)
    python manage.py all --profile starter  # same, small dataset (seconds)

    python manage.py generate  --profile full     # Step 1-7: synthetic data + ground truth + manifest
    python manage.py validate  --profile full     # Step 8:  validation suite -> validation_summary.md
    python manage.py reproduce --profile full     # Step 10: generate twice, compare checksums
    python manage.py load      --profile full     # load CSVs into the database (SQLite / PostgreSQL)
    python manage.py serve                        # start API + web UI on http://localhost:8000
    python manage.py test                         # run the automated test-suite
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def banner(text: str) -> None:
    print(f"\n=== {text} " + "=" * max(0, 60 - len(text)))


def cmd_generate(a):
    from data_generator.config import config_for
    from data_generator.pipeline import generate
    banner(f"Generating '{a.profile}' dataset (seed {a.seed})")
    generate(config_for(a.profile, None, a.seed), ROOT / "data" / a.profile)


def cmd_validate(a):
    from data_generator.validate import validate
    banner(f"Validating '{a.profile}' dataset")
    s = validate(ROOT / "data" / a.profile)
    for r in s["checks"]:
        print(f"  [{r['status']}] {r['check']:<40} violations={r['violations']:<5} unexplained={r['unexplained']}")
    print(f"  => {s['overall_status']} ({s['checks_passed']}/{s['checks_total']}) "
          f"report: data/{a.profile}/validation_summary.md")
    if s["overall_status"] != "PASS":
        sys.exit(1)


def cmd_reproduce(a):
    from data_generator.config import config_for
    from data_generator.pipeline import reproduce
    banner(f"Reproducibility check for '{a.profile}' (two runs, same seed)")
    r = reproduce(config_for(a.profile, None, a.seed), ROOT / "data" / f"reproducibility_{a.profile}.json")
    print(f"  identical={r['identical']}  files_compared={r['files_compared']}  mismatched={r['mismatched_files']}")
    if not r["identical"]:
        sys.exit(1)


def cmd_load(a):
    os.environ["DATA_PROFILE"] = a.profile
    from backend.app.config import get_settings
    from backend.app.db import Database
    from backend.app.loader import load_dataset
    s = get_settings()
    banner(f"Loading '{a.profile}' into {s.database_url.split('://')[0]}")
    if not (s.data_dir / "manifest.json").exists():
        sys.exit(f"  no dataset at {s.data_dir} - run: python manage.py generate --profile {a.profile}")
    load_dataset(Database(s.database_url), s.data_dir)


def cmd_serve(a):
    import threading
    import webbrowser

    import uvicorn
    banner(f"Starting app on http://localhost:{a.port}  (API docs: http://localhost:{a.port}/docs)")
    print("  press Ctrl+C to stop")
    if a.open:
        threading.Timer(2.5, webbrowser.open, args=[f"http://localhost:{a.port}"]).start()
    uvicorn.run("backend.app.main:app", host=a.host, port=a.port, reload=a.reload)


def cmd_test(_a):
    banner("Running tests")
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=ROOT))


def cmd_all(a):
    cmd_generate(a)
    cmd_validate(a)
    cmd_load(a)
    cmd_serve(a)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("generate", cmd_generate), ("validate", cmd_validate), ("reproduce", cmd_reproduce),
                     ("load", cmd_load), ("serve", cmd_serve), ("test", cmd_test), ("all", cmd_all)]:
        s = sub.add_parser(name)
        s.set_defaults(fn=fn)
        s.add_argument("--profile", default="full", choices=["starter", "full"])
        s.add_argument("--seed", type=int, default=20261022)
        s.add_argument("--host", default="127.0.0.1")
        s.add_argument("--port", type=int, default=8000)
        s.add_argument("--reload", action="store_true")
        s.add_argument("--open", action="store_true", help="open the web UI in your browser once the server starts")
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

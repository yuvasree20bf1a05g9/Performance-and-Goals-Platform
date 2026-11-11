"""
main.py - run the whole project and see every result in the terminal.

In VS Code: open this file and click the Run button (top-right triangle, "Run Python File"),
or in a terminal:  python main.py

What it does, step by step (each step prints its output):
  1. checks / installs the Python packages it needs
  2. generates the synthetic dataset (3,000 employees, 500 managers, 10,000 goals, 20,000 check-ins)
  3. validates it (27 checks)
  4. loads it into the database
  5. demonstrates every business rule against the real API
  6. prints the KPIs and the anomaly-detection scores
  7. saves everything to output/run_report.txt
  8. starts the web app and opens http://localhost:8000 (press Ctrl+C to stop)

Options:  --profile starter   small dataset, finishes in seconds
          --no-serve          stop after printing the results (don't start the web app)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
REQUIRED = ("fastapi", "sqlalchemy", "uvicorn", "httpx", "pydantic")


# --------------------------------------------------------------------------- setup
def ensure_dependencies() -> None:
    """Use the project's .venv if VS Code picked another interpreter; install packages if missing."""
    missing = []
    for mod in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if not missing:
        return
    venv_python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        print(f"Packages {missing} are not in this interpreter; switching to {venv_python}\n", flush=True)
        sys.exit(subprocess.call([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]))
    print(f"Installing required packages ({', '.join(missing)}) ...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])


class Tee:
    """Print to the terminal and save the same text to output/run_report.txt."""

    def __init__(self, path: Path):
        path.parent.mkdir(exist_ok=True)
        self.file = path.open("w", encoding="utf-8", newline="\n")
        self.console = sys.stdout

    def write(self, text):
        self.console.write(text)
        self.file.write(text)

    def flush(self):
        self.console.flush()
        self.file.flush()


def step(n: int, title: str) -> float:
    print(f"\n{'=' * 78}\n STEP {n}: {title}\n{'=' * 78}", flush=True)
    return time.perf_counter()


def done(t0: float) -> None:
    print(f"  ... done in {time.perf_counter() - t0:.1f}s", flush=True)


def table(headers: list[str], rows: list[list], widths: list[int]) -> None:
    line = "  " + " | ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  " + "-+-".join("-" * w for w in widths))
    for r in rows:
        print("  " + " | ".join(str(c)[:w].ljust(w) for c, w in zip(r, widths)))


# --------------------------------------------------------------------------- business-rule demo
def demo_business_rules(client) -> None:
    meta = client.get("/api/meta").json()
    actors = {a["label"]: a["employee_id"] for a in meta["demo_actors"]}
    emp, mgr, hr = actors["Employee (has active goals)"], actors["Their manager"], actors["HR partner"]
    print(f"  Demo users: employee {emp}, their manager {mgr}, HR partner {hr}\n")
    goal = client.get("/api/goals", params={"employee_id": emp, "cycle_id": "CYCLE-2026-H2",
                                            "status": "in_progress"}).json()["items"][0]
    gid = goal["goal_id"]
    krs = client.get(f"/api/goals/{gid}").json()["key_results"]

    def checkin(fraction, rationale=None):
        return {"confidence": "high", "note": "Weekly update",
                "updates": [{"kr_id": k["kr_id"], "reported_value": k["start_value"] + (k["target_value"] - k["start_value"]) * fraction,
                             "over_scale_rationale": rationale} for k in krs]}

    closed = client.get("/api/goals", params={"cycle_id": "CYCLE-2026-H1", "status": "closed"}).json()["items"][0]["goal_id"]
    review = next(r for r in client.get("/api/reviews", params={"cycle_id": "CYCLE-2026-H2", "size": 200}).json()["items"]
                  if r["employee_id"] == emp)
    H = lambda who: {"X-Actor-Id": who}  # noqa: E731
    fb = {"competency_id": "COMP-01", "rating": 4, "comment": "Good work"}
    target_up = {"kr_targets": [{"kr_id": krs[0]["kr_id"], "target_value": krs[0]["target_value"] + 5}]}
    cases = [
        ("Check-in with no logged-in user", "401", lambda: client.post(f"/api/goals/{gid}/checkins", json=checkin(0.5))),
        ("Check-in by HR (not owner/manager)", "403", lambda: client.post(f"/api/goals/{gid}/checkins", json=checkin(0.5), headers=H(hr))),
        ("Check-in at 130% with NO reason", "422", lambda: client.post(f"/api/goals/{gid}/checkins", json=checkin(1.3), headers=H(emp))),
        ("Check-in at 130% WITH a reason", "201", lambda: client.post(f"/api/goals/{gid}/checkins", json=checkin(1.3, "Big deal closed early"), headers=H(emp))),
        ("Check-in at 80% by the manager", "201", lambda: client.post(f"/api/goals/{gid}/checkins", json=checkin(0.8), headers=H(mgr))),
        ("Change KR target with NO reason", "422", lambda: client.patch(f"/api/goals/{gid}", json=target_up, headers=H(mgr))),
        ("Change KR target WITH a reason", "200", lambda: client.patch(f"/api/goals/{gid}", json={**target_up, "rationale": "Re-baselined"}, headers=H(mgr))),
        ("Edit goal in CLOSED cycle (owner)", "409", lambda: client.patch(f"/api/goals/{closed}", json={"title": "Silent edit"}, headers=H(closed[5:15]))),
        ("HR correction after close, no reason", "422", lambda: client.patch(f"/api/goals/{closed}", json={"title": "Corrected title"}, headers=H(hr))),
        ("HR correction after close, WITH reason", "200", lambda: client.patch(f"/api/goals/{closed}", json={"title": "Corrected title", "rationale": "Approved typo fix"}, headers=H(hr))),
        ("Manager feedback from unrelated HR", "403", lambda: client.post(f"/api/reviews/{review['review_id']}/feedback", json={**fb, "feedback_type": "manager"}, headers=H(hr))),
        ("Peer feedback without a nomination", "403", lambda: client.post(f"/api/reviews/{review['review_id']}/feedback", json={**fb, "feedback_type": "peer"}, headers=H(mgr))),
        ("Finalize a review that never started", "409", lambda: client.post(f"/api/reviews/{review['review_id']}/transition", json={"to_status": "finalized"}, headers=H(review["reviewer_id"]))),
    ]
    rows, ok = [], 0
    for name, expected, call in cases:
        r = call()
        body = r.json()
        if "error" in body:
            result = body["error"]["message"]
        elif "goal_progress_pct" in body:
            result = f"accepted - goal progress now {body['goal_progress_pct']}%"
        else:
            result = f"accepted - saved as version v{body.get('current_version')}"
        passed = str(r.status_code) == expected
        ok += passed
        rows.append([name, expected, r.status_code, "OK" if passed else "UNEXPECTED", result])
    table(["Scenario", "Expect", "Got", "Check", "API answer"], rows, [38, 6, 4, 10, 70])
    print(f"\n  {ok}/{len(cases)} business rules behaved exactly as specified.")


# --------------------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full PerformanceHub pipeline and show the output.")
    parser.add_argument("--profile", choices=["full", "starter"], default="full")
    parser.add_argument("--no-serve", action="store_true", help="don't start the web app at the end")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    ensure_dependencies()
    report = ROOT / "output" / "run_report.txt"
    sys.stdout = Tee(report)
    started = time.perf_counter()

    import platform
    print("PerformanceHub - goals, check-ins, feedback & reviews")
    print(f"Python {platform.python_version()} on {platform.system()} | profile '{args.profile}' | folder {ROOT}")

    # 2. generate -------------------------------------------------------------
    from data_generator.config import config_for
    from data_generator.pipeline import generate
    data_dir = ROOT / "data" / args.profile
    t0 = step(1, f"Generate the synthetic dataset ('{args.profile}', seed 20261022)")
    manifest = generate(config_for(args.profile), data_dir, log=lambda m: print(m, flush=True))
    table(["Table", "Rows"], [[k, f"{v:,}"] for k, v in manifest["row_counts"].items()], [22, 9])
    print("\n  Ground-truth labels (stored separately in data/<profile>/ground_truth/):")
    table(["Kind", "Type", "Labels"], [[*k.split(":"), v] for k, v in manifest["ground_truth_counts"].items()], [9, 34, 7])
    done(t0)

    # 3. validate -------------------------------------------------------------
    from data_generator.validate import validate
    t0 = step(2, "Validate the dataset (integrity, dates, lifecycles, arithmetic, business rules)")
    summary = validate(data_dir)
    table(["Check", "Rows checked", "Violations", "Explained", "Status"],
          [[c["check"], f"{c['rows_checked']:,}", c["violations"], c["explained_by_ground_truth"], c["status"]]
           for c in summary["checks"]], [38, 12, 10, 9, 6])
    print(f"\n  RESULT: {summary['overall_status']} - {summary['checks_passed']}/{summary['checks_total']} checks passed "
          f"(violations are only allowed on records deliberately labelled in ground truth)")
    done(t0)

    # 4. load database ----------------------------------------------------------
    os.environ["DATA_PROFILE"] = args.profile
    from backend.app.config import get_settings
    from backend.app.db import Database
    from backend.app.loader import load_dataset
    settings = get_settings()
    t0 = step(3, f"Load the database ({settings.database_url.split(':')[0]})")
    load_dataset(Database(settings.database_url), data_dir, log=lambda m: print(m, flush=True))
    done(t0)

    # 5-6. API demo on a throw-away copy of the database -------------------------
    import sqlite3
    import tempfile

    from fastapi.testclient import TestClient

    from backend.app.config import Settings
    from backend.app.main import create_app
    t0 = step(4, "Business rules - live requests against the real API")
    with tempfile.TemporaryDirectory() as tmp:
        if settings.database_url.startswith("sqlite"):
            demo_db = Path(tmp) / "demo.db"
            src = sqlite3.connect(settings.database_url.split("sqlite:///", 1)[1])
            dst = sqlite3.connect(demo_db)
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            demo_url = f"sqlite:///{demo_db.as_posix()}"     # demo writes never touch your real data
        else:
            demo_url = settings.database_url
        demo_settings = Settings(database_url=demo_url, data_profile=args.profile,
                                 frontend_dist=Path(tmp) / "none", cors_origins=[])
        demo_app = create_app(demo_settings)
        with TestClient(demo_app) as client:
            demo_business_rules(client)
            done(t0)

            t0 = step(5, "KPIs and anomaly detection")
            for cycle in ("CYCLE-2026-H1", "CYCLE-2026-H2"):
                ov = client.get("/api/metrics/overview", params={"cycle_id": cycle}).json()
                print(f"\n  {cycle}")
                print(f"    goals {ov['goals']['total']:,} | avg progress {ov['goals']['avg_progress_pct']}% "
                      f"| goals with check-ins {ov['goals']['with_checkin_pct']}%")
                print(f"    check-ins {ov['checkins']['total']:,} | evidence attached {ov['checkins']['evidence_coverage_pct']}% "
                      f"| per month {[m['count'] for m in ov['checkins']['monthly']]}")
                print(f"    reviews {ov['reviews']['total']:,} | complete {ov['reviews']['completion_pct']}% "
                      f"| finalized {ov['reviews']['finalized_pct']}% | avg score {ov['reviews']['avg_overall_score']}")
                print(f"    ratings {ov['reviews']['rating_distribution']}")
                print(f"    why incomplete {ov['reviews']['missing_inputs']}")
            ev = client.get("/api/quality/evaluation").json()["detectors_vs_ground_truth"]
            print("\n  Anomaly detectors vs ground truth:")
            table(["Issue type", "Labels", "Findings", "Precision", "Recall", "F1"],
                  [[k, m["labels"], m["findings"], f"{m['precision']:.2f}", f"{m['recall']:.2f}", f"{m['f1']:.2f}"]
                   for k, m in ev.items()], [34, 6, 8, 9, 6, 5])
            done(t0)
        demo_app.state.db.engine.dispose()

    print(f"\n{'=' * 78}\n ALL STEPS FINISHED in {time.perf_counter() - started:.0f}s")
    print(f" Full report saved to: {report}")
    print(f" Validation report:    {data_dir / 'validation_summary.md'}")
    print(f" Generated data:       {data_dir}  (csv/, json/, sql/, ground_truth/)")
    print("=" * 78)
    sys.stdout.flush()
    sys.stdout = sys.stdout.console

    if args.no_serve:
        return 0
    import threading
    import webbrowser

    import uvicorn
    url = f"http://localhost:{args.port}"
    print(f"\nStarting the web app at {url}  (API docs: {url}/docs)")
    print("Your browser will open automatically. Press Ctrl+C in this terminal to stop.\n", flush=True)
    threading.Timer(2.5, webbrowser.open, args=[url]).start()
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())

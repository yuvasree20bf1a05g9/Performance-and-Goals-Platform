# PerformanceHub — Goals, Check-ins, Feedback & Reviews

A full-stack app for managing **goals, key results (OKRs), periodic check-ins, competency feedback, review cycles and development plans**, with progress that is always **calculated from evidence** (never typed in by hand).

It comes with a **synthetic data generator** that builds a realistic company (3,000 employees, 500 managers, 10,000 goals, 20,000 check-ins), deliberately plants 5 kinds of data problems, labels them in a separate *ground truth* file, and proves the app catches every one of them.

```
React UI  ──►  FastAPI backend (business rules)  ──►  SQL database (SQLite or PostgreSQL)
```

![Overview dashboard](docs/screenshots/overview.png)

---

## 1. Run it in 2 minutes

### Easiest: run `main.py` in VS Code

Open the folder in VS Code, open **`main.py`**, and click the **Run** button (top-right) — or press **F5**.
It prints every step in the terminal (dataset → 27 validation checks → database → 13 business-rule
demonstrations → KPIs → anomaly-detection scores), saves the same text to `output/run_report.txt`,
then opens the web app at http://localhost:8000. Press `Ctrl + C` in the terminal to stop.
`python main.py --profile starter --no-serve` gives a 2-second run without the web app.

### Or step by step

**You need:** Python 3.10+ (check with `python --version`). Node.js is **not** needed — the UI is pre-built.

### Windows (PowerShell)

```powershell
cd performance-goals-platform
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py all
```

### macOS / Linux

```bash
cd performance-goals-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py all
```

Then open **http://localhost:8000** (the app) and **http://localhost:8000/docs** (interactive API docs).

`python manage.py all` runs the whole pipeline in order: **generate data → validate it → load the database → start the app**. The first run takes about 30 seconds. Stop the server with `Ctrl + C`.

> **In a hurry?** `python manage.py all --profile starter` uses a 5% sample (150 employees) and starts in about 3 seconds.
>
> **One-click (no typing):** on Windows just **double-click `run.bat`**. It creates the virtual environment, installs everything, runs the pipeline and opens the app in your browser. (`run.ps1` and `./run.sh` do the same from PowerShell / macOS / Linux.)

---

## 2. Try it (a 3-minute tour)

1. **Overview** — KPIs for the selected cycle: goal progress, review completion, check-in cadence, rating distribution, and *why* reviews are incomplete.
2. **Goals & OKRs → open any goal** — see key results, the check-in timeline with evidence links, and the append-only version history.
3. Pick **"Acting as → Employee (has active goals)"** in the top bar, open one of their *in-progress* goals in the **2026 H2** cycle, and submit a check-in:
   * enter a value **above the target** without a rationale → the API refuses it (`422`);
   * add a rationale → it is accepted and the goal score is capped at **120%**.
4. Switch **"Acting as" → HR partner** and try the same check-in → refused with `403` (*goal owner mismatch*).
5. Open a goal from the **closed 2026 H1** cycle and try to change a target → `409` locked. As HR with a rationale it becomes an audited *post-close correction*.
6. **Data quality** — every planted anomaly, how the detectors scored against ground truth, and the 27 validation checks.

| Goal detail | Review detail | Data quality |
|---|---|---|
| ![](docs/screenshots/goal_detail.png) | ![](docs/screenshots/review_detail.png) | ![](docs/screenshots/data_quality.png) |

---

## 3. How it is built (3-tier architecture)

```mermaid
flowchart LR
    subgraph Presentation["1 · Frontend (React + Vite)"]
        UI[Dashboard · Employees · Goals · Reviews · Plans · Data quality]
    end
    subgraph Application["2 · Backend (FastAPI)"]
        API[REST routes /api/*] --> SVC[Services: goals · check-ins · reviews · plans · analytics]
        SVC --> RULES[domain/rules.py<br/>single source of business rules]
    end
    subgraph Data["3 · Database (SQLAlchemy)"]
        DB[(SQLite default<br/>PostgreSQL via DATABASE_URL)]
    end
    GEN[data_generator<br/>seeded synthetic data] -->|CSV / JSON / SQL| LOAD[loader] --> DB
    GEN -->|ground_truth.csv kept separate| EVAL[quality evaluation]
    UI -->|fetch + X-Actor-Id| API
    SVC --> DB
    RULES -.same rules.- GEN
```

**The key design decision:** every business rule (progress maths, rating bands, review completeness, lifecycle transitions, the anomaly detectors) lives **once** in `domain/`. The data generator uses it to *create* derived values, the validator uses it to *re-check* them, and the API uses it to *recompute* them on every write. The three can never disagree.

More detail: [`docs/architecture.md`](docs/architecture.md).

### Project layout

```
performance-goals-platform/
├── manage.py                 ← single entry point (generate | validate | reproduce | load | serve | test | all)
├── domain/                   ← shared core: data dictionary (schema.py), rules.py, quality_rules.py
├── data_generator/           ← seeded synthetic data → CSV / JSON / SQL + ground truth + manifest
├── backend/app/              ← FastAPI: routes → services → SQLAlchemy models
├── frontend/                 ← React app (src/) and its pre-built bundle (dist/)
├── data/starter/             ← committed 5% sample dataset (full dataset is generated locally)
├── tests/                    ← 42 automated tests (rules, data, schema parity, API)
├── docs/                     ← architecture, data dictionary, execution log, screenshots
├── Dockerfile, docker-compose.yml, .github/workflows/ci.yml
└── run.ps1 / run.sh          ← one-click setup + run
```

---

## 4. Execution milestones

The project was built and verified in six milestones. Each one has a command you can re-run; the real output is recorded in [`docs/EXECUTION_LOG.md`](docs/EXECUTION_LOG.md).

| # | Milestone | Command | What "done" looks like |
|---|---|---|---|
| **M1** | Generate synthetic data | `python manage.py generate --profile full` | 249,470 rows across 17 tables in ~20 s, exact volumes 3,000 / 500 / 10,000 / 20,000 |
| **M2** | Validate + reproduce | `python manage.py validate --profile full` <br> `python manage.py reproduce --profile full` | **PASS 27/27** checks; two runs with the same seed give **identical SHA-256** for all 39 files |
| **M3** | Load the database | `python manage.py load --profile full` | All tables loaded in one transaction in ~3 s, zero FK violations (SQLite and PostgreSQL) |
| **M4** | Backend API + rules | `python manage.py serve` → http://localhost:8000/docs | Every acceptance rule enforced (401 / 403 / 409 / 422 paths) |
| **M5** | Frontend | open http://localhost:8000 | 6 screens, zero console errors |
| **M6** | Tests | `python manage.py test` | **42 passed** |

---

## 5. The data model

17 tables; every table has a primary key, every relationship a foreign key. Full field-level dictionary (types, allowed values, units, uniqueness, validation): **[`docs/data_dictionary.md`](docs/data_dictionary.md)** — generated from `domain/schema.py`, so it is always up to date.

| Entity (required by the brief) | Table | ID format | Notes |
|---|---|---|---|
| Employee | `employees` | `EMP-000001` | IDs follow hiring order |
| Manager | `managers` | same as employee ID | 1:1 subtype of Employee |
| ReviewCycle | `review_cycles` | `CYCLE-2026-H1` | planned → active → closed |
| Goal | `goals` | `GOAL-EMP-000001-001` | owner is encoded in the ID |
| KeyResult | `key_results` | `KR-GOAL-EMP-000001-001-01` | 1–4 per goal |
| CheckIn | `checkins` (+ `kr_updates`, `evidence_links`) | `CHK-0000001` | one update per KR per check-in |
| Competency | `competencies` | `COMP-01` | 5 for everyone + leadership for managers |
| Feedback | `feedback` (+ `peer_nominations` bridge) | `FB-2026-0000001` | self / manager / peer |
| Review | `reviews` (+ `review_events`) | `REV-2026-000001` | one per employee per cycle |
| DevelopmentPlan | `development_plans` (+ `plan_approvals`) | `DP-2026-000001` | manager + HR approvals |

History is **never overwritten**: manager transfers add rows to `manager_assignments`, goal changes add rows to `goal_versions`, review changes add rows to `review_events`.

---

## 6. Business rules (acceptance criteria)

| Rule | Where it is enforced | What happens if broken |
|---|---|---|
| **Progress derives from key results** — KR progress = `(value − start) / (target − start)`, goal = KR-weighted average, review = goal-weighted average | `domain/rules.py`, recomputed after every write | Clients cannot send a progress number at all |
| Progress above 100% needs a **rationale**; scored progress is capped at 100% (120% with rationale) | check-in API | `422 business_rule_violation` |
| Only the **goal owner or their current manager** may check in | check-in API | `403 goal owner mismatch` |
| **Review permissions** — self = same person, manager = managed them during the cycle, peer = accepted nomination | feedback API | `403 reviewer lacks relationship` |
| **Changes are versioned** — target/title edits need a rationale and create a new version | goal API | `422` without rationale |
| **Closed cycles are locked** — only HR/admin can correct, with a rationale, recorded as `post_close_correction` | goal / review / feedback APIs | `409 conflict` |
| **Completion reflects required inputs** — a review can be finalized only with full self + reviewer assessment and ≥1 check-in on every active goal | review API | `422` with the list of missing inputs |
| Development plan is **mandatory** if any competency is rated 1 or two are rated ≤ 2; plans over $1,000 also need HR approval | generator + plan API | status derived from approvals |

Ratings: `overall = 0.6 × goal rating + 0.4 × competency rating` → Exceptional ≥ 4.5, Exceeds ≥ 3.75, Meets ≥ 2.75, Partially Meets ≥ 2.0, else Below.

---

## 7. Edge cases and ground truth

The generator first builds a **clean** dataset, then injects the required edge cases into a few chosen records and writes a label for each one to `data/<profile>/ground_truth/` — a separate folder that is **never** loaded into the database or used as an input feature.

| Required edge case | How it is planted | Labels (full) | Detector precision / recall |
|---|---|---:|---:|
| Goal owner mismatch | goal re-assigned without re-keying its ID; check-ins by unrelated people | 65 | 1.00 / 1.00 |
| Progress exceeds scale without rationale | latest KR update pushed to 115–160% with no rationale | 50 | 1.00 / 1.00 |
| Reviewer lacks relationship | review by a manager who never managed the person; peer feedback without nomination | 65 | 1.00 / 1.00 |
| Closed cycle accepts silent edits | target / summary changed after close with no approver | 45 | 1.00 / 1.00 |
| Feedback is untraceable | imported feedback with no giver | 40 | 1.00 / 1.00 |

Required **scenarios** are also labelled: changed goals (1,226), manager transfers (132), incomplete reviews (311), conflicting feedback (759), justified over-achievement (1,102). `ground_truth/review_outcomes.csv` holds the expected decision for every review (finalize / hold / calibrate / invalidate).

**How the validator proves the injection was clean:** every check reports violations; a violation is *explained* only if it touches a labelled record. One unexplained violation fails the run — so an anomaly that accidentally broke an unrelated row would be caught (this actually happened during development and was fixed).

---

## 8. API reference

Reads are open; **writes need an `X-Actor-Id` header** (simulated login — swap for SSO/JWT in production). Errors always look like `{"error": {"code", "message", "details"}}`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health`, `/api/meta` | status; cycles, competencies, demo users |
| GET | `/api/employees`, `/api/employees/{id}` | search; profile, manager chain, transfer history |
| GET | `/api/goals`, `/api/goals/{id}` | list; KRs, check-ins, evidence, versions, data-quality flags |
| POST | `/api/goals` | create goal with key results |
| PATCH | `/api/goals/{id}` | versioned title / target change (rationale required) |
| POST | `/api/goals/{id}/transition` | draft → pending_approval → in_progress → closed / cancelled |
| POST | `/api/goals/{id}/checkins` | check-in with KR values + evidence links |
| GET | `/api/reviews`, `/api/reviews/{id}` | list; scores, feedback matrix, conflicts, audit trail |
| POST | `/api/reviews/{id}/feedback` | self / manager / peer feedback |
| POST | `/api/reviews/{id}/transition` | self_submitted → manager_submitted → finalized |
| GET / POST | `/api/development-plans`, `/{id}/decisions` | list; approve or reject |
| GET | `/api/metrics/overview`, `/api/metrics/departments` | KPIs per cycle |
| GET | `/api/quality/summary`, `/findings`, `/evaluation` | detector output and precision/recall vs ground truth |

Example:

```bash
# EMP-000002 checks in on their active goal (a check-in must report every key result)
curl -X POST http://localhost:8000/api/goals/GOAL-EMP-000002-003/checkins \
  -H "Content-Type: application/json" -H "X-Actor-Id: EMP-000002" \
  -d '{"confidence":"high","note":"Weekly update","updates":[
        {"kr_id":"KR-GOAL-EMP-000002-003-01","reported_value":400},
        {"kr_id":"KR-GOAL-EMP-000002-003-02","reported_value":20},
        {"kr_id":"KR-GOAL-EMP-000002-003-03","reported_value":8}]}'
```

---

## 9. All commands

| Command | What it does |
|---|---|
| `python manage.py all [--profile starter\|full]` | generate → validate → load → serve |
| `python manage.py generate --profile full [--seed 20261022]` | write `data/full/` (CSV, JSON, SQL seeds, ground truth, manifest) |
| `python manage.py validate --profile full` | run 27 checks → `data/full/validation_summary.md` |
| `python manage.py reproduce --profile full` | generate twice, compare SHA-256 → `data/reproducibility_full.json` |
| `python manage.py load --profile full` | (re)load the database |
| `python manage.py serve [--port 8000] [--reload] [--open]` | start API + UI (`--open` launches your browser) |
| `python manage.py test` | run the 42 tests |

**Generated output** (`data/<profile>/`): `csv/` and `json/` (one file per table), `sql/seed_sqlite.sql` and `sql/seed_postgres.sql`, `ground_truth/`, `manifest.json` (seed, command, row counts, SHA-256 of every file, provenance), `validation_summary.md/json`.

---

## 10. Using PostgreSQL / Docker

```bash
# Option A - your own PostgreSQL
pip install "psycopg[binary]"
set DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/pgp      # Windows (macOS/Linux: export ...)
python manage.py all

# Option B - everything in Docker (PostgreSQL + app)
docker compose up --build        # then open http://localhost:8000
```

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/performance.db` | any SQLAlchemy URL |
| `DATA_PROFILE` | `full` | which generated dataset the app reports on |
| `CORS_ORIGINS` | `http://localhost:5173` | allowed origins for the Vite dev server |

**Frontend development** (needs Node 18+): run the backend with `python manage.py serve`, then in `frontend/` run `npm install` and `npm run dev` → http://localhost:5173 (API calls are proxied). `npm run build` refreshes `frontend/dist/`.

---

## 11. Reproducibility and data provenance

* Fixed seed **20261022**; a fixed business date (**as of 2026-11-11**) so cycle states never depend on when you run it.
* Each generator step has its own random stream (`seed:step`), so changing one step never reshuffles the others.
* **Identical across machines and Python versions** (verified on Python 3.10 and 3.13): averages use `math.fsum`, because the built-in `sum()` changed float precision in Python 3.12 and flipped a few half-cent roundings. A golden-fingerprint test guards this.
* `manifest.json` records the exact command, seed, scale, Python version, row counts and a SHA-256 per file.
* **100% synthetic.** No external datasets, no real people: names come from a generic list and every e-mail is `@example.com`. License: MIT.

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found (Windows) | install Python from python.org and tick **"Add python.exe to PATH"**, or use `py` instead of `python` |
| `.venv\Scripts\activate` is blocked | run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once in PowerShell |
| Port 8000 is busy | `python manage.py serve --port 8001` |
| Page says "Cannot reach the API" | the backend isn't running — start it with `python manage.py serve` |
| Want a clean slate | `python manage.py all` regenerates and reloads everything |

---

## 13. Design decisions & trade-offs

* **One rules module, three consumers** (generator, validator, API) — eliminates the most common bug in data projects: the generated "truth" and the app silently disagreeing.
* **Derived values are never random.** Progress, scores, ratings, completeness, current manager, plan status are all computed from source records; the validator recomputes them on a copy and compares.
* **Effective-dated history** instead of updates in place — answers "who was this person's manager on 3 March?" which is exactly what the reviewer-relationship rule needs.
* **Progress uses the target in force at the time of each check-in**, so a later re-baseline never rewrites the meaning of earlier updates.
* **Ground truth lives outside the database** and is only joined at evaluation time — no label leakage.
* **Simulated auth (`X-Actor-Id`)** keeps the demo friction-free; the permission logic is real and sits behind a single dependency that an SSO/JWT middleware can replace.
* **SQLite by default, PostgreSQL ready** — zero-setup for reviewers, with deferred/`use_alter` foreign keys so the `employees ↔ managers` cycle loads on both. Schema is created with `create_all`; a growing project would add Alembic migrations.
* **Pre-built UI committed** so the app runs with Python alone; CI rebuilds it from source.

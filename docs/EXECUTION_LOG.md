# Execution log

Real output from running every milestone end-to-end on a clean checkout
(Python 3.13.18, seed `20261022`, business date `2026-11-11`).
Re-run any step with the command shown; you should get byte-identical data.

---

## M1 — Generate synthetic data

```text
$ python manage.py generate --profile full
=== Generating 'full' dataset (seed 20261022) ===
  generated 249,470 rows in ~17s
  wrote 39 files to data/full
```

| Table | Rows |
|---|---:|
| employees | 3,000 |
| managers | 500 |
| manager_assignments | 3,131 |
| review_cycles | 3 |
| goals | 10,000 |
| key_results | 23,064 |
| goal_versions | 35,276 |
| checkins | 20,000 |
| kr_updates | 45,986 |
| evidence_links | 15,515 |
| competencies | 6 |
| peer_nominations | 16,745 |
| feedback | 54,135 |
| reviews | 5,668 |
| review_events | 14,983 |
| development_plans | 654 |
| plan_approvals | 804 |

Ground-truth labels written to `data/full/ground_truth/` (kept out of the input tables):

| Kind | Type | Labels |
|---|---|---:|
| anomaly | closed_cycle_silent_edit | 45 |
| anomaly | goal_owner_mismatch | 65 |
| anomaly | progress_over_scale_no_rationale | 50 |
| anomaly | reviewer_lacks_relationship | 65 |
| anomaly | untraceable_feedback | 40 |
| scenario | changed_goal | 1,226 |
| scenario | conflicting_feedback | 759 |
| scenario | incomplete_review | 311 |
| scenario | manager_transfer | 132 |
| scenario | overachievement_with_rationale | 1,102 |

---

## M2 — Validate and prove reproducibility

```text
$ python manage.py validate --profile full
  => PASS (27/27) report: data/full/validation_summary.md
```

| Check | Category | Rows checked | Violations | Explained | Unexplained | Status |
|---|---|---:|---:|---:|---:|---|
| primary_key_uniqueness | integrity | 249,470 | 0 | 0 | 0 | PASS |
| required_fields | integrity | 249,470 | 0 | 0 | 0 | PASS |
| allowed_values | integrity | 249,470 | 0 | 0 | 0 | PASS |
| id_conventions | integrity | 249,470 | 0 | 0 | 0 | PASS |
| numeric_ranges | integrity | 249,470 | 0 | 0 | 0 | PASS |
| unique_fields | duplicates | 249,470 | 0 | 0 | 0 | PASS |
| foreign_key_integrity | integrity | 249,470 | 0 | 0 | 0 | PASS |
| duplicate_business_keys | duplicates | 157,770 | 0 | 0 | 0 | PASS |
| date_ordering | dates | 97,395 | 0 | 0 | 0 | PASS |
| review_lifecycle | lifecycle | 5,668 | 0 | 0 | 0 | PASS |
| goal_lifecycle | lifecycle | 10,000 | 0 | 0 | 0 | PASS |
| cycle_lifecycle | lifecycle | 3 | 0 | 0 | 0 | PASS |
| derived_values_reconcile | reconciliation | 108,372 | 0 | 0 | 0 | PASS |
| goal_weights_sum_100 | reconciliation | 5,697 | 50 | 50 | 0 | PASS |
| kr_weights_sum_100 | reconciliation | 10,000 | 0 | 0 | 0 | PASS |
| kr_target_matches_history | reconciliation | 23,064 | 0 | 0 | 0 | PASS |
| department_matches_assignment | reconciliation | 3,000 | 0 | 0 | 0 | PASS |
| R1_goal_owner_matches | business_rule | 89,803 | 128 | 128 | 0 | PASS |
| R2_progress_within_scale_or_justified | business_rule | 89,803 | 50 | 50 | 0 | PASS |
| R3_reviewer_has_relationship | business_rule | 89,803 | 196 | 196 | 0 | PASS |
| R4_no_silent_edits_after_close | business_rule | 89,803 | 45 | 45 | 0 | PASS |
| R5_feedback_traceable | business_rule | 89,803 | 40 | 40 | 0 | PASS |
| ground_truth_separation | ground_truth | 17 | 0 | 0 | 0 | PASS |
| ground_truth_references | ground_truth | 3,795 | 0 | 0 | 0 | PASS |
| anomaly_label_coverage | ground_truth | 265 | 0 | 0 | 0 | PASS |
| scenario_coverage | coverage | 10 | 0 | 0 | 0 | PASS |
| volume_targets | coverage | 4 | 0 | 0 | 0 | PASS |

```text
$ python manage.py reproduce --profile full
=== Reproducibility check for 'full' (two runs, same seed) ===
  run 1/2 ...
  run 2/2 ...
  identical=True  files_compared=39  mismatched=[]
```

| File | SHA-256 run 1 | SHA-256 run 2 | Match |
|---|---|---|---|
| csv/checkins.csv | `1887c4c83e226867…` | `1887c4c83e226867…` | ✅ |
| csv/competencies.csv | `16d565a0a9fe487b…` | `16d565a0a9fe487b…` | ✅ |
| csv/development_plans.csv | `9005071908174fd2…` | `9005071908174fd2…` | ✅ |
| csv/employees.csv | `c50a3657db4671b6…` | `c50a3657db4671b6…` | ✅ |
| csv/evidence_links.csv | `2f189f5ef5fd3510…` | `2f189f5ef5fd3510…` | ✅ |
| csv/feedback.csv | `d680a961924d2e7c…` | `d680a961924d2e7c…` | ✅ |
| csv/goal_versions.csv | `7733978fde402281…` | `7733978fde402281…` | ✅ |
| csv/goals.csv | `9ee935b0ef0a10e7…` | `9ee935b0ef0a10e7…` | ✅ |
| csv/key_results.csv | `60a57a2c02fc3b2e…` | `60a57a2c02fc3b2e…` | ✅ |
| csv/kr_updates.csv | `ee19a7cd17047268…` | `ee19a7cd17047268…` | ✅ |
| csv/manager_assignments.csv | `8ff1e193c679964f…` | `8ff1e193c679964f…` | ✅ |
| csv/managers.csv | `ccff26d7037cd58f…` | `ccff26d7037cd58f…` | ✅ |
| csv/peer_nominations.csv | `0ea2bba67966b9dc…` | `0ea2bba67966b9dc…` | ✅ |
| csv/plan_approvals.csv | `c08752629b124e09…` | `c08752629b124e09…` | ✅ |
| csv/review_cycles.csv | `685128488306e35e…` | `685128488306e35e…` | ✅ |
| csv/review_events.csv | `d851cab104591f69…` | `d851cab104591f69…` | ✅ |
| csv/reviews.csv | `841d95059d95bd6a…` | `841d95059d95bd6a…` | ✅ |
| ground_truth/ground_truth.csv | `441d11a82385f288…` | `441d11a82385f288…` | ✅ |
| ground_truth/ground_truth.json | `ccfaf5e3fe8f56af…` | `ccfaf5e3fe8f56af…` | ✅ |
| ground_truth/review_outcomes.csv | `b2706e5e645352cf…` | `b2706e5e645352cf…` | ✅ |
| json/checkins.json | `1c8a548900e5ab02…` | `1c8a548900e5ab02…` | ✅ |
| json/competencies.json | `87a640fe0e8a3289…` | `87a640fe0e8a3289…` | ✅ |
| json/development_plans.json | `3171c020d4236545…` | `3171c020d4236545…` | ✅ |
| json/employees.json | `611a2cafc4a664fb…` | `611a2cafc4a664fb…` | ✅ |
| json/evidence_links.json | `a2c0f3c546c77299…` | `a2c0f3c546c77299…` | ✅ |
| json/feedback.json | `b4022620185f1f52…` | `b4022620185f1f52…` | ✅ |
| json/goal_versions.json | `cf85bb601505ef56…` | `cf85bb601505ef56…` | ✅ |
| json/goals.json | `b139c8fb10b9b211…` | `b139c8fb10b9b211…` | ✅ |
| json/key_results.json | `d2b8fa942e346c0c…` | `d2b8fa942e346c0c…` | ✅ |
| json/kr_updates.json | `8e71521dcd855e8c…` | `8e71521dcd855e8c…` | ✅ |
| json/manager_assignments.json | `9d4d1c89244a5d6f…` | `9d4d1c89244a5d6f…` | ✅ |
| json/managers.json | `6254dbfc6d4e9cee…` | `6254dbfc6d4e9cee…` | ✅ |
| json/peer_nominations.json | `fc4f398a0040e0b9…` | `fc4f398a0040e0b9…` | ✅ |
| json/plan_approvals.json | `4e091498bfdb64fb…` | `4e091498bfdb64fb…` | ✅ |
| json/review_cycles.json | `07c202548febaeed…` | `07c202548febaeed…` | ✅ |
| json/review_events.json | `7ae17af553dbd5c5…` | `7ae17af553dbd5c5…` | ✅ |
| json/reviews.json | `ff9283247cbe8eb1…` | `ff9283247cbe8eb1…` | ✅ |
| sql/seed_postgres.sql | `5fc08b840bfd8007…` | `5fc08b840bfd8007…` | ✅ |
| sql/seed_sqlite.sql | `8e04fe95369cf640…` | `8e04fe95369cf640…` | ✅ |

---

## M3 — Load the database

```text
$ python manage.py load --profile full
  loaded employees              3,000 rows
  loaded managers                 500 rows
  ...
  loaded plan_approvals           804 rows
  database ready in 3.0s (sqlite)
```

Also verified against **PostgreSQL 16**: loader (run twice — idempotent), all read endpoints, a write, and the
standalone `seed_postgres.sql` (41 foreign keys added and validated after insert). `seed_sqlite.sql` loads with
`PRAGMA foreign_keys=ON` and passes `PRAGMA foreign_key_check`.

---

## M4 — Backend API: every acceptance rule exercised live

```text
$ python manage.py serve
```

| Scenario | HTTP | Result |
|---|---:|---|
| Check-in with no X-Actor-Id | 401 | X-Actor-Id header is required for write operations |
| Check-in by HR partner (not owner/manager) | 403 | goal owner mismatch: only the goal owner or their current manager can check in |
| Check-in at 130% without rationale | 422 | progress exceeds 100% of target; an over_scale_rationale is required |
| Check-in at 130% with rationale | 201 | goal progress = 120.0% |
| Check-in at 80% by the manager | 201 | goal progress = 80.0% |
| KR target change without rationale | 422 | changing a key-result target requires a rationale |
| KR target change with rationale | 200 | version v5 saved |
| Edit closed-cycle goal (owner) | 409 | CYCLE-2026-H1 is closed; only HR partners/admins can make an approved correction |
| Post-close correction by HR, no rationale | 422 | post-close corrections require a rationale |
| Post-close correction by HR with rationale | 200 | version v6 saved |
| Manager feedback from HR (no relationship) | 403 | reviewer lacks relationship for manager feedback |
| Peer feedback without nomination | 403 | reviewer lacks relationship for peer feedback |
| Finalize a not-started review | 409 | cannot move review from not_started to finalized |

| Detector | Labels | Findings | Precision | Recall |
|---|---:|---:|---:|---:|
| closed_cycle_silent_edit | 45 | 45 | 1.00 | 1.00 |
| goal_owner_mismatch | 65 | 128 | 1.00 | 1.00 |
| progress_over_scale_no_rationale | 50 | 50 | 1.00 | 1.00 |
| reviewer_lacks_relationship | 65 | 196 | 1.00 | 1.00 |
| untraceable_feedback | 40 | 40 | 1.00 | 1.00 |

---

## M5 — Frontend

Built with `npm run build` (209 kB JS / 65 kB gzipped) and rendered in headless Chrome against the full dataset:
6 screens, **0 console errors**. Screenshots in [`screenshots/`](screenshots/).

---

## M6 — Automated tests

```text
$ python manage.py test
42 passed
```

```text
tests/test_api.py::test_health_meta_and_metrics PASSED
tests/test_api.py::test_employee_detail_has_hierarchy_and_history PASSED
tests/test_api.py::test_quality_detectors_match_ground_truth PASSED
tests/test_api.py::test_checkin_requires_identity_and_ownership PASSED
tests/test_api.py::test_progress_is_derived_and_over_scale_needs_rationale PASSED
tests/test_api.py::test_checkin_must_cover_every_key_result PASSED
tests/test_api.py::test_target_change_is_versioned_and_needs_rationale PASSED
tests/test_api.py::test_closed_cycle_rejects_silent_edits PASSED
tests/test_api.py::test_feedback_permissions_follow_relationships PASSED
tests/test_api.py::test_review_cannot_finalize_without_required_inputs PASSED
tests/test_api.py::test_development_plan_approval_flow PASSED
tests/test_api.py::test_leadership_competency_only_for_managers PASSED
tests/test_data_generation.py::test_validation_suite_passes PASSED
tests/test_data_generation.py::test_volumes_follow_scale PASSED
tests/test_data_generation.py::test_every_anomaly_and_scenario_is_labelled PASSED
tests/test_data_generation.py::test_ground_truth_never_leaks_into_inputs PASSED
tests/test_data_generation.py::test_ids_are_consistent_across_files PASSED
tests/test_data_generation.py::test_progress_derives_from_key_results PASSED
tests/test_data_generation.py::test_same_seed_is_byte_identical_and_new_seed_differs PASSED
tests/test_data_generation.py::test_loader_is_idempotent PASSED
tests/test_rules.py::test_kr_raw_progress[0-10-5-50.0] PASSED
tests/test_rules.py::test_kr_raw_progress[500-300-400-50.0] PASSED
tests/test_rules.py::test_kr_raw_progress[0-10-15-150.0] PASSED
tests/test_rules.py::test_kr_raw_progress[0-10--2--20.0] PASSED
tests/test_rules.py::test_scoring_cap_depends_on_rationale PASSED
tests/test_rules.py::test_goal_progress_is_weighted PASSED
tests/test_rules.py::test_goal_score_excludes_inactive_goals_and_renormalises PASSED
tests/test_rules.py::test_target_at_uses_target_in_force_at_the_time PASSED
tests/test_rules.py::test_rating_bands[4.6-Exceptional] PASSED
tests/test_rules.py::test_rating_bands[4.0-Exceeds] PASSED
tests/test_rules.py::test_rating_bands[3.0-Meets] PASSED
tests/test_rules.py::test_rating_bands[2.2-Partially Meets] PASSED
tests/test_rules.py::test_rating_bands[1.5-Below] PASSED
tests/test_rules.py::test_rating_bands[None-None] PASSED
tests/test_rules.py::test_overall_requires_both_components PASSED
tests/test_rules.py::test_review_completeness_lists_every_missing_input PASSED
tests/test_rules.py::test_lifecycle_transitions PASSED
tests/test_rules.py::test_plan_status_derives_from_approvals PASSED
tests/test_rules.py::test_mandatory_plan_rule PASSED
tests/test_rules.py::test_silent_post_close_edit PASSED
tests/test_schema_parity.py::test_orm_matches_data_dictionary PASSED
```

---

## Issues found and fixed during execution

| Found by | Problem | Fix |
|---|---|---|
| Validator (`date_ordering`) | Goals approved in December produced check-ins before the cycle started | check-in window now starts at `max(cycle start, approval + 7 days)` |
| Validator (`review_lifecycle`) | Goal-owner anomaly could move someone's *only* goal, leaving a finalized review with no goals (a side-effect on an unlabelled row) | anomaly only targets owners with ≥ 2 active goals |
| Validator (`goal_weights_sum_100`) | Ground-truth `related_ids` used `\|` as separator, colliding with `EMP\|CYCLE` keys | separator changed to `;` |
| Distribution review | 68% of reviews triggered development plans — unrealistic | rule tightened (any rating 1, or two ≤ 2) and ratings recentred → 26% |
| PostgreSQL run | Inline FK to a table created later is rejected by PostgreSQL | dialect-specific seeds; PostgreSQL adds FKs with `ALTER TABLE` after insert |
| Reload test | Second `load` on SQLite failed dropping the `employees ↔ managers` FK cycle | FK checks disabled only during `drop_all`; regression test added |
| API test | Leadership competency could be rated for non-managers | API now returns `422` |
| Cross-machine run (laptop, Python 3.10 vs cloud, Python 3.13) | 2 goals and 5 check-ins differed by 0.01: Python 3.12+ `sum()` is more precise, flipping values that sit exactly on a rounding half-point | averages use `math.fsum` (exactly rounded, version-independent); golden-fingerprint test added |
| Laptop sandbox (files cannot be deleted) | Generator wiped the output folder with `rmtree` before writing | files are overwritten in place; manifest lists exactly the files this run wrote |
| Laptop test run | API tests copied the template SQLite file with a plain file copy, which is not a consistent snapshot under WAL | fixture uses SQLite's backup API |
| Laptop test run | Importing `backend.app.main` created the app and opened the default database as a side effect; WAL failed on a shared folder | app is created lazily (`uvicorn backend.app.main:app` unchanged); WAL is best-effort with fallback |

---

## Re-run on the target laptop (Windows host, Python 3.10 sandbox)

The same pipeline was executed directly on the delivery machine in `C:\CandidateWorkspace`:

| Step | Result |
|---|---|
| `python manage.py generate --profile full` | 249,470 rows, 39 files |
| Dataset fingerprint vs cloud (Python 3.13) | **identical** (`full e673746558bc9b9f`, `starter 2c8923bbd3dfd7fd`) |
| `python manage.py validate --profile full` | PASS 27/27 |
| `python manage.py reproduce --profile starter` | identical=True, 39 files |
| `python manage.py load --profile full` (run twice) | ready in 9.5 s / 9.7 s |
| Live API: 13 rule scenarios | all as expected (401/403/422/201/200/409) |
| Detectors vs ground truth | precision 1.00 / recall 1.00 for all 5 issue types |
| `python -m pytest` | **42 passed** |

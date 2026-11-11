# Validation summary - `starter` dataset

**Overall: PASS** - 27/27 checks passed (seed `20261022`, as-of `2026-11-11`)

A violation is *explained* when it touches an entity that was deliberately labelled in `ground_truth/`. Any *unexplained* violation fails the run.

| Check | Category | Rows checked | Violations | Explained | Unexplained | Status |
|---|---|---:|---:|---:|---:|---|
| primary_key_uniqueness | integrity | 12,417 | 0 | 0 | 0 | PASS |
| required_fields | integrity | 12,417 | 0 | 0 | 0 | PASS |
| allowed_values | integrity | 12,417 | 0 | 0 | 0 | PASS |
| id_conventions | integrity | 12,417 | 0 | 0 | 0 | PASS |
| numeric_ranges | integrity | 12,417 | 0 | 0 | 0 | PASS |
| unique_fields | duplicates | 12,417 | 0 | 0 | 0 | PASS |
| foreign_key_integrity | integrity | 12,417 | 0 | 0 | 0 | PASS |
| duplicate_business_keys | duplicates | 7,845 | 0 | 0 | 0 | PASS |
| date_ordering | dates | 4,816 | 0 | 0 | 0 | PASS |
| review_lifecycle | lifecycle | 284 | 0 | 0 | 0 | PASS |
| goal_lifecycle | lifecycle | 500 | 0 | 0 | 0 | PASS |
| cycle_lifecycle | lifecycle | 3 | 0 | 0 | 0 | PASS |
| derived_values_reconcile | reconciliation | 5,402 | 0 | 0 | 0 | PASS |
| goal_weights_sum_100 | reconciliation | 285 | 6 | 6 | 0 | PASS |
| kr_weights_sum_100 | reconciliation | 500 | 0 | 0 | 0 | PASS |
| kr_target_matches_history | reconciliation | 1,140 | 0 | 0 | 0 | PASS |
| department_matches_assignment | reconciliation | 150 | 0 | 0 | 0 | PASS |
| R1_goal_owner_matches | business_rule | 4,443 | 11 | 11 | 0 | PASS |
| R2_progress_within_scale_or_justified | business_rule | 4,443 | 3 | 3 | 0 | PASS |
| R3_reviewer_has_relationship | business_rule | 4,443 | 23 | 23 | 0 | PASS |
| R4_no_silent_edits_after_close | business_rule | 4,443 | 6 | 6 | 0 | PASS |
| R5_feedback_traceable | business_rule | 4,443 | 3 | 3 | 0 | PASS |
| ground_truth_separation | ground_truth | 17 | 0 | 0 | 0 | PASS |
| ground_truth_references | ground_truth | 189 | 0 | 0 | 0 | PASS |
| anomaly_label_coverage | ground_truth | 24 | 0 | 0 | 0 | PASS |
| scenario_coverage | coverage | 10 | 0 | 0 | 0 | PASS |
| volume_targets | coverage | 4 | 0 | 0 | 0 | PASS |

## Rule detectors vs ground truth

| Issue type | Labels | Findings | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| closed_cycle_silent_edit | 6 | 6 | 1.000 | 1.000 | 1.000 |
| goal_owner_mismatch | 6 | 11 | 1.000 | 1.000 | 1.000 |
| progress_over_scale_no_rationale | 3 | 3 | 1.000 | 1.000 | 1.000 |
| reviewer_lacks_relationship | 6 | 23 | 1.000 | 1.000 | 1.000 |
| untraceable_feedback | 3 | 3 | 1.000 | 1.000 | 1.000 |

## Row counts

| Table | Rows |
|---|---:|
| employees | 150 |
| managers | 25 |
| manager_assignments | 152 |
| review_cycles | 3 |
| goals | 500 |
| key_results | 1,140 |
| goal_versions | 1,786 |
| checkins | 1,000 |
| kr_updates | 2,296 |
| evidence_links | 776 |
| competencies | 6 |
| peer_nominations | 823 |
| feedback | 2,659 |
| reviews | 284 |
| review_events | 749 |
| development_plans | 32 |
| plan_approvals | 36 |

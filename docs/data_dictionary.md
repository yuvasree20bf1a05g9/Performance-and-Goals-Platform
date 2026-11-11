# Data dictionary

> Auto-generated from `domain/schema.py` by `python manage.py generate`. Do not edit by hand.

Legend: **PK** primary key, **FK** foreign key, **U** unique, **D** derived (calculated from other records, never random), **Req** required.

## Tables

### `employees` - Employee (master)

Every person in the organisation (managers are also employees).

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `employee_id` | string | yes | PK | pattern `^EMP-\d{6}$` |  | Immutable employee key |
| `first_name` | string | yes |  |  |  |  |
| `last_name` | string | yes |  |  |  |  |
| `email` | string | yes | U |  |  | Synthetic address on example.com |
| `department` | string | yes |  | `Engineering`, `Sales`, `Customer Success`, `Operations`, `Product`, `Marketing`, `Finance`, `HR` |  | Current department |
| `job_title` | string | yes |  |  |  |  |
| `job_level` | string | yes |  | `L1`, `L2`, `L3`, `L4`, `L5`, `L6`, `L7`, `L8` |  |  |
| `role` | string | yes |  | `employee`, `manager`, `hr_partner`, `it_ops`, `admin`, `executive` |  | System role used for permissions |
| `location` | string | yes |  | `Bengaluru`, `Hyderabad`, `Pune`, `Chennai`, `Remote-IN`, `London`, `Austin` |  |  |
| `hire_date` | date | yes |  |  |  |  |
| `termination_date` | date | no |  |  |  | >= hire_date when present |
| `employment_status` | string | yes |  | `active`, `on_leave`, `terminated` |  |  |
| `current_manager_id` | string | no | FK -> `managers.manager_id` D |  |  | Derived from the open manager_assignments row; null only for the CEO |

### `managers` - Manager (master)

Manager profile; 1:1 subtype of Employee.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `manager_id` | string | yes | PK FK -> `employees.employee_id` | pattern `^EMP-\d{6}$` |  | Same value as the employee_id of the manager |
| `management_level` | string | yes |  | `line_manager`, `director`, `vp`, `executive` |  |  |
| `max_span` | integer | yes |  | [1 .. 60] |  | Maximum direct reports allowed |
| `manager_since` | date | yes |  |  |  |  |
| `is_active` | boolean | yes |  |  |  |  |

### `manager_assignments` - ManagerAssignment (event)

Effective-dated reporting line history (manager transfers are new rows, never overwrites).

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `assignment_id` | string | yes | PK | pattern `^MA-\d{6}$` |  |  |
| `employee_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `manager_id` | string | yes | FK -> `managers.manager_id` |  |  |  |
| `department` | string | yes |  | `Engineering`, `Sales`, `Customer Success`, `Operations`, `Product`, `Marketing`, `Finance`, `HR` |  | Department during this assignment |
| `effective_from` | date | yes |  |  |  |  |
| `effective_to` | date | no |  |  |  | Null = currently effective |
| `change_reason` | string | yes |  | `initial`, `new_hire`, `transfer`, `reorg` |  |  |

### `review_cycles` - ReviewCycle (master)

Half-yearly performance cycles and their lifecycle state.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `cycle_id` | string | yes | PK | pattern `^CYCLE-\d{4}-H[12]$` |  |  |
| `name` | string | yes |  |  |  |  |
| `start_date` | date | yes |  |  |  |  |
| `end_date` | date | yes |  |  |  |  |
| `goal_setting_deadline` | date | yes |  |  |  |  |
| `review_deadline` | date | yes |  |  |  |  |
| `status` | string | yes |  | `planned`, `active`, `calibration`, `closed` |  |  |
| `closed_at` | datetime | no |  |  |  | Set when status = closed; edits after this are locked |

### `goals` - Goal (master)

Employee goals per cycle.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `goal_id` | string | yes | PK | pattern `^GOAL-EMP-\d{6}-\d{3}$` |  | GOAL-<owner employee_id>-NNN |
| `employee_id` | string | yes | FK -> `employees.employee_id` |  |  | Goal owner |
| `cycle_id` | string | yes | FK -> `review_cycles.cycle_id` |  |  |  |
| `title` | string | yes |  |  |  |  |
| `category` | string | yes |  | `business`, `customer`, `operational`, `team`, `development` |  |  |
| `weight_pct` | integer | yes |  | [5 .. 100] | percent | Weights of an owner's goals in a cycle sum to 100 |
| `status` | string | yes |  | `draft`, `pending_approval`, `in_progress`, `closed`, `cancelled` |  |  |
| `approved_by` | string | no | FK -> `managers.manager_id` |  |  |  |
| `approved_at` | datetime | no |  |  |  |  |
| `created_at` | datetime | yes |  |  |  |  |
| `current_version` | integer | yes | D | [1 .. ] |  | = max(goal_versions.version_no) |
| `progress_pct` | decimal | yes | D | [0 .. 120] | percent | Weighted average of key-result scoring progress |

### `key_results` - KeyResult (master)

Measurable key results of a goal.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `kr_id` | string | yes | PK | pattern `^KR-GOAL-EMP-\d{6}-\d{3}-\d{2}$` |  | KR-<goal_id>-NN |
| `goal_id` | string | yes | FK -> `goals.goal_id` |  |  |  |
| `description` | string | yes |  |  |  |  |
| `metric_type` | string | yes |  | `count`, `percentage`, `currency`, `duration` |  |  |
| `unit` | string | yes |  |  |  |  |
| `direction` | string | yes |  | `increase`, `decrease` |  |  |
| `start_value` | decimal | yes |  |  |  |  |
| `target_value` | decimal | yes |  |  |  | Current target; history in goal_versions |
| `weight_pct` | integer | yes |  | [1 .. 100] | percent | KR weights sum to 100 per goal |
| `current_value` | decimal | yes | D |  |  | Latest kr_updates.reported_value, else start_value |
| `raw_progress_pct` | decimal | yes | D |  | percent | Uncapped progress |
| `scoring_progress_pct` | decimal | yes | D | [0 .. 120] | percent | Capped at 100, or 120 when an over-scale rationale exists |

### `goal_versions` - GoalVersion (event)

Append-only change history for goals and key results.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `version_id` | string | yes | PK | pattern `^GV-\d{7}$` |  |  |
| `goal_id` | string | yes | FK -> `goals.goal_id` |  |  |  |
| `kr_id` | string | no | FK -> `key_results.kr_id` |  |  |  |
| `version_no` | integer | yes |  | [1 .. ] |  |  |
| `change_type` | string | yes |  | `created`, `status_changed`, `target_changed`, `title_changed`, `post_close_correction` |  |  |
| `field_name` | string | no |  |  |  |  |
| `old_value` | string | no |  |  |  |  |
| `new_value` | string | no |  |  |  |  |
| `changed_by` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `changed_at` | datetime | yes |  |  |  |  |
| `rationale` | string | no |  |  |  |  |
| `approved_by` | string | no | FK -> `employees.employee_id` |  |  |  |

### `checkins` - CheckIn (transaction)

Periodic goal check-ins.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `checkin_id` | string | yes | PK | pattern `^CHK-\d{7}$` |  |  |
| `goal_id` | string | yes | FK -> `goals.goal_id` |  |  |  |
| `cycle_id` | string | yes | FK -> `review_cycles.cycle_id` |  |  |  |
| `submitted_by` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `checkin_date` | date | yes |  |  |  |  |
| `sequence_no` | integer | yes |  | [1 .. ] |  |  |
| `confidence` | string | yes |  | `low`, `medium`, `high` |  |  |
| `note` | string | yes |  |  |  |  |
| `goal_progress_pct` | decimal | yes | D |  | percent | Goal progress snapshot as of this check-in |

### `kr_updates` - KeyResultUpdate (transaction)

Key-result values reported inside a check-in.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `update_id` | string | yes | PK | pattern `^KRU-\d{7}$` |  |  |
| `checkin_id` | string | yes | FK -> `checkins.checkin_id` |  |  |  |
| `kr_id` | string | yes | FK -> `key_results.kr_id` |  |  |  |
| `reported_value` | decimal | yes |  |  |  |  |
| `raw_progress_pct` | decimal | yes | D |  | percent | Against the target effective on the check-in date |
| `over_scale_rationale` | string | no |  |  |  | Mandatory when raw progress > 100 |

### `evidence_links` - EvidenceLink (transaction)

Evidence attached to check-ins.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `evidence_id` | string | yes | PK | pattern `^EVD-\d{7}$` |  |  |
| `checkin_id` | string | yes | FK -> `checkins.checkin_id` |  |  |  |
| `kr_id` | string | no | FK -> `key_results.kr_id` |  |  |  |
| `evidence_type` | string | yes |  | `document`, `dashboard`, `ticket`, `repository`, `crm_record` |  |  |
| `uri` | string | yes |  |  |  |  |
| `added_by` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `added_at` | datetime | yes |  |  |  |  |

### `competencies` - Competency (reference)

Competency framework.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `competency_id` | string | yes | PK | pattern `^COMP-\d{2}$` |  |  |
| `name` | string | yes | U |  |  |  |
| `category` | string | yes |  | `core`, `technical`, `leadership` |  |  |
| `description` | string | yes |  |  |  |  |
| `scale_min` | integer | yes |  |  |  |  |
| `scale_max` | integer | yes |  |  |  |  |
| `applies_to` | string | yes |  | `all`, `managers` |  |  |

### `peer_nominations` - PeerNomination (bridge)

N:M bridge between employees (subject <-> peer) per cycle.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `nomination_id` | string | yes | PK | pattern `^PN-\d{7}$` |  |  |
| `cycle_id` | string | yes | FK -> `review_cycles.cycle_id` |  |  |  |
| `subject_employee_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `peer_employee_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `nominated_by` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `status` | string | yes |  | `accepted`, `declined` |  |  |
| `nominated_at` | datetime | yes |  |  |  |  |

### `feedback` - Feedback (transaction)

Self / manager / peer competency feedback.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `feedback_id` | string | yes | PK | pattern `^FB-\d{4}-\d{7}$` |  |  |
| `cycle_id` | string | yes | FK -> `review_cycles.cycle_id` |  |  |  |
| `subject_employee_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `giver_employee_id` | string | no | FK -> `employees.employee_id` |  |  | Must be present for traceability |
| `feedback_type` | string | yes |  | `self`, `manager`, `peer` |  |  |
| `competency_id` | string | yes | FK -> `competencies.competency_id` |  |  |  |
| `rating` | integer | yes |  | [1 .. 5] |  |  |
| `comment` | string | yes |  |  |  |  |
| `linked_goal_id` | string | no | FK -> `goals.goal_id` |  |  |  |
| `source` | string | yes |  | `in_app`, `imported_survey`, `email` |  |  |
| `submitted_at` | datetime | yes |  |  |  |  |

### `reviews` - Review (transaction)

One review per employee per cycle.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `review_id` | string | yes | PK | pattern `^REV-\d{4}-\d{6}$` |  |  |
| `cycle_id` | string | yes | FK -> `review_cycles.cycle_id` |  |  |  |
| `employee_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `reviewer_id` | string | yes | FK -> `managers.manager_id` |  |  |  |
| `status` | string | yes |  | `not_started`, `self_submitted`, `manager_submitted`, `finalized` |  |  |
| `self_submitted_at` | datetime | no |  |  |  |  |
| `manager_submitted_at` | datetime | no |  |  |  |  |
| `finalized_at` | datetime | no |  |  |  |  |
| `manager_summary` | string | no |  |  |  |  |
| `goal_score_pct` | decimal | no | D |  | percent |  |
| `goal_rating` | decimal | no | D | [1 .. 5] |  |  |
| `competency_rating` | decimal | no | D | [1 .. 5] |  |  |
| `overall_score` | decimal | no | D | [1 .. 5] |  |  |
| `overall_rating` | string | no | D | `Exceptional`, `Exceeds`, `Meets`, `Partially Meets`, `Below` |  |  |
| `is_complete` | boolean | yes | D |  |  |  |
| `missing_inputs` | string | no | D |  |  | Semicolon list |

### `review_events` - ReviewEvent (event)

Append-only review history.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `event_id` | string | yes | PK | pattern `^REVEV-\d{7}$` |  |  |
| `review_id` | string | yes | FK -> `reviews.review_id` |  |  |  |
| `event_type` | string | yes |  | `status_change`, `comment_edit` |  |  |
| `from_status` | string | no |  | `not_started`, `self_submitted`, `manager_submitted`, `finalized` |  |  |
| `to_status` | string | no |  | `not_started`, `self_submitted`, `manager_submitted`, `finalized` |  |  |
| `field_name` | string | no |  |  |  |  |
| `old_value` | string | no |  |  |  |  |
| `new_value` | string | no |  |  |  |  |
| `actor_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `occurred_at` | datetime | yes |  |  |  |  |
| `rationale` | string | no |  |  |  |  |
| `approved_by` | string | no | FK -> `employees.employee_id` |  |  |  |

### `development_plans` - DevelopmentPlan (transaction)

Development plans arising from reviews.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `plan_id` | string | yes | PK | pattern `^DP-\d{4}-\d{6}$` |  |  |
| `employee_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `cycle_id` | string | yes | FK -> `review_cycles.cycle_id` |  |  |  |
| `review_id` | string | yes | FK -> `reviews.review_id` |  |  |  |
| `competency_id` | string | yes | FK -> `competencies.competency_id` |  |  |  |
| `objective` | string | yes |  |  |  |  |
| `training_cost` | decimal | yes |  | [0 .. ] | USD |  |
| `requires_hr_approval` | boolean | yes | D |  |  | training_cost > 1000 |
| `target_date` | date | yes |  |  |  |  |
| `created_at` | datetime | yes |  |  |  |  |
| `completed_at` | datetime | no |  |  |  | Set when the employee completes the plan |
| `status` | string | yes | D | `draft`, `submitted`, `approved`, `rejected`, `completed` |  | Derived from plan_approvals and completed_at |

### `plan_approvals` - PlanApproval (event)

Approval steps for development plans.

| Field | Type | Req | Keys | Allowed values / range | Unit | Description |
|---|---|---|---|---|---|---|
| `approval_id` | string | yes | PK | pattern `^DPA-\d{6}$` |  |  |
| `plan_id` | string | yes | FK -> `development_plans.plan_id` |  |  |  |
| `approver_id` | string | yes | FK -> `employees.employee_id` |  |  |  |
| `approver_role` | string | yes |  | `manager`, `hr_partner` |  |  |
| `decision` | string | yes |  | `pending`, `approved`, `rejected` |  |  |
| `decided_at` | datetime | no |  |  |  |  |
| `comment` | string | no |  |  |  |  |

## Relationships and cardinality

| From | To | Cardinality | Notes |
|---|---|---|---|
| `employees` | `managers` | 1:0..1 | An employee may be a manager (subtype) |
| `managers` | `employees` | 1:N | Manager has many direct reports (current_manager_id) |
| `employees` | `manager_assignments` | 1:N | Effective-dated reporting history |
| `employees` | `goals` | 1:N | Owner of goals |
| `review_cycles` | `goals` | 1:N | Goals belong to one cycle |
| `goals` | `key_results` | 1:N (1..4) | Each goal has 1-4 key results |
| `goals` | `goal_versions` | 1:N | Append-only version history |
| `goals` | `checkins` | 1:N | Periodic check-ins |
| `checkins` | `kr_updates` | 1:N | One update per key result per check-in |
| `checkins` | `evidence_links` | 1:N (0..n) | Optional evidence |
| `employees` | `employees` | N:M via peer_nominations | Peer reviewer relationships per cycle |
| `employees` | `feedback` | 1:N | Subject and giver of feedback |
| `competencies` | `feedback` | 1:N | Feedback is per competency |
| `employees` | `reviews` | 1:N (1 per cycle) | Unique (employee_id, cycle_id) |
| `reviews` | `review_events` | 1:N | Append-only status/edit history |
| `reviews` | `development_plans` | 1:N (0..n) | Plans created from a review |
| `development_plans` | `plan_approvals` | 1:N (1..2) | Manager + optional HR approval |

## Derivation rules

| Value | Rule |
|---|---|
| KR raw progress | `(value - start) / (target_effective_at_checkin - start) * 100` (works for decrease KRs) |
| KR scoring progress | clamp to [0, 100], or [0, 120] when the latest update carries an over-scale rationale |
| Goal progress | KR-weighted average of scoring progress |
| Review goal score | goal-weighted average of active goals (draft / pending / cancelled excluded, weights re-normalised) |
| Goal rating | `1 + 4 * min(goal_score, 100) / 100` |
| Competency rating | mean of the reviewer's manager ratings on required competencies |
| Overall score | `0.6 * goal_rating + 0.4 * competency_rating` - only when complete |
| Overall rating | >=4.5 Exceptional, >=3.75 Exceeds, >=2.75 Meets, >=2.0 Partially Meets, else Below |
| Review complete | full self assessment + full reviewer assessment + >=1 check-in on every active goal |
| Plan requires HR | `training_cost > 1000` |
| Mandatory development plan | any competency rated 1, or two or more rated <= 2 (otherwise optional) |
| Plan status | draft (no approvals) / rejected (any) / approved (all required) / completed (approved + completed_at) / submitted |

## Lifecycle states

* **Review cycle:** planned -> active -> calibration -> closed (closed cycles are edit-locked).
* **Goal:** draft -> pending_approval -> in_progress -> closed; cancel allowed from any non-terminal state.
* **Review:** not_started -> self_submitted -> manager_submitted -> finalized (finalize requires completeness).
* **Manager assignment:** effective-dated; a transfer closes the old row and opens a new one.
* **Development plan:** draft -> submitted -> approved / rejected -> completed.

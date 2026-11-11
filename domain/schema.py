"""Single source of truth for the data model (the data dictionary).

Every table, field, type, allowed value, uniqueness rule and foreign key is
declared once here. The generator, the validator, the SQL seed exporter, the
docs builder and a backend parity test all read from this module, so the
schema can never silently drift between layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Enumerations (allowed values)                                               #
# --------------------------------------------------------------------------- #
DEPARTMENTS = ["Engineering", "Sales", "Customer Success", "Operations",
               "Product", "Marketing", "Finance", "HR"]
LOCATIONS = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Remote-IN", "London", "Austin"]
JOB_LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"]
EMPLOYEE_ROLES = ["employee", "manager", "hr_partner", "it_ops", "admin", "executive"]
EMPLOYMENT_STATUSES = ["active", "on_leave", "terminated"]
MANAGEMENT_LEVELS = ["line_manager", "director", "vp", "executive"]
ASSIGNMENT_REASONS = ["initial", "new_hire", "transfer", "reorg"]
CYCLE_STATUSES = ["planned", "active", "calibration", "closed"]
GOAL_CATEGORIES = ["business", "customer", "operational", "team", "development"]
GOAL_STATUSES = ["draft", "pending_approval", "in_progress", "closed", "cancelled"]
METRIC_TYPES = ["count", "percentage", "currency", "duration"]
DIRECTIONS = ["increase", "decrease"]
GOAL_CHANGE_TYPES = ["created", "status_changed", "target_changed", "title_changed",
                     "post_close_correction"]
CONFIDENCE_LEVELS = ["low", "medium", "high"]
EVIDENCE_TYPES = ["document", "dashboard", "ticket", "repository", "crm_record"]
COMPETENCY_CATEGORIES = ["core", "technical", "leadership"]
COMPETENCY_APPLIES_TO = ["all", "managers"]
NOMINATION_STATUSES = ["accepted", "declined"]
FEEDBACK_TYPES = ["self", "manager", "peer"]
FEEDBACK_SOURCES = ["in_app", "imported_survey", "email"]
REVIEW_STATUSES = ["not_started", "self_submitted", "manager_submitted", "finalized"]
RATING_LABELS = ["Exceptional", "Exceeds", "Meets", "Partially Meets", "Below"]
REVIEW_EVENT_TYPES = ["status_change", "comment_edit"]
PLAN_STATUSES = ["draft", "submitted", "approved", "rejected", "completed"]
APPROVER_ROLES = ["manager", "hr_partner"]
APPROVAL_DECISIONS = ["pending", "approved", "rejected"]

# Ground-truth vocabulary (lives ONLY in ground_truth/, never in input tables)
ANOMALY_TYPES = ["goal_owner_mismatch", "progress_over_scale_no_rationale",
                 "reviewer_lacks_relationship", "closed_cycle_silent_edit",
                 "untraceable_feedback"]
SCENARIO_TYPES = ["changed_goal", "manager_transfer", "incomplete_review",
                  "conflicting_feedback", "overachievement_with_rationale"]

# --------------------------------------------------------------------------- #
# Field / table descriptors                                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Field:
    name: str
    type: str                       # string | integer | decimal | boolean | date | datetime
    required: bool = True
    description: str = ""
    allowed: Optional[list] = None
    unique: bool = False
    fk: Optional[str] = None        # "table.column"
    pattern: Optional[str] = None   # regex for IDs
    unit: Optional[str] = None
    derived: bool = False           # calculated from other records, never random
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass(frozen=True)
class Table:
    name: str
    entity: str
    pk: str
    description: str
    kind: str                      # master | transaction | event | bridge | reference
    fields: list = field(default_factory=list)

    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]

    def get(self, name: str) -> Field:
        return next(f for f in self.fields if f.name == name)


F = Field
EMP_ID = r"^EMP-\d{6}$"
CYCLE_ID = r"^CYCLE-\d{4}-H[12]$"
GOAL_ID = r"^GOAL-EMP-\d{6}-\d{3}$"
KR_ID = r"^KR-GOAL-EMP-\d{6}-\d{3}-\d{2}$"
REV_ID = r"^REV-\d{4}-\d{6}$"

TABLES: list[Table] = [
    Table("employees", "Employee", "employee_id",
          "Every person in the organisation (managers are also employees).", "master", [
              F("employee_id", "string", unique=True, pattern=EMP_ID, description="Immutable employee key"),
              F("first_name", "string"),
              F("last_name", "string"),
              F("email", "string", unique=True, description="Synthetic address on example.com"),
              F("department", "string", allowed=DEPARTMENTS, description="Current department"),
              F("job_title", "string"),
              F("job_level", "string", allowed=JOB_LEVELS),
              F("role", "string", allowed=EMPLOYEE_ROLES, description="System role used for permissions"),
              F("location", "string", allowed=LOCATIONS),
              F("hire_date", "date"),
              F("termination_date", "date", required=False, description=">= hire_date when present"),
              F("employment_status", "string", allowed=EMPLOYMENT_STATUSES),
              F("current_manager_id", "string", required=False, fk="managers.manager_id", derived=True,
                description="Derived from the open manager_assignments row; null only for the CEO"),
          ]),
    Table("managers", "Manager", "manager_id",
          "Manager profile; 1:1 subtype of Employee.", "master", [
              F("manager_id", "string", unique=True, pattern=EMP_ID, fk="employees.employee_id",
                description="Same value as the employee_id of the manager"),
              F("management_level", "string", allowed=MANAGEMENT_LEVELS),
              F("max_span", "integer", min=1, max=60, description="Maximum direct reports allowed"),
              F("manager_since", "date"),
              F("is_active", "boolean"),
          ]),
    Table("manager_assignments", "ManagerAssignment", "assignment_id",
          "Effective-dated reporting line history (manager transfers are new rows, never overwrites).",
          "event", [
              F("assignment_id", "string", unique=True, pattern=r"^MA-\d{6}$"),
              F("employee_id", "string", fk="employees.employee_id"),
              F("manager_id", "string", fk="managers.manager_id"),
              F("department", "string", allowed=DEPARTMENTS, description="Department during this assignment"),
              F("effective_from", "date"),
              F("effective_to", "date", required=False, description="Null = currently effective"),
              F("change_reason", "string", allowed=ASSIGNMENT_REASONS),
          ]),
    Table("review_cycles", "ReviewCycle", "cycle_id",
          "Half-yearly performance cycles and their lifecycle state.", "master", [
              F("cycle_id", "string", unique=True, pattern=CYCLE_ID),
              F("name", "string"),
              F("start_date", "date"),
              F("end_date", "date"),
              F("goal_setting_deadline", "date"),
              F("review_deadline", "date"),
              F("status", "string", allowed=CYCLE_STATUSES),
              F("closed_at", "datetime", required=False, description="Set when status = closed; edits after this are locked"),
          ]),
    Table("goals", "Goal", "goal_id", "Employee goals per cycle.", "master", [
        F("goal_id", "string", unique=True, pattern=GOAL_ID, description="GOAL-<owner employee_id>-NNN"),
        F("employee_id", "string", fk="employees.employee_id", description="Goal owner"),
        F("cycle_id", "string", fk="review_cycles.cycle_id"),
        F("title", "string"),
        F("category", "string", allowed=GOAL_CATEGORIES),
        F("weight_pct", "integer", min=5, max=100, unit="percent",
          description="Weights of an owner's goals in a cycle sum to 100"),
        F("status", "string", allowed=GOAL_STATUSES),
        F("approved_by", "string", required=False, fk="managers.manager_id"),
        F("approved_at", "datetime", required=False),
        F("created_at", "datetime"),
        F("current_version", "integer", min=1, derived=True, description="= max(goal_versions.version_no)"),
        F("progress_pct", "decimal", min=0, max=120, unit="percent", derived=True,
          description="Weighted average of key-result scoring progress"),
    ]),
    Table("key_results", "KeyResult", "kr_id", "Measurable key results of a goal.", "master", [
        F("kr_id", "string", unique=True, pattern=KR_ID, description="KR-<goal_id>-NN"),
        F("goal_id", "string", fk="goals.goal_id"),
        F("description", "string"),
        F("metric_type", "string", allowed=METRIC_TYPES),
        F("unit", "string"),
        F("direction", "string", allowed=DIRECTIONS),
        F("start_value", "decimal"),
        F("target_value", "decimal", description="Current target; history in goal_versions"),
        F("weight_pct", "integer", min=1, max=100, unit="percent", description="KR weights sum to 100 per goal"),
        F("current_value", "decimal", derived=True, description="Latest kr_updates.reported_value, else start_value"),
        F("raw_progress_pct", "decimal", unit="percent", derived=True, description="Uncapped progress"),
        F("scoring_progress_pct", "decimal", min=0, max=120, unit="percent", derived=True,
          description="Capped at 100, or 120 when an over-scale rationale exists"),
    ]),
    Table("goal_versions", "GoalVersion", "version_id",
          "Append-only change history for goals and key results.", "event", [
              F("version_id", "string", unique=True, pattern=r"^GV-\d{7}$"),
              F("goal_id", "string", fk="goals.goal_id"),
              F("kr_id", "string", required=False, fk="key_results.kr_id"),
              F("version_no", "integer", min=1),
              F("change_type", "string", allowed=GOAL_CHANGE_TYPES),
              F("field_name", "string", required=False),
              F("old_value", "string", required=False),
              F("new_value", "string", required=False),
              F("changed_by", "string", fk="employees.employee_id"),
              F("changed_at", "datetime"),
              F("rationale", "string", required=False),
              F("approved_by", "string", required=False, fk="employees.employee_id"),
          ]),
    Table("checkins", "CheckIn", "checkin_id", "Periodic goal check-ins.", "transaction", [
        F("checkin_id", "string", unique=True, pattern=r"^CHK-\d{7}$"),
        F("goal_id", "string", fk="goals.goal_id"),
        F("cycle_id", "string", fk="review_cycles.cycle_id"),
        F("submitted_by", "string", fk="employees.employee_id"),
        F("checkin_date", "date"),
        F("sequence_no", "integer", min=1),
        F("confidence", "string", allowed=CONFIDENCE_LEVELS),
        F("note", "string"),
        F("goal_progress_pct", "decimal", unit="percent", derived=True,
          description="Goal progress snapshot as of this check-in"),
    ]),
    Table("kr_updates", "KeyResultUpdate", "update_id",
          "Key-result values reported inside a check-in.", "transaction", [
              F("update_id", "string", unique=True, pattern=r"^KRU-\d{7}$"),
              F("checkin_id", "string", fk="checkins.checkin_id"),
              F("kr_id", "string", fk="key_results.kr_id"),
              F("reported_value", "decimal"),
              F("raw_progress_pct", "decimal", unit="percent", derived=True,
                description="Against the target effective on the check-in date"),
              F("over_scale_rationale", "string", required=False,
                description="Mandatory when raw progress > 100"),
          ]),
    Table("evidence_links", "EvidenceLink", "evidence_id", "Evidence attached to check-ins.", "transaction", [
        F("evidence_id", "string", unique=True, pattern=r"^EVD-\d{7}$"),
        F("checkin_id", "string", fk="checkins.checkin_id"),
        F("kr_id", "string", required=False, fk="key_results.kr_id"),
        F("evidence_type", "string", allowed=EVIDENCE_TYPES),
        F("uri", "string"),
        F("added_by", "string", fk="employees.employee_id"),
        F("added_at", "datetime"),
    ]),
    Table("competencies", "Competency", "competency_id", "Competency framework.", "reference", [
        F("competency_id", "string", unique=True, pattern=r"^COMP-\d{2}$"),
        F("name", "string", unique=True),
        F("category", "string", allowed=COMPETENCY_CATEGORIES),
        F("description", "string"),
        F("scale_min", "integer"),
        F("scale_max", "integer"),
        F("applies_to", "string", allowed=COMPETENCY_APPLIES_TO),
    ]),
    Table("peer_nominations", "PeerNomination", "nomination_id",
          "N:M bridge between employees (subject <-> peer) per cycle.", "bridge", [
              F("nomination_id", "string", unique=True, pattern=r"^PN-\d{7}$"),
              F("cycle_id", "string", fk="review_cycles.cycle_id"),
              F("subject_employee_id", "string", fk="employees.employee_id"),
              F("peer_employee_id", "string", fk="employees.employee_id"),
              F("nominated_by", "string", fk="employees.employee_id"),
              F("status", "string", allowed=NOMINATION_STATUSES),
              F("nominated_at", "datetime"),
          ]),
    Table("feedback", "Feedback", "feedback_id", "Self / manager / peer competency feedback.", "transaction", [
        F("feedback_id", "string", unique=True, pattern=r"^FB-\d{4}-\d{7}$"),
        F("cycle_id", "string", fk="review_cycles.cycle_id"),
        F("subject_employee_id", "string", fk="employees.employee_id"),
        F("giver_employee_id", "string", required=False, fk="employees.employee_id",
          description="Must be present for traceability"),
        F("feedback_type", "string", allowed=FEEDBACK_TYPES),
        F("competency_id", "string", fk="competencies.competency_id"),
        F("rating", "integer", min=1, max=5),
        F("comment", "string"),
        F("linked_goal_id", "string", required=False, fk="goals.goal_id"),
        F("source", "string", allowed=FEEDBACK_SOURCES),
        F("submitted_at", "datetime"),
    ]),
    Table("reviews", "Review", "review_id", "One review per employee per cycle.", "transaction", [
        F("review_id", "string", unique=True, pattern=REV_ID),
        F("cycle_id", "string", fk="review_cycles.cycle_id"),
        F("employee_id", "string", fk="employees.employee_id"),
        F("reviewer_id", "string", fk="managers.manager_id"),
        F("status", "string", allowed=REVIEW_STATUSES),
        F("self_submitted_at", "datetime", required=False),
        F("manager_submitted_at", "datetime", required=False),
        F("finalized_at", "datetime", required=False),
        F("manager_summary", "string", required=False),
        F("goal_score_pct", "decimal", required=False, derived=True, unit="percent"),
        F("goal_rating", "decimal", required=False, derived=True, min=1, max=5),
        F("competency_rating", "decimal", required=False, derived=True, min=1, max=5),
        F("overall_score", "decimal", required=False, derived=True, min=1, max=5),
        F("overall_rating", "string", required=False, derived=True, allowed=RATING_LABELS),
        F("is_complete", "boolean", derived=True),
        F("missing_inputs", "string", required=False, derived=True, description="Semicolon list"),
    ]),
    Table("review_events", "ReviewEvent", "event_id", "Append-only review history.", "event", [
        F("event_id", "string", unique=True, pattern=r"^REVEV-\d{7}$"),
        F("review_id", "string", fk="reviews.review_id"),
        F("event_type", "string", allowed=REVIEW_EVENT_TYPES),
        F("from_status", "string", required=False, allowed=REVIEW_STATUSES),
        F("to_status", "string", required=False, allowed=REVIEW_STATUSES),
        F("field_name", "string", required=False),
        F("old_value", "string", required=False),
        F("new_value", "string", required=False),
        F("actor_id", "string", fk="employees.employee_id"),
        F("occurred_at", "datetime"),
        F("rationale", "string", required=False),
        F("approved_by", "string", required=False, fk="employees.employee_id"),
    ]),
    Table("development_plans", "DevelopmentPlan", "plan_id", "Development plans arising from reviews.",
          "transaction", [
              F("plan_id", "string", unique=True, pattern=r"^DP-\d{4}-\d{6}$"),
              F("employee_id", "string", fk="employees.employee_id"),
              F("cycle_id", "string", fk="review_cycles.cycle_id"),
              F("review_id", "string", fk="reviews.review_id"),
              F("competency_id", "string", fk="competencies.competency_id"),
              F("objective", "string"),
              F("training_cost", "decimal", min=0, unit="USD"),
              F("requires_hr_approval", "boolean", derived=True, description="training_cost > 1000"),
              F("target_date", "date"),
              F("created_at", "datetime"),
              F("completed_at", "datetime", required=False, description="Set when the employee completes the plan"),
              F("status", "string", allowed=PLAN_STATUSES, derived=True,
                description="Derived from plan_approvals and completed_at"),
          ]),
    Table("plan_approvals", "PlanApproval", "approval_id", "Approval steps for development plans.", "event", [
        F("approval_id", "string", unique=True, pattern=r"^DPA-\d{6}$"),
        F("plan_id", "string", fk="development_plans.plan_id"),
        F("approver_id", "string", fk="employees.employee_id"),
        F("approver_role", "string", allowed=APPROVER_ROLES),
        F("decision", "string", allowed=APPROVAL_DECISIONS),
        F("decided_at", "datetime", required=False),
        F("comment", "string", required=False),
    ]),
]

TABLE_BY_NAME = {t.name: t for t in TABLES}
TABLE_ORDER = [t.name for t in TABLES]  # parents before children

# Relationship / cardinality documentation (rendered into the data dictionary)
RELATIONSHIPS = [
    ("employees", "managers", "1:0..1", "An employee may be a manager (subtype)"),
    ("managers", "employees", "1:N", "Manager has many direct reports (current_manager_id)"),
    ("employees", "manager_assignments", "1:N", "Effective-dated reporting history"),
    ("employees", "goals", "1:N", "Owner of goals"),
    ("review_cycles", "goals", "1:N", "Goals belong to one cycle"),
    ("goals", "key_results", "1:N (1..4)", "Each goal has 1-4 key results"),
    ("goals", "goal_versions", "1:N", "Append-only version history"),
    ("goals", "checkins", "1:N", "Periodic check-ins"),
    ("checkins", "kr_updates", "1:N", "One update per key result per check-in"),
    ("checkins", "evidence_links", "1:N (0..n)", "Optional evidence"),
    ("employees", "employees", "N:M via peer_nominations", "Peer reviewer relationships per cycle"),
    ("employees", "feedback", "1:N", "Subject and giver of feedback"),
    ("competencies", "feedback", "1:N", "Feedback is per competency"),
    ("employees", "reviews", "1:N (1 per cycle)", "Unique (employee_id, cycle_id)"),
    ("reviews", "review_events", "1:N", "Append-only status/edit history"),
    ("reviews", "development_plans", "1:N (0..n)", "Plans created from a review"),
    ("development_plans", "plan_approvals", "1:N (1..2)", "Manager + optional HR approval"),
]

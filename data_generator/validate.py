"""Step 8 - validation suite run against the *exported files* (not memory).

Every check returns violations. A violation is "explained" when it touches an
entity that ground truth deliberately labelled as an anomaly; anything else is
"unexplained" and fails the run. This proves anomalies were injected surgically
without silently corrupting unrelated rows.
"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from domain import quality_rules, rules
from domain.schema import ANOMALY_TYPES, SCENARIO_TYPES, TABLES, TABLE_BY_NAME

from .derive import derive_all, target_histories
from .io import read_dataset, read_ground_truth

TOL = 0.011


class Check:
    def __init__(self, name: str, category: str, description: str):
        self.name, self.category, self.description = name, category, description
        self.rows_checked = 0
        self.violations: list[dict] = []

    def fail(self, entity_id: str, detail: str, related=()):
        self.violations.append({"entity_id": entity_id, "related_ids": [r for r in related if r], "detail": detail})


def _close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= TOL
    return a == b


# ------------------------------------------------------------------ structure
def check_structure(ds: dict) -> list[Check]:
    pk = Check("primary_key_uniqueness", "integrity", "Primary keys are unique and non-null")
    req = Check("required_fields", "integrity", "Required fields are populated")
    enum = Check("allowed_values", "integrity", "Enumerated fields only use allowed values")
    pat = Check("id_conventions", "integrity", "IDs follow the documented zero-padded patterns")
    rng = Check("numeric_ranges", "integrity", "Numeric fields respect documented min/max")
    uniq = Check("unique_fields", "duplicates", "Unique attributes (e.g. email) are not duplicated")
    fk = Check("foreign_key_integrity", "integrity", "Every foreign key resolves to an existing parent")
    keys = {t.name: {r[t.pk] for r in ds[t.name]} for t in TABLES}
    for t in TABLES:
        rows = ds[t.name]
        for c in (pk, req, enum, pat, rng, uniq, fk):
            c.rows_checked += len(rows)
        counts = Counter(r[t.pk] for r in rows)
        for k, n in counts.items():
            if n > 1 or k is None:
                pk.fail(str(k), f"{t.name}.{t.pk} duplicated {n}x")
        for f in t.fields:
            regex = re.compile(f.pattern) if f.pattern else None
            if f.unique and f.name != t.pk:
                for v, n in Counter(r[f.name] for r in rows if r[f.name] is not None).items():
                    if n > 1:
                        uniq.fail(str(v), f"{t.name}.{f.name} duplicated")
            parent = keys[f.fk.split(".")[0]] if f.fk else None
            for r in rows:
                v = r[f.name]
                if v is None:
                    if f.required:
                        req.fail(r[t.pk], f"{t.name}.{f.name} is null")
                    continue
                if f.allowed and v not in f.allowed:
                    enum.fail(r[t.pk], f"{t.name}.{f.name}={v!r} not allowed")
                if regex and not regex.match(str(v)):
                    pat.fail(r[t.pk], f"{t.name}.{f.name}={v!r} breaks pattern")
                if f.min is not None and v < f.min or f.max is not None and v > f.max:
                    rng.fail(r[t.pk], f"{t.name}.{f.name}={v} outside [{f.min}, {f.max}]")
                if parent is not None and v not in parent:
                    fk.fail(r[t.pk], f"{t.name}.{f.name}={v} has no parent in {f.fk}")
    return [pk, req, enum, pat, rng, uniq, fk]


def check_duplicates(ds: dict) -> Check:
    c = Check("duplicate_business_keys", "duplicates", "Natural keys are unique (one review per employee-cycle, etc.)")
    specs = {"reviews": ("employee_id", "cycle_id"), "kr_updates": ("checkin_id", "kr_id"),
             "peer_nominations": ("cycle_id", "subject_employee_id", "peer_employee_id"),
             "goal_versions": ("goal_id", "version_no"),
             "feedback": ("cycle_id", "subject_employee_id", "giver_employee_id", "feedback_type", "competency_id")}
    for tname, cols in specs.items():
        t = TABLE_BY_NAME[tname]
        rows = [r for r in ds[tname] if all(r[x] is not None for x in cols)]
        c.rows_checked += len(rows)
        for key, n in Counter(tuple(r[x] for x in cols) for r in rows).items():
            if n > 1:
                c.fail("|".join(map(str, key)), f"{tname} natural key duplicated {n}x")
    open_rows = Counter(a["employee_id"] for a in ds["manager_assignments"] if a["effective_to"] is None)
    for emp, n in open_rows.items():
        if n > 1:
            c.fail(emp, "more than one open manager assignment")
    return c


# ------------------------------------------------------------------ dates
def check_dates(ds: dict, as_of: date) -> Check:
    c = Check("date_ordering", "dates", "Start/end dates and lifecycle timestamps are in a valid order")
    cyc = {x["cycle_id"]: x for x in ds["review_cycles"]}
    goals = {g["goal_id"]: g for g in ds["goals"]}
    mgr_since = {m["manager_id"]: m["manager_since"] for m in ds["managers"]}
    for e in ds["employees"]:
        if e["termination_date"] and e["termination_date"] < e["hire_date"]:
            c.fail(e["employee_id"], "termination before hire")
        if (e["employment_status"] == "terminated") != (e["termination_date"] is not None):
            c.fail(e["employee_id"], "termination_date inconsistent with status")
    for x in ds["review_cycles"]:
        if not (x["start_date"] <= x["goal_setting_deadline"] <= x["end_date"] <= x["review_deadline"]):
            c.fail(x["cycle_id"], "cycle dates out of order")
    by_emp = defaultdict(list)
    for a in ds["manager_assignments"]:
        by_emp[a["employee_id"]].append(a)
        if a["effective_to"] and a["effective_to"] < a["effective_from"]:
            c.fail(a["assignment_id"], "effective_to before effective_from")
        if a["effective_from"] < mgr_since[a["manager_id"]]:
            c.fail(a["assignment_id"], "assignment starts before manager_since")
    for emp, lst in by_emp.items():
        lst.sort(key=lambda a: a["effective_from"])
        for a, b in zip(lst, lst[1:]):
            if a["effective_to"] is None or a["effective_to"] >= b["effective_from"]:
                c.fail(b["assignment_id"], "overlapping manager assignments", [emp])
    for g in ds["goals"]:
        if g["approved_at"] and g["approved_at"] < g["created_at"]:
            c.fail(g["goal_id"], "approved before created")
    for ch in ds["checkins"]:
        g, cy = goals[ch["goal_id"]], cyc[ch["cycle_id"]]
        if not (cy["start_date"] <= ch["checkin_date"] <= min(cy["end_date"], as_of)):
            c.fail(ch["checkin_id"], "check-in outside cycle window", [ch["goal_id"]])
        if g["approved_at"] is None or ch["checkin_date"] < g["approved_at"].date():
            c.fail(ch["checkin_id"], "check-in before goal approval", [ch["goal_id"]])
        if ch["cycle_id"] != g["cycle_id"]:
            c.fail(ch["checkin_id"], "check-in cycle differs from goal cycle", [ch["goal_id"]])
    for f in ds["feedback"]:
        if f["submitted_at"].date() > min(cyc[f["cycle_id"]]["review_deadline"], as_of):
            c.fail(f["feedback_id"], "feedback after review deadline / as-of date")
    for r in ds["reviews"]:
        ts = [r["self_submitted_at"], r["manager_submitted_at"], r["finalized_at"]]
        present = [t for t in ts if t]
        if present != sorted(present):
            c.fail(r["review_id"], "review timestamps out of order")
        closed = cyc[r["cycle_id"]]["closed_at"]
        if r["finalized_at"] and closed and r["finalized_at"] > closed:
            c.fail(r["review_id"], "finalized after cycle close")
    plans = {p["plan_id"]: p for p in ds["development_plans"]}
    for p in ds["development_plans"]:
        if p["target_date"] <= p["created_at"].date():
            c.fail(p["plan_id"], "target_date not after creation")
    for a in ds["plan_approvals"]:
        if a["decided_at"] and a["decided_at"] < plans[a["plan_id"]]["created_at"]:
            c.fail(a["approval_id"], "approval decided before plan created")
    c.rows_checked = sum(len(ds[t]) for t in ("employees", "review_cycles", "manager_assignments", "goals",
                                             "checkins", "feedback", "reviews", "development_plans", "plan_approvals"))
    return c


# ------------------------------------------------------------------ lifecycle
def check_lifecycles(ds: dict) -> list[Check]:
    rv = Check("review_lifecycle", "lifecycle", "Review status matches timestamps, events and completeness")
    gv = Check("goal_lifecycle", "lifecycle", "Goal versions are contiguous and status transitions are legal")
    cy = Check("cycle_lifecycle", "lifecycle", "Cycle status, closed_at and goal states are consistent")
    events = defaultdict(list)
    for e in ds["review_events"]:
        events[e["review_id"]].append(e)
    for r in ds["reviews"]:
        rv.rows_checked += 1
        expect = {"not_started": (False, False, False), "self_submitted": (True, False, False),
                  "manager_submitted": (True, True, False), "finalized": (True, True, True)}[r["status"]]
        actual = (r["self_submitted_at"] is not None, r["manager_submitted_at"] is not None, r["finalized_at"] is not None)
        if expect != actual:
            rv.fail(r["review_id"], f"status {r['status']} inconsistent with timestamps")
        if r["status"] == "finalized" and not r["is_complete"]:
            rv.fail(r["review_id"], "finalized without all required inputs")
        chain = sorted((e for e in events[r["review_id"]] if e["event_type"] == "status_change"),
                       key=lambda e: e["occurred_at"])
        state = None
        for e in chain:
            if e["from_status"] != state or (state is not None and not rules.can_transition(
                    rules.REVIEW_TRANSITIONS, state, e["to_status"])):
                rv.fail(e["event_id"], f"illegal transition {state} -> {e['to_status']}", [r["review_id"]])
            state = e["to_status"]
        if state != r["status"]:
            rv.fail(r["review_id"], f"event history ends at {state}, row says {r['status']}")
    vers = defaultdict(list)
    for v in ds["goal_versions"]:
        vers[v["goal_id"]].append(v)
    for g in ds["goals"]:
        gv.rows_checked += 1
        lst = sorted(vers[g["goal_id"]], key=lambda v: v["version_no"])
        if [v["version_no"] for v in lst] != list(range(1, len(lst) + 1)) or not lst or lst[0]["change_type"] != "created":
            gv.fail(g["goal_id"], "version numbers not contiguous from a 'created' version")
        if [v["changed_at"] for v in lst] != sorted(v["changed_at"] for v in lst):
            gv.fail(g["goal_id"], "version order does not follow time")
        state = "draft"
        for v in lst:
            if v["change_type"] == "status_changed":
                if v["old_value"] != state or not rules.can_transition(rules.GOAL_TRANSITIONS, state, v["new_value"]):
                    gv.fail(v["version_id"], f"illegal goal transition {state} -> {v['new_value']}", [g["goal_id"]])
                state = v["new_value"]
        if state != g["status"]:
            gv.fail(g["goal_id"], f"version history ends at {state}, row says {g['status']}")
        if g["status"] in ("in_progress", "closed") and not (g["approved_by"] and g["approved_at"]):
            gv.fail(g["goal_id"], "active goal lacks approval")
    cyc = {c["cycle_id"]: c for c in ds["review_cycles"]}
    for c in ds["review_cycles"]:
        cy.rows_checked += 1
        if (c["status"] == "closed") != (c["closed_at"] is not None):
            cy.fail(c["cycle_id"], "closed_at inconsistent with status")
    for g in ds["goals"]:
        st = cyc[g["cycle_id"]]["status"]
        if st == "planned" or (st == "closed" and g["status"] not in ("closed", "cancelled")):
            cy.fail(g["goal_id"], f"goal status {g['status']} invalid for {st} cycle")
    return [rv, gv, cy]


# ------------------------------------------------------------------ reconciliation
DERIVED = {"employees": ["current_manager_id"], "kr_updates": ["raw_progress_pct"],
           "key_results": ["current_value", "raw_progress_pct", "scoring_progress_pct"],
           "goals": ["progress_pct", "current_version"], "checkins": ["goal_progress_pct"],
           "reviews": ["goal_score_pct", "goal_rating", "competency_rating", "overall_score", "overall_rating",
                       "is_complete", "missing_inputs"],
           "development_plans": ["requires_hr_approval", "status"]}


def check_reconciliation(ds: dict, as_of: date) -> list[Check]:
    der = Check("derived_values_reconcile", "reconciliation",
                "Every derived column equals a fresh recomputation from source records")
    wts = Check("goal_weights_sum_100", "reconciliation", "Goal weights per owner and cycle sum to 100")
    krw = Check("kr_weights_sum_100", "reconciliation", "Key-result weights per goal sum to 100")
    tgt = Check("kr_target_matches_history", "reconciliation", "Current KR target equals the last versioned target")
    dep = Check("department_matches_assignment", "reconciliation", "Employee department equals current assignment")
    fresh = derive_all(copy.deepcopy(ds), as_of)
    for tname, cols in DERIVED.items():
        pkn = TABLE_BY_NAME[tname].pk
        fmap = {r[pkn]: r for r in fresh[tname]}
        for r in ds[tname]:
            der.rows_checked += 1
            for col in cols:
                if not _close(r[col], fmap[r[pkn]][col]):
                    der.fail(r[pkn], f"{tname}.{col} stored={r[col]} recomputed={fmap[r[pkn]][col]}")
    groups = defaultdict(list)
    for g in ds["goals"]:
        groups[(g["employee_id"], g["cycle_id"])].append(g)
    for (emp, cyc), gs in groups.items():
        wts.rows_checked += 1
        if sum(g["weight_pct"] for g in gs) != 100:
            wts.fail(f"{emp}|{cyc}", f"weights sum to {sum(g['weight_pct'] for g in gs)}", [g["goal_id"] for g in gs])
    krs = defaultdict(list)
    for k in ds["key_results"]:
        krs[k["goal_id"]].append(k)
    for gid, ks in krs.items():
        krw.rows_checked += 1
        if sum(k["weight_pct"] for k in ks) != 100:
            krw.fail(gid, "KR weights do not sum to 100")
    hist = target_histories(ds)
    for k in ds["key_results"]:
        tgt.rows_checked += 1
        if k["kr_id"] in hist and not _close(hist[k["kr_id"]][-1][2], k["target_value"]):
            tgt.fail(k["kr_id"], "target differs from last version", [k["goal_id"]])
    cur = {a["employee_id"]: a for a in sorted(ds["manager_assignments"], key=lambda a: a["effective_from"])}
    for e in ds["employees"]:
        dep.rows_checked += 1
        if e["employee_id"] in cur and cur[e["employee_id"]]["department"] != e["department"]:
            dep.fail(e["employee_id"], "department differs from latest assignment")
    return [der, wts, krw, tgt, dep]


# ------------------------------------------------------------------ business rules
RULE_CHECK_NAMES = {
    "goal_owner_mismatch": "R1_goal_owner_matches",
    "progress_over_scale_no_rationale": "R2_progress_within_scale_or_justified",
    "reviewer_lacks_relationship": "R3_reviewer_has_relationship",
    "closed_cycle_silent_edit": "R4_no_silent_edits_after_close",
    "untraceable_feedback": "R5_feedback_traceable",
}


def check_business_rules(ds: dict, as_of: date) -> tuple[list[Check], list[dict]]:
    findings = quality_rules.run_all(ds, as_of)
    checks = {k: Check(v, "business_rule", f"Detector for '{k}' (violations must all be labelled)")
              for k, v in RULE_CHECK_NAMES.items()}
    for c in checks.values():
        c.rows_checked = len(ds["goals"]) + len(ds["checkins"]) + len(ds["feedback"]) + len(ds["reviews"])
    for f in findings:
        checks[f["issue_type"]].fail(f["entity_id"], f["detail"], f["related_ids"])
    return list(checks.values()), findings


# ------------------------------------------------------------------ ground truth
def check_ground_truth(ds: dict, labels: list[dict], findings: list[dict], expected_counts: dict) -> list[Check]:
    sep = Check("ground_truth_separation", "ground_truth", "No label columns or label IDs leak into input tables")
    ref = Check("ground_truth_references", "ground_truth", "Every label points at an existing entity")
    cov = Check("anomaly_label_coverage", "ground_truth", "Every anomaly label is caught by a rule detector")
    scen = Check("scenario_coverage", "coverage", "Every required anomaly and scenario type is present")
    vol = Check("volume_targets", "coverage", "Baseline volumes match the configured scale")
    banned = re.compile(r"(anomal|ground|label_|issue_type|is_injected)", re.I)
    for t in TABLES:
        sep.rows_checked += 1
        for f in t.fields:
            if banned.search(f.name):
                sep.fail(f"{t.name}.{f.name}", "label-like column in input table")
    all_ids = set()
    for t in TABLES:
        all_ids |= {r[t.pk] for r in ds[t.name]}
    for l in labels:
        ref.rows_checked += 1
        if l["entity_id"] not in all_ids:
            ref.fail(l["label_id"], f"entity {l['entity_id']} not found")
    anomalies = [l for l in labels if l["label_kind"] == "anomaly"]
    rep = quality_rules.evaluate(findings, anomalies)
    cov.rows_checked = len(anomalies)
    for issue, m in rep.items():
        if m["missed_labels"]:
            cov.fail(issue, f"{m['missed_labels']} labels not detected")
    present = Counter(l["issue_type"] for l in labels)
    for t in ANOMALY_TYPES + SCENARIO_TYPES:
        scen.rows_checked += 1
        if present[t] == 0:
            scen.fail(t, "no labelled examples")
    actual = {"employees": len(ds["employees"]), "managers": len(ds["managers"]),
              "goals": len(ds["goals"]), "checkins": len(ds["checkins"])}
    for k, v in expected_counts.items():
        vol.rows_checked += 1
        if actual[k] != v:
            vol.fail(k, f"expected {v}, got {actual[k]}")
    return [sep, ref, cov, scen, vol]


# ------------------------------------------------------------------ orchestration
def validate(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    as_of = date.fromisoformat(manifest["as_of"])
    ds = read_dataset(data_dir)
    labels = read_ground_truth(data_dir)
    rule_checks, findings = check_business_rules(ds, as_of)
    checks = (check_structure(ds) + [check_duplicates(ds), check_dates(ds, as_of)] + check_lifecycles(ds)
              + check_reconciliation(ds, as_of) + rule_checks
              + check_ground_truth(ds, labels, findings, manifest["expected_counts"]))
    labelled = set()
    for l in labels:
        if l["label_kind"] == "anomaly":
            labelled |= {l["entity_id"], *l["related_ids"]}
    results, ok = [], True
    for c in checks:
        unexplained = [v for v in c.violations if not ({v["entity_id"], *v["related_ids"]} & labelled)]
        if c.category == "ground_truth" or c.category == "coverage":
            unexplained = c.violations
        status = "PASS" if not unexplained else "FAIL"
        ok &= status == "PASS"
        results.append({"check": c.name, "category": c.category, "description": c.description,
                        "rows_checked": c.rows_checked, "violations": len(c.violations),
                        "explained_by_ground_truth": len(c.violations) - len(unexplained),
                        "unexplained": len(unexplained), "status": status,
                        "sample_unexplained": unexplained[:5]})
    evaluation = quality_rules.evaluate(findings, [l for l in labels if l["label_kind"] == "anomaly"])
    summary = {"dataset": manifest["profile"], "seed": manifest["seed"], "as_of": manifest["as_of"],
               "overall_status": "PASS" if ok else "FAIL", "checks_total": len(results),
               "checks_passed": sum(r["status"] == "PASS" for r in results),
               "row_counts": manifest["row_counts"], "detector_evaluation": evaluation, "checks": results}
    (data_dir / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    (data_dir / "validation_summary.md").write_text(render_md(summary), encoding="utf-8", newline="\n")
    return summary


def render_md(s: dict) -> str:
    lines = [f"# Validation summary - `{s['dataset']}` dataset", "",
             f"**Overall: {s['overall_status']}** - {s['checks_passed']}/{s['checks_total']} checks passed "
             f"(seed `{s['seed']}`, as-of `{s['as_of']}`)", "",
             "A violation is *explained* when it touches an entity that was deliberately labelled in "
             "`ground_truth/`. Any *unexplained* violation fails the run.", "",
             "| Check | Category | Rows checked | Violations | Explained | Unexplained | Status |",
             "|---|---|---:|---:|---:|---:|---|"]
    for r in s["checks"]:
        lines.append(f"| {r['check']} | {r['category']} | {r['rows_checked']:,} | {r['violations']:,} | "
                     f"{r['explained_by_ground_truth']:,} | {r['unexplained']:,} | {r['status']} |")
    lines += ["", "## Rule detectors vs ground truth", "",
              "| Issue type | Labels | Findings | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|---:|"]
    for k, m in s["detector_evaluation"].items():
        lines.append(f"| {k} | {m['labels']} | {m['findings']} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |")
    lines += ["", "## Row counts", "", "| Table | Rows |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in s["row_counts"].items()]
    return "\n".join(lines) + "\n"

"""Step 6 - every derived value is calculated from source records.

The same function is used by the generator (to fill derived columns) and by the
validator (to recompute on a copy and reconcile), so 'derived == recomputed' is a
real arithmetic check rather than a tautology on independently random numbers.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time

from domain import rules


def eod(d: date) -> datetime:
    return datetime.combine(d, time(23, 59, 59))


def target_histories(ds: dict) -> dict:
    hist = defaultdict(list)
    for v in ds["goal_versions"]:
        if v["kr_id"] and v["field_name"] == "target_value":
            hist[v["kr_id"]].append((v["changed_at"], float(v["old_value"]), float(v["new_value"])))
    for h in hist.values():
        h.sort()
    return hist


def derive_all(ds: dict, as_of: date) -> dict:
    # 1. Reporting line -> current manager (open assignment wins)
    open_mgr = {a["employee_id"]: a["manager_id"] for a in ds["manager_assignments"] if a["effective_to"] is None}
    for e in ds["employees"]:
        e["current_manager_id"] = open_mgr.get(e["employee_id"])

    # 2. Key-result updates: progress against the target effective at check-in time
    hist = target_histories(ds)
    krs = {k["kr_id"]: k for k in ds["key_results"]}
    checkins = {c["checkin_id"]: c for c in ds["checkins"]}
    for u in ds["kr_updates"]:
        kr = krs[u["kr_id"]]
        tgt = rules.target_at(kr["target_value"], hist.get(kr["kr_id"], []), eod(checkins[u["checkin_id"]]["checkin_date"]))
        u["raw_progress_pct"] = rules.kr_raw_progress(kr["start_value"], tgt, u["reported_value"])

    # 3. Key results: current value = latest reported value
    updates_by_kr = defaultdict(list)
    for u in ds["kr_updates"]:
        c = checkins[u["checkin_id"]]
        updates_by_kr[u["kr_id"]].append(((c["checkin_date"], c["sequence_no"], u["update_id"]), u))
    for kr in ds["key_results"]:
        ups = sorted(updates_by_kr.get(kr["kr_id"], []), key=lambda x: x[0])
        latest = ups[-1][1] if ups else None
        kr["current_value"] = latest["reported_value"] if latest else kr["start_value"]
        kr["raw_progress_pct"] = rules.kr_raw_progress(kr["start_value"], kr["target_value"], kr["current_value"])
        kr["scoring_progress_pct"] = rules.kr_scoring_progress(
            kr["raw_progress_pct"], bool(latest and latest["over_scale_rationale"]))

    # 4. Goals: weighted progress + current version
    krs_by_goal = defaultdict(list)
    for kr in ds["key_results"]:
        krs_by_goal[kr["goal_id"]].append(kr)
    max_version = defaultdict(int)
    for v in ds["goal_versions"]:
        max_version[v["goal_id"]] = max(max_version[v["goal_id"]], v["version_no"])
    for g in ds["goals"]:
        g["progress_pct"] = rules.goal_progress([(k["weight_pct"], k["scoring_progress_pct"])
                                                 for k in krs_by_goal[g["goal_id"]]])
        g["current_version"] = max_version[g["goal_id"]]

    # 5. Check-in snapshot of goal progress
    ups_by_checkin = defaultdict(list)
    for u in ds["kr_updates"]:
        ups_by_checkin[u["checkin_id"]].append(u)
    for c in ds["checkins"]:
        pairs = [(krs[u["kr_id"]]["weight_pct"],
                  rules.kr_scoring_progress(u["raw_progress_pct"], bool(u["over_scale_rationale"])))
                 for u in ups_by_checkin[c["checkin_id"]]]
        c["goal_progress_pct"] = rules.goal_progress(pairs)

    # 6. Reviews: completeness + scores
    comps = ds["competencies"]
    managers = {m["manager_id"] for m in ds["managers"]}
    goals_by_owner = defaultdict(list)
    for g in ds["goals"]:
        goals_by_owner[(g["employee_id"], g["cycle_id"])].append(g)
    goals_with_checkins = {c["goal_id"] for c in ds["checkins"]}
    fb = defaultdict(list)
    for f in ds["feedback"]:
        fb[(f["subject_employee_id"], f["cycle_id"])].append(f)
    for r in ds["reviews"]:
        key = (r["employee_id"], r["cycle_id"])
        required = rules.applicable_competencies(comps, r["employee_id"] in managers)
        self_c = {f["competency_id"] for f in fb[key]
                  if f["feedback_type"] == "self" and f["giver_employee_id"] == r["employee_id"]}
        mgr_rows = [f for f in fb[key] if f["feedback_type"] == "manager" and f["giver_employee_id"] == r["reviewer_id"]]
        mgr_c = {f["competency_id"] for f in mgr_rows}
        goals = goals_by_owner[key]
        active = [g["goal_id"] for g in goals if g["status"] not in rules.INACTIVE_GOAL_STATUSES]
        missing = rules.review_missing_inputs(required, self_c, mgr_c, active, goals_with_checkins)
        r["is_complete"] = not missing
        r["missing_inputs"] = ";".join(missing) if missing else None
        r["goal_score_pct"] = rules.goal_score_pct([(g["weight_pct"], g["progress_pct"], g["status"]) for g in goals])
        r["goal_rating"] = rules.goal_rating(r["goal_score_pct"])
        r["competency_rating"] = rules.competency_rating([f["rating"] for f in mgr_rows if f["competency_id"] in required])
        if r["is_complete"]:
            r["overall_score"] = rules.overall_score(r["goal_rating"], r["competency_rating"])
            r["overall_rating"] = rules.rating_label(r["overall_score"])
        else:
            r["overall_score"], r["overall_rating"] = None, None

    # 7. Development plans: HR approval requirement + status from approvals
    appr = defaultdict(list)
    for a in ds["plan_approvals"]:
        appr[a["plan_id"]].append(a)
    for p in ds["development_plans"]:
        p["requires_hr_approval"] = rules.plan_requires_hr(p["training_cost"])
        p["status"] = rules.plan_status(appr[p["plan_id"]], p["requires_hr_approval"], p["completed_at"])
    return ds

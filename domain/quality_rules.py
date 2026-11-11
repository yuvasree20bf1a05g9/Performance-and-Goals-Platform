"""Business-rule detectors for the five required exception paths.

They work on an in-memory ``dataset`` (``{table_name: [row_dict, ...]}`` with typed
values), so the generator's validator and the API's data-quality endpoint run the
*same* rules: one against freshly generated files, the other against the database.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, time
from typing import Iterable, Optional

from . import rules

GOAL_OWNER_RE = re.compile(r"^GOAL-(EMP-\d{6})-\d{3}$")


class Index:
    """Lookup helpers built once per dataset (O(n) build, O(log n) queries)."""

    def __init__(self, ds: dict, as_of: date):
        self.ds = ds
        self.as_of = as_of
        self.employees = {e["employee_id"]: e for e in ds["employees"]}
        self.cycles = {c["cycle_id"]: c for c in ds["review_cycles"]}
        self.goals = {g["goal_id"]: g for g in ds["goals"]}
        self.krs = {k["kr_id"]: k for k in ds["key_results"]}
        self.checkins = {c["checkin_id"]: c for c in ds["checkins"]}
        self.reviews_by_key = {(r["employee_id"], r["cycle_id"]): r for r in ds["reviews"]}
        self.assignments = defaultdict(list)
        for a in ds["manager_assignments"]:
            self.assignments[a["employee_id"]].append(a)
        for lst in self.assignments.values():
            lst.sort(key=lambda a: a["effective_from"])
        self._starts = {k: [a["effective_from"] for a in v] for k, v in self.assignments.items()}
        self.accepted_peers = {(n["cycle_id"], n["subject_employee_id"], n["peer_employee_id"])
                               for n in ds["peer_nominations"] if n["status"] == "accepted"}

    def manager_at(self, employee_id: str, on: date) -> Optional[str]:
        lst = self.assignments.get(employee_id, [])
        i = bisect_right(self._starts.get(employee_id, []), on) - 1
        if i < 0:
            return None
        a = lst[i]
        if a["effective_to"] is None or a["effective_to"] >= on:
            return a["manager_id"]
        return None

    def managers_during(self, employee_id: str, start: date, end: date) -> set:
        return {a["manager_id"] for a in self.assignments.get(employee_id, [])
                if a["effective_from"] <= end and (a["effective_to"] is None or a["effective_to"] >= start)}

    def cycle_window(self, cycle_id: str) -> tuple[date, date]:
        c = self.cycles[cycle_id]
        return c["start_date"], min(c["end_date"], self.as_of)

    def closed_at(self, cycle_id: str) -> Optional[datetime]:
        c = self.cycles[cycle_id]
        return c["closed_at"] if c["status"] == "closed" else None


def finding(issue_type: str, sub_type: str, entity_type: str, entity_id: str,
            related: Iterable[str], detail: str) -> dict:
    return {"issue_type": issue_type, "sub_type": sub_type, "entity_type": entity_type,
            "entity_id": entity_id, "related_ids": sorted({r for r in related if r}), "detail": detail}


# --------------------------------------------------------------------------- #
def detect_goal_owner_mismatch(ix: Index) -> list[dict]:
    out = []
    for g in ix.ds["goals"]:
        m = GOAL_OWNER_RE.match(g["goal_id"])
        if m and m.group(1) != g["employee_id"]:
            out.append(finding("goal_owner_mismatch", "goal_id_owner_conflict", "goal", g["goal_id"],
                               [m.group(1), g["employee_id"]],
                               f"goal_id encodes {m.group(1)} but owner is {g['employee_id']}"))
    for c in ix.ds["checkins"]:
        g = ix.goals[c["goal_id"]]
        owner = g["employee_id"]
        if c["submitted_by"] == owner:
            continue
        if c["submitted_by"] == ix.manager_at(owner, c["checkin_date"]):
            continue
        out.append(finding("goal_owner_mismatch", "checkin_by_non_owner", "checkin", c["checkin_id"],
                           [g["goal_id"], c["submitted_by"]],
                           f"check-in by {c['submitted_by']} who is neither owner nor owner's manager"))
    return out


def detect_progress_over_scale(ix: Index) -> list[dict]:
    out = []
    for u in ix.ds["kr_updates"]:
        if rules.is_over_scale(u["raw_progress_pct"]) and not u["over_scale_rationale"]:
            kr = ix.krs[u["kr_id"]]
            out.append(finding("progress_over_scale_no_rationale", "missing_rationale", "kr_update",
                               u["update_id"], [u["kr_id"], u["checkin_id"], kr["goal_id"]],
                               f"raw progress {u['raw_progress_pct']}% > 100% without rationale"))
    return out


def detect_reviewer_lacks_relationship(ix: Index) -> list[dict]:
    out = []
    for r in ix.ds["reviews"]:
        start, end = ix.cycle_window(r["cycle_id"])
        if r["reviewer_id"] not in ix.managers_during(r["employee_id"], start, end):
            out.append(finding("reviewer_lacks_relationship", "review_by_non_manager", "review",
                               r["review_id"], [r["reviewer_id"], r["employee_id"]],
                               f"{r['reviewer_id']} never managed {r['employee_id']} during {r['cycle_id']}"))
    for f in ix.ds["feedback"]:
        giver, subj = f["giver_employee_id"], f["subject_employee_id"]
        if giver is None:
            continue  # handled by untraceable detector
        start, end = ix.cycle_window(f["cycle_id"])
        ok = True
        if f["feedback_type"] == "self":
            ok = giver == subj
        elif f["feedback_type"] == "manager":
            ok = giver in ix.managers_during(subj, start, end)
        elif f["feedback_type"] == "peer":
            ok = (f["cycle_id"], subj, giver) in ix.accepted_peers
        if not ok:
            rev = ix.reviews_by_key.get((subj, f["cycle_id"]))
            out.append(finding("reviewer_lacks_relationship", f"{f['feedback_type']}_feedback_no_relationship",
                               "feedback", f["feedback_id"], [rev["review_id"] if rev else None, giver],
                               f"{giver} gave {f['feedback_type']} feedback to {subj} without a valid relationship"))
    return out


def detect_closed_cycle_silent_edits(ix: Index) -> list[dict]:
    out = []
    for v in ix.ds["goal_versions"]:
        g = ix.goals[v["goal_id"]]
        if rules.is_silent_post_close_edit(ix.closed_at(g["cycle_id"]), v["changed_at"],
                                           v["rationale"], v["approved_by"]):
            out.append(finding("closed_cycle_silent_edit", "goal_version_after_close", "goal_version",
                               v["version_id"], [v["goal_id"], v["kr_id"]],
                               f"{v['change_type']} on {v['goal_id']} after cycle close without approval"))
    reviews = {r["review_id"]: r for r in ix.ds["reviews"]}
    for e in ix.ds["review_events"]:
        r = reviews[e["review_id"]]
        if rules.is_silent_post_close_edit(ix.closed_at(r["cycle_id"]), e["occurred_at"],
                                           e["rationale"], e["approved_by"]):
            out.append(finding("closed_cycle_silent_edit", "review_event_after_close", "review_event",
                               e["event_id"], [e["review_id"]],
                               f"{e['event_type']} on {e['review_id']} after cycle close without approval"))
    return out


def detect_untraceable_feedback(ix: Index) -> list[dict]:
    out = []
    for f in ix.ds["feedback"]:
        if f["giver_employee_id"] is None or f["giver_employee_id"] not in ix.employees:
            rev = ix.reviews_by_key.get((f["subject_employee_id"], f["cycle_id"]))
            out.append(finding("untraceable_feedback", "missing_giver", "feedback", f["feedback_id"],
                               [rev["review_id"] if rev else None],
                               f"{f['feedback_type']} feedback from source={f['source']} has no traceable giver"))
    return out


DETECTORS = [detect_goal_owner_mismatch, detect_progress_over_scale, detect_reviewer_lacks_relationship,
             detect_closed_cycle_silent_edits, detect_untraceable_feedback]


def run_all(ds: dict, as_of: date) -> list[dict]:
    ix = Index(ds, as_of)
    out = []
    for d in DETECTORS:
        out.extend(d(ix))
    return out


# --------------------------------------------------------------------------- #
def conflicting_feedback(ds: dict) -> list[tuple[str, str, str]]:
    """(cycle_id, subject, competency) where self and manager ratings differ by >= CONFLICT_GAP."""
    reviewer = {(r["employee_id"], r["cycle_id"]): r["reviewer_id"] for r in ds["reviews"]}
    self_r, mgr_r = {}, {}
    for f in ds["feedback"]:
        key = (f["cycle_id"], f["subject_employee_id"], f["competency_id"])
        if f["feedback_type"] == "self" and f["giver_employee_id"] == f["subject_employee_id"]:
            self_r[key] = f["rating"]
        elif f["feedback_type"] == "manager" and \
                f["giver_employee_id"] == reviewer.get((f["subject_employee_id"], f["cycle_id"])):
            mgr_r[key] = f["rating"]
    return sorted(k for k in self_r if k in mgr_r and abs(self_r[k] - mgr_r[k]) >= rules.CONFLICT_GAP)


# --------------------------------------------------------------------------- #
def _matches(fnd: dict, label: dict) -> bool:
    l_ids = {label["entity_id"], *label["related_ids"]}
    f_ids = {fnd["entity_id"], *fnd["related_ids"]}
    return fnd["entity_id"] in l_ids or label["entity_id"] in f_ids


def evaluate(findings: list[dict], labels: list[dict]) -> dict:
    """Precision / recall / F1 of detector findings against ground-truth anomaly labels."""
    report = {}
    for issue in sorted({l["issue_type"] for l in labels} | {f["issue_type"] for f in findings}):
        fs = [f for f in findings if f["issue_type"] == issue]
        ls = [l for l in labels if l["issue_type"] == issue]
        by_entity = defaultdict(list)
        for l in ls:
            for i in {l["entity_id"], *l["related_ids"]}:
                by_entity[i].append(l)
        matched_labels, tp = set(), 0
        for f in fs:
            cands = {id(l): l for i in {f["entity_id"], *f["related_ids"]} for l in by_entity.get(i, [])}
            hits = [l for l in cands.values() if _matches(f, l)]
            if hits:
                tp += 1
                matched_labels.update(l["label_id"] for l in hits)
        fp = len(fs) - tp
        fn = len(ls) - len(matched_labels)
        precision = tp / len(fs) if fs else 1.0
        recall = len(matched_labels) / len(ls) if ls else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[issue] = {"labels": len(ls), "findings": len(fs), "true_positive_findings": tp,
                         "false_positive_findings": fp, "missed_labels": fn,
                         "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
    return report


def end_of_day(d: date) -> datetime:
    return datetime.combine(d, time(23, 59, 59))

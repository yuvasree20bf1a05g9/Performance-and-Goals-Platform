"""API integration tests: acceptance criteria end-to-end against a real (SQLite) database."""


def _active_goal(client, owner):
    goals = client.get("/api/goals", params={"employee_id": owner, "cycle_id": "CYCLE-2026-H2",
                                             "status": "in_progress"}).json()["items"]
    return client.get(f"/api/goals/{goals[0]['goal_id']}").json()


def _body(goal, fraction, rationale=None):
    return {"confidence": "medium", "note": "progress update",
            "updates": [{"kr_id": k["kr_id"], "reported_value": k["start_value"] + (k["target_value"] - k["start_value"]) * fraction,
                         "over_scale_rationale": rationale} for k in goal["key_results"]],
            "evidence": [{"evidence_type": "dashboard", "uri": "https://evidence.example.com/d/1"}]}


# ---------------------------------------------------------------- read side
def test_health_meta_and_metrics(client):
    assert client.get("/api/health").json()["employees"] == 150
    meta = client.get("/api/meta").json()
    assert {c["cycle_id"] for c in meta["cycles"]} == {"CYCLE-2026-H1", "CYCLE-2026-H2", "CYCLE-2027-H1"}
    ov = client.get("/api/metrics/overview", params={"cycle_id": "CYCLE-2026-H1"}).json()
    assert ov["goals"]["total"] > 0 and 0 <= ov["reviews"]["completion_pct"] <= 100
    assert sum(ov["reviews"]["rating_distribution"].values()) > 0
    assert client.get("/api/metrics/departments").status_code == 200


def test_employee_detail_has_hierarchy_and_history(client, actors):
    e = client.get(f"/api/employees/{actors['Employee (has active goals)']}").json()
    assert e["manager_chain"] and e["assignments"] and e["reviews"]
    assert client.get("/api/employees/EMP-999999").status_code == 404
    page = client.get("/api/employees", params={"department": "Engineering", "size": 5}).json()
    assert page["total"] > 5 and len(page["items"]) == 5


def test_quality_detectors_match_ground_truth(client):
    ev = client.get("/api/quality/evaluation").json()["detectors_vs_ground_truth"]
    assert set(ev) == {"goal_owner_mismatch", "progress_over_scale_no_rationale", "reviewer_lacks_relationship",
                       "closed_cycle_silent_edit", "untraceable_feedback"}
    for issue, m in ev.items():
        assert m["recall"] == 1.0 and m["precision"] == 1.0, issue


# ---------------------------------------------------------------- check-ins & progress
def test_checkin_requires_identity_and_ownership(client, actors):
    goal = _active_goal(client, actors["Employee (has active goals)"])
    url = f"/api/goals/{goal['goal_id']}/checkins"
    assert client.post(url, json=_body(goal, 0.5)).status_code == 401
    r = client.post(url, json=_body(goal, 0.5), headers={"X-Actor-Id": actors["HR partner"]})
    assert r.status_code == 403 and "owner" in r.json()["error"]["message"]


def test_progress_is_derived_and_over_scale_needs_rationale(client, actors):
    owner = actors["Employee (has active goals)"]
    goal = _active_goal(client, owner)
    url, h = f"/api/goals/{goal['goal_id']}/checkins", {"X-Actor-Id": owner}
    r = client.post(url, json=_body(goal, 1.4), headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "business_rule_violation"
    r = client.post(url, json=_body(goal, 1.4, "Signed a large deal early"), headers=h)
    assert r.status_code == 201 and r.json()["goal_progress_pct"] == 120.0          # stretch cap
    r = client.post(url, json=_body(goal, 0.5), headers={"X-Actor-Id": actors["Their manager"]})
    assert r.status_code == 201 and r.json()["goal_progress_pct"] == 50.0           # manager may update
    detail = client.get(f"/api/goals/{goal['goal_id']}").json()
    assert detail["progress_pct"] == 50.0 and detail["checkins"][-1]["sequence_no"] >= 2


def test_checkin_must_cover_every_key_result(client, actors):
    owner = actors["Employee (has active goals)"]
    goal = _active_goal(client, owner)
    body = _body(goal, 0.5)
    body["updates"] = body["updates"][:-1] or [{"kr_id": "KR-UNKNOWN", "reported_value": 1}]
    r = client.post(f"/api/goals/{goal['goal_id']}/checkins", json=body, headers={"X-Actor-Id": owner})
    assert r.status_code == 422


# ---------------------------------------------------------------- versioning & closed cycles
def test_target_change_is_versioned_and_needs_rationale(client, actors):
    goal = _active_goal(client, actors["Employee (has active goals)"])
    kr = goal["key_results"][0]
    h = {"X-Actor-Id": actors["Their manager"]}
    change = {"kr_targets": [{"kr_id": kr["kr_id"], "target_value": kr["target_value"] * 2}]}
    assert client.patch(f"/api/goals/{goal['goal_id']}", json=change, headers=h).status_code == 422
    r = client.patch(f"/api/goals/{goal['goal_id']}", json={**change, "rationale": "Scope doubled"}, headers=h)
    assert r.status_code == 200 and r.json()["current_version"] == goal["current_version"] + 1
    last = client.get(f"/api/goals/{goal['goal_id']}").json()["versions"][-1]
    assert last["change_type"] == "target_changed" and last["approved_by"] == actors["Their manager"]
    assert float(last["old_value"]) == kr["target_value"]                          # history kept


def test_closed_cycle_rejects_silent_edits(client, actors):
    closed = client.get("/api/goals", params={"cycle_id": "CYCLE-2026-H1", "status": "closed"}).json()["items"][0]
    url = f"/api/goals/{closed['goal_id']}"
    r = client.patch(url, json={"title": "Edited after close"}, headers={"X-Actor-Id": closed["employee_id"]})
    assert r.status_code == 409
    hr = {"X-Actor-Id": actors["HR partner"]}
    assert client.patch(url, json={"title": "Edited after close"}, headers=hr).status_code == 422
    r = client.patch(url, json={"title": "Edited after close", "rationale": "Approved typo fix"}, headers=hr)
    assert r.status_code == 200
    v = client.get(url).json()["versions"][-1]
    assert v["change_type"] == "post_close_correction" and v["approved_by"] == actors["HR partner"]
    # the audited correction must NOT be reported as a silent edit
    flags = client.get(url).json()["flags"]
    assert not [f for f in flags if f["entity_id"] == v["version_id"]]


# ---------------------------------------------------------------- feedback & reviews
def _h2_review(client, employee):
    items = client.get("/api/reviews", params={"cycle_id": "CYCLE-2026-H2", "size": 200}).json()["items"]
    return next(r for r in items if r["employee_id"] == employee)


def test_feedback_permissions_follow_relationships(client, actors):
    emp = actors["Employee (has active goals)"]
    review = _h2_review(client, emp)
    url = f"/api/reviews/{review['review_id']}/feedback"
    fb = {"competency_id": "COMP-01", "rating": 4, "comment": "Solid delivery"}
    assert client.post(url, json={**fb, "feedback_type": "manager"}, headers={"X-Actor-Id": actors["HR partner"]}).status_code == 403
    assert client.post(url, json={**fb, "feedback_type": "peer"}, headers={"X-Actor-Id": actors["Their manager"]}).status_code == 403
    assert client.post(url, json={**fb, "feedback_type": "self"}, headers={"X-Actor-Id": actors["Their manager"]}).status_code == 403
    r = client.post(url, json={**fb, "feedback_type": "manager"}, headers={"X-Actor-Id": review["reviewer_id"]})
    if r.status_code == 409:      # already rated this competency in the generated data
        assert "already" in r.json()["error"]["message"]
    else:
        assert r.status_code == 201 and r.json()["feedback"]["giver_employee_id"] == review["reviewer_id"]


def test_review_cannot_finalize_without_required_inputs(client, actors):
    emp = actors["Employee (has active goals)"]
    review = _h2_review(client, emp)
    rid, h_emp, h_mgr = review["review_id"], {"X-Actor-Id": emp}, {"X-Actor-Id": review["reviewer_id"]}
    is_mgr = client.get(f"/api/employees/{emp}").json()["role"] in ("manager", "executive")
    comps = [c["competency_id"] for c in client.get("/api/meta").json()["competencies"]
             if c["applies_to"] == "all" or is_mgr]
    # walk the lifecycle: self assessment -> manager assessment -> finalize
    if review["status"] == "not_started":
        r = client.post(f"/api/reviews/{rid}/transition", json={"to_status": "self_submitted"}, headers=h_emp)
        if "self_feedback" in (review["missing_inputs"] or ""):
            assert r.status_code == 422
            for c in comps:
                client.post(f"/api/reviews/{rid}/feedback", json={"feedback_type": "self", "competency_id": c,
                                                                 "rating": 4, "comment": "self view"}, headers=h_emp)
            r = client.post(f"/api/reviews/{rid}/transition", json={"to_status": "self_submitted"}, headers=h_emp)
        assert r.status_code == 200
    # finalizing straight from self_submitted is an illegal transition
    state = client.get(f"/api/reviews/{rid}").json()["status"]
    if state == "self_submitted":
        assert client.post(f"/api/reviews/{rid}/transition", json={"to_status": "finalized"}, headers=h_mgr).status_code == 409
    # only the reviewer may submit the manager assessment
    assert client.post(f"/api/reviews/{rid}/transition", json={"to_status": "manager_submitted"},
                       headers=h_emp).status_code in (403, 409)
    events = client.get(f"/api/reviews/{rid}").json()["events"]
    assert events[0]["to_status"] == "not_started"


def test_development_plan_approval_flow(client):
    plans = client.get("/api/development-plans", params={"size": 200}).json()["items"]
    pending = next((p for p in plans if any(a["decision"] == "pending" for a in p["approvals"])), None)
    if pending is None:
        return
    approver = next(a for a in pending["approvals"] if a["decision"] == "pending")["approver_id"]
    url = f"/api/development-plans/{pending['plan_id']}/decisions"
    assert client.post(url, json={"decision": "approved"}, headers={"X-Actor-Id": pending["employee_id"]}).status_code == 403
    r = client.post(url, json={"decision": "approved"}, headers={"X-Actor-Id": approver})
    assert r.status_code == 200 and r.json()["status"] in ("approved", "submitted")


def test_leadership_competency_only_for_managers(client):
    items = client.get("/api/reviews", params={"cycle_id": "CYCLE-2026-H2", "size": 200}).json()["items"]
    for r in items:
        if client.get(f"/api/employees/{r['employee_id']}").json()["role"] == "employee":
            resp = client.post(f"/api/reviews/{r['review_id']}/feedback",
                               json={"feedback_type": "self", "competency_id": "COMP-06", "rating": 3, "comment": "n/a"},
                               headers={"X-Actor-Id": r["employee_id"]})
            assert resp.status_code == 422
            return

"""Unit tests for the pure business rules (fast, no I/O)."""
from datetime import datetime

import pytest

from domain import rules


@pytest.mark.parametrize("start,target,value,expected", [
    (0, 10, 5, 50.0),          # increase KR
    (500, 300, 400, 50.0),     # decrease KR (lower is better)
    (0, 10, 15, 150.0),        # over-achievement stays visible in raw progress
    (0, 10, -2, -20.0),        # regression
])
def test_kr_raw_progress(start, target, value, expected):
    assert rules.kr_raw_progress(start, target, value) == expected


def test_scoring_cap_depends_on_rationale():
    assert rules.kr_scoring_progress(150, has_rationale=False) == 100
    assert rules.kr_scoring_progress(150, has_rationale=True) == 120
    assert rules.kr_scoring_progress(-5, has_rationale=False) == 0


def test_goal_progress_is_weighted():
    assert rules.goal_progress([(50, 100), (50, 0)]) == 50
    assert rules.goal_progress([(80, 100), (20, 50)]) == 90


def test_goal_score_excludes_inactive_goals_and_renormalises():
    goals = [(50, 80, "closed"), (30, 40, "cancelled"), (20, 100, "closed")]
    assert rules.goal_score_pct(goals) == round((50 * 80 + 20 * 100) / 70, 2)
    assert rules.goal_score_pct([(100, 50, "draft")]) is None


def test_target_at_uses_target_in_force_at_the_time():
    hist = [(datetime(2026, 3, 1), 100.0, 150.0), (datetime(2026, 5, 1), 150.0, 120.0)]
    assert rules.target_at(120.0, hist, datetime(2026, 2, 1)) == 100.0
    assert rules.target_at(120.0, hist, datetime(2026, 4, 1)) == 150.0
    assert rules.target_at(120.0, hist, datetime(2026, 6, 1)) == 120.0
    assert rules.target_at(77.0, [], datetime(2026, 6, 1)) == 77.0


@pytest.mark.parametrize("score,label", [(4.6, "Exceptional"), (4.0, "Exceeds"), (3.0, "Meets"),
                                         (2.2, "Partially Meets"), (1.5, "Below"), (None, None)])
def test_rating_bands(score, label):
    assert rules.rating_label(score) == label


def test_overall_requires_both_components():
    assert rules.overall_score(5.0, 3.0) == 4.2
    assert rules.overall_score(None, 3.0) is None


def test_review_completeness_lists_every_missing_input():
    missing = rules.review_missing_inputs(["C1", "C2"], {"C1"}, {"C1", "C2"}, ["G1", "G2"], {"G1"})
    assert missing == ["self_feedback", "checkin:G2"]
    assert rules.review_missing_inputs(["C1"], {"C1"}, {"C1"}, ["G1"], {"G1"}) == []
    assert rules.review_missing_inputs(["C1"], {"C1"}, {"C1"}, [], set()) == ["active_goal"]


def test_lifecycle_transitions():
    assert rules.can_transition(rules.REVIEW_TRANSITIONS, "self_submitted", "manager_submitted")
    assert not rules.can_transition(rules.REVIEW_TRANSITIONS, "not_started", "finalized")
    assert rules.can_transition(rules.GOAL_TRANSITIONS, "in_progress", "cancelled")
    assert not rules.can_transition(rules.GOAL_TRANSITIONS, "closed", "in_progress")


def test_plan_status_derives_from_approvals():
    mgr_ok = {"approver_role": "manager", "decision": "approved"}
    hr_pending = {"approver_role": "hr_partner", "decision": "pending"}
    assert rules.plan_status([], False, None) == "draft"
    assert rules.plan_status([mgr_ok], False, None) == "approved"
    assert rules.plan_status([mgr_ok, hr_pending], True, None) == "submitted"
    assert rules.plan_status([mgr_ok, {**hr_pending, "decision": "approved"}], True, "x") == "completed"
    assert rules.plan_status([{**mgr_ok, "decision": "rejected"}], False, None) == "rejected"
    assert rules.plan_requires_hr(1000.01) and not rules.plan_requires_hr(1000)


def test_mandatory_plan_rule():
    assert rules.plan_mandatory([1, 4, 4])
    assert rules.plan_mandatory([2, 2, 4])
    assert not rules.plan_mandatory([2, 3, 4])


def test_silent_post_close_edit():
    closed = datetime(2026, 8, 14, 18)
    after = datetime(2026, 9, 1)
    assert rules.is_silent_post_close_edit(closed, after, None, None)
    assert not rules.is_silent_post_close_edit(closed, after, "fix typo", "EMP-000001")
    assert not rules.is_silent_post_close_edit(closed, datetime(2026, 8, 1), None, None)
    assert not rules.is_silent_post_close_edit(None, after, None, None)

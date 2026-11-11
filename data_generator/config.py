"""Generator configuration. Scale is a single knob so starter and full datasets
come from exactly the same code path."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

DEFAULT_SEED = 20261022
GENERATOR_VERSION = "1.0.0"

PROFILES = {
    "starter": 0.05,   # 150 employees / 25 managers / 500 goals / 1,000 check-ins
    "full": 1.0,       # 3,000 employees / 500 managers / 10,000 goals / 20,000 check-ins
}


@dataclass
class GeneratorConfig:
    seed: int = DEFAULT_SEED
    scale: float = 1.0
    profile: str = "full"
    as_of: date = date(2026, 11, 11)       # fixed "today" -> reproducible lifecycle states

    base_employees: int = 3000             # includes the managers
    base_managers: int = 500
    base_goals: int = 10000
    base_checkins: int = 20000

    # Baseline behaviour rates
    transfer_rate: float = 0.06
    termination_rate: float = 0.04
    on_leave_rate: float = 0.02
    target_change_rate: float = 0.12
    title_change_rate: float = 0.03
    overachievement_rate: float = 0.06
    goal_without_checkin_rate: float = 0.015   # drives incomplete reviews
    self_submit_rate_closed: float = 0.97
    manager_submit_rate_closed: float = 0.96
    conflict_injection_rate: float = 0.05

    # Labelled anomaly volumes at full scale (scaled, minimum 3 each)
    anomalies_full: dict = field(default_factory=lambda: {
        "goal_id_owner_conflict": 25,
        "checkin_by_non_owner": 40,
        "progress_over_scale_no_rationale": 50,
        "review_by_non_manager": 25,
        "peer_feedback_no_relationship": 40,
        "silent_review_edit": 25,
        "silent_goal_edit": 20,
        "untraceable_feedback": 40,
    })

    def n(self, base: int, minimum: int = 1) -> int:
        return max(minimum, round(base * self.scale))

    def anomaly_count(self, key: str) -> int:
        return max(3, round(self.anomalies_full[key] * self.scale))


def config_for(profile: str | None = None, scale: float | None = None, seed: int | None = None) -> GeneratorConfig:
    if profile and profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose from {sorted(PROFILES)}")
    prof = profile or ("custom" if scale is not None else "full")
    sc = scale if scale is not None else PROFILES.get(prof, 1.0)
    return GeneratorConfig(seed=seed if seed is not None else DEFAULT_SEED, scale=sc, profile=prof)

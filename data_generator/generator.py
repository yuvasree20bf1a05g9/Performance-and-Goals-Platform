"""Deterministic synthetic data generator.

Pipeline (mirrors the brief):
  1. master data   -> employees, managers, assignments, cycles, competencies
  2. goals & KRs   -> goals, key_results, goal_versions
  3. transactions  -> checkins, kr_updates, evidence_links
  4. feedback      -> peer_nominations, feedback, reviews, review_events
  5. development   -> development_plans, plan_approvals
  6. anomalies     -> labelled edge cases injected into a valid baseline
  7. derive        -> all calculated columns recomputed from source records
  8. labels        -> scenario labels + expected review outcomes from documented rules

Every sub-step uses its own RNG stream (``seed:stream``) so tweaking one step never
reshuffles the others - a property that keeps diffs small and reviews easy.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from domain import quality_rules, rules
from domain.schema import DEPARTMENTS

from . import catalog as C
from .config import GeneratorConfig
from .derive import derive_all, eod


def d(s: str) -> date:
    return date.fromisoformat(s)


class Generator:
    def __init__(self, cfg: GeneratorConfig):
        self.cfg = cfg
        self.as_of = cfg.as_of
        self.ds: dict[str, list[dict]] = defaultdict(list)
        self.labels: list[dict] = []           # anomaly labels (entity refs resolved later)

    # ------------------------------------------------------------------ utils
    def rng(self, stream: str) -> random.Random:
        return random.Random(f"{self.cfg.seed}:{stream}")

    @staticmethod
    def wchoice(rng: random.Random, weights: dict):
        return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]

    @staticmethod
    def rdate(rng: random.Random, start: date, end: date) -> date:
        if end <= start:
            return start
        return start + timedelta(days=rng.randint(0, (end - start).days))

    @staticmethod
    def rdt(rng: random.Random, start: date, end: date) -> datetime:
        day = Generator.rdate(rng, start, end)
        return datetime.combine(day, time(rng.randint(9, 18), rng.randint(0, 59), rng.randint(0, 59)))

    # ------------------------------------------------------------------ run
    def run(self) -> tuple[dict, list[dict], list[dict]]:
        self.gen_org()
        self.gen_cycles_and_competencies()
        self.gen_goals()
        self.gen_checkins()
        self.gen_feedback_and_reviews()
        self.gen_development_plans()
        self.inject_anomalies()
        self.assign_event_ids()
        derive_all(self.ds, self.as_of)
        labels = self.finalize_labels()
        outcomes = self.review_outcomes(labels)
        return dict(self.ds), labels, outcomes

    # ================================================================== 1. ORG
    def gen_org(self):
        cfg, rng = self.cfg, self.rng("org")
        n_emp, n_mgr = cfg.n(cfg.base_employees, 20), cfg.n(cfg.base_managers, 12)
        n_vp = min(len(DEPARTMENTS), n_mgr - 2)
        n_dir = max(1, round(n_mgr * 0.10))
        n_line = n_mgr - 1 - n_vp - n_dir
        people = []

        def person(level, dept, hire):
            p = {"level": level, "dept": dept, "hire_date": hire, "_i": len(people)}
            people.append(p)
            return p

        ceo = person("executive", "Operations", d("2014-04-01"))
        vps = [person("vp", DEPARTMENTS[i], self.rdate(rng, d("2014-06-01"), d("2019-12-31"))) for i in range(n_vp)]
        dept_w = {k: v for k, v in C.DEPT_WEIGHTS.items()}
        dirs = [person("director", self.wchoice(rng, dept_w), self.rdate(rng, d("2015-01-01"), d("2022-06-30")))
                for _ in range(n_dir)]
        lines = [person("line_manager", self.wchoice(rng, dept_w), self.rdate(rng, d("2015-01-01"), d("2024-06-30")))
                 for _ in range(n_line)]
        ics = []
        for _ in range(n_emp - n_mgr):
            hire = (self.rdate(rng, d("2026-01-01"), d("2026-10-15")) if rng.random() < 0.08
                    else self.rdate(rng, d("2016-01-01"), d("2025-12-31")))
            ics.append(person("ic", self.wchoice(rng, dept_w), hire))

        # Employee IDs follow hiring order (like a real HRIS)
        for n, p in enumerate(sorted(people, key=lambda p: (p["hire_date"], p["_i"])), start=1):
            p["id"] = f"EMP-{n:06d}"

        # Manager profiles
        span = {"executive": 15, "vp": 12, "director": 10, "line_manager": 12}
        for p in [ceo, *vps, *dirs, *lines]:
            latest = min(p["hire_date"] + timedelta(days=3 * 365), d("2025-12-01"))
            p["manager_since"] = p["hire_date"] if p["level"] in ("executive", "vp") else self.rdate(rng, p["hire_date"], latest)
            p["max_span"] = span[p["level"]]
            p["reports"] = 0

        vp_by_dept = {p["dept"]: p for p in vps}
        dirs_by_dept, lines_by_dept = defaultdict(list), defaultdict(list)
        for p in dirs:
            dirs_by_dept[p["dept"]].append(p)
        for p in lines:
            lines_by_dept[p["dept"]].append(p)

        def pick_with_capacity(cands):
            open_ = [c for c in cands if c["reports"] < c["max_span"]]
            pool = open_ or sorted(cands, key=lambda c: c["reports"])[:1]
            choice = rng.choice(pool)
            choice["reports"] += 1
            return choice

        def upline(dept, level):
            if level == "line_manager" and dirs_by_dept[dept]:
                return pick_with_capacity(dirs_by_dept[dept])
            if level in ("line_manager", "director") and dept in vp_by_dept:
                return pick_with_capacity([vp_by_dept[dept]])
            return pick_with_capacity([ceo])

        for p in vps:
            p["mgr"] = pick_with_capacity([ceo])
        for p in dirs:
            p["mgr"] = upline(p["dept"], "director")
        for p in lines:
            p["mgr"] = upline(p["dept"], "line_manager")
        for p in ics:
            if lines_by_dept[p["dept"]] and rng.random() > 0.05:
                p["mgr"] = pick_with_capacity(lines_by_dept[p["dept"]])
            elif dirs_by_dept[p["dept"]]:
                p["mgr"] = pick_with_capacity(dirs_by_dept[p["dept"]])
            else:
                p["mgr"] = upline(p["dept"], "line_manager")

        # Roles, levels, titles, status
        hr_ics = [p for p in ics if p["dept"] == "HR"] or ics[:1]
        for i, p in enumerate(hr_ics):
            p["role"] = "hr_partner" if i == 0 or rng.random() < 0.5 else "employee"
        ops_ics = [p for p in ics if p["dept"] == "Operations" and "role" not in p]
        for i, p in enumerate(ops_ics):
            p["role"] = "admin" if i < 3 else ("it_ops" if rng.random() < 0.15 else "employee")
        for p in people:
            lvl = p["level"]
            if lvl == "ic":
                p.setdefault("role", "employee")
                p["job_level"] = rng.choices(["L1", "L2", "L3", "L4", "L5"], [15, 30, 30, 18, 7])[0]
                p["title"] = f"{C.LEVEL_PREFIX[p['job_level']]}{C.IC_TITLES[p['dept']]}"
            else:
                p["role"] = "executive" if lvl in ("executive", "vp") else "manager"
                p["job_level"] = {"executive": "L8", "vp": "L8", "director": "L7"}.get(lvl) or rng.choice(["L5", "L6"])
                p["title"] = {"executive": "Chief Executive Officer", "vp": f"VP, {p['dept']}",
                              "director": f"Director, {p['dept']}"}.get(lvl, f"Manager, {p['dept']}")
            p["status"], p["term"] = "active", None
        for p in ics:
            r = rng.random()
            if r < self.cfg.termination_rate:
                lo = max(d("2026-02-01"), p["hire_date"] + timedelta(days=60))
                if lo <= d("2026-10-31"):
                    p["status"], p["term"] = "terminated", self.rdate(rng, lo, d("2026-10-31"))
            elif r < self.cfg.termination_rate + self.cfg.on_leave_rate:
                p["status"] = "on_leave"

        # Effective-dated reporting lines + transfers (history is appended, never overwritten)
        assignments = []
        for p in sorted(people, key=lambda p: p["id"]):
            if p is ceo:
                continue
            start = max(p["hire_date"], p["mgr"]["manager_since"])
            assignments.append({"employee_id": p["id"], "manager_id": p["mgr"]["id"], "department": p["dept"],
                                "effective_from": start, "effective_to": p["term"],
                                "change_reason": "new_hire" if p["hire_date"] >= d("2026-01-01") else "initial"})
        by_emp = {a["employee_id"]: a for a in assignments}
        movable = [p for p in ics if p["status"] != "terminated" and p["hire_date"] < d("2026-01-01")]
        trng = self.rng("transfers")
        for p in trng.sample(movable, round(len(movable) * self.cfg.transfer_rate)):
            cur = by_emp[p["id"]]
            dept = p["dept"] if trng.random() < 0.8 else trng.choice([x for x in DEPARTMENTS if lines_by_dept[x]])
            cands = [m for m in lines_by_dept[dept] if m["id"] != cur["manager_id"]]
            if not cands:
                continue
            new_mgr = trng.choice(cands)
            when = self.rdate(trng, d("2026-02-01"), d("2026-10-15"))
            cur["effective_to"] = when - timedelta(days=1)
            reason = "reorg" if dept == p["dept"] and trng.random() < 0.25 else "transfer"
            new = {"employee_id": p["id"], "manager_id": new_mgr["id"], "department": dept,
                   "effective_from": when, "effective_to": None, "change_reason": reason}
            assignments.append(new)
            by_emp[p["id"]] = new
            p["dept"] = dept
        assignments.sort(key=lambda a: (a["employee_id"], a["effective_from"]))
        for n, a in enumerate(assignments, start=1):
            a["assignment_id"] = f"MA-{n:06d}"

        # Materialise tables
        lrng = self.rng("names")
        for p in sorted(people, key=lambda p: p["id"]):
            fn, ln = lrng.choice(C.FIRST_NAMES), lrng.choice(C.LAST_NAMES)
            self.ds["employees"].append({
                "employee_id": p["id"], "first_name": fn, "last_name": ln,
                "email": f"{fn.lower()}.{ln.lower()}.{p['id'][-6:]}@example.com",
                "department": p["dept"], "job_title": p["title"], "job_level": p["job_level"], "role": p["role"],
                "location": self.wchoice(lrng, C.LOCATION_WEIGHTS), "hire_date": p["hire_date"],
                "termination_date": p["term"], "employment_status": p["status"], "current_manager_id": None})
            if p["level"] != "ic":
                self.ds["managers"].append({"manager_id": p["id"], "management_level": p["level"],
                                            "max_span": p["max_span"], "manager_since": p["manager_since"],
                                            "is_active": True})
        self.ds["manager_assignments"] = assignments
        self.emp = {e["employee_id"]: e for e in self.ds["employees"]}
        self.mgr_level = {m["manager_id"]: m["management_level"] for m in self.ds["managers"]}
        self.line_managers = sorted(m for m, lvl in self.mgr_level.items() if lvl in ("line_manager", "director"))
        self.hr_partners = sorted(e["employee_id"] for e in self.ds["employees"] if e["role"] == "hr_partner")
        self.ceo_id = ceo["id"]
        rp = self.rng("perf")
        self.perf = {e: min(1.3, max(0.2, rp.gauss(0.78, 0.2))) for e in sorted(self.emp)}

    def _ix(self) -> quality_rules.Index:
        # lightweight index over whatever exists so far (assignments are final after gen_org)
        ds = {k: self.ds.get(k, []) for k in ["employees", "review_cycles", "goals", "key_results", "checkins",
                                              "reviews", "manager_assignments", "peer_nominations"]}
        return quality_rules.Index(ds, self.as_of)

    # ============================================================ 1b. CYCLES
    def gen_cycles_and_competencies(self):
        self.ds["review_cycles"] = [
            {"cycle_id": "CYCLE-2026-H1", "name": "2026 H1 Performance Cycle", "start_date": d("2026-01-01"),
             "end_date": d("2026-06-30"), "goal_setting_deadline": d("2026-01-31"),
             "review_deadline": d("2026-07-31"), "status": "closed", "closed_at": datetime(2026, 8, 14, 18, 0, 0)},
            {"cycle_id": "CYCLE-2026-H2", "name": "2026 H2 Performance Cycle", "start_date": d("2026-07-01"),
             "end_date": d("2026-12-31"), "goal_setting_deadline": d("2026-07-31"),
             "review_deadline": d("2027-01-31"), "status": "active", "closed_at": None},
            {"cycle_id": "CYCLE-2027-H1", "name": "2027 H1 Performance Cycle", "start_date": d("2027-01-01"),
             "end_date": d("2027-06-30"), "goal_setting_deadline": d("2027-01-31"),
             "review_deadline": d("2027-07-31"), "status": "planned", "closed_at": None},
        ]
        self.cycles = {c["cycle_id"]: c for c in self.ds["review_cycles"]}
        self.ds["competencies"] = [{"competency_id": cid, "name": n, "category": cat, "description": desc,
                                    "scale_min": 1, "scale_max": 5, "applies_to": ap}
                                   for cid, n, cat, desc, ap in C.COMPETENCIES]
        self.ix = self._ix()

    # ================================================================ 2. GOALS
    def _eligible(self, e: dict, cycle_id: str) -> bool:
        if e["employee_id"] == self.ceo_id:
            return False   # CEO goals are set by the board, outside this system
        hire_limit = {"CYCLE-2026-H1": d("2026-03-15"), "CYCLE-2026-H2": d("2026-09-15")}[cycle_id]
        if e["hire_date"] > hire_limit:
            return False
        t = e["termination_date"]
        if cycle_id == "CYCLE-2026-H1":
            return t is None or t > d("2026-06-30")
        return t is None or t >= d("2026-08-01")

    @staticmethod
    def split_weights(rng: random.Random, k: int, unit: int = 5, minimum: int = 10) -> list[int]:
        units, min_u = 100 // unit, minimum // unit
        alloc = [min_u] * k
        for _ in range(units - min_u * k):
            alloc[rng.randrange(k)] += 1
        return [a * unit for a in alloc]

    def gen_goals(self):
        cfg, rng = self.cfg, self.rng("goals")
        pairs = [(e["employee_id"], c) for c in ("CYCLE-2026-H1", "CYCLE-2026-H2")
                 for e in self.ds["employees"] if self._eligible(e, c)]
        target = cfg.n(cfg.base_goals, 10)
        if target < len(pairs):
            pairs = sorted(rng.sample(pairs, target))
        counts = {p: 1 for p in pairs}
        extra = target - len(pairs)
        while extra > 0:
            p = rng.choice(pairs)
            if counts[p] < 5:
                counts[p] += 1
                extra -= 1

        goal_seq = defaultdict(int)
        versions = []
        for (emp_id, cyc_id) in sorted(counts, key=lambda p: (p[1], p[0])):
            e, cyc = self.emp[emp_id], self.cycles[cyc_id]
            weights = self.split_weights(rng, counts[(emp_id, cyc_id)])
            for w in weights:
                goal_seq[emp_id] += 1
                gid = f"GOAL-{emp_id}-{goal_seq[emp_id]:03d}"
                cat = self.wchoice(rng, C.CATEGORY_WEIGHTS)
                title = rng.choice(C.GOAL_TITLES[cat]).format(dept=e["department"], h=cyc_id[-1])
                created_lo = max(cyc["start_date"] - timedelta(days=14), e["hire_date"] + timedelta(days=3))
                created = self.rdt(rng, created_lo, max(created_lo, cyc["goal_setting_deadline"]))
                status = self._goal_status(rng, e, cyc_id)
                g = {"goal_id": gid, "employee_id": emp_id, "cycle_id": cyc_id, "title": title, "category": cat,
                     "weight_pct": w, "status": status, "approved_by": None, "approved_at": None,
                     "created_at": created, "current_version": None, "progress_pct": None}
                vlist = [self._ver(g, None, "created", "title", None, title, emp_id, created)]
                if status != "draft":
                    submitted = created + timedelta(hours=rng.randint(1, 48))
                    vlist.append(self._ver(g, None, "status_changed", "status", "draft", "pending_approval",
                                           emp_id, submitted))
                approved = status in ("in_progress", "closed") or (status == "cancelled" and rng.random() < 0.7)
                if approved:
                    at = submitted + timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 6))
                    mgr = self.ix.manager_at(emp_id, at.date()) or self.ix.manager_at(emp_id, cyc["start_date"])
                    g["approved_by"], g["approved_at"] = mgr, at
                    vlist.append(self._ver(g, None, "status_changed", "status", "pending_approval", "in_progress",
                                           mgr, at))
                self.ds["goals"].append(g)
                self._gen_krs(rng, g, e)
                vlist += self._goal_changes(rng, g, cyc, approved)
                versions += vlist
        self.ds["goal_versions"] = versions
        self.goals = {g["goal_id"]: g for g in self.ds["goals"]}
        self.krs_by_goal = defaultdict(list)
        for k in self.ds["key_results"]:
            self.krs_by_goal[k["goal_id"]].append(k)

    def _goal_status(self, rng, e, cyc_id) -> str:
        if cyc_id == "CYCLE-2026-H1":
            return "cancelled" if rng.random() < 0.05 else "closed"
        if e["termination_date"]:
            return "cancelled"
        r = rng.random()
        return "draft" if r < 0.07 else "pending_approval" if r < 0.12 else "cancelled" if r < 0.14 else "in_progress"

    def _ver(self, g, kr_id, change_type, field, old, new, by, at, rationale=None, approved_by=None):
        return {"version_id": None, "goal_id": g["goal_id"], "kr_id": kr_id, "version_no": None,
                "change_type": change_type, "field_name": field, "old_value": old, "new_value": new,
                "changed_by": by, "changed_at": at, "rationale": rationale, "approved_by": approved_by}

    def _gen_krs(self, rng, g, e):
        templates = C.KR_TEMPLATES[e["department"]] + C.GENERIC_KRS
        k = rng.choices([1, 2, 3, 4], [20, 40, 30, 10])[0]
        chosen = rng.sample(templates, min(k, len(templates)))
        for i, (desc, mtype, unit, direction, (s_lo, s_hi), (d_lo, d_hi)) in enumerate(chosen, start=1):
            start = float(rng.randint(s_lo, s_hi)) if s_hi else 0.0
            delta = float(rng.randint(d_lo, d_hi))
            if direction == "decrease":
                delta = min(delta, start - 1) if start > 1 else delta
            target = start + delta if direction == "increase" else start - delta
            if mtype == "currency" and direction == "increase":
                target = float(round(target, -3)) or 1000.0
            self.ds["key_results"].append({
                "kr_id": f"KR-{g['goal_id']}-{i:02d}", "goal_id": g["goal_id"], "description": desc,
                "metric_type": mtype, "unit": unit, "direction": direction, "start_value": start,
                "target_value": target, "weight_pct": None, "current_value": None,
                "raw_progress_pct": None, "scoring_progress_pct": None})
        krs = self.ds["key_results"][-len(chosen):]
        for kr, w in zip(krs, self.split_weights(rng, len(krs), unit=5, minimum=10)):
            kr["weight_pct"] = w

    def _goal_changes(self, rng, g, cyc, approved) -> list[dict]:
        out = []
        if not approved:
            if g["status"] == "cancelled":
                at = g["created_at"] + timedelta(days=rng.randint(3, 20))
                out.append(self._ver(g, None, "status_changed", "status", "pending_approval", "cancelled",
                                     g["employee_id"], at))
            return out
        window_end = min(cyc["end_date"], self.as_of - timedelta(days=5))
        krs = [k for k in self.ds["key_results"] if k["goal_id"] == g["goal_id"]]
        mgr = g["approved_by"] or g["employee_id"]
        # Changed goals: re-baselined KR target with rationale + manager approval
        if rng.random() < self.cfg.target_change_rate and g["status"] != "cancelled":
            lo = g["approved_at"].date() + timedelta(days=20)
            hi = window_end - timedelta(days=20)
            if lo < hi:
                kr = rng.choice(krs)
                at = self.rdt(rng, lo, hi)
                old = kr["target_value"]
                factor = rng.choice([0.8, 0.85, 0.9, 1.1, 1.15, 1.2])
                new = round(kr["start_value"] + (old - kr["start_value"]) * factor, 0)
                if new != old and new != kr["start_value"]:
                    kr["target_value"] = float(new)
                    approver = self.ix.manager_at(g["employee_id"], at.date()) or mgr
                    out.append(self._ver(g, kr["kr_id"], "target_changed", "target_value", f"{old:.2f}",
                                         f"{new:.2f}", g["employee_id"], at,
                                         rng.choice(C.TARGET_CHANGE_RATIONALES), approver))
        if rng.random() < self.cfg.title_change_rate:
            at = self.rdt(rng, g["approved_at"].date() + timedelta(days=5), window_end)
            new_title = g["title"] + " (revised)"
            out.append(self._ver(g, None, "title_changed", "title", g["title"], new_title, g["employee_id"], at,
                                 "Clarified scope with manager", mgr))
            g["title"] = new_title
        if g["status"] == "cancelled":
            end = min(cyc["end_date"], self.as_of - timedelta(days=1))
            if g["cycle_id"] == "CYCLE-2026-H2" and self.emp[g["employee_id"]]["termination_date"]:
                end = self.emp[g["employee_id"]]["termination_date"]
            start = g["approved_at"].date() + timedelta(days=1)
            at = self.rdt(rng, start, max(start, end))
            g["_cancelled_on"] = at.date()
            out.append(self._ver(g, None, "status_changed", "status", "in_progress", "cancelled", mgr, at,
                                 "Goal no longer relevant"))
        if g["status"] == "closed":
            closed_at = self.cycles[g["cycle_id"]]["closed_at"] - timedelta(hours=rng.randint(1, 72))
            out.append(self._ver(g, None, "status_changed", "status", "in_progress", "closed", mgr, closed_at))
            # Boundary case: approved post-close correction (rationale + HR approval) is *allowed*
            if rng.random() < 0.005 and self.hr_partners:
                at = self.cycles[g["cycle_id"]]["closed_at"] + timedelta(days=rng.randint(5, 40))
                out.append(self._ver(g, None, "post_close_correction", "title", g["title"],
                                     g["title"] + " [corrected]", rng.choice(self.hr_partners), at,
                                     "Typo correction requested by employee", rng.choice(self.hr_partners)))
                g["title"] += " [corrected]"
        return out

    # ============================================================= 3. CHECKINS
    def gen_checkins(self):
        cfg, rng = self.cfg, self.rng("checkins")
        hist = defaultdict(list)
        for v in self.ds["goal_versions"]:
            if v["kr_id"] and v["field_name"] == "target_value":
                hist[v["kr_id"]].append((v["changed_at"], float(v["old_value"]), float(v["new_value"])))

        caps = {"closed": 6, "in_progress": 4, "cancelled": 2}
        weight = {"closed": 3.0, "in_progress": 2.0, "cancelled": 0.5}
        windows = {}
        for g in self.ds["goals"]:
            if g["approved_at"] is None or g["status"] not in caps:
                continue
            cyc = self.cycles[g["cycle_id"]]
            start = max(cyc["start_date"], g["approved_at"].date() + timedelta(days=7))
            end = min(cyc["end_date"], self.as_of - timedelta(days=1))
            term = self.emp[g["employee_id"]]["termination_date"]
            if term:
                end = min(end, term)
            if g.get("_cancelled_on"):
                end = min(end, g["_cancelled_on"])
            if start <= end:
                windows[g["goal_id"]] = (start, end)
        cap_of = {gid: min(caps[self.goals[gid]["status"]], (e - s).days + 1) for gid, (s, e) in windows.items()}
        eligible = sorted(windows)
        skip = {gid for gid in eligible if self.goals[gid]["status"] == "closed"
                and rng.random() < cfg.goal_without_checkin_rate}
        eligible = [gid for gid in eligible if gid not in skip]
        total = cfg.n(cfg.base_checkins, 20)
        counts = {gid: 0 for gid in eligible}
        for gid in eligible[:total]:
            counts[gid] = 1
        remaining = total - sum(counts.values())
        ws = [weight[self.goals[g]["status"]] for g in eligible]
        while remaining > 0:
            gid = rng.choices(eligible, ws)[0]
            if counts[gid] < cap_of[gid]:
                counts[gid] += 1
                remaining -= 1

        achieve = {}
        for kr in self.ds["key_results"]:
            p = self.perf[self.goals[kr["goal_id"]]["employee_id"]]
            a = min(1.0, max(0.0, rng.gauss(p, 0.2)))
            if rng.random() < cfg.overachievement_rate:
                a = rng.uniform(1.03, 1.35)
            achieve[kr["kr_id"]] = a

        checkins, updates, evidence = [], [], []
        for gid in eligible:
            k = counts[gid]
            if k == 0:
                continue
            g, (start, end) = self.goals[gid], windows[gid]
            cyc = self.cycles[g["cycle_id"]]
            span = (end - start).days + 1
            taken = set()
            for i in range(k):   # one date per equal slice of the window -> periodic cadence
                off = min(span - 1, int(span * (i + rng.random()) / k))
                while off in taken:
                    off = (off + 1) % span
                taken.add(off)
            dates = [start + timedelta(days=o) for o in sorted(taken)]
            owner = g["employee_id"]
            dept = self.emp[owner]["department"]
            for seq, day in enumerate(dates, start=1):
                frac_time = min(1.0, max(0.05, (day - cyc["start_date"]).days / (cyc["end_date"] - cyc["start_date"]).days))
                is_final = g["status"] == "closed" and seq == len(dates)
                mgr_now = self.ix.manager_at(owner, day)
                submitter = mgr_now if (mgr_now and rng.random() < 0.10) else owner
                c = {"checkin_id": None, "goal_id": gid, "cycle_id": g["cycle_id"], "submitted_by": submitter,
                     "checkin_date": day, "sequence_no": seq, "confidence": None, "note": None,
                     "goal_progress_pct": None}
                fracs = []
                for kr in self.krs_by_goal[gid]:
                    s = 1.0 if is_final else frac_time
                    f = max(0.0, achieve[kr["kr_id"]] * s + rng.gauss(0, 0.03))
                    tgt = rules.target_at(kr["target_value"], sorted(hist.get(kr["kr_id"], [])), eod(day))
                    val = kr["start_value"] + (tgt - kr["start_value"]) * f
                    val = float(round(val)) if kr["metric_type"] in ("count", "currency") else round(val, 2)
                    raw = rules.kr_raw_progress(kr["start_value"], tgt, val)
                    updates.append({"update_id": None, "checkin_id": c, "kr_id": kr["kr_id"], "reported_value": val,
                                    "raw_progress_pct": None,
                                    "over_scale_rationale": rng.choice(C.OVERACHIEVE_RATIONALES) if raw > 100 else None})
                    fracs.append(f / max(s, 0.05))
                pace = math.fsum(fracs) / len(fracs)
                c["confidence"] = "high" if pace >= 0.9 else "medium" if pace >= 0.65 else "low"
                c["note"] = rng.choice(C.CHECKIN_NOTES[c["confidence"]])
                checkins.append(c)
                if rng.random() < 0.65:
                    for n in range(1 if rng.random() < 0.8 else 2):
                        et = rng.choice(C.EVIDENCE_BY_DEPT[dept])
                        evidence.append({"evidence_id": None, "checkin_id": c, "kr_id": rng.choice(self.krs_by_goal[gid])["kr_id"]
                                         if rng.random() < 0.7 else None, "evidence_type": et, "uri": None,
                                         "added_by": submitter,
                                         "added_at": datetime.combine(day, time(rng.randint(9, 18), rng.randint(0, 59)))})
        # Chronological, zero-padded, immutable IDs
        checkins.sort(key=lambda c: (c["checkin_date"], c["goal_id"], c["sequence_no"]))
        for n, c in enumerate(checkins, start=1):
            c["checkin_id"] = f"CHK-{n:07d}"
        updates.sort(key=lambda u: (u["checkin_id"]["checkin_id"], u["kr_id"]))
        for n, u in enumerate(updates, start=1):
            u["update_id"], u["checkin_id"] = f"KRU-{n:07d}", u["checkin_id"]["checkin_id"]
        evidence.sort(key=lambda e: (e["checkin_id"]["checkin_id"], e["evidence_type"], e["added_at"]))
        for n, e in enumerate(evidence, start=1):
            e["evidence_id"], e["checkin_id"] = f"EVD-{n:07d}", e["checkin_id"]["checkin_id"]
            e["uri"] = f"https://evidence.example.com/{e['evidence_type']}/{e['evidence_id'].lower()}"
        self.ds["checkins"], self.ds["kr_updates"], self.ds["evidence_links"] = checkins, updates, evidence

    # ================================================== 4. FEEDBACK & REVIEWS
    def gen_feedback_and_reviews(self):
        cfg, rng = self.cfg, self.rng("reviews")
        comps = self.ds["competencies"]
        managers = {m["manager_id"] for m in self.ds["managers"]}
        goals_by_key = defaultdict(list)
        for g in self.ds["goals"]:
            goals_by_key[(g["employee_id"], g["cycle_id"])].append(g)
        with_checkins = {c["goal_id"] for c in self.ds["checkins"]}
        true_comp = {}
        reviews, events, feedback, noms = [], [], [], []
        rev_n = 0
        for cyc_id in ("CYCLE-2026-H1", "CYCLE-2026-H2"):
            cyc = self.cycles[cyc_id]
            closed = cyc["status"] == "closed"
            ref_day = min(cyc["end_date"], self.as_of)
            team = defaultdict(list)
            for e in self.ds["employees"]:
                m = self.ix.manager_at(e["employee_id"], ref_day)
                if m:
                    team[m].append(e["employee_id"])
            for emp_id in sorted({k[0] for k in goals_by_key if k[1] == cyc_id}):
                e = self.emp[emp_id]
                reviewer = self.ix.manager_at(emp_id, ref_day)
                if reviewer is None or (e["termination_date"] and e["termination_date"] <= ref_day):
                    continue
                rev_n += 1
                rid = f"REV-{cyc_id[6:10]}-{rev_n:06d}"
                req = rules.applicable_competencies(comps, emp_id in managers)
                p = self.perf[emp_id]
                for cid in req:
                    true_comp.setdefault((emp_id, cid), min(5.0, max(1.0, rng.gauss(3.4 + (p - 0.78) * 2.0, 0.6))))
                # Peer nominations (N:M bridge)
                peers = [x for x in team[reviewer] if x != emp_id]
                pool = sorted(set(peers) | {x["employee_id"] for x in rng.sample(self.ds["employees"], 12)
                                            if x["department"] == e["department"] and x["employee_id"] != emp_id})
                nom_lo = cyc["end_date"] - timedelta(days=25) if closed else d("2026-10-15")
                nom_hi = cyc["end_date"] if closed else self.as_of - timedelta(days=1)
                my_noms = []
                for peer in rng.sample(pool, min(3, len(pool))):
                    n = {"nomination_id": None, "cycle_id": cyc_id, "subject_employee_id": emp_id,
                         "peer_employee_id": peer, "nominated_by": rng.choice([emp_id, reviewer]),
                         "status": "accepted" if rng.random() < 0.85 else "declined",
                         "nominated_at": self.rdt(rng, nom_lo, nom_hi)}
                    noms.append(n)
                    my_noms.append(n)
                # Submission flags (source events)
                if closed:
                    self_ok = rng.random() < cfg.self_submit_rate_closed
                    mgr_ok = self_ok and rng.random() < cfg.manager_submit_rate_closed
                    self_at = self.rdt(rng, d("2026-07-01"), d("2026-07-18")) if self_ok else None
                    mgr_at = self.rdt(rng, d("2026-07-19"), d("2026-07-31")) if mgr_ok else None
                else:
                    self_ok = rng.random() < 0.35
                    mgr_ok = self_ok and rng.random() < 0.4
                    self_at = self.rdt(rng, d("2026-10-20"), d("2026-11-03")) if self_ok else None
                    mgr_at = self.rdt(rng, d("2026-11-04"), self.as_of - timedelta(days=1)) if mgr_ok else None
                ratings_self, ratings_mgr = {}, {}
                for cid in req:
                    t = true_comp[(emp_id, cid)]
                    if self_ok:
                        ratings_self[cid] = int(min(5, max(1, round(t + 0.35 + rng.gauss(0, 0.5)))))
                    if mgr_ok:
                        ratings_mgr[cid] = int(min(5, max(1, round(t + rng.gauss(0, 0.4)))))
                if self_ok and mgr_ok and rng.random() < cfg.conflict_injection_rate:   # conflicting feedback
                    for cid in rng.sample(req, rng.choice([1, 2])):
                        m = ratings_mgr[cid]
                        ratings_self[cid] = min(5, m + rng.choice([2, 3])) if m <= 3 else m - 2
                my_goals = goals_by_key[(emp_id, cyc_id)]
                goal_ids = [g["goal_id"] for g in my_goals]

                def fb(giver, ftype, cid, rating, at):
                    feedback.append({"feedback_id": None, "cycle_id": cyc_id, "subject_employee_id": emp_id,
                                     "giver_employee_id": giver, "feedback_type": ftype, "competency_id": cid,
                                     "rating": rating, "comment": C.FEEDBACK_COMMENTS[rating],
                                     "linked_goal_id": rng.choice(goal_ids) if rng.random() < 0.3 else None,
                                     "source": rng.choices(["in_app", "email", "imported_survey"], [85, 5, 10])[0],
                                     "submitted_at": at})
                for cid, r_ in ratings_self.items():
                    fb(emp_id, "self", cid, r_, self_at)
                for cid, r_ in ratings_mgr.items():
                    fb(reviewer, "manager", cid, r_, mgr_at)
                # Former manager input for transferred employees (valid relationship)
                former = self.ix.managers_during(emp_id, cyc["start_date"], ref_day) - {reviewer}
                for fm in sorted(former):
                    if rng.random() < 0.5:
                        for cid in rng.sample(req, 2):
                            t = true_comp[(emp_id, cid)]
                            fb(fm, "manager", cid, int(min(5, max(1, round(t + rng.gauss(0, 0.5))))),
                               self.rdt(rng, nom_lo, nom_hi))
                for n in my_noms:
                    if n["status"] == "accepted" and rng.random() < (0.8 if closed else 0.3):
                        for cid in rng.sample(req, rng.choice([2, 3])):
                            t = true_comp[(emp_id, cid)]
                            fb(n["peer_employee_id"], "peer", cid, int(min(5, max(1, round(t + rng.gauss(0, 0.8))))),
                               self.rdt(rng, n["nominated_at"].date() + timedelta(days=1),
                                        max(n["nominated_at"].date() + timedelta(days=1),
                                            cyc["review_deadline"] if closed else self.as_of - timedelta(days=1))))
                # Status follows the documented lifecycle; finalisation requires all inputs
                active_goals = [g for g in my_goals if g["status"] not in rules.INACTIVE_GOAL_STATUSES]
                inputs_ok = bool(active_goals) and all(g["goal_id"] in with_checkins for g in active_goals)
                status = "not_started"
                if self_ok:
                    status = "self_submitted"
                if mgr_ok:
                    status = "manager_submitted"
                fin_at = None
                if closed and mgr_ok and inputs_ok:
                    status = "finalized"
                    fin_at = self.rdt(rng, d("2026-08-01"), d("2026-08-13"))
                reviews.append({"review_id": rid, "cycle_id": cyc_id, "employee_id": emp_id, "reviewer_id": reviewer,
                                "status": status, "self_submitted_at": self_at, "manager_submitted_at": mgr_at,
                                "finalized_at": fin_at,
                                "manager_summary": rng.choice(C.MANAGER_SUMMARIES) if mgr_ok else None,
                                "goal_score_pct": None, "goal_rating": None, "competency_rating": None,
                                "overall_score": None, "overall_rating": None, "is_complete": None,
                                "missing_inputs": None})
                # Append-only review history
                def ev(etype, frm, to, actor, at, **kw):
                    events.append({"event_id": None, "review_id": rid, "event_type": etype, "from_status": frm,
                                   "to_status": to, "field_name": kw.get("field"), "old_value": kw.get("old"),
                                   "new_value": kw.get("new"), "actor_id": actor, "occurred_at": at,
                                   "rationale": kw.get("rationale"), "approved_by": kw.get("approved_by")})
                ev("status_change", None, "not_started", self.hr_partners[0] if self.hr_partners else reviewer,
                   datetime.combine(cyc["start_date"], time(9, 0)))
                if self_at:
                    ev("status_change", "not_started", "self_submitted", emp_id, self_at)
                if mgr_at:
                    ev("status_change", "self_submitted", "manager_submitted", reviewer, mgr_at)
                    if rng.random() < 0.05:
                        ev("comment_edit", None, None, reviewer, mgr_at + timedelta(days=1), field="manager_summary",
                           old="Draft summary", new=reviews[-1]["manager_summary"])
                if fin_at:
                    ev("status_change", "manager_submitted", "finalized", reviewer, fin_at)
                    if rng.random() < 0.005 and self.hr_partners:   # approved post-close correction (allowed)
                        hr = rng.choice(self.hr_partners)
                        new = reviews[-1]["manager_summary"] + " (HR-approved correction)"
                        ev("comment_edit", None, None, hr, cyc["closed_at"] + timedelta(days=rng.randint(3, 30)),
                           field="manager_summary", old=reviews[-1]["manager_summary"], new=new,
                           rationale="Factual correction after appeal", approved_by=hr)
                        reviews[-1]["manager_summary"] = new
        feedback.sort(key=lambda f: (f["submitted_at"], f["subject_employee_id"], f["feedback_type"], f["competency_id"],
                                     f["giver_employee_id"] or ""))
        for n, f in enumerate(feedback, start=1):
            f["feedback_id"] = f"FB-2026-{n:07d}"
        noms.sort(key=lambda n: (n["nominated_at"], n["subject_employee_id"], n["peer_employee_id"]))
        for n, x in enumerate(noms, start=1):
            x["nomination_id"] = f"PN-{n:07d}"
        self.ds["reviews"], self.ds["review_events"] = reviews, events
        self.ds["feedback"], self.ds["peer_nominations"] = feedback, noms

    # ======================================================= 5. DEV PLANS
    def gen_development_plans(self):
        rng = self.rng("plans")
        mgr_ratings = defaultdict(dict)
        reviewer = {r["review_id"]: r["reviewer_id"] for r in self.ds["reviews"]}
        rkey = {(r["employee_id"], r["cycle_id"]): r for r in self.ds["reviews"]}
        for f in self.ds["feedback"]:
            r = rkey.get((f["subject_employee_id"], f["cycle_id"]))
            if r and f["feedback_type"] == "manager" and f["giver_employee_id"] == r["reviewer_id"]:
                mgr_ratings[r["review_id"]][f["competency_id"]] = f["rating"]
        plans, approvals, n = [], [], 0
        for r in self.ds["reviews"]:
            if r["status"] != "finalized":
                continue
            ratings = mgr_ratings[r["review_id"]]
            lowest = min(ratings.values())
            mandatory = rules.plan_mandatory(list(ratings.values()))
            if not mandatory and not (lowest <= 3 and rng.random() < 0.10):
                continue
            n += 1
            cid = sorted(c for c, v in ratings.items() if v == lowest)[0]
            created = r["finalized_at"] + timedelta(days=rng.randint(1, 14), hours=rng.randint(0, 5))
            target = created.date() + timedelta(days=rng.randint(60, 180))
            cost = 0.0 if rng.random() < 0.55 else float(rng.randint(15, 300) * 10)
            p = {"plan_id": f"DP-2026-{n:06d}", "employee_id": r["employee_id"], "cycle_id": r["cycle_id"],
                 "review_id": r["review_id"], "competency_id": cid, "objective": C.PLAN_OBJECTIVES[cid],
                 "training_cost": cost, "requires_hr_approval": None, "target_date": target,
                 "created_at": created, "completed_at": None, "status": None}
            plans.append(p)
            if rng.random() < 0.05:
                continue   # still draft
            dec = rng.choices(["approved", "rejected", "pending"], [88, 4, 8])[0]
            m_at = created + timedelta(days=rng.randint(1, 10)) if dec != "pending" else None
            approvals.append({"plan_id": p["plan_id"], "approver_id": reviewer[r["review_id"]], "approver_role": "manager",
                              "decision": dec, "decided_at": m_at, "comment": None if dec != "rejected" else "Re-scope plan"})
            fully = dec == "approved"
            if dec == "approved" and rules.plan_requires_hr(cost) and self.hr_partners:
                hdec = rng.choices(["approved", "rejected", "pending"], [85, 5, 10])[0]
                approvals.append({"plan_id": p["plan_id"], "approver_id": rng.choice(self.hr_partners),
                                  "approver_role": "hr_partner", "decision": hdec,
                                  "decided_at": m_at + timedelta(days=rng.randint(1, 7)) if hdec != "pending" else None,
                                  "comment": None if hdec != "rejected" else "Budget not available"})
                fully = hdec == "approved"
            if fully and target < self.as_of and rng.random() < 0.6:
                p["completed_at"] = datetime.combine(target - timedelta(days=rng.randint(0, 20)), time(17, 0))
        for i, a in enumerate(approvals, start=1):
            a["approval_id"] = f"DPA-{i:06d}"
        self.ds["development_plans"], self.ds["plan_approvals"] = plans, [
            {k: a[k] for k in ("approval_id", "plan_id", "approver_id", "approver_role", "decision", "decided_at", "comment")}
            for a in approvals]

    # ========================================================= 6. ANOMALIES
    def _label(self, issue, sub, etype, obj, related, decision, rule, desc):
        self.labels.append({"issue_type": issue, "sub_type": sub, "entity_type": etype, "_obj": obj,
                            "related_ids": related, "expected_decision": decision, "rule_reference": rule,
                            "description": desc})

    def inject_anomalies(self):
        """Edge cases are injected into a valid baseline and labelled; unrelated rows untouched."""
        cfg, rng = self.cfg, self.rng("anomalies")
        touched_goals, touched_reviews, touched_fb = set(), set(), set()
        checkins_by_goal = defaultdict(list)
        for c in self.ds["checkins"]:
            checkins_by_goal[c["goal_id"]].append(c)
        reviews_by_key = {(r["employee_id"], r["cycle_id"]): r for r in self.ds["reviews"]}

        # A. Goal owner mismatch - owner field disagrees with the immutable goal_id
        active_count = defaultdict(int)
        for g in self.ds["goals"]:
            if g["status"] in ("closed", "in_progress"):
                active_count[(g["employee_id"], g["cycle_id"])] += 1
        # only owners with >= 2 active goals, so the original owner's review keeps a goal
        cands = sorted(g["goal_id"] for g in self.ds["goals"] if g["status"] in ("closed", "in_progress")
                       and checkins_by_goal[g["goal_id"]] and active_count[(g["employee_id"], g["cycle_id"])] >= 2)
        for gid in rng.sample(cands, min(cfg.anomaly_count("goal_id_owner_conflict"), len(cands))):
            g = self.goals[gid]
            orig = g["employee_id"]
            peers = sorted(e["employee_id"] for e in self.ds["employees"] if e["department"] == self.emp[orig]["department"]
                           and e["employee_id"] != orig and e["employment_status"] == "active")
            new = rng.choice(peers)
            g["employee_id"] = new
            touched_goals.add(gid)
            self._label("goal_owner_mismatch", "goal_id_owner_conflict", "goal", g, [orig, new, f"{orig}|{g['cycle_id']}",
                        f"{new}|{g['cycle_id']}"], "block_update_and_reassign_owner", "R1: goal owner must match goal_id",
                        f"Owner changed from {orig} to {new} without re-keying the goal")
        # B. Check-ins by someone who is neither owner nor owner's manager
        cands = [c for c in self.ds["checkins"] if c["goal_id"] not in touched_goals]
        active = sorted(e["employee_id"] for e in self.ds["employees"] if e["employment_status"] == "active")
        for c in rng.sample(cands, min(cfg.anomaly_count("checkin_by_non_owner"), len(cands))):
            owner = self.goals[c["goal_id"]]["employee_id"]
            bad = {owner, self.ix.manager_at(owner, c["checkin_date"])}
            c["submitted_by"] = rng.choice([x for x in active if x not in bad])
            for ev in self.ds["evidence_links"]:
                if ev["checkin_id"] == c["checkin_id"]:
                    ev["added_by"] = c["submitted_by"]
            self._label("goal_owner_mismatch", "checkin_by_non_owner", "checkin", c, [c["goal_id"], c["submitted_by"]],
                        "reject_checkin", "R1: only goal owner or their manager may check in",
                        f"{c['submitted_by']} updated a goal they do not own")
            touched_goals.add(c["goal_id"])

        # C. Progress beyond scale without rationale (on the latest update so it drives current progress)
        latest = {}
        ck = {c["checkin_id"]: c for c in self.ds["checkins"]}
        for u in self.ds["kr_updates"]:
            key = (ck[u["checkin_id"]]["checkin_date"], ck[u["checkin_id"]]["sequence_no"])
            if u["kr_id"] not in latest or key > latest[u["kr_id"]][0]:
                latest[u["kr_id"]] = (key, u)
        krs = {k["kr_id"]: k for k in self.ds["key_results"]}
        cands = sorted((u for _, u in latest.values() if not u["over_scale_rationale"]
                        and krs[u["kr_id"]]["goal_id"] not in touched_goals), key=lambda u: u["update_id"])
        hist_krs = {v["kr_id"] for v in self.ds["goal_versions"] if v["kr_id"]}
        cands = [u for u in cands if u["kr_id"] not in hist_krs]
        for u in rng.sample(cands, min(cfg.anomaly_count("progress_over_scale_no_rationale"), len(cands))):
            kr = krs[u["kr_id"]]
            f = rng.uniform(1.15, 1.6)
            val = kr["start_value"] + (kr["target_value"] - kr["start_value"]) * f
            u["reported_value"] = float(round(val)) if kr["metric_type"] in ("count", "currency") else round(val, 2)
            u["over_scale_rationale"] = None
            self._label("progress_over_scale_no_rationale", "missing_rationale", "kr_update", u,
                        [u["kr_id"], u["checkin_id"], kr["goal_id"]], "cap_progress_at_100_and_request_rationale",
                        "R2: progress > 100% requires a rationale",
                        f"Reported {f*100:.0f}% of target with no rationale")
            touched_goals.add(kr["goal_id"])

        # D. Reviewer lacks relationship (review + peer feedback)
        fb_by_key = defaultdict(list)
        for f in self.ds["feedback"]:
            fb_by_key[(f["subject_employee_id"], f["cycle_id"])].append(f)
        cands = sorted(r["review_id"] for r in self.ds["reviews"] if r["status"] == "finalized")
        rev_by_id = {r["review_id"]: r for r in self.ds["reviews"]}
        for rid in rng.sample(cands, min(cfg.anomaly_count("review_by_non_manager"), len(cands))):
            r = rev_by_id[rid]
            cyc = self.cycles[r["cycle_id"]]
            related = self.ix.managers_during(r["employee_id"], cyc["start_date"], cyc["end_date"])
            new = rng.choice([m for m in self.line_managers if m not in related and m != r["employee_id"]])
            old = r["reviewer_id"]
            r["reviewer_id"] = new
            for f in fb_by_key[(r["employee_id"], r["cycle_id"])]:
                if f["feedback_type"] == "manager" and f["giver_employee_id"] == old:
                    f["giver_employee_id"] = new
                    touched_fb.add(f["feedback_id"])
            for e in self.ds["review_events"]:
                if e["review_id"] == rid and e["actor_id"] == old:
                    e["actor_id"] = new
            touched_reviews.add(rid)
            self._label("reviewer_lacks_relationship", "review_by_non_manager", "review", r,
                        [r["employee_id"], new], "invalidate_review_and_reassign_to_actual_manager",
                        "R3: reviewer must have managed the employee during the cycle",
                        f"{new} reviewed {r['employee_id']} without a reporting relationship")
        peer_fb = [f for f in self.ds["feedback"] if f["feedback_type"] == "peer" and f["feedback_id"] not in touched_fb]
        for f in rng.sample(peer_fb, min(cfg.anomaly_count("peer_feedback_no_relationship"), len(peer_fb))):
            subj = self.emp[f["subject_employee_id"]]
            noms = {(n["peer_employee_id"]) for n in self.ds["peer_nominations"]
                    if n["subject_employee_id"] == subj["employee_id"] and n["cycle_id"] == f["cycle_id"]}
            outsiders = [x for x in active if x not in noms and x != subj["employee_id"]
                         and self.emp[x]["department"] != subj["department"]]
            f["giver_employee_id"] = rng.choice(outsiders)
            touched_fb.add(f["feedback_id"])
            rv = reviews_by_key.get((f["subject_employee_id"], f["cycle_id"]))
            self._label("reviewer_lacks_relationship", "peer_feedback_no_relationship", "feedback", f,
                        [rv["review_id"] if rv else None, f["giver_employee_id"]], "discard_feedback",
                        "R3: peer feedback requires an accepted nomination",
                        f"{f['giver_employee_id']} gave peer feedback without a nomination")

        # E. Closed cycle accepts silent edits
        closed_at = self.cycles["CYCLE-2026-H1"]["closed_at"]
        cands = sorted(r["review_id"] for r in self.ds["reviews"]
                       if r["status"] == "finalized" and r["review_id"] not in touched_reviews)
        for rid in rng.sample(cands, min(cfg.anomaly_count("silent_review_edit"), len(cands))):
            r = rev_by_id[rid]
            new = "Revised after close: " + rng.choice(C.MANAGER_SUMMARIES)
            ev = {"event_id": None, "review_id": rid, "event_type": "comment_edit", "from_status": None,
                  "to_status": None, "field_name": "manager_summary", "old_value": r["manager_summary"],
                  "new_value": new, "actor_id": r["reviewer_id"],
                  "occurred_at": closed_at + timedelta(days=rng.randint(1, 60), hours=rng.randint(1, 8)),
                  "rationale": None, "approved_by": None}
            r["manager_summary"] = new
            self.ds["review_events"].append(ev)
            self._label("closed_cycle_silent_edit", "review_event_after_close", "review_event", ev, [rid],
                        "revert_change_and_audit", "R4: edits after close need rationale + approval",
                        "Manager summary edited after cycle close without approval")
        cands = sorted(g["goal_id"] for g in self.ds["goals"] if g["cycle_id"] == "CYCLE-2026-H1"
                       and g["status"] == "closed" and g["goal_id"] not in touched_goals)
        for gid in rng.sample(cands, min(cfg.anomaly_count("silent_goal_edit"), len(cands))):
            g = self.goals[gid]
            kr = rng.choice(self.krs_by_goal[gid])
            old = kr["target_value"]
            new = float(round(kr["start_value"] + (old - kr["start_value"]) * 0.8)) or old - 1
            if new == kr["start_value"]:
                new = round(old * 0.9, 2)
            kr["target_value"] = new
            v = self._ver(g, kr["kr_id"], "target_changed", "target_value", f"{old:.2f}", f"{new:.2f}",
                          g["employee_id"], closed_at + timedelta(days=rng.randint(1, 60), hours=2))
            self.ds["goal_versions"].append(v)
            touched_goals.add(gid)
            self._label("closed_cycle_silent_edit", "goal_version_after_close", "goal_version", v, [gid, kr["kr_id"]],
                        "revert_change_and_audit", "R4: edits after close need rationale + approval",
                        "KR target lowered after cycle close, inflating progress")

        # F. Untraceable feedback
        cands = [f for f in self.ds["feedback"] if f["feedback_type"] == "peer" and f["feedback_id"] not in touched_fb]
        for f in rng.sample(cands, min(cfg.anomaly_count("untraceable_feedback"), len(cands))):
            f["giver_employee_id"], f["source"], f["linked_goal_id"] = None, "imported_survey", None
            rv = reviews_by_key.get((f["subject_employee_id"], f["cycle_id"]))
            self._label("untraceable_feedback", "missing_giver", "feedback", f, [rv["review_id"] if rv else None],
                        "exclude_from_scoring_and_trace_source", "R5: every feedback row must name its giver",
                        "Imported feedback has no giver reference")

    def assign_event_ids(self):
        vers = sorted(self.ds["goal_versions"], key=lambda v: (v["goal_id"], v["changed_at"]))
        per_goal = defaultdict(int)
        for n, v in enumerate(vers, start=1):
            per_goal[v["goal_id"]] += 1
            v["version_no"], v["version_id"] = per_goal[v["goal_id"]], f"GV-{n:07d}"
        self.ds["goal_versions"] = vers
        evs = sorted(self.ds["review_events"], key=lambda e: (e["review_id"], e["occurred_at"]))
        for n, e in enumerate(evs, start=1):
            e["event_id"] = f"REVEV-{n:07d}"
        self.ds["review_events"] = evs

    # ============================================================ 7. LABELS
    def finalize_labels(self) -> list[dict]:
        pk = {"goal": "goal_id", "checkin": "checkin_id", "kr_update": "update_id", "review": "review_id",
              "feedback": "feedback_id", "review_event": "event_id", "goal_version": "version_id",
              "manager_assignment": "assignment_id"}
        ck = {c["checkin_id"]: c for c in self.ds["checkins"]}
        rev_cycle = {r["review_id"]: r["cycle_id"] for r in self.ds["reviews"]}
        out = []
        for l in self.labels:
            obj = l.pop("_obj")
            l["entity_id"] = obj[pk[l["entity_type"]]]
            goal_id = obj.get("goal_id") or (ck[obj["checkin_id"]]["goal_id"] if obj.get("checkin_id") else None)
            l["cycle_id"] = obj.get("cycle_id") or self.goals.get(goal_id or "", {}).get("cycle_id") or \
                rev_cycle.get(obj.get("review_id"))
            l["label_kind"] = "anomaly"
            l["related_ids"] = sorted({x for x in l["related_ids"] if x})
            out.append(l)

        # Scenario labels derived by documented rules from the final data
        def scen(issue, etype, eid, related, cycle, decision, rule, desc):
            out.append({"label_kind": "scenario", "issue_type": issue, "sub_type": issue, "entity_type": etype,
                        "entity_id": eid, "related_ids": sorted(set(related)), "cycle_id": cycle,
                        "expected_decision": decision, "rule_reference": rule, "description": desc})
        for v in self.ds["goal_versions"]:
            if v["change_type"] in ("target_changed", "title_changed") and v["rationale"] and v["approved_by"]:
                scen("changed_goal", "goal_version", v["version_id"], [v["goal_id"]], self.goals[v["goal_id"]]["cycle_id"],
                     "use_latest_approved_value", "S1: approved mid-cycle change is versioned",
                     f"{v['field_name']} changed {v['old_value']} -> {v['new_value']}")
        for a in self.ds["manager_assignments"]:
            if a["change_reason"] in ("transfer", "reorg"):
                scen("manager_transfer", "manager_assignment", a["assignment_id"], [a["employee_id"], a["manager_id"]],
                     "CYCLE-2026-H1" if a["effective_from"] <= d("2026-06-30") else "CYCLE-2026-H2",
                     "reviewer_is_manager_at_cycle_end", "S2: transfers create a new effective-dated row",
                     f"{a['employee_id']} moved to {a['manager_id']} on {a['effective_from']}")
        for r in self.ds["reviews"]:
            if r["cycle_id"] == "CYCLE-2026-H1" and not r["is_complete"]:
                scen("incomplete_review", "review", r["review_id"], [r["employee_id"]], r["cycle_id"],
                     "hold_from_calibration", "S3: completion requires all inputs", f"missing: {r['missing_inputs']}")
        rk = {(r["employee_id"], r["cycle_id"]): r["review_id"] for r in self.ds["reviews"]}
        conflicts = defaultdict(list)
        for cyc, subj, comp in quality_rules.conflicting_feedback(self.ds):
            conflicts[(subj, cyc)].append(comp)
        for (subj, cyc), comps in sorted(conflicts.items()):
            scen("conflicting_feedback", "review", rk[(subj, cyc)], comps, cyc, "flag_for_calibration",
                 "S4: |self - manager| >= 2 on a competency", f"conflict on {', '.join(comps)}")
        for u in self.ds["kr_updates"]:
            if u["raw_progress_pct"] > 100 and u["over_scale_rationale"]:
                scen("overachievement_with_rationale", "kr_update", u["update_id"], [u["kr_id"]], None,
                     "allow_stretch_credit_up_to_120", "S5: justified over-achievement is capped at 120%",
                     f"raw {u['raw_progress_pct']}% with rationale")
        for n, l in enumerate(out, start=1):
            l["label_id"] = f"GT-{n:06d}"
        cols = ["label_id", "label_kind", "issue_type", "sub_type", "entity_type", "entity_id", "related_ids",
                "cycle_id", "expected_decision", "rule_reference", "description"]
        return [{c: l.get(c) for c in cols} for l in out]

    def review_outcomes(self, labels: list[dict]) -> list[dict]:
        invalid = {l["entity_id"] for l in labels if l["sub_type"] == "review_by_non_manager"}
        conflict = {l["entity_id"] for l in labels if l["issue_type"] == "conflicting_feedback"}
        out = []
        for r in self.ds["reviews"]:
            closed = self.cycles[r["cycle_id"]]["status"] == "closed"
            if r["review_id"] in invalid:
                dec = "invalidate_and_reassign"
            elif not r["is_complete"]:
                dec = "hold_incomplete" if closed else "in_progress"
            elif r["review_id"] in conflict:
                dec = "calibrate_then_finalize"
            else:
                dec = "finalize"
            out.append({"review_id": r["review_id"], "cycle_id": r["cycle_id"], "employee_id": r["employee_id"],
                        "expected_is_complete": r["is_complete"], "expected_overall_score": r["overall_score"],
                        "expected_overall_rating": r["overall_rating"], "expected_decision": dec})
        return out

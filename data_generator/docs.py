"""Renders docs/data_dictionary.md from domain.schema (Step 1)."""
from __future__ import annotations

from pathlib import Path

from domain import rules
from domain.schema import RELATIONSHIPS, TABLES


def write_data_dictionary(path: Path) -> None:
    L = ["# Data dictionary", "",
         "> Auto-generated from `domain/schema.py` by `python manage.py generate`. Do not edit by hand.", "",
         "Legend: **PK** primary key, **FK** foreign key, **U** unique, **D** derived (calculated from other "
         "records, never random), **Req** required.", "",
         "## Tables", ""]
    for t in TABLES:
        L += [f"### `{t.name}` - {t.entity} ({t.kind})", "", t.description, "",
              "| Field | Type | Req | Keys | Allowed values / range | Unit | Description |",
              "|---|---|---|---|---|---|---|"]
        for f in t.fields:
            keys = []
            if f.name == t.pk:
                keys.append("PK")
            if f.fk:
                keys.append(f"FK -> `{f.fk}`")
            if f.unique and f.name != t.pk:
                keys.append("U")
            if f.derived:
                keys.append("D")
            allowed = ", ".join(f"`{a}`" for a in f.allowed) if f.allowed else ""
            if f.pattern:
                allowed = f"pattern `{f.pattern}`"
            if f.min is not None or f.max is not None:
                allowed = (allowed + " " if allowed else "") + f"[{f.min if f.min is not None else ''} .. {f.max if f.max is not None else ''}]"
            L.append(f"| `{f.name}` | {f.type} | {'yes' if f.required else 'no'} | {' '.join(keys)} | {allowed} | "
                     f"{f.unit or ''} | {f.description} |")
        L.append("")
    L += ["## Relationships and cardinality", "", "| From | To | Cardinality | Notes |", "|---|---|---|---|"]
    L += [f"| `{a}` | `{b}` | {c} | {n} |" for a, b, c, n in RELATIONSHIPS]
    L += ["", "## Derivation rules", "",
          "| Value | Rule |", "|---|---|",
          "| KR raw progress | `(value - start) / (target_effective_at_checkin - start) * 100` (works for decrease KRs) |",
          f"| KR scoring progress | clamp to [0, {rules.SCORING_CAP_DEFAULT:.0f}], or [0, {rules.SCORING_CAP_WITH_RATIONALE:.0f}] when the latest update carries an over-scale rationale |",
          "| Goal progress | KR-weighted average of scoring progress |",
          "| Review goal score | goal-weighted average of active goals (draft / pending / cancelled excluded, weights re-normalised) |",
          "| Goal rating | `1 + 4 * min(goal_score, 100) / 100` |",
          "| Competency rating | mean of the reviewer's manager ratings on required competencies |",
          f"| Overall score | `{rules.GOAL_WEIGHT_IN_OVERALL} * goal_rating + {rules.COMPETENCY_WEIGHT_IN_OVERALL} * competency_rating` - only when complete |",
          "| Overall rating | >=4.5 Exceptional, >=3.75 Exceeds, >=2.75 Meets, >=2.0 Partially Meets, else Below |",
          "| Review complete | full self assessment + full reviewer assessment + >=1 check-in on every active goal |",
          f"| Plan requires HR | `training_cost > {rules.HR_APPROVAL_COST_THRESHOLD:.0f}` |",
          "| Mandatory development plan | any competency rated 1, or two or more rated <= 2 (otherwise optional) |",
          "| Plan status | draft (no approvals) / rejected (any) / approved (all required) / completed (approved + completed_at) / submitted |",
          "", "## Lifecycle states", "",
          "* **Review cycle:** planned -> active -> calibration -> closed (closed cycles are edit-locked).",
          "* **Goal:** draft -> pending_approval -> in_progress -> closed; cancel allowed from any non-terminal state.",
          "* **Review:** not_started -> self_submitted -> manager_submitted -> finalized (finalize requires completeness).",
          "* **Manager assignment:** effective-dated; a transfer closes the old row and opens a new one.",
          "* **Development plan:** draft -> submitted -> approved / rejected -> completed.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8", newline="\n")

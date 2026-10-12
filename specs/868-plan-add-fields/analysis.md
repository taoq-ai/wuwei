# Specification Analysis Report: 868-plan-add-fields

Artifacts read: spec.md, plan.md, tasks.md; the constitution (III one behaviour one function,
IV test first, V ponytail); the design spec on admission after the gate; `plan.py` (`add`,
`_proposal`), `dispatch.py` (`_start`, `candidate`), `commands/worktree.py`, `shepherd.py` and
`commands/build.py` (the other `plan.add` callers), `charters/planner.md`.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| B1 | Duplication | HIGH | FR-002 | Validating `--track` with argparse choices and flags separately would be a second path. | Resolved: argparse only parses; `_admitted` is the one check, called by `_proposal` and `add`. |
| B2 | Regression | HIGH | FR-003 | Requiring `--repo` could break the other `plan.add` callers (an adopted PR in `shepherd`, the main-broken fix item in `build`, a seat finding). | Resolved: the requirement applies to owner items only (`source` empty); Assumption 2. |
| B3 | Coverage | MEDIUM | US1.1 | `worktree add` without `--repo` reads the proposal row only. | Resolved: `_start` passes `--repo` from the item's record, so the start command needs no change in `worktree add`. |
| B4 | Ambiguity | MEDIUM | Input "recorded on the owner's card" | `plan add` has no Owner step card. | Resolved: Assumption 1; values are recorded on the item and the `plan.added` event. Raising a track or a flag lowers no gate. |
| B5 | Docs | LOW | T005 | The planner charter names the admission command. | Resolved: one sentence names the new options; the user docs follow. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 options recorded | yes | T001-T004 |
| FR-002 one validation | yes | T003, T004 |
| FR-003 repo required, known | yes | T001, T002 |
| FR-004 start reads item repo | yes | T001, T002 |

**Constitution alignment**: III (one validation function), IV (tests first), V (no new
module). No conflict.

**Metrics**: 4 requirements, 6 tasks, 100% coverage, 0 CRITICAL, 2 HIGH (resolved).

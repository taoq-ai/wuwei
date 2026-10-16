# Specification analysis: gate-rules

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Dependency | LOW | spec.md Assumptions | free-lines-3 (#1104) edits hook.py and verdict.py | Merged origin/main before push; the suite re-ran green on the merge |
| A2 | Scope | LOW | charters/builder.md | The AUTH rule names a WUWEI fixture in a charter other repositories read | A repository without the corpus writes N.A. with the reason |
| A3 | Ambiguity | LOW | spec.md Clarifications | planner.md is not built into agents/ | Acceptance 5 reads the charter; it is vendored into .claude/ |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 main worktree | yes | T006 | |
| FR-002 Write tool | yes | T006 | |
| FR-003 mutant re-run | yes | T006 | |
| FR-004 stub execution | yes | T006 | |
| FR-005 normalisation round | yes | T007 | |
| FR-006 route corpus | yes | T007 | |
| FR-007 line budget | yes | T008 | |
| FR-008 wording | yes | T002, T004, T005 | |
| FR-009 build, vendor | yes | T009, T010 | |

## Constitution alignment

No conflict: strings only in the runtime, no door change, no config key, budget not raised.

# Requirements Checklist: 839-edges-exact-argv

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Every removed unit is classed (a) or (b), and each (b) unit names its new home [plan.md unit table]
- [x] CHK002 Merge, approve, admin, branch protection, deploy and outward send block with `guards.enforce` false [FR-007, US1.9, Assumption 1]
- [x] CHK003 A bare `gh pr create` for a recorded item and the seat launch contract block with enforce on [US1.7, US5]
- [x] CHK004 Canary and marker scans of `gh` bodies keep the records floor [Assumption 5, analysis R3]

## Completeness

- [x] CHK005 Each edge's exact argv, near misses and refusal text are specified [What changes, US1, US3]
- [x] CHK006 The splitter's unwrapping, here-doc handling, ceilings and unreadable outcome are specified [What changes, Edge Cases, FR-003]
- [x] CHK007 Every caller of each deleted `shell.py` function is listed with its fate [plan.md callers table]
- [x] CHK008 Every file deleted, moved and edited is listed, tests included [plan.md]
- [x] CHK009 Retired config keys considered: none [Assumption 10, plan.md RETIRED]
- [x] CHK010 Integrity is a SessionStart warning and the #831 reconfirm card stays [US4]

## Consistency

- [x] CHK011 Design spec 4.1, 4.5, 4.7, 9.1, 9.2 and constitution II edits match the behaviour [plan.md Governance]
- [x] CHK012 No host-terminal text, no new wall, no loosened test [Assumption 6, analysis T1, T2]
- [x] CHK013 Docs edits follow the pass plan; the rest is deferred to part 24 [spec Deferred]

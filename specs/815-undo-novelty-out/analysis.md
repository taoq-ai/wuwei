# Specification Analysis Report: 815-undo-novelty-out

**Artifacts read**

- spec.md, plan.md and tasks.md
- `.specify/memory/constitution.md` (1.5.0)
- the #789 pass plan
- the code and tests at ac5403f, with part 9's plan applied

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Inconsistency | HIGH | conftest `rehearsed_undo` | The autouse fixture faked commit and decision as rehearsed. Tests may rely on the correction for `merge`, `message`, `other` and class-less records. | Resolved: T003 runs both decision test files in full and handles each case (delete a test of the deleted rule, or make its record one-way). Recorded in plan Risks. |
| A2 | Coverage | HIGH | FR-005, `merge.monitor` | Deleting the journal could break the kept red-base revert. | Resolved: `merge.revert` and the `monitor` red path stay. `tests/test_merge.py:995-1005` keeps the revert test, and T010 runs the whole file. |
| D1 | Constitution | HIGH | design spec edits | The design spec is amended only by its owner. | Resolved: the edits are part of the owner-approved #789 pass (Assumption 8). |
| D2 | Constitution | HIGH | Workflow, invariant rule | Rows I22, I23 and I33 go. | Resolved: the rules they guard are deleted. Skip this if #798 removed the walk. |
| S1 | Scope | MEDIUM | FR-006 | The issue asks `init --upgrade` to remove "the retired files". #799 handles keys, not files. | Resolved: one `RETIRED_FILES` tuple in `init.py` also takes part 9's `memory/cruise.json`. A red test comes first (T007). |
| C1 | Coverage | MEDIUM | Assumption 1 (#600) | The config-write correction goes without a replacement. | Accepted: a config record never reaches the mandate (#529), so only the card text changes. `test_calibrate.py` keeps the card a Routine value card. |
| C2 | Coverage | LOW | Assumption 2 | A two-way message record can now be taken by the mandate. | Accepted: the record sends nothing, and the outbound tiers gate the send. |
| E1 | Edge case | LOW | spec Edge Cases | Old `novel` route fields and `undo.jsonl` files stay on disk. | Accepted: nothing reads them, and they are day history. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 written door routes | yes | T001, T002 |
| FR-002 no lint correction | yes | T001, T002 |
| FR-003 no seen set | yes | T004, T005 |
| FR-004 commands, rows, events, sections gone | yes | T007, T008, T009 |
| FR-005 journal gone, revert kept | yes | T008, T009, T010 |
| FR-006 init removes files | yes | T007, T008 |
| FR-007 charters and docs | yes | T011, T012 |

**Constitution Alignment**

- D1 and D2 are resolved.
- Principles I to III hold.
- Principle IV holds: each behaviour change has a red test first (T001, T004, T007).
- Principle V holds: net deletion.

**Unmapped Tasks**: none.

**Metrics**: 7 requirements and 13 tasks; coverage is 100%. There are 4 HIGH findings, all
resolved, and no CRITICAL.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to the checklist and
implement.

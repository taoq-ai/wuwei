# Specification Analysis Report: 864-governed-by-file

Artifacts read: spec.md, plan.md, tasks.md; the constitution (II three-state exits, III one
behaviour one function, IV test first, V ponytail, VII owner-only decisions on a card); the
design spec on the governing document (#664) and admission after the gate; `plan.py`,
`specmode.py`, `dispatch.py` (`launch_set`, `_start`), `brief.py` (builder brief path),
`commands/build.py` (`build analysis`).

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Duplication | HIGH | FR-002, plan Design 2 | A second governed_by check at propose would duplicate `specmode.governing` and drift from what the brief reads. | Resolved: `plan.governed` calls `specmode.governing`; the directory rule lives only there, so propose, set, start, brief and `build analysis` share it. |
| A2 | Coverage | HIGH | US3 | The issue's acceptance is that the stuck item does not hold a seat and the next item launches; a check only at propose leaves states approved on 0.28.0 stuck. | Resolved: FR-005 and T007/T008 check at `_start`, reusing the #603 park path that takes no seat. |
| A3 | Ambiguity | MEDIUM | US1.3 | Which tree resolves a reference before the worktree exists. | Resolved: Assumption 1 and `plan.checkout` (worktree, else the named or only repository, else shape only). |
| A4 | Security | MEDIUM | US2 | `plan set governed_by=` changes what governs an item after the gate. | Resolved: the Owner step card, as `spec=skipped`; the value is in the card's command, so a Yes binds to that value. `specmode.governing` already refuses absolute paths and paths that leave the tree. |
| A5 | Exit codes | LOW | US2.2 | Resolution failure exit. | Resolved: ValueError, exit 2, as every plan JSON shape error; the missing Yes is exit 1. |
| A6 | Scope | LOW | Deferred | Other brief refusals could also hold a seat. | Recorded under Deferred. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 directory rule | yes | T001, T002 |
| FR-002 one check | yes | T003, T004 |
| FR-003 propose refuses | yes | T003, T004 |
| FR-004 plan set governed_by | yes | T005, T006 |
| FR-005 start parks | yes | T007, T008 |

**Constitution alignment**: II (exit 2 for invalid input, exit 1 for the owner's missing Yes),
III (one check), IV (tests precede each implementation task), V (no new module or abstraction),
VII (owner card). No conflict.

**Metrics**: 5 requirements, 9 tasks, 100% coverage, 0 CRITICAL, 2 HIGH (resolved).

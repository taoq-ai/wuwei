# Requirements Checklist: 901-reconcile

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 Each review claim is checked against the base branch with its lines, and the ones that hold have a failing test [spec Claims checked]
- [x] CHK002 The issue's test cases are covered: three repositories, dirty work, an item in implement, a missing build record, interruption, repeat [US1]
- [x] CHK003 The owner decision on the launch guard has its refusal, its exit and the enforce-off log [US2]
- [x] CHK004 PR, branch and repository inputs, and the refusals that need explicit resolution [US3]

## Quality

- [x] CHK005 Tests run red before the code [tasks Phase 1]
- [x] CHK006 Nothing outside counts as tested or approved [A3]
- [x] CHK007 No new loop between the guard and `build next`, also at CAP [A1, A2]
- [x] CHK008 Reuse over new code: adoption, claim, brief, checks; the checkout path and the adoption recipe are shared [plan Constitution Check]
- [x] CHK009 No emojis, no em-dashes, no absolute local paths [all artifacts]

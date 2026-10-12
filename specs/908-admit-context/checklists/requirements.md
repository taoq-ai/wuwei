# Requirements Checklist: 908-admit-context

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 Each review claim is checked against the base branch, and each one that holds has a failing test [spec Claims checked]
- [x] CHK002 The issue's tests are covered: identical filenames and PR numbers in three repositories, a seat finding outside the first goal, an owner item admitted by title, an adopted worktree outside worktrees/ITEM [US1 to US4]
- [x] CHK003 Ambiguous provenance gets one refusal naming the exact flags, never a first goal or repository [US1-3, FR-002, FR-007]

## Quality

- [x] CHK004 Tests run red before the code [tasks Phase 1]
- [x] CHK005 Shared spots only: plan.add, dispatch._start, one id helper [plan Constitution Check]
- [x] CHK006 No new state kind or event [plan Constitution Check]
- [x] CHK007 No emojis, no em-dashes, no absolute local paths [all artifacts]

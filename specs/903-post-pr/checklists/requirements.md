# Requirements Checklist: 903-post-pr

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 Each claim is checked against this branch with its lines; each that holds has a failing test [spec Claims checked]
- [x] CHK002 The issue's test: one PR, one required delta review, no raise command [US1, US2]
- [x] CHK003 The red-checks-at-gate field case and the --complete lease case [US3, US4]
- [x] CHK004 The all-gate reread for an unrelated moved head is kept [FR-001]

## Quality

- [x] CHK005 Tests run red before the code [tasks Phase 1]
- [x] CHK006 Hook paths stay pure reads [plan Constitution Check]
- [x] CHK007 Remote-head lease, clean-tree checks and teammate protection kept [FR-004, FR-008]
- [x] CHK008 Claimed-only paths deleted where one path covers both [plan Summary]
- [x] CHK009 No emojis, no em-dashes, no absolute local paths [all artifacts]

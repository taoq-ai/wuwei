# Requirements Checklist: 904-recovery

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 Each issue claim is checked against 0.29.1 with its lines, and the ones that hold have a failing test [spec Claims checked]
- [x] CHK002 The repair, the unchanged failure and the owner's resume are covered for the environment class [US1, US2]
- [x] CHK003 Every round-cap check site is named [FR-003]
- [x] CHK004 Security, PARK-verdict and owner parks stay with the owner [Edge Cases, A8]

## Quality

- [x] CHK005 Tests run red before the code [tasks Phase 1]
- [x] CHK006 Unchanged failures stay bounded [A1, A2, A3]
- [x] CHK007 The fix is at shared spots and deletes the `granted` special case [plan Constitution Check]
- [x] CHK008 No emojis, no em-dashes, no absolute local paths [all artifacts]

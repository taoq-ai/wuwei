# Requirements Checklist: 910-gates-that-fit

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 Each review claim is checked against current main and named held or not [spec What happened]
- [x] CHK002 Three gates on two seats, a second opinion on a spent runtime, a stopped builder awaiting checks are each a test [US1, US2]
- [x] CHK003 Eventual progress without exceeding host seats or CAP is asserted end to end [US1]
- [x] CHK004 The kept gate-first rule is stated [Assumptions]
- [x] CHK005 Head pinning and invalidation are tested on a deferred seat [Edge Cases]

## Quality

- [x] CHK006 Tests ran red before the code [tasks T005]
- [x] CHK007 One count, `next.building`; the four sums and the guard's live builder count are gone [FR-003]
- [x] CHK008 No emojis, no em-dashes, no absolute local paths [all artifacts]

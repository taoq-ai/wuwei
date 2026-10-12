# Requirements Checklist: 902-one-action

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 Each listed contradiction is checked against the base branch with its lines; each that holds has a failing test [spec Claims checked]
- [x] CHK002 The issue's test cases are covered: missing receipts, changed verdict files, lost delta seats, failed shepherds [US3]
- [x] CHK003 One gate decision for next and dispatch next, execution in dispatch [FR-001, FR-002]
- [x] CHK004 resolve_offer keeps the action; build next and next share the resolver [FR-003, FR-004]

## Quality

- [x] CHK005 Tests run red before the code [tasks Phase 1]
- [x] CHK006 Hook paths stay pure reads [A1]
- [x] CHK007 No merge, approval or trust-boundary protection lowered [A2, A3]
- [x] CHK008 No generic workflow framework; the duplicate decision table is deleted [plan Constitution Check]
- [x] CHK009 No emojis, no em-dashes, no absolute local paths [all artifacts]

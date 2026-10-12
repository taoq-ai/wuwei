# Requirements Checklist: 898-memory-floor

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 The root cause names where the floor is and is not applied, and the three seat counters [spec Root cause]
- [x] CHK002 Below, at, unmeasured and off are each a test [US1]
- [x] CHK003 Seat launches wait with a timed re-check; runs without a seat are never held [FR-004]
- [x] CHK004 Adhoc, handed-back, stopped and unmeasured seats hold no slot [US2]

## Quality

- [x] CHK005 Tests run red before the code; no test reads the machine's memory [tasks T005]
- [x] CHK006 The floor is read once, in `dispatch.host`; the count is one helper, `brief.live` [FR-003, FR-005]
- [x] CHK007 No emojis, no em-dashes, no absolute local paths [all artifacts]

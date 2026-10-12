# Tasks: a seat's end is recorded apart from acceptance of its report

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `test_malformed_usage_keeps_the_result` (FR-001): three malformed shapes.
- [x] T002 [US1] `test_unrecorded_result_ends_the_seat_and_keeps_its_report` (FR-003, FR-005,
  FR-006): seat unmeasured, report kept, next offers `--verdict`, result recorded once.
- [x] T003 [US1] `test_late_or_foreign_stop_never_ends_the_bound_seat` (FR-002).
- [x] T004 [US1] `test_duplicate_stop_records_once` (FR-004).
- [x] T005 [US2] `test_stuck_seat_offers_its_transcript_report` and
  `test_unreadable_report_still_offers_unmeasured` (FR-005, FR-006).
- [x] T006 run them; seven fail on main for the stated reasons.

## Phase 2: implementation (green)

- [x] T007 `build.stopped`: `Mismatch`, unmeasured usage (FR-001, FR-002).
- [x] T008 `agent_launch.stop` and `_unrecorded`; `state.stop_seat` `report`, `expected`
  (FR-002, FR-003, FR-004).
- [x] T009 `brief.keep_report`, `brief.recovery`, `next`, `seat stop --verdict` (FR-005, FR-006).
- [x] T010 docs: recovery and reference.

## Fix round (review F1, F2)

- [x] T012 tests first: kept report Write and shell write refused; tampered kept report refused;
  mismatched message keeps the transcript turn, or nothing (FR-003, FR-007).
- [x] T013 `protect_state._protected_name`, `report_sha256`, `kept_report` check, `_unrecorded`
  keeps `tail_turn`.

- [x] T014 review D1: tests first (a file swapped after the check is never recorded; a symlinked
  `reports` directory keeps nothing), then one read of the kept bytes passed to
  `stop_with_report`.

## Phase 3: verification

- [x] T011 full suite under 3.12; stop-path files under 3.11.

# Tasks: build next never hands out a brief a seat already used

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_build_next.py`: `test_a_brief_a_seat_already_ran_continues_that_seat`
  (FR-001 to FR-003, SC-001); run it, see `build next` answer while the seat runs.
- [x] T002 [US1] the `recorded` case (a 0.29.0 record on the used brief).

## Phase 2: implementation (green)

- [x] T003 [US1] `next_action` used-seat binding (FR-001, FR-002, FR-003).

## Phase 3: verification

- [x] T004 build, brief, hooks, agent_launch, next and dispatch files under 3.12 and 3.11.

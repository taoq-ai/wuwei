# Tasks: a resumed item whose build finished goes on to its gates

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_plan.py`: `test_plan_resume_continues_from_the_build_record`, park
  then resume in every phase (FR-001, FR-002, SC-002); run it, see the `implement`/`done` and
  `fix`/`done` rows fail.
- [x] T002 [US1] `tests/test_next.py`: `test_resumed_item_whose_build_finished_goes_to_its_gates`
  (SC-001); run it, see `next` offer `wuwei build next A` instead of the gates.

## Phase 2: implementation (green)

- [x] T003 [US1] `cli/wuwei/commands/build.py`: `AFTER` and `built` out of `complete_checks`
  (FR-003).
- [x] T004 [US1] `cli/wuwei/plan.py` `resume`: advance a `done` build phase through
  `build.built` (FR-001).

## Phase 3: verification

- [x] T005 Run every test file that imports `wuwei.plan` or `wuwei.commands.build` under 3.12,
  and the next, build and state tests under 3.11.

## Phase 4: review fix round

- [x] T006 F1: `tests/test_build_next.py` `test_park_during_passing_checks_keeps_the_item_parked`
  (red: the item ended at `gate`); `build.built` re-checks the phase under the writer lock
  and leaves a paused item to `plan resume`.
- [x] T007 F3: `tests/test_build_next.py` `test_checks_passing_while_parked_still_run_the_spec_step`
  (red: the build went `done`); the spec-step check in `complete_checks` reads the paused
  item's `resume_phase`.

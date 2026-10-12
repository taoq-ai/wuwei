# Tasks: environment failures are holds, an approved resume moves the build on

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `test_build_next.py`: `test_a_missing_interpreter_holds_for_a_recheck_and_the_repair_moves_on`;
  `test_build.py`: `test_environment_failure_holds_after_first_check_without_feedback` (FR-001).
- [x] T002 [US1, US2] `test_an_unchanged_environment_failure_parks_and_a_resume_rechecks_once` (FR-001, FR-002).
- [x] T003 [US2] `test_a_resumed_stuck_build_continues_its_builder_once` (FR-002).
- [x] T004 [US3] `test_dispatch.py` round-three test updated to the documented grant;
  `test_pr_actions.py` and `test_derive.py` resume-at-cap tests (FR-003).
- [x] T005 [US4] `test_derive.py`: `test_a_released_owner_merge_is_not_a_hold`; `test_loop.py`
  stores the real record (FR-004).
- [x] T006 run them, see each fail for the stated reason.

## Phase 2: implementation (green)

- [x] T007 [US1] `complete_checks` environment hold, `recheck`, `run_loop` stop (FR-001).
- [x] T008 [US2] `plan.resume` build reset (FR-002).
- [x] T009 [US3] `dispatch.capped` and its callers; `open_fix` drops `granted` (FR-003).
- [x] T010 [US4] `derive.offers` uses `merge.owner_hold` (FR-004).
- [x] T011 `docs/site/concepts.md` Park.

## Phase 3: verification

- [x] T012 every importing test file under 3.12; the named files under 3.11.

## Phase 4: review fix round

- [x] T013 [US2, US3] red: `test_a_resumed_build_spends_the_resume_at_its_check` (stuck and
  environment), `test_a_build_park_resume_spent_by_its_check_grants_nothing_at_the_gates` (PARK,
  ESCALATE), and a `derive._gate` assertion in the round-three test (FR-005, FR-006).
- [x] T014 `build.checked` ends the grant in `dispatch._resumed`; `derive._gate` uses `capped`;
  the Codex hold message names only `bin/wuwei build check <item>`.

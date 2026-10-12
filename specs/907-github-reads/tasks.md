# Tasks: one evidence read per PR action, a listing read per repository, briefs without a standing doctor run

**Input**: [spec.md](spec.md), [plan.md](plan.md), [../900-listing-unmeasured/spec.md](../900-listing-unmeasured/spec.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_pr_actions.py`: `test_one_pr_action_collects_one_evidence_bundle`
  (act, launch, thread); red: `[2, 2, 2]` reads.
- [x] T002 [US2] `tests/test_derive.py`: `test_each_repository_refreshes_alone_and_a_failed_one_keeps_its_retry_time`;
  900 US1: `test_a_failed_repository_leaves_its_pr_rows_unmeasured_and_the_others_usable`; red.
- [x] T003 [US2] `tests/test_next.py`: `test_issue_acceptance_907_an_unchanged_next_makes_no_remote_call`
  (three repositories, thirteen PR lanes); red: 2 calls on every next.
- [x] T004 [US3] `tests/test_brief.py`: the Doctor line is conditional; counterparts read the
  listing (no `pr` call); red.
- [x] T005 [US4] `tests/test_charters.py`: `test_no_seat_polls_the_code_host`.

## Phase 2: implementation (green)

- [x] T006 `pr_actions`: `evaluate(read=)`; `launch`, `act`, `_rebase` use it (FR-001).
- [x] T007 `derive`: `listing.repos`, `stale` per repository, `refresh(names)`, unmeasured rows
  (FR-002; 900 FR-001).
- [x] T008 `next`: due repositories only; unmeasured rows wait and print (900 FR-002).
- [x] T009 `brief`: `DOCTOR` conditional; counterparts from the listing (FR-003, FR-004; 900 FR-003).
- [x] T010 `_common.md` rule 5, `bin/wuwei agents build` (FR-005).

## Phase 3: verification

- [x] T011 Changed modules' test files on 3.12 (pipeline venv); derive, next, pr_actions, brief,
  charters on 3.11.

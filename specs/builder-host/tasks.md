# Tasks: builder-host

## Phase 1: Tests first

- [x] T001 Worktree from origin/main 1b8ef2b on `leone/builder-host`; runtime 3,697
- [x] T002 [US1] tests/test_plan.py: `--host` stored, defaulted to agent, refused otherwise (CLI and `plan.add`); `plan session` records a session item and refuses an agent item or a missing id
- [x] T003 [US2] tests/test_watch.py: a recorded session builder is a live seat (`hosted=True`) that names its session, absent from the hook's default read, gone once the item is done
- [x] T004 [US3] tests/test_charters.py: the planner's `create_session` paragraph and gates as Agent-tool seats; builder standard 7 in the charter and the generated agent
- [x] T005 Red at 1b8ef2b's runtime and charters: 4 failed, 311 passed

## Phase 2: Implementation

- [x] T006 `plan.HOSTS`, `plan.add(host=)`, `add_from` passes `host`; CLI `--host` and `plan session`
- [x] T007 `board.running(hosted=)`; `compute` and `flow` read hosted seats; `hook.py` unchanged
- [x] T008 Vendored copy (`setup.vendor('.')`); runtime 3,709 (+12, cap +14). Green: 122 passed (test_plan, test_watch)
- [x] T009 Charters (planner rule 1, builder standard 7), `bin/wuwei agents build`, vendored copy; docs/site/reference.md and docs/design.md section 6. Green: 359 passed (test_charters, test_setup, test_plan, test_watch)

## Phase 3: Proof

- [x] T010 8 mutants on both runtime copies, one at a time: 6 killed at first; the `flow` stale read and the `add_from` host survived, so tests/test_flow.py and tests/test_plan.py gained a case each and both are now killed (8 of 8). The flow test's `running` stub takes `hosted`
- [x] T011 The full suite once before the final push: 3750 passed, 5 skipped

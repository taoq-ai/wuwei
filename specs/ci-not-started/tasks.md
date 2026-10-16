# Tasks: a head with no CI checks registered yet reads as CI not started

## Phase 1: Tests first

- [x] T001 Read the real Actions runs shape for taoq-ai/wuwei with one read-only call (`total_count`, `workflow_runs[].path`, `workflow_runs[].event`)
- [x] T002 [US1] Empty rollup with a pull_request run prints `- CI not started at aaaaaaa [waiting]`, exit 1, and the Actions call is made with `per_page=1` (tests/test_evidence.py)
- [x] T003 [US1] No pull_request run: no gap, as on main (tests/test_evidence.py)
- [x] T004 [US1] GhError, `workflow_runs: null` and a non-JSON reply count as CI (tests/test_evidence.py)
- [x] T005 [US1] The Actions read is made once across two evidence reads (tests/test_evidence.py)
- [x] T006 [US2] `gh pr merge 5 -R o/r --auto --squash` is refused naming the gap; with only CI running it passes (tests/test_guards.py)
- [x] T007 [US3] FIX at the old head, no checks at the new head: both gaps named (tests/test_evidence.py)
- [x] T008 Run the new tests on e34586d: 7 red, T003 green (holds on main)

## Phase 2: Implementation

- [x] T009 Add the empty-rollup check and gap in `evidence.gaps`
- [x] T010 Name #1085 on the merge door's `--auto` exemption comment
- [x] T011 Run the new tests green

## Phase 3: Integration

- [x] T012 Merge origin/main (free-lines-3, #1104) and resolve the test_guards.py append conflict
- [x] T013 Re-vendor `.claude/` with `setup.vendor`
- [x] T014 Full suite green; runtime at 2,992 lines
- [x] T015 Compare `wuwei evidence o/r#5` and the `--auto` door on main and head with a stubbed code host

## Phase 4: Gate findings at 97553d7

- [x] T016 [US1] Two repositories keep their own cached Actions answer (quality, blocking: a shared key survived)
- [x] T017 [US1] A failed Actions read is not cached; the next read retries (quality note)
- [x] T018 [US2] A plain merge without --auto is refused on the gap (goal note)
- [x] T019 Name the gap in docs/site/concepts/evidence.md and docs/design.md section 6 (arch notes)

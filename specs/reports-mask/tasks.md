# Tasks: a kept seat report is masked before it is written

## Phase 1: Tests first

- [x] T001 [US1] A kept report with a ghp_ token and the canary holds *** for both in the file and the planner's note (tests/test_hook.py)
- [x] T002 [US2] A kept report with neither is written unchanged (tests/test_hook.py)
- [x] T003 [US3] A masked report repeated is kept once, and a raw task notification makes it a pointer (tests/test_hook.py)
- [x] T004 [US1, US3] A Codex native kept report is masked and its raw final answer makes it a pointer (tests/test_native_evidence.py)
- [x] T005 Run the new tests red

## Phase 2: Implementation

- [x] T006 Mask the kept report and compare the masked text in `subagent_stop` (cli/wuwei/hook.py)
- [x] T007 Mask the notified text before comparing in `deliver` and `_native_told` (cli/wuwei/hook.py)
- [x] T008 Copy to .claude/wuwei/cli/wuwei/hook.py
- [x] T009 Run the full suite green, runtime at 4,000 or fewer

## Phase 3: Docs and checks

- [x] T010 docs/design.md SubagentStop row names the masking
- [x] T011 Mutants of each new mask, on both copies one at a time, each fail a test

## Phase 4: Fix round on c70bbcb

- [x] T012 A full-length sk- key and github_pat_ token glued to the canary leave no canary fragment (tests/test_hook.py), run red
- [x] T013 A kept report with the canary file absent, empty or blank has every secret masked and keeps a NUL (tests/test_hook.py), run red
- [x] T014 One `mask()` helper, canary first, at all seven sites; copy to the vendored hook.py
- [x] T015 docs/site/concepts/hooks.md names the masking; the PR body carries How this fails
- [x] T016 Mutants of the helper (secrets first, raw without a canary, NUL stand-in) each fail a test

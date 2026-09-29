# Tasks: Scope stop verdict lint

## Phase 1: Setup

- [X] T001 Read design, constitution, hook contracts and existing guard code; reproduce supplied dry-run evidence read-only and record findings in specs/166-stop-lint-scope/plan.md.
- [X] T002 Complete specs/166-stop-lint-scope/spec.md and plan.md with assumptions and requirements checklist.

## Phase 2: User Story 1

Independent test: a registered quality stop ignores other seats, refuses its own invalid
verdict with filename and row, and fails closed on unreadable ownership evidence.

- [X] T003 [US1] Add ownership, cross-seat, filename, error and scope table tests in tests/test_verdict.py; update tests/test_retro.py hook integration; run and confirm expected failures.
- [X] T004 [US1] Extract existing stop ownership lookup in cli/wuwei/guards/agent_launch.py and reuse it from cli/wuwei/guards/verdict.py to select only the owned verdict and name refusals.
- [X] T005 [US1] Run tests/test_verdict.py, tests/test_retro.py and tests/test_agent_launch.py, preserving write lint and lifecycle behavior.

## Phase 3: Verification

- [X] T006 Run the full pytest suite and review changed files for scope, prohibited local paths, em-dashes and emojis; record results in specs/166-stop-lint-scope/tasks.md.

## Dependencies and Implementation Strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006. One story is the complete MVP.
Tests precede implementation. No parallel work is needed for this shared guard change;
independent verification can inspect the spec while the suite runs.

## Deferred

None.

## Validation Evidence

- Before implementation: 9 ownership table failures and 10 hook integration failures,
  showing cross-seat lint, missing filename diagnostics and missing ownership checks.
- Scope regression: unrelated override and anchored worktree cases both failed before
  reusing the shared scope helper.
- Targeted suite: 359 passed.
- Read-only replay with the original quality transcript now returns 0 with no rejections.
- Full suite: 4941 passed, 5 skipped in 110.22s (0:01:50).
- Skips: three timing checks under host load and two optional ZIRAN audits.
- Final diff review and hygiene checks passed; changes remain uncommitted.

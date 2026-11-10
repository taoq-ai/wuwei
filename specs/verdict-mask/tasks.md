# Tasks: verdict files and the verdict.missing row are masked before they sync

## Phase 1: Tests first

- [x] T001 [US1] A worktree verdict with a ghp_ token and the canary is copied in masked, attested at the copy's hash, and passes a repeat stop (tests/test_hook.py)
- [x] T002 [US2] A verdict written in the workspace is masked in place before its hash, and evidence.verdicts still counts it (tests/test_hook.py)
- [x] T003 [US2] A verdict with no match keeps its bytes, a stray non-UTF-8 byte included (tests/test_hook.py)
- [x] T004 [US3] verdict.missing quotes a malformed finding line with *** for the token and the canary (tests/test_hook.py)
- [x] T005 [US3] verdict.missing masks before its cut, swept over 55 path lengths (tests/test_hook.py)
- [x] T006 Run the new tests red (4 failed, T003 passed as a regression guard)

## Phase 2: Implementation

- [x] T007 `scrub` over `hook.mask` in `_verdict_problem`, applied at the copy-in and the in-place rewrite (cli/wuwei/hook.py)
- [x] T008 Mask `problem` before the cut in `_seat_stop` (cli/wuwei/hook.py)
- [x] T009 Copy to .claude/wuwei/cli/wuwei/hook.py
- [x] T010 Run the full suite green, runtime at 4,000 or fewer

## Phase 3: Docs and checks

- [x] T011 docs/design.md and docs/site/concepts/hooks.md SubagentStop rows name the masking
- [x] T012 Mutants of each new mask, on both copies one at a time, each fail a test
- [x] T013 Route corpus differential, main against the head, in the PR body

## Phase 4: Fix round on ed7f415

- [x] T014 [US5] A verdicts folder linked outside the workspace is never written through (tests/test_hook.py), run red
- [x] T015 [US3] A hand-back refused for its verdict records no secret or canary (tests/test_hook.py), run red
- [x] T016 [US4] A verdict no stop masked is pushed masked and pulls back clean (tests/test_sync.py), run red
- [x] T017 `guards.mask` takes bytes; hook.py and sync.py use it; rewrite rooted at the workspace; refused row masked
- [x] T018 Copy guards.py, hook.py and sync.py to the vendored tree; full suite green; runtime 3,973
- [x] T019 docs/design.md PreToolUse row and state paragraph; mutants of each fix on both copies

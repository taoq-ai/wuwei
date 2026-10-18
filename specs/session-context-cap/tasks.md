# Tasks: the SessionStart context fits Claude Code's 10,000-character cap

## Phase 1: Tests first

- [x] T001 [US1] An empty workspace: the context is at most 10,000 characters and holds the CLI path, the planner.md path, the way and the Decisions and Done sections (tests/test_charters.py)
- [x] T002 [US2] A 40-item board with 3,000-character goals and standards: the context is at most 10,000 characters, the shown items plus the left-out count make 40, and at least 10 show (tests/test_charters.py)
- [x] T003 Thirty long andon lines, no item line to drop: the context is cut at exactly 10,000 and still starts with the CLI line (tests/test_charters.py)
- [x] T004 Run the new tests red on main's code: 3 failed (16,092, 28,638 and 29,162 characters)

## Phase 2: Implementation

- [x] T005 `session_start` inlines the CLI path, `_way.md` and the Decisions and Done sections, and names planner.md, _common.md and the goals and standards folder (cli/wuwei/hook.py)
- [x] T006 The board drops its last item lines until the whole fits, and counts them (cli/wuwei/hook.py)
- [x] T007 The final cut at 10,000 (cli/wuwei/hook.py)
- [x] T008 Docs: the SessionStart rows in docs/design.md and docs/site/concepts/hooks.md, the first-day line in docs/site/getting-started.md
- [x] T009 Run the full suite green, runtime at 2,995

## Phase 3: Checks

- [x] T010 Measure the context at main and at the head for 0, 40 and 200 items
- [x] T011 Route corpus differential through guards.bash, the PreToolUse hook, the fixture payloads and SessionStart at main and at the head, with its sha256
- [x] T012 Eight mutants of `session_start` in fresh copies, each fails a test
- [x] T013 Re-vendor .claude/ with setup.vendor('.')

## Phase 4: Fix round 1 (gate verdicts at 3fab3cb)

- [x] T014 The 40-item test asserts under 10,000 and that the text ends with the whole left-out line (quality, mutants X1 and X2)
- [x] T015 The andon test asserts the way and the Decisions and Done sections come whole before the board (security note 1, mutant S3)
- [x] T016 One left-out item reads "1 more item left out" (tests/test_charters.py, cli/wuwei/hook.py)
- [x] T017 A title that holds a newline no longer stops the trim; only item lines count (security note 2)
- [x] T018 Run the new tests red on 3fab3cb's hook.py: 2 failed (singular, newline), 6 passed; green at the fix: 8 passed
- [x] T019 /wuwei-run step 2 reads planner.md; the counting unit and the newline limits go under Assumptions
- [x] T020 Thirteen mutants in fresh copies, applied to cli/ and .claude/: 13 killed, 0 holes

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

## Phase 5: Fix round 2 (quality verdict at d9d48c1)

- [x] T021 Merge origin/main at 6682925 with a merge commit; the wuwei-run step 1 and 2 conflict with #1145 keeps both changes
- [x] T022 The sweep: 40 items over title paddings 0 to 190 in steps of 10, two root lengths (the tmp path and one 120 characters deeper), with and without a newline in the titles; at each of the 80 points the board is also pushed to exactly 9,999 and 10,000 characters (tests/test_charters.py)
- [x] T023 An andon reason holding `- item-00, ...` keeps the board header and is not counted, with and without the final cut (tests/test_charters.py)
- [x] T024 One and two left-out items read "1 more item" and "2 more items"; a board at 9,999 characters keeps every item (tests/test_charters.py)
- [x] T025 Run the new tests red on 9422fdf's hook.py: 81 failed (80 sweep points, the andon test), 5 passed
- [x] T026 Remove the 9,900 room: the trim measures the final string against SESSION_CAP and drops whole items in the board.text item shape (cli/wuwei/hook.py)
- [x] T027 Mutants in fresh copies, both hook.py copies: specs/session-context-cap/mutants.py at 9eba49f
- [x] T028 Route differential at main 6682925 and the head, and the measurements, at 9eba49f

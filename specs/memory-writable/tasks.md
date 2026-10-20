# Tasks: the transcript guard leaves Claude Code's memory folder writable

## Phase 1: Tests first

- [x] T001 [US1] Write, Edit and MultiEdit on `memory/note.md` and `MEMORY.md` pass (tests/test_guards.py)
- [x] T002 [US2] Bash writes to a memory file pass in 8 spellings x 10 writer shapes (tests/test_guards.py)
- [x] T003 [US3] [US4] Transcripts, tool-results, subagent transcripts and look-alikes are refused (tests/test_guards.py)
- [x] T004 [US4] A `memory` link, a link maker (ln, mv, cp -P, python, find) and a working directory in or below memory are refused (tests/test_guards.py)
- [x] T005 Run the new tests red: 86 failed, 66 passed on main's code (the refusals already hold on main)

## Phase 2: Implementation

- [x] T006 `harness` takes `keep`: a literal path that resolves to a file directly in a memory folder under `ws.PROJECTS` (cli/wuwei/guards.py)
- [x] T007 The Edit door and Bash redirect targets use `keep`; writer words only for tee, sed, truncate, rm (cli/wuwei/guards.py)
- [x] T008 The refusal names the memory routes that pass (cli/wuwei/guards.py)
- [x] T009 Copy guards.py into .claude/wuwei/cli/wuwei/
- [x] T010 Run the suite green, runtime at 3,351

## Phase 3: Checks

- [x] T011 Eight route corpus rows; the corpus through the guards at main and at the head, with its sha256
- [x] T012 The combinatorial probe under real bash at main, at the head and at two mutants
- [x] T013 Mutants of each new condition, in fresh copies, each fail a behavioural test
- [x] T014 SECURITY.md and docs/site/concepts/doors.md name the memory pass and what stays open

# Tasks: the board shows a registered Codex job's state

## Phase 1: Tests first

- [x] T001 [US1] [US2] [US3] Each job status, a HANDOFF path in markdown and backtick form, and a question ending show on the board (tests/test_plan.py)
- [x] T002 [US4] A missing, malformed, list, empty, null-status or bad-result file reads `job state unreadable`, never done; a later `--reason` keeps the job (tests/test_plan.py)
- [x] T003 Run the new tests red: 14 failed, 24 passed (`--job` unrecognised)

## Phase 2: Implementation

- [x] T004 `plan run --job` stores the path on the item (cli/wuwei/__main__.py)
- [x] T005 `board.job` reads the registered file and the run row shows its state (cli/wuwei/board.py, cli/wuwei/upgrade.py)
- [x] T006 Copy the three files into .claude/wuwei/cli/wuwei/
- [x] T007 Run the suite green, runtime at 3,357 (+6)

## Phase 3: Docs

- [x] T008 charters/planner.md (and its vendored copy), docs/design.md, docs/site/reference.md; `bin/wuwei agents build`
